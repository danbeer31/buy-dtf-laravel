#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

trim_cr() {
  printf "%s" "${1//$'\r'/}"
}

read_env() {
  local key="$1"
  local line
  line="$(grep -m1 -E "^${key}=" .env || true)"
  if [[ -z "$line" ]]; then
    printf ""
    return 0
  fi
  line="${line#*=}"
  line="$(trim_cr "$line")"
  if [[ "$line" == \"*\" && "$line" == *\" ]]; then
    line="${line:1:${#line}-2}"
  elif [[ "$line" == \'*\' && "$line" == *\' ]]; then
    line="${line:1:${#line}-2}"
  fi
  printf "%s" "$line"
}

REMOTE_FUEL_DB_HOST="$(read_env "REMOTE_FUEL_DB_HOST")"
REMOTE_FUEL_DB_PORT="$(read_env "REMOTE_FUEL_DB_PORT")"
REMOTE_FUEL_DB_DATABASE="$(read_env "REMOTE_FUEL_DB_DATABASE")"
REMOTE_FUEL_DB_USERNAME="$(read_env "REMOTE_FUEL_DB_USERNAME")"
REMOTE_FUEL_DB_PASSWORD="$(read_env "REMOTE_FUEL_DB_PASSWORD")"

FUEL_DB_HOST="$(read_env "FUEL_DB_HOST")"
FUEL_DB_PORT="$(read_env "FUEL_DB_PORT")"
FUEL_DB_DATABASE="$(read_env "FUEL_DB_DATABASE")"
FUEL_DB_USERNAME="$(read_env "FUEL_DB_USERNAME")"
FUEL_DB_PASSWORD="$(read_env "FUEL_DB_PASSWORD")"

REMOTE_FUEL_DB_PORT="${REMOTE_FUEL_DB_PORT:-3306}"
FUEL_DB_PORT="${FUEL_DB_PORT:-3306}"

echo "REMOTE:${REMOTE_FUEL_DB_HOST}:${REMOTE_FUEL_DB_PORT}/${REMOTE_FUEL_DB_DATABASE}"
echo "TARGET:${FUEL_DB_HOST}:${FUEL_DB_PORT}/${FUEL_DB_DATABASE}"

mkdir -p storage/cutover
backup_file="storage/cutover/fuelmysql_pre_run2.sql"

echo "[1/5] Backup target DB"
mysqldump \
  -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" \
  -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" \
  --single-transaction --quick --routines --triggers --no-tablespaces \
  "${FUEL_DB_DATABASE}" > "${backup_file}"
ls -lh "${backup_file}"

echo "[2/5] Recreate target DB"
cat <<SQL | mysql -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}"
DROP DATABASE IF EXISTS \`${FUEL_DB_DATABASE}\`;
CREATE DATABASE \`${FUEL_DB_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SQL

echo "[3/5] Copy source -> target"
mysqldump \
  -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" \
  -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" \
  --single-transaction --quick --routines --triggers --no-tablespaces --column-statistics=0 --set-gtid-purged=OFF \
  "${REMOTE_FUEL_DB_DATABASE}" \
  | sed \
      -e 's/utf8mb3_uca1400_ai_ci/utf8mb4_unicode_ci/g' \
      -e 's/utf8mb4_uca1400_ai_ci/utf8mb4_unicode_ci/g' \
      -e 's/utf8mb3_general_ci/utf8mb4_unicode_ci/g' \
      -e 's/CHARSET=utf8mb3/CHARSET=utf8mb4/g' \
      -e 's/CHARACTER SET utf8mb3/CHARACTER SET utf8mb4/g' \
  | mysql \
      -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" \
      -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" \
      "${FUEL_DB_DATABASE}"

echo "[4/5] Run fuel compatibility migrations"
migrations=(
  "2026_01_16_023755_increase_dropbox_token_length.php"
  "2026_01_16_225545_add_shippo_fields_to_dtforders.php"
  "2026_01_16_231824_add_shipping_method_to_dtforders.php"
  "2026_01_17_005600_sync_remote_db_shipping_changes.php"
  "2026_01_17_020821_add_stripe_fee_to_paymentinfos.php"
  "2026_01_17_025529_create_stripe_payouts_tables.php"
  "2026_01_22_232856_add_qbo_and_stripe_ids_to_paymentinfos.php"
  "2026_01_29_012144_add_qbo_ids_to_stripe_payout_tables.php"
  "2026_01_29_021640_add_qbo_fee_expense_id_to_paymentinfos_table.php"
  "2026_01_31_013614_create_stripe_webhook_events_table.php"
  "2026_01_31_045531_add_thumbnail_to_dtfimages_table.php"
  "2026_01_31_155550_add_business_id_to_paymentinfos.php"
  "2026_01_31_181635_add_qbo_invoice_number_to_dtforders_table.php"
  "2026_01_31_181731_create_stripe_sync_logs_table.php"
  "2026_01_31_181807_add_qbo_invoice_numbers_to_paymentinfos_table.php"
  "2026_03_10_120000_create_accounting_reconciliation_checks_table.php"
)

for m in "${migrations[@]}"; do
  php artisan migrate --database=fuelmysql --path="database/migrations/${m}" --force
done

echo "[5/5] Validate key table counts"
count_remote_dtforders=$(printf "SELECT COUNT(*) FROM dtforders;" | mysql -N -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" "${REMOTE_FUEL_DB_DATABASE}")
count_target_dtforders=$(printf "SELECT COUNT(*) FROM dtforders;" | mysql -N -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" "${FUEL_DB_DATABASE}")
count_remote_dtfimages=$(printf "SELECT COUNT(*) FROM dtfimages;" | mysql -N -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" "${REMOTE_FUEL_DB_DATABASE}")
count_target_dtfimages=$(printf "SELECT COUNT(*) FROM dtfimages;" | mysql -N -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" "${FUEL_DB_DATABASE}")
count_remote_paymentinfos=$(printf "SELECT COUNT(*) FROM paymentinfos;" | mysql -N -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" "${REMOTE_FUEL_DB_DATABASE}")
count_target_paymentinfos=$(printf "SELECT COUNT(*) FROM paymentinfos;" | mysql -N -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" "${FUEL_DB_DATABASE}")

echo "dtforders remote=${count_remote_dtforders} target=${count_target_dtforders}"
echo "dtfimages remote=${count_remote_dtfimages} target=${count_target_dtfimages}"
echo "paymentinfos remote=${count_remote_paymentinfos} target=${count_target_paymentinfos}"
echo "run_complete"
