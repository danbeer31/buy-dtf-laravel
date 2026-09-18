# BuyDTF Stabilization and Production Drift Report

Date: 2026-09-18 (America/Chicago)

Status: **local preparation complete; no production write or deployment performed**

## Decision

The production working files are the source of truth. The detached production Git commit is not a safe deployment baseline.

The stabilization candidate preserves the live runtime source. A normalized comparison of 270 production-relevant files found 266 exact matches and four explained differences: `composer.json`, `composer.lock`, `config/database.php`, and `phpunit.xml`. The dependency deployment must therefore be a narrowly scoped `composer.lock` plus staged `vendor/` replacement. It must not use Git, replace production `composer.json`, replace production configuration, run migrations, or restart shared services.

The dependency lock/vendor candidate is credible, and a frozen deployment artifact now implements the compare-and-swap, atomic directory exchange, automatic rollback, and OPcache checks specified below. It passed disposable local-Linux rehearsal. Live cutover remains **conditional NO-GO** until the artifact receives independent review, passes rehearsal on a disposable directory on the actual production filesystem, generates a reviewed staged-release receipt/vendor manifest, and receives a separate low-traffic-window approval. A sequential `vendor/` rename is not acceptable.

The Stripe payout schema correction is prepared and tested locally as a separate change. It binds DDL to the migrator-selected connection and fails unless that active connection is the configured/audited Fuel connection. It must not be applied through a bulk migration.

## Scope and Guardrails

Completed:

