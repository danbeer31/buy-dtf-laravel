# Product Cutover Plan and Run Log

## Scope
- Goal: migrate production data and images from old server to the new server running updated code.
- Source DB connection: `REMOTE_FUEL_DB_CONNECTION` (`remotefuel` / `REMOTE_FUEL_DB_*` env).
- Target DB connection: `FUEL_DB_CONNECTION` (`fuelmysql` / `FUEL_DB_*` env).
- Constraint: all `artisan` and MySQL commands must be run in WSL.

## Guardrails
- Never run schema/data write commands against `remotefuel`.
- Always back up source and target before each rehearsal and final cutover.
- Keep an explicit freeze window for final cutover to prevent write drift.
- Log every command run and every result in this document.

## Phases
1. Preflight
2. Schema readiness on target
3. Data copy
4. Data compatibility transforms
5. Image migration
6. Validation and smoke tests
7. Final cutover switch
8. Post-cutover monitoring
9. Rollback (if needed)

## Preflight Checklist
- [ ] Confirm environment variables for both DB connections are correct.
- [ ] Confirm target app code revision/tag is deployed.
- [ ] Confirm queue worker and scheduler strategy for rehearsal vs cutover.
- [ ] Confirm external integration credentials (Stripe, QBO, Shippo, Dropbox) in new env.
- [ ] Confirm maintenance/freeze communications prepared.

## Data Migration Strategy
- Rehearsal runs:
  - Prefer repeatable full refresh into target (`fuelmysql`) using truncate + reload.
  - Execute all new schema migrations on target before data load or as required by load tooling.
- Final cutover:
  - Enforce write freeze on old production app.
  - Run final source backup.
  - Perform final DB copy from `remotefuel` to `fuelmysql`.
  - Run compatibility transforms and integrity checks.
  - Run smoke tests before opening traffic.

## Image Migration Strategy
- Copy all required image assets from old server to new server, preserving relative paths used by DB records (for example `/uploads/images/...`).
- Include generated thumbnails and derivative files where present.
- Validate file counts and spot-check rendering in:
  - customer cart/image views
  - admin order image edit/download flows

### Current Tested Image Sync Command (Rehearsal)
```bash
sudo rsync -avz --progress --partial --inplace \
  -e "ssh -p 65002" \
  u115974381@82.197.89.138:/home/u115974381/domains/buy-dtf.com/public_html/uploads/images/ \
  /var/www/buy-dtf/public/uploads/images/
```

Notes:
- Keep this command as the baseline for test cutovers.
- For final freeze-window delta sync, add `--delete` only after confirming target path is correct.
- Run post-sync file-count and missing-file checks before opening traffic.

## Validation Checklist
- Data shape and counts:
  - [ ] Table row counts match expected thresholds (source vs target).
  - [ ] Key relations valid (`businesses`, `dtforders`, `dtfimages`, `paymentinfos`).
  - [ ] New columns required by current code exist and are populated safely.
- Functional smoke tests:
  - [ ] Login and account pages
  - [ ] Cart load and image cards
  - [ ] Checkout flow (invoice path)
  - [ ] Checkout flow (Stripe test path)
  - [ ] Admin orders list/show/production actions
  - [ ] Shipping label/rate behavior
  - [ ] Stripe webhook ingestion and payout sync sanity
- Operational:
  - [ ] Queue worker health
  - [ ] Scheduler health
  - [ ] Application logs free of critical exceptions

## Rollback Plan
- Trigger rollback if critical failures occur in payment, order placement, order processing, or data correctness.
- Rollback steps:
  1. Route traffic back to old production server.
  2. Disable writes on new server if needed.
  3. Restore target from pre-cutover backup before next attempt.
  4. Document root cause and remediation tasks before rerun.

## Run Log Template
Copy this section for each rehearsal and final run.

### Run X - <name>
- Date:
- Operator:
- Type: `rehearsal` | `final`
- Source snapshot/backup ID:
- Target snapshot/backup ID:
- Freeze window:
- Result: `pass` | `partial` | `fail`

#### Commands Executed (WSL)
```bash
# paste exact commands here
```

#### DB Validation
- Source connection checked:
- Target connection checked:
- Row count comparisons:
  - businesses:
  - dtforders:
  - dtfimages:
  - paymentinfos:
  - other critical tables:
- Integrity findings:

#### Image Validation
- Source image count:
- Target image count:
- Missing files check:
- Spot checks performed:

#### Smoke Tests
- Login/account:
- Cart/images:
- Checkout invoice:
- Checkout stripe:
- Admin orders/production:
- Shipping:
- Webhooks/payout sync:

#### Issues and Fixes
- Issue:
- Impact:
- Fix:
- Retest result:

#### Decision
- Go/No-Go:
- Notes:

## Run 0 - Planning Baseline
- Date: 2026-03-08 (America/Chicago)
- Operator: Codex + project owner
- Type: rehearsal planning
- Result: pass (planning complete)

### Outcomes
- Confirmed migration direction: `remotefuel` -> `fuelmysql`.
- Confirmed requirement: all `artisan` and MySQL commands run in WSL.
- Established phased plan, validation checklist, and rollback criteria.

### Open Items Before Run 1
- [ ] Finalize exact DB copy command set for rehearsal.
- [x] Define baseline image transfer command set.
- [ ] Add checksum or hash-sample validation method for image transfer.
- [ ] Define table-by-table acceptance thresholds.
- [ ] Define freeze communication template and approval path.

## Run 1 - Rehearsal (Images Command Baseline)
- Date: 2026-03-08 (America/Chicago)
- Operator: project owner
- Type: rehearsal
- Result: in progress

### Commands Executed (WSL)
```bash
sudo rsync -avzn --progress --partial --inplace \
  -e "ssh -p 65002" \
  u115974381@82.197.89.138:/home/u115974381/domains/buy-dtf.com/public_html/uploads/images/ \
  /var/www/buy-dtf/public/uploads/images/

sudo rsync -avz --progress --partial --inplace \
  -e "ssh -p 65002" \
  u115974381@82.197.89.138:/home/u115974381/domains/buy-dtf.com/public_html/uploads/images/ \
  /var/www/buy-dtf/public/uploads/images/
```

### Follow-up Required
- [ ] Record start/end times and total bytes transferred (real run).
- [ ] Record source/target file counts.
- [ ] Record any missing files from DB-backed manifest check.

### Rehearsal Notes Captured
- Dry-run summary:
  - `sent 2,253 bytes`
  - `received 263,587 bytes`
  - `31,275.29 bytes/sec`
  - `total size is 12,009,847,803`
  - `speedup is 45,176.98 (DRY RUN)`
- Real sync summary:
  - `sent 14,479 bytes`
  - `received 1,383,688,182 bytes`
  - `22,871,118.36 bytes/sec`
  - `total size is 12,033,223,987`
  - `speedup is 8.70`

## Run 2 - Rehearsal (DB Copy + Compatibility Migrations)
- Date: 2026-03-08 (America/Chicago)
- Operator: project owner
- Type: rehearsal
- Result: pass (after migration script adjustments)

### Objective
- Copy production-like DB from `REMOTE_FUEL_DB_*` into `FUEL_DB_*`.
- Apply only fuel-targeted compatibility migrations required by new code.

