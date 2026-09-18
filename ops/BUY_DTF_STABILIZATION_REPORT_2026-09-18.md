# BuyDTF Stabilization and Production Drift Report

Date: 2026-09-18 (America/Chicago)

Status: **local preparation complete; no production write or deployment performed**

## Decision

The production working files are the source of truth. The detached production Git commit is not a safe deployment baseline.

The stabilization candidate preserves the live runtime source. A normalized comparison of 270 production-relevant files found 266 exact matches and four explained differences: `composer.json`, `composer.lock`, `config/database.php`, and `phpunit.xml`. The dependency deployment must therefore be a narrowly scoped `composer.lock` plus staged `vendor/` replacement. It must not use Git, replace production `composer.json`, replace production configuration, run migrations, or restart shared services.

The dependency candidate is ready for review and staging. A live cutover should occur only in a low-traffic maintenance window after the pre-cutover stop checks in this document pass.

The Stripe payout schema correction is prepared and tested locally, but is a separate change from the dependency deployment. It must not be applied through a bulk migration.

## Scope and Guardrails

Completed:

- Created a clean worktree from current `origin/main`.
- Reconciled the Step 1 test/CI safety work and Step 2 Composer security work with current main.
- Updated the newly vulnerable CommonMark package within the existing major constraint.
- Ran the complete isolated test suite, frontend build, Composer audits, and static checks.
- Compared the live working files with the stabilization candidate.
- Audited both production migration ledgers and the corresponding live schemas read-only.
- Prepared and tested a guarded migration for the missing payout-entry `notes` column locally.
- Finalized the incoming-order v1 proposal in a separate contract document.

Not performed:

- No production file, configuration, dependency, cache, data, schema, or service change.
- No production migration, dependency install, deploy, restart, or queue action.
- No `git pull`, reset, checkout, merge, or cleanup on production.
- No job-label implementation.
- No ShopNLTees change.

## Candidate Branch and Commits

Worktree: `C:\Users\danie\projects\buy-dtf-stabilization-20260918`

Branch: `security/stabilize-step1-step2-20260918`

Base:

- `fe9e97e39e36392c97106c589c071f2a17f36915` - current `origin/main` at preparation time

Candidate commits before this report:

- `e7882cb` - Merge Step 1 and Step 2 security baseline
- `7c344ea` - security: update CommonMark for September advisories
- `c0ae1c5` - fix: add guarded Stripe payout entry notes migration

The final documentation commit and remote branch status are reported in the final handoff after this document is committed.

## Production Drift Report

### Runtime and repository state

Read-only observation on 2026-09-18:

| Item | Live production state | Assessment |
|---|---|---|
| Application path | `/var/www/buy-dtf` | Real directory, not a symlink |
| Owner/mode | `dan:dan`, `0755` | Application owner can stage inside this directory |
| Git HEAD | `939e8dc90c2871eb909969c7555f9ac246bb92dc` | Detached and obsolete as a source baseline |
| Tracked status entries | 80 | Live working files have diverged from detached HEAD |
| Unmerged index entries | 33 | Do not use Git for deployment; working files themselves have no conflict markers in audited runtime source |
| Individually counted untracked files | 277 | Includes current source/migrations/views plus runtime artifacts |
| PHP lint | No failures in audited `app/`, `bootstrap/`, `config/`, `routes/`, and migration PHP | Working runtime source is syntactically valid |
| PHP | 8.2.30 | Compatible with candidate lock |
| Laravel | 12.46.0 before dependency update | Candidate moves to 12.61.1 |
| Composer | 2.9.3 | Use this pinned production executable; do not self-update |
| Vendor size | 65,353,344 bytes apparent | Retaining old vendor for rollback is practical |
| Free filesystem space | 52,781,891,584 bytes | Sufficient for staged and rollback vendor trees, subject to a fresh cutover check |
| OPcache | enabled; timestamps enabled; revalidate 2 seconds; file protection 2 seconds | No PHP-FPM restart should be necessary |

### Live-source comparison

The audit compared 270 normalized files covering all PHP under `app/`, `bootstrap/`, `config/`, `routes/`, and `database/migrations/`; Blade templates; `artisan`; Composer/npm manifests and locks; PHPUnit; Vite; and Tailwind configuration.

- 266 files match the stabilization candidate after line-ending normalization.
- No audited runtime file exists on only one side.
- Exactly four files differ:

| File | Difference | Required treatment |
|---|---|---|
| `composer.json` | Dependency constraints/autoload/config match; only the candidate's safer test script differs | Preserve live file byte-for-byte during dependency deployment |
| `composer.lock` | Candidate contains the reviewed 18-package security update | This is the only application file to replace in the dependency cutover |
| `config/database.php` | Four literal fallback values differ under the obsolete `remotefuel` connection | Preserve live file during this cutover; remove and rotate the obsolete credentials in a separately approved security change |
| `phpunit.xml` | Candidate contains the isolated test configuration | Test-only; do not deploy as part of dependency cutover |

The live and candidate Composer dependency constraints are identical, and both locks use the same Composer content hash. The candidate lock is therefore valid with the exact live `composer.json`; replacing the live JSON is unnecessary and prohibited by this plan.

Reviewed artifact hashes (SHA-256 over exact file bytes):

| Artifact | SHA-256 |
|---|---|
| Live `composer.json` to retain | `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872` |
| Live pre-cutover `composer.lock` for rollback | `16eef909889a727717fccf52e9c7c23e8a0d2cc661777f6044abde97713d2579` |
| Candidate `composer.lock` to deploy | `eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831` |
| Live `config/database.php` to retain | `d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9` |
| Candidate payout `notes` migration (separate change) | `628bdf45fa5d69d5bb25382eff5464b4578c532a898ef83ebe6ebb9ff56614d6` |

These are preparation-time hashes. A mismatch at cutover is a stop condition, not permission to overwrite the changed live file.

### Configuration observations

Only non-secret classifications were recorded:

- Effective `APP_ENV` is `local` while `APP_DEBUG` is false. This should be corrected separately after impact review; it is not part of the dependency cutover.
- Default and Fuel data use distinct MySQL connections.
- Queue connection is `sync`; no queue worker is required for the current behavior.
- Cache and session drivers are file-backed; mail uses Resend.
- Live Stripe mode and QBO production mode are configured; Shippo, Dropbox, Resend, Name/Number, and incoming HMAC credentials are present.
- Configuration is not cached.
- The live `remotefuel` block still contains obsolete import-era literal credential fallbacks. Values were not retained in this report. The manual legacy import command is not scheduled, and normal Fuel models route to the current Fuel connection. Preserve this file for the dependency-only change, then remove the block and rotate any credential that was ever valid in a separate security task.

### Dependency-lock drift

The live lock currently reports 42 advisory records across 14 packages (13 high, 24 medium, 4 low, and 1 unscored). Excluding dev packages, it reports 38 records across 12 packages.

The candidate lock has zero Composer advisories in both the full and `--no-dev` audits. It changes exactly 18 packages, adds none, removes none, retains PHP `^8.2`, and makes no major-version jump:

| Package | Live | Candidate |
|---|---:|---:|
| `guzzlehttp/guzzle` | 7.10.0 | 7.15.2 |
| `guzzlehttp/promises` | 2.3.0 | 2.5.2 |
| `guzzlehttp/psr7` | 2.8.0 | 2.13.0 |
| `laravel/framework` | 12.46.0 | 12.61.1 |
| `league/commonmark` | 2.8.0 | 2.10.0 |
| `phpunit/phpunit` | 11.5.46 | 11.5.50 |
| `psy/psysh` | 0.12.18 | 0.12.19 |
| `sebastian/comparator` | 6.3.2 | 6.3.3 |
| `symfony/http-foundation` | 7.4.3 | 7.4.13 |
| `symfony/http-kernel` | 7.4.3 | 7.4.12 |
| `symfony/mailer` | 7.4.3 | 7.4.12 |
| `symfony/mime` | 7.4.0 | 7.4.12 |
| `symfony/polyfill-intl-idn` | 1.33.0 | 1.38.1 |
| `symfony/polyfill-php84` | 1.33.0 | 1.38.1 |
| `symfony/polyfill-php85` | 1.33.0 | 1.41.0 |
| `symfony/process` | 7.4.3 | 7.4.5 |
| `symfony/routing` | 7.4.3 | 7.4.13 |
| `symfony/yaml` | 7.4.1 | 7.4.12 |

### Public health baseline

At approximately 15:55 CDT on 2026-09-18:

- `https://buy-dtf.com/`, `/up`, and `/login` returned 200.
- `/admin` and `/checkout` returned the expected 302 redirect to login.
- The `www` home and `/up` returned 200.
- The production Vite manifest returned 200.
- Manifest assets `app-B5oFf84X.css` and `app-cwinOvGr.js` returned 200.

This is a baseline, not proof that payment, upload, or integration requests are idle. Cutover still requires a fresh traffic/write check.

## Verification Results

| Check | Result |
|---|---|
| Full isolated PHP suite | 106 tests, 705 assertions, pass (randomized seed `9182026`) |
| Targeted payout migration regression | 1 test, 6 assertions, pass |
| Composer validation | `composer validate --strict`, pass |
| Composer audit | Full and `--no-dev`, zero advisories |
| PHP 8.2 platform check | Pass |
| Clean lock installability | Pass under PHP 8.2 |
| Package discovery / optimized autoload | Pass in isolated local candidate |
| Config and view cache compile/clear | Pass in isolated local candidate |
| Route discovery | 174 routes, pass |
| Frontend clean install | `npm ci`, pass |
| Frontend production build | `npm run build`, pass |
| PHP syntax | 189 baseline PHP files plus the new migration/test, pass |
| Scoped formatter | All Step 1/2 and payout-correction PHP changes pass Pint |
| Whitespace validation | `git diff --check`, pass |

Known non-blocking findings:

- npm audit reports 14 build/development dependency findings: 2 critical, 9 high, 2 moderate, and 1 low. This is a separate frontend dependency phase and is not hidden by the PHP dependency change.
- The frontend build emits existing Sass deprecation warnings and stale Browserslist-data notice but completes successfully.
- Full-repository Pint reports 88 pre-existing style findings across 188 files. The changed PHP files pass; mass-formatting is outside this stabilization scope.
- PHP emits an existing `rtrim(null)` deprecation from `config/filesystems.php`; it is not introduced by the dependency update.

## Migration Ledger and Schema Adjudication

Production has two databases and two independent migration ledgers. A migration shown as pending by one ledger may explicitly operate on the other database. Therefore `php artisan migrate` is unsafe.

### Entries reported pending by the default ledger

| Migration | Live schema evidence | Classification | Action |
|---|---|---|---|
| `2026_01_29_021640_add_qbo_fee_expense_id_to_paymentinfos_table` | `qbo_fee_expense_id` exists on Fuel; `paymentinfos` does not exist on default | Already represented on intended schema; unsafe from default ledger | Do not run; later reconcile ledger deliberately |
| `2026_01_31_013614_create_stripe_webhook_events_table` | Fuel table exists with unique event ID index and 242 rows | Already represented; unguarded create would fail | Do not run |
| `2026_01_31_045531_add_thumbnail_to_dtfimages_table` | `thumbnail` exists on Fuel `dtfimages` and `savedimages` | Already represented; false pending/obsolete on default ledger | Do not run even though guards make schema portion a no-op |
| `2026_03_10_120000_create_accounting_reconciliation_checks_table` | Fuel table and expected indexes exist; 180 rows | Already represented; unguarded create would fail | Do not run |
| `2026_03_23_110000_add_gang_sheet_fields_to_dtfimages_table` | `item_type`, `item_meta`, and `upload_mime` exist on Fuel | Already represented; false pending/obsolete on default ledger | Do not run |
| `2026_03_28_210000_add_admin_price_overrides_to_orders_and_images` | All image/order override fields exist on Fuel | Already represented; false pending/obsolete on default ledger | Do not run |

### Entries reported pending by the Fuel ledger