- Created a clean worktree from current `origin/main`.
- Reconciled the Step 1 test/CI safety work and Step 2 Composer security work with current main.
- Updated the newly vulnerable CommonMark package within the existing major constraint.
- Ran the complete isolated test suite, frontend build, Composer audits, and static checks.
- Compared the live working files with the stabilization candidate.
- Audited both production migration ledgers and the corresponding live schemas read-only.
- Prepared and tested a guarded migration for the missing payout-entry `notes` column locally.
- Prepared an exact single-migration payout runner with restricted backup, precheck, validated `--pretend`, verification, and rollback receipts.
- Implemented and locally rehearsed the atomic dependency staging/cutover/recovery artifact.
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
- `c0ae1c5` - fix: add initial guarded Stripe payout entry notes migration (superseded by the connection hardening in this report's final commit; do not deploy this commit alone)

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
| Candidate payout `notes` migration (separate change) | `6bdd43d63d2427af19a2fb65afd1b295b12759ac916d2803d245de2c6f7c1e0c` |
| Payout execution runner | `80f99eee566a2fc212a17ba34dc55c94db47c6816abe49deca9d78a55cae98b2` |
| Atomic dependency deployment script | `7d20222e058a7890a095eb00f80695bd2dd0348d105bf0b6a9d9c23e6f6898a5` |

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
| Full isolated PHP suite | 108 tests, 714 assertions, pass (randomized seed `9182026`) |
| Targeted payout migration regressions | 3 tests, 15 assertions, pass |
| Payout artifact self-check | Exact migration/helper hashes, pass |
| Atomic dependency rehearsal | Success plus post-exchange, post-lock, package-discovery, interruption, and double-exchange recovery scenarios, pass |
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

The production `stripe_payout_entries` table lacks `notes`, while the deployed model/service writes that field. This caused recurring `SQLSTATE 42S22` payout-processing failures at `StripePayoutService.php` during August. An independent read-only recheck found 85 rows and no payout sync running.

### Prepared correction

The initial local migration commit `c0ae1c5`, as superseded by this report's final connection-hardening commit, provides:

- `database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php`
- `tests/Feature/Migrations/StripePayoutEntryNotesMigrationTest.php`

The migration:

- uses Laravel's active/default migration connection, which is the connection selected by `--database` while the migrator runs;
- compares that active connection with `database.fuel_connection` and fails before any schema query when they differ;
- applies the same connection check during `down()` so a rollback cannot mutate the wrong migration ledger;
- refuses to continue if the target table is missing;
- adds one nullable `TEXT notes` column only when absent;
- appends the column, keeping the alteration narrow;
- is idempotent;
- intentionally retains the additive column on code rollback.

The regression coverage first reproduces the exact missing-column write failure, applies the migration, proves the write succeeds, runs `up()` again, and proves `down()` preserves the column and data. A separate two-connection test makes a different SQLite connection active, proves the migration refuses it, and proves neither the wrong schema nor the intended Fuel schema was altered. A third regression proves Laravel pretend mode emits exactly the additive `notes` DDL without changing the schema.

The exact execution artifact and receipts are defined in `ops/PAYOUT_NOTES_EXECUTION_ARTIFACT.md`. Production execution remains separately gated; neither the migration nor its runner has been copied to the live application.

### Separate future execution plan

This must not be combined with the dependency deployment or a bulk migration.

1. Review and approve the exact final branch-tip SHA reported in the handoff; do not deploy `c0ae1c5` alone.
2. Reconfirm the table exists, `notes` is absent, row count is plausible, MySQL is 8.0.x, and no payout sync is running.
3. Take a timestamped, access-restricted schema/data backup of the payout tables and verify that the dump is nonempty/readable.
4. Deploy only the reviewed migration file, recording its SHA-256.
5. Before `--pretend`, verify that the migrator-selected connection name and `database.fuel_connection` both resolve to the audited `fuelmysql` connection. Any mismatch is a no-go; do not edit configuration to bypass the guard.
6. Run `--pretend` with the exact Fuel connection/path and confirm the only DDL is an additive nullable `notes` column.
7. Run only the exact migration path with `--database=fuelmysql --path=database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php --force`.
8. Verify the Fuel ledger entry, column type/nullability, unchanged row count, and public health.
9. Do not manually trigger a command capable of Stripe/QBO writes merely as a smoke test. Observe the next natural payout event/scheduled sync and verify that the former missing-column error does not recur.

Rollback is application-safe by retaining the nullable column. If the application must be rolled back, leave the column and ledger entry in place; restoring/dropping it would add risk without restoring useful behavior.

## Exact Dependency-Only Deployment Plan

This section is implemented by `ops/deployment/atomic_dependency_deploy.py` and detailed in `ops/ATOMIC_DEPENDENCY_DEPLOYMENT_ARTIFACT.md`. Its exact reviewed SHA-256 is recorded above. It has not been copied to, staged on, or executed against production. The production cutover remains a no-go until independent review, a disposable rehearsal on the actual production filesystem, staged-release receipt/vendor-manifest approval, and a separate GO.

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
- Linux `renameat2(..., RENAME_EXCHANGE)` support is successfully rehearsed on two disposable directories on the same production filesystem. The rehearsal must prove both directory contents exchange in one syscall. If unsupported, stop; sequential renames are not a fallback.
- A reviewed script contains no Git command, no `composer update`/`self-update`, no migration command, no generic Artisan command supplied by user input, and no service restart.

Any failed condition is a no-go. Do not compensate with Git operations, a broad Composer update, a shared PHP-FPM restart, or an unreviewed source/config change.

### Frozen-script and compare-and-swap requirements

The script must:

1. Run with strict shell error handling, a restrictive umask, an exclusive application deployment lock, fixed absolute paths, and no untrusted/evaluated input.
2. Embed or receive only reviewed immutable values: live application path, live `composer.json` SHA-256, old lock SHA-256, candidate lock SHA-256, staged vendor manifest hash, expected device ID, owners, and modes.
3. Resolve every path and fail if the application, live vendor, staged vendor, candidate lock, rollback directory, or cache backup is a symlink or is outside `/var/www/buy-dtf`.
4. Perform a compare-and-swap preflight immediately before maintenance: all live source/config/Composer hashes, Git-independent source manifest, owner/mode/device, free-space threshold, public health, queue/scheduler state, and no active checkout/upload/payout/artisan process must still equal the approved baseline.
5. Use a state file plus an exit/error/signal trap. Once any live artifact changes, every non-successful exit automatically exchanges the old vendor back, atomically restores the old lock and cache snapshot, verifies their hashes, and reports rollback health.
6. Write a timestamped append-only run log containing commands by stable step identifier, hashes, state transitions, smoke results, and rollback result, but no secrets or environment values.
7. Refuse Git operations, unrestricted `php artisan migrate`, any migration, dependency resolution/update, shared-service restart, or production source/config replacement.

### Staging

1. Create an access-restricted staging directory inside `/var/www/buy-dtf` so it is on the same filesystem as live `vendor/`. Do not stage under `/var/www`; the application owner cannot write there.
2. Copy the exact live `composer.json` into the stage and place the reviewed candidate `composer.lock` beside it. Do not copy candidate `composer.json` over production.
3. Record SHA-256, owner, mode, and size for both staged Composer files.
4. With production PHP 8.2.30 and Composer 2.9.3, run a locked install into the staged vendor using `--no-dev --prefer-dist --optimize-autoloader --no-interaction --no-scripts`. Never run `composer update` or `self-update`.
5. In the stage, run strict validation, locked audit, `check-platform-reqs --no-dev`, package inventory, and checksum capture.
6. Build a shadow application smoke directory from the exact live runtime files and live `config/database.php`, pointing it at the staged vendor and safe non-network test settings. Run package discovery, framework boot, route discovery, Markdown mail rendering, and the focused mocked integration tests without touching live caches or external providers.
7. Produce a deterministic staged-vendor manifest of relative path, file type, size, mode, and SHA-256; record its aggregate hash in a restricted staged-release receipt. Exit without cutover so that exact receipt SHA-256 and vendor aggregate can be independently approved. Cutover accepts only that approved receipt and requires it to identify the exact deployment-script SHA-256.
8. Rehearse the script's `renameat2(RENAME_EXCHANGE)` helper and its automatic rollback against disposable directories on the same filesystem. Verify normal cutover, injected lock-swap failure, injected package-discovery failure, and interruption after the exchange.
9. Preserve the complete staging/rehearsal logs and hashes for approval.

### Maintenance and atomic cutover

1. Re-run all stop checks and record a timestamped baseline.
2. Acquire the exclusive deployment lock, repeat the checksum/CAS verification, and keep the lock until final success or completed rollback.
3. Create an application-scoped rollback directory with mode `0700` on the same filesystem. Back up the exact live `composer.lock` and existing `bootstrap/cache/` files with owners, modes, hashes, and a manifest; verify the copies byte-for-byte.
4. Enter Laravel maintenance mode with a private bypass secret and verify it. Wait at least the maximum normal request duration, then verify there is no in-flight scoped PHP/artisan process. If requests cannot be drained, use a separately approved web-server-level static maintenance response; do not continue through active traffic.
5. Invoke one previously rehearsed `renameat2(AT_FDCWD, live_vendor, AT_FDCWD, staged_vendor, RENAME_EXCHANGE)` syscall. This atomically places the candidate at `vendor/` and the exact old vendor at the staged path; there is never a missing `vendor/` pathname.
6. Verify the live vendor manifest. Atomically replace only `composer.lock` using a same-directory temporary file plus `rename(2)`, then verify its SHA-256. Leave `composer.json`, `.env`, `config/database.php`, source, assets, and tests untouched.
7. Run package discovery against the live application. Rebuild only package/cache artifacts that existed before the cutover; do not introduce config or route caching as a new behavior.
8. With maintenance active, run CLI boot/route checks and loopback HTTP smoke through the private bypass.
9. Because FPM OPcache has timestamp validation enabled with a two-second revalidation interval and two-second file protection, wait at least five seconds after the exchange. Invoke a reviewed temporary probe outside the public webroot through the local FPM socket/internal-only location; it must report `Illuminate\Foundation\Application::VERSION=12.61.1`, Guzzle `7.15.2` through Composer `InstalledVersions`, and reflection paths under the live vendor. Run it twice at least three seconds apart, alongside `/up`, login, and application-route probes. Both rounds must match the candidate and be 5xx-free, and logs must contain no preload/autoload/redeclare/stale-path error. Remove the probe and verify it is absent before leaving maintenance. If direct FPM verification cannot be isolated from public access or does not prove the candidate versions, roll back; CLI PHP or a CLI OPcache reset is not evidence for FPM.
10. Leave maintenance mode and run the public smoke matrix: home, `/up`, login, protected redirects, current manifest/assets, authenticated admin/order view, safe cart/upload display, and non-mutating construction checks for mail and integration clients.
11. Mark the state file successful only after all hashes and smoke tests pass. Until then, the automatic rollback trap remains armed.
12. Monitor HTTP status, Laravel/PHP/nginx logs, checkout/order/payment/upload activity, scheduler freshness, and external-integration errors for at least 30 minutes and through the next scheduler boundary.

### Rollback triggers

Rollback immediately for any of the following:

- package discovery, autoload, boot, or cache failure;
- any new 5xx or route/auth/session regression;
- upload, image rendering, checkout, payment, webhook, mail, accounting, shipping, or Dropbox regression;
- new dependency-related exception or sustained latency increase;
- unexpected checksum/source/config drift;
- scheduler or queue state change from baseline.

### Rollback procedure

The frozen script performs these automatically on any failure/signal after the exchange; the operator may also invoke the same idempotent rollback mode explicitly:

1. Enter or retain maintenance mode and hold the deployment lock.
2. If the exchange occurred, call the same `renameat2(RENAME_EXCHANGE)` operation again, returning the exact old vendor atomically to `vendor/`.
3. Restore the old lock through a same-directory temporary file and atomic `rename(2)`. Restore the exact cache snapshot.
4. Verify old vendor aggregate manifest, old lock/config/source/cache hashes, owners, modes, and framework boot.
5. Perform the same five-second wait and two internal FPM-backed probe rounds, this time proving the retained old Laravel/Guzzle versions and live-vendor reflection paths; remove the probe afterward.
6. Leave maintenance mode only after rollback health passes; otherwise keep the static/maintenance response and escalate.
7. Preserve the failed candidate tree, state file, and logs; do not delete evidence during the incident.

This rollback changes no schema and restores the actual previously running dependency tree rather than attempting to recreate it.

## Remaining Work Requiring Separate Approval

- Independently review the exact payout execution artifact, then approve or reject its separate single-migration window.
- Independently review the frozen atomic dependency deployment artifact, run its disposable production-filesystem rehearsal only after approval, review its generated staged-release receipt/vendor manifest, and only then request a low-traffic cutover GO.
- Reconcile the two migration ledgers without running schema migrations.
- Remove the obsolete `remotefuel` fallback credentials and rotate any once-valid credential.
- Change production `APP_ENV` from `local` only after reviewing environment-dependent branches.
- Remediate npm audit findings and Sass deprecations in a separate frontend dependency phase.
- Implement the reviewed incoming-order v1 contract only after explicit approval; deploy BuyDTF capability first, then enable ShopNLTees sending.

## Stop Point

This report is the requested pre-deployment handoff. Production remains unchanged. Review is required before any production write, dependency swap, schema correction, job-label implementation, or ShopNLTees activation.