### Commands Executed (WSL)
```bash
# 0) Move to app root
cd /var/www/buy-dtf

# 1) Load env vars for this shell session
set -a
source .env
set +a

# 2) Safety check: print non-secret endpoints only
echo "REMOTE: ${REMOTE_FUEL_DB_HOST}:${REMOTE_FUEL_DB_PORT}/${REMOTE_FUEL_DB_DATABASE}"
echo "TARGET: ${FUEL_DB_HOST}:${FUEL_DB_PORT}/${FUEL_DB_DATABASE}"

# 3) Backup target before overwrite
mkdir -p storage/cutover
mysqldump \
  -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" \
  -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" \
  --single-transaction --quick --routines --triggers \
  "${FUEL_DB_DATABASE}" \
  > "storage/cutover/fuelmysql_pre_run2_$(date +%F_%H%M%S).sql"

# 4) Recreate target DB (clean slate)
mysql \
  -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" \
  -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" \
  -e "DROP DATABASE IF EXISTS \`${FUEL_DB_DATABASE}\`; CREATE DATABASE \`${FUEL_DB_DATABASE}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 5) Copy source -> target via stream
mysqldump \
  -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" \
  -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" \
  --single-transaction --quick --routines --triggers --set-gtid-purged=OFF \
  "${REMOTE_FUEL_DB_DATABASE}" \
  | mysql \
      -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" \
      -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" \
      "${FUEL_DB_DATABASE}"

# 6) Run fuel compatibility migrations only (do not run full migrate on fuel)
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_16_023755_increase_dropbox_token_length.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_16_225545_add_shippo_fields_to_dtforders.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_16_231824_add_shipping_method_to_dtforders.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_17_005600_sync_remote_db_shipping_changes.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_17_020821_add_stripe_fee_to_paymentinfos.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_17_025529_create_stripe_payouts_tables.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_22_232856_add_qbo_and_stripe_ids_to_paymentinfos.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_29_012144_add_qbo_ids_to_stripe_payout_tables.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_29_021640_add_qbo_fee_expense_id_to_paymentinfos_table.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_31_013614_create_stripe_webhook_events_table.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_31_045531_add_thumbnail_to_dtfimages_table.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_31_155550_add_business_id_to_paymentinfos.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_31_181635_add_qbo_invoice_number_to_dtforders_table.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_31_181731_create_stripe_sync_logs_table.php --force
php artisan migrate --database=fuelmysql --path=database/migrations/2026_01_31_181807_add_qbo_invoice_numbers_to_paymentinfos_table.php --force

# 7) Quick validation counts
mysql -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" -N -e "SELECT COUNT(*) FROM dtforders;" "${REMOTE_FUEL_DB_DATABASE}"
mysql -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" -N -e "SELECT COUNT(*) FROM dtforders;" "${FUEL_DB_DATABASE}"
mysql -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" -N -e "SELECT COUNT(*) FROM dtfimages;" "${REMOTE_FUEL_DB_DATABASE}"
mysql -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" -N -e "SELECT COUNT(*) FROM dtfimages;" "${FUEL_DB_DATABASE}"
mysql -h "${REMOTE_FUEL_DB_HOST}" -P "${REMOTE_FUEL_DB_PORT}" -u "${REMOTE_FUEL_DB_USERNAME}" -p"${REMOTE_FUEL_DB_PASSWORD}" -N -e "SELECT COUNT(*) FROM paymentinfos;" "${REMOTE_FUEL_DB_DATABASE}"
mysql -h "${FUEL_DB_HOST}" -P "${FUEL_DB_PORT}" -u "${FUEL_DB_USERNAME}" -p"${FUEL_DB_PASSWORD}" -N -e "SELECT COUNT(*) FROM paymentinfos;" "${FUEL_DB_DATABASE}"
```

### Notes
- This runbook intentionally avoids `php artisan migrate --database=fuelmysql` (full migration set) to prevent creating Laravel app tables in the fuel schema.
- All commands above must be executed in WSL.

### Actual Execution (WSL)
```bash
cd /mnt/c/Users/danie/projects/buy-dtf-laravel
bash scripts/run_cutover_test.sh
```

### Run 2 Results
- Import and migration sequence completed successfully.
- Migration table was created in `fuelmysql`, then all targeted 2026 fuel compatibility migrations ran successfully.
- Row count validation:
  - `dtforders`: remote `932`, target `932`
  - `dtfimages`: remote `9107`, target `9107`
  - `paymentinfos`: remote `974`, target `974`

### Issues Encountered and Fixes
- Issue: source dump failed on `COLUMN_STATISTICS` with client/server version mismatch.
- Fix: added `--column-statistics=0` to source `mysqldump`.
- Issue: import failed on unsupported source collations (`utf8mb3_uca1400_ai_ci`) and charset/collation incompatibility.
- Fix: remapped unsupported collations and charset in stream during import:
  - `utf8mb3_uca1400_ai_ci` -> `utf8mb4_unicode_ci`
  - `utf8mb4_uca1400_ai_ci` -> `utf8mb4_unicode_ci`
  - `utf8mb3_general_ci` -> `utf8mb4_unicode_ci`
  - `CHARSET=utf8mb3` -> `CHARSET=utf8mb4`
  - `CHARACTER SET utf8mb3` -> `CHARACTER SET utf8mb4`