| Migration | Live schema evidence | Classification | Action |
|---|---|---|---|
| `0001_01_01_000000_create_users_table` | Users and password-reset tables belong to default DB; Fuel already has a populated legacy `sessions` table | Obsolete/wrong connection and unsafe: it can partially create tables before failing on `sessions` | Do not run |
| `0001_01_01_000001_create_cache_table` | Cache tables already exist on default DB | Obsolete/wrong connection; would create unintended Fuel tables | Do not run |
| `0001_01_01_000002_create_jobs_table` | Jobs tables already exist on default DB; queue is currently `sync` | Obsolete/wrong connection; would create unintended Fuel tables | Do not run |
| `2026_01_10_222937_add_role_to_users_table` | Migration body is an empty no-op; default users already have role | Obsolete | Do not run |
| `2026_01_11_013046_add_business_link_and_reset_to_users_table` | Required columns and indexes already exist on default users; Fuel has no users table | Already represented on default; unsafe on Fuel | Do not run |
| `2026_01_12_042344_create_businesses_table` | Fuel already has the populated legacy businesses table (42 rows) | Already represented by an incompatible legacy schema; unguarded create would fail | Do not run |
| `2026_01_12_042628_create_business_settings_table` | Fuel already has the populated business settings table (42 rows) | Already represented; unguarded create would fail | Do not run |
| `2026_03_22_140000_create_business_user_table` | Migration explicitly targets default MySQL; pivot exists there with 47 rows | Already represented; false pending in Fuel ledger and create would fail on default | Do not run |
| `2026_03_22_141000_allow_multiple_users_per_business` | Default users have a non-unique Fuel business index; uniqueness is already removed | Already represented; false pending in Fuel ledger | Do not run |

Adjudication result: **zero ledger-reported migrations are both genuinely pending and safe to run.** Ledger reconciliation must be a separately reviewed metadata operation; it must not be improvised during a deployment.

## Stripe Payout `notes` Correction

### Evidence and cause

The production `stripe_payout_entries` table lacks `notes`, while the deployed model/service writes that field. This caused recurring `SQLSTATE 42S22` payout-processing failures at `StripePayoutService.php` during August. The table is small (approximately 81 rows at audit time).

### Prepared correction

Local commit `c0ae1c5` adds:

- `database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php`
- `tests/Feature/Migrations/StripePayoutEntryNotesMigrationTest.php`

The migration:

- resolves the explicitly configured Fuel connection;
- refuses to continue if the target table is missing;
- adds one nullable `TEXT notes` column only when absent;
- appends the column, keeping the alteration narrow;
- is idempotent;
- intentionally retains the additive column on code rollback.

The regression test first reproduces the exact missing-column write failure, applies the migration, proves the write succeeds, runs `up()` again, and proves `down()` preserves the column and data.

### Separate future execution plan

This must not be combined with the dependency deployment or a bulk migration.

1. Review and approve commit `c0ae1c5` independently.
2. Reconfirm the table exists, `notes` is absent, row count is plausible, MySQL is 8.0.x, and no payout sync is running.
3. Take a timestamped, access-restricted schema/data backup of the payout tables and verify that the dump is nonempty/readable.
4. Deploy only the reviewed migration file, recording its SHA-256.
5. Run `--pretend` against the Fuel connection and confirm the only DDL is an additive nullable `notes` column.
6. Run only the exact migration path with `--database=fuelmysql --path=database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php --force`.
7. Verify the Fuel ledger entry, column type/nullability, unchanged row count, and public health.
8. Do not manually trigger a command capable of Stripe/QBO writes merely as a smoke test. Observe the next natural payout event/scheduled sync and verify that the former missing-column error does not recur.

Rollback is application-safe by retaining the nullable column. If the application must be rolled back, leave the column and ledger entry in place; restoring/dropping it would add risk without restoring useful behavior.

## Exact Dependency-Only Deployment Plan

### Preconditions and stop conditions

Do not begin unless all of the following are true immediately before the window:

- The production working-source manifest still matches the reviewed manifest; only the four explained files differ from candidate.
- The live `composer.json` SHA-256 is unchanged and its require/autoload/config sections still match the candidate assumptions.
- Candidate `composer.lock` SHA-256 matches the reviewed artifact and its content hash matches live `composer.json`.
- Full and `--no-dev` audits are zero, PHP 8.2 platform checks pass, CI is green, and the exact 18-package diff is unchanged.
- `/`, `/up`, `/login`, protected redirects, manifest, CSS, and JS match the baseline.
- No new database, payout, payment, webhook, QBO, Shippo, Dropbox, Resend, Name/Number, Guzzle, or cURL failure is present.
- Queue remains `sync`; no queued/failed job has unexpectedly appeared.
- The hourly accounting schedule is healthy and no payout sync is active.
- No checkout, order, payment, upload, or production handoff is in flight; choose a low-traffic window away from the top of the hour and the 01:30 accounting task.
- Disk, ownership, permissions, and same-filesystem atomic rename capability are rechecked.
- The old vendor rollback tree and exact old lock/cache backup locations are named and verified before maintenance begins.

Any failed condition is a no-go. Do not compensate with Git operations, a broad Composer update, a shared PHP-FPM restart, or an unreviewed source/config change.

