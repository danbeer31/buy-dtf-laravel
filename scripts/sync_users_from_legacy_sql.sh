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

LEGACY_SQL="${1:-/mnt/c/Users/danie/Downloads/users (1).sql}"
if [[ ! -f "$LEGACY_SQL" ]]; then
  echo "legacy_sql_missing:$LEGACY_SQL" >&2
  exit 1
fi

DB_HOST="$(read_env "DB_HOST")"
DB_PORT="$(read_env "DB_PORT")"
DB_NAME="$(read_env "DB_DATABASE")"
DB_USER="$(read_env "DB_USERNAME")"
DB_PASS="$(read_env "DB_PASSWORD")"

DB_PORT="${DB_PORT:-3306}"

if [[ -z "$DB_HOST" || -z "$DB_NAME" || -z "$DB_USER" ]]; then
  echo "missing_db_env:DB_HOST/DB_DATABASE/DB_USERNAME" >&2
  exit 1
fi

echo "Target DB: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
mkdir -p storage/cutover

stamp="$(date +%F_%H%M%S)"
backup_file="storage/cutover/mysql_users_pre_legacy_sync_${stamp}.sql"
transformed_file="storage/cutover/legacy_users_import_transformed_${stamp}.sql"

echo "[1/6] Backup current users table"
mysqldump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" --no-tablespaces "$DB_NAME" users > "$backup_file"
ls -lh "$backup_file"

echo "[2/6] Transform source SQL into staging table SQL"
sed \
  -e 's/CREATE TABLE `users`/CREATE TABLE `legacy_users_import`/g' \
  -e 's/INSERT INTO `users`/INSERT INTO `legacy_users_import`/g' \
  -e 's/ALTER TABLE `users`/ALTER TABLE `legacy_users_import`/g' \
  -e 's/AUTO_INCREMENT for table `users`/AUTO_INCREMENT for table `legacy_users_import`/g' \
  "$LEGACY_SQL" > "$transformed_file"

echo "[3/6] Load legacy data into staging table"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" <<'SQL'
DROP TABLE IF EXISTS legacy_users_import;
SQL
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$transformed_file"

echo "[4/6] Upsert into Laravel users table"
before_count="$(mysql -N -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) FROM users;")"

mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" <<'SQL'
INSERT INTO users (
  name,
  email,
  password,
  role,
  password_reset_required,
  email_verified_at,
  remember_token,
  created_at,
  updated_at
)
SELECT
  CASE
    WHEN TRIM(COALESCE(username, '')) = '' THEN email
    ELSE username
  END AS name,
  LOWER(email) AS email,
  password,
  'customer' AS role,
  0 AS password_reset_required,
  NULL AS email_verified_at,
  NULL AS remember_token,
  FROM_UNIXTIME(NULLIF(created_at, 0)) AS created_at,
  FROM_UNIXTIME(NULLIF(updated_at, 0)) AS updated_at
FROM legacy_users_import
WHERE TRIM(COALESCE(email, '')) <> ''
  AND LOWER(TRIM(username)) <> 'guest'
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  password = VALUES(password),
  password_reset_required = 0,
  updated_at = VALUES(updated_at);
SQL

after_count="$(mysql -N -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT COUNT(*) FROM users;")"

echo "[5/6] Verify john hammons record"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" -N "$DB_NAME" -e \
  "SELECT id, name, email, role FROM users WHERE LOWER(name) LIKE '%john%' OR LOWER(email) LIKE '%jhammons%';"

echo "[6/6] Cleanup staging table"
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" <<'SQL'
DROP TABLE IF EXISTS legacy_users_import;
SQL

echo "users_before=${before_count}"
echo "users_after=${after_count}"
echo "run_complete"