### Artifact Added
- Rehearsal script: `scripts/run_cutover_test.sh`

## Post-Cutover Improvements
### Multi-User Per Business (Pivot Model) - Phased Plan

### Goal
- Replace brittle email-based `User -> Business` linkage with explicit membership mapping.
- Support multiple users per business with per-user role controls.
- Preserve current production behavior during migration window.

### Current State Constraints
- Current linkage is effectively by email match (`users.email` <-> `businesses.email`).
- Business context is assumed in checkout, account, cart, and admin flows.
- Immediate pre-cutover rewrite is high risk; execute only after production stabilizes.

### Phase 0 - Stabilization Window (No Behavior Changes)
- Duration target: 1-2 weeks after hard cutover.
- Activities:
  - Keep existing email-link logic unchanged.
  - Gather production telemetry on auth/account/order flows.
  - Freeze non-critical schema refactors.
- Exit criteria:
  - No critical incidents in checkout/order/payment flows for 7 consecutive days.

### Phase 1 - Schema Foundation
- Deliverables:
  - New pivot table: `business_user` on `fuelmysql`.
  - Columns: `business_id`, `user_id`, `role`, `is_active`, `invited_by`, `created_at`, `updated_at`.
  - Unique index on (`business_id`, `user_id`).
  - Optional helper index on (`user_id`, `is_active`).
- Role baseline:
  - `owner`, `admin`, `member` (simple initial set).
- Exit criteria:
  - Migration applied in staging and production with no runtime regressions.

### Phase 2 - Backfill and Dual-Read Compatibility
- Deliverables:
  - Backfill script/command:
    - Create `business_user` rows from current email-based mapping.
    - Set first mapped user as `owner`; others default to `member`.
  - Add model relationships:
    - `User::businesses()` belongsToMany
    - `Business::users()` belongsToMany
  - Keep temporary fallback:
    - If no pivot rows, continue current email-link read path.
- Validation:
  - Count checks:
    - users with old mapping vs users with pivot mapping.
    - businesses with at least one active member.
- Exit criteria:
  - 100% of active users/businesses have pivot memberships.

### Phase 3 - Context Selection and Authorization
- Deliverables:
  - Introduce `current_business_id` context in session (or persistent user preference).
  - Middleware to enforce:
    - authenticated user has active membership in selected business.
  - Role gates/policies for business-scoped actions.
- UI updates:
  - Business switcher (for users with >1 business membership).
  - Membership/role management in admin or account settings.
- Exit criteria:
  - Cart/checkout/account/admin flows operate from selected business context, not email.

### Phase 4 - Write Path Migration
- Deliverables:
  - Update write flows to use membership context:
    - Cart creation/retrieval
    - Checkout and order placement
    - Invoice/payment views
  - Update background jobs/webhooks that infer business by email.
- Regression test scope:
  - Login + business selection
  - Cart and checkout (invoice + Stripe)
  - Order history visibility scoped to selected business
  - Admin impersonation and business management
- Exit criteria:
  - No critical authorization/data-leak regressions in staging and production canary.

### Phase 5 - Deprecate Email Linkage
- Deliverables:
  - Remove fallback email-match relationship in code.
  - Add data integrity guardrails:
    - enforce at least one active owner per business.
  - Cleanup migrations for deprecated assumptions if needed.
- Exit criteria:
  - All business association logic uses `business_user` only.

### Operational Rollout Controls
- Use feature flags:
  - `FEATURE_BUSINESS_MEMBERSHIPS_READ`
  - `FEATURE_BUSINESS_MEMBERSHIPS_WRITE`
  - `FEATURE_BUSINESS_SWITCHER_UI`
- Rollout pattern:
  1. Enable read flag in staging.
  2. Enable write flag in staging.
  3. Canary in production for admins/internal accounts.
  4. Gradual rollout to all users.
- Rollback plan:
  - Disable write flag first.
  - Re-enable email-link fallback read path.
  - Revert only affected release if needed.

### Estimated Effort (Post-Cutover)
- Phase 1-2: 2-4 days
- Phase 3-4: 4-8 days
- Phase 5 + cleanup: 1-2 days
- Total: 1.5-3 weeks including testing and safe rollout.