### Staging

1. Create an access-restricted staging directory inside `/var/www/buy-dtf` so it is on the same filesystem as live `vendor/`. Do not stage under `/var/www`; the application owner cannot write there.
2. Copy the exact live `composer.json` into the stage and place the reviewed candidate `composer.lock` beside it. Do not copy candidate `composer.json` over production.
3. Record SHA-256, owner, mode, and size for both staged Composer files.
4. With production PHP 8.2.30 and Composer 2.9.3, run a locked install into the staged vendor using `--no-dev --prefer-dist --optimize-autoloader --no-interaction --no-scripts`. Never run `composer update` or `self-update`.
5. In the stage, run strict validation, locked audit, `check-platform-reqs --no-dev`, package inventory, and checksum capture.
6. Build a shadow application smoke directory from the exact live runtime files and live `config/database.php`, pointing it at the staged vendor and safe non-network test settings. Run package discovery, framework boot, route discovery, Markdown mail rendering, and the focused mocked integration tests without touching live caches or external providers.
7. Preserve the complete staging log and hashes for approval.

### Maintenance and atomic cutover

1. Re-run all stop checks and record a timestamped baseline.
2. Create an application-scoped rollback directory with mode `0700` on the same filesystem.
3. Back up the exact live `composer.lock` and all existing files under `bootstrap/cache/`, retaining owners, modes, hashes, and a manifest.
4. Enter a brief Laravel maintenance window with a private bypass secret and verify the maintenance response. Do not restart nginx, PHP-FPM, MySQL, or other shared services.
5. Rename live `vendor/` to a timestamped rollback name. Do not delete or reconstruct it.
6. Rename the fully staged vendor directory to `vendor/` on the same filesystem.
7. Atomically place only the reviewed `composer.lock`. Leave `composer.json`, `.env`, `config/database.php`, application source, assets, and test configuration untouched.
8. Run package discovery against the live application. Rebuild only package/cache artifacts that existed before the cutover; do not introduce config or route caching as a new production behavior.
9. With maintenance still active, run CLI boot/route checks and loopback HTTP smoke checks using the private bypass.
10. Leave maintenance mode and run the public smoke matrix: home, `/up`, login, protected redirects, current manifest/assets, authenticated admin/order view, safe cart/upload display, and non-mutating construction checks for mail and integration clients.
11. Monitor HTTP status, Laravel/PHP/nginx logs, checkout/order/payment/upload activity, scheduler freshness, and external-integration errors for at least 30 minutes and through the next scheduler boundary.

### Rollback triggers

Rollback immediately for any of the following:

- package discovery, autoload, boot, or cache failure;
- any new 5xx or route/auth/session regression;
- upload, image rendering, checkout, payment, webhook, mail, accounting, shipping, or Dropbox regression;
- new dependency-related exception or sustained latency increase;
- unexpected checksum/source/config drift;
- scheduler or queue state change from baseline.

### Rollback procedure

1. Enter or retain maintenance mode.
2. Rename the candidate vendor aside for diagnosis.
3. Atomically rename the retained old vendor back to `vendor/`.
4. Atomically restore the exact old `composer.lock` and backed-up `bootstrap/cache/` contents.
5. Confirm owners, modes, hashes, and old-package discovery/boot.
6. Leave maintenance mode, repeat the public smoke matrix, and monitor logs.
7. Preserve the failed candidate tree and logs; do not delete evidence during the incident.

This rollback changes no schema and restores the actual previously running dependency tree rather than attempting to recreate it.

## Remaining Work Requiring Separate Approval

- Execute the dependency-only production cutover in an approved low-traffic window.
- Execute the targeted payout `notes` correction in a separate reviewed window.
- Reconcile the two migration ledgers without running schema migrations.
- Remove the obsolete `remotefuel` fallback credentials and rotate any once-valid credential.
- Change production `APP_ENV` from `local` only after reviewing environment-dependent branches.
- Remediate npm audit findings and Sass deprecations in a separate frontend dependency phase.
- Implement the reviewed incoming-order v1 contract only after explicit approval; deploy BuyDTF capability first, then enable ShopNLTees sending.

## Stop Point

This report is the requested pre-deployment handoff. Production remains unchanged. Review is required before any production write, dependency swap, schema correction, job-label implementation, or ShopNLTees activation.
