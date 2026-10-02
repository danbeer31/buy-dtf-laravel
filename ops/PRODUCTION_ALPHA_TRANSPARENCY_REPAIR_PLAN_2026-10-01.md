# Production alpha transparency repair deployment plan

Status: review only; do not stage or deploy.

## Scope and invariant

This is now a schema-aware repair. It adds one guarded nullable `TEXT` column,
`savedimages.item_meta`, so a Saved Image retains its versioned production-alpha
policy and immutable source-artwork reference after every source `dtfimages` row
is deleted. It also makes the admin production comparison use the same policy
as the real production handoff.

The only production paths in the candidate are:

1. `app/Helpers/ImageHelper.php`
2. `app/Helpers/ProductionHelper.php`
3. `app/Http/Controllers/Admin/OrderImageController.php`
4. `app/Http/Controllers/CartController.php`
5. `app/Http/Controllers/TeamCustomizationController.php`
6. `app/Models/DtfImage.php`
7. `app/Models/SavedImage.php`
8. `database/migrations/2026_10_01_120000_add_item_meta_to_savedimages_table.php`

There is no dependency, environment, cache, service, ShopNLTees, retention,
customer-deletion, or incoming-order capability action. Receiver, job-label,
and retention capabilities must remain disabled; the artwork-host allowlist
must remain empty. Original customer artwork is never rewritten. Only derived
production PNGs receive the versioned threshold policy.

## Required starting state

The future runner must stop before mutation unless every condition is true:

- the independently accepted receiver closeout remains the source baseline;
- production dependency identities remain the accepted Laravel 12.69.0
  generation;
- source hashes for all seven existing paths match the frozen expected-live
  hashes in the reviewed artifact manifest;
- the new migration path does not exist in live source;
- Fuel schema fingerprint is
  `4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed`;
- Fuel migration ledger contains 20 rows with SHA-256
  `3168a7da9ca4aad0a81e673ec61c1647242916d054768f4dd48ff4b9d7eb28d4`;
- there is no ledger row named
  `2026_10_01_120000_add_item_meta_to_savedimages_table`;
- `savedimages` exists and `savedimages.item_meta` does not exist;
- record the exact `savedimages` row count before any action;
- queues and failed jobs are empty, deployment and scheduler locks are free,
  the static gate and Laravel maintenance mode are inactive, and the public
  and authenticated health matrix is green;
- all incoming-order capabilities are false and allowed artwork hosts are
  empty.

Any already-present column or migration entry is drift, not permission to
resume. It requires a separately reviewed schema-present artifact.

## Phase 0: read-only production preflight

1. Acquire only a read-only deployment-inspection lock.
2. Record hashes, byte counts, owner, and mode for the seven existing paths;
   record the migration path as absent.
3. Record Composer lock/vendor/cache/front-controller identities without
   changing them.
4. Produce deterministic, redacted schema and migration-ledger fingerprints.
5. Query `information_schema` for the exact `savedimages` column definition,
   indexes, engine, and row count. Prove `item_meta` is absent.
6. Record capability, allowlist, queue, failed-job, maintenance, gate, lock,
   scheduler, Stripe-sync, public health, FPM, and authenticated-view state.
7. Stop on any difference from the reviewed expectations.

Phase 0 performs no Git command, migration command, write, cache operation, or
service action.

## Phase 1: restricted staging and migration pretend

Staging requires separate authorization. It must use a new private release
directory on the production filesystem and must not alter live source.

1. Extract exactly the eight reviewed candidate paths into the private release.
2. Verify every staged byte count and SHA-256 against the reviewed manifest;
   enforce the reviewed owner and modes; run PHP syntax checks on all PHP files.
3. Copy the frozen runner and runtime probe into the release and verify their
   hashes. The runner must reject unrestricted `php artisan migrate`.
4. Re-run the complete read-only Phase 0 state check.
5. Invoke only the staged migration by absolute path:

   ```text
   php artisan migrate --database=fuelmysql \
     --path=/absolute/private/release/candidate/database/migrations/2026_10_01_120000_add_item_meta_to_savedimages_table.php \
     --realpath --pretend --force
   ```

6. Require exit zero and exactly one MySQL statement equivalent to:

   ```sql
   alter table `savedimages` add `item_meta` text null
   ```

7. Repeat the full schema fingerprint, migration-ledger fingerprint, column
   absence, and `savedimages` row-count checks after `--pretend`. They must be
   byte-for-byte unchanged.
8. Emit a signed/reproducible staging receipt containing candidate and runner
   identities, every command result hash, raw pretend-output hash, before/after
   schema and ledger hashes, row counts, health results, and a complete evidence
   manifest. Stop for independent review.

Phase 1 does not install a gate, create Phase 2 backups, run the migration,
replace live source, restart anything, or reopen/close the site.

## Phase 2: backups and controlled cutover

Phase 2 requires a separately reviewed runner, release receipt, receipt hash,
approval token, and explicit production authorization.

1. Re-run the hard-stop preflight and verify the staged release has not changed.
2. Create private, restrictive, hashed backups of:
   - the seven live source files and proof that the migration file was absent;
   - the exact original front controller;
   - `SHOW CREATE TABLE savedimages`;
   - a consistent full `savedimages` table dump, including row count;
   - the complete migration ledger and its deterministic fingerprint.
3. Verify every backup is readable and its receipt is durable before mutation.
4. Install and verify the reviewed boot-independent 0644 static gate. Separate
   local/origin validation from the public Cloudflare 503 probe.
5. Recheck source CAS, schema, ledger, column absence, row count, capabilities,
   hosts, locks, and queues under the gate.
6. Repeat the exact absolute-path `--realpath --pretend`; require the same
   reviewed one-statement output and prove schema/ledger remain unchanged.
7. Execute only that one staged migration with `--database=fuelmysql`, absolute
   `--path`, `--realpath`, and `--force`. Never run general `php artisan migrate`.
8. Immediately verify and receipt all of the following before source install:
   - one and only one new migration-ledger entry;
   - ledger count increased from 20 to 21;
   - `savedimages.item_meta` is nullable `TEXT` with no default;
   - every pre-existing `savedimages.item_meta` value is `NULL`;
   - `savedimages` row count and all pre-existing row data are unchanged;
   - no other table, column, index, or migration entry changed.
9. Atomically install exactly the eight reviewed paths on the same filesystem,
   persisting replacement-pending and installed identities around every swap.
10. Verify installed hashes before any candidate Laravel command. Run syntax,
    FPM/runtime, admin comparison, cart, authenticated order-view, capability,
    queue, and schema/ledger checks while the gate remains installed.
11. Restore the exact original front controller only after all candidate checks
    pass. Verify public and authenticated health, then complete a full 30-minute
    invariant monitor.

No synthetic customer upload is authorized by this plan. A write smoke test
requires separate explicit approval.

## Failure containment and rollback

- Before the migration executes, restore the exact original seven source files
  and original front controller. The schema and ledger must remain at their
  preflight identities.
- Once the migration begins, any failure retains the static gate until source
  rollback and health checks finish. Never reopen partially installed code.
- After the migration succeeds, automatic rollback restores the exact original
  seven source files and removes the newly installed migration file if it was
  absent before cutover, but deliberately preserves the additive nullable
  column and its migration-ledger row. Old code ignores the column; preserving
  it avoids deleting frozen policy/source metadata.
- Do not run `migrate:rollback`, do not drop `savedimages.item_meta`, and do not
  restore the database dump automatically. A database restore can erase
  concurrent customer writes and therefore requires a new incident-specific
  authorization.
- Any Saved Image rows written after source install keep their `item_meta`
  values through code rollback. Record their IDs/count only; do not delete or
  redact customer assets as part of rollback.
- Every recovery decision must use durable phase state plus actual gate,
  source, schema, and ledger identities. It must never trust a stale boolean.

## Required review evidence

Before production staging, independent review must receive:

- exact target commit and clean local/remote branch tips;
- expected-live/target manifest for all eight paths;
- migration SHA-256 and guarded-connection tests;
- MySQL grammar and isolated `--pretend` evidence;
- full PHPUnit output and observed test/assertion counts;
- PHP extension list, syntax results, Composer validation/audit, npm production
  audit, frontend build, and `git diff --check`;
- fixture and render manifests plus fresh deterministic render hashes;
- the Saved Image deletion/tenant-isolation/legacy regressions;
- real Imagick proof that admin comparison and production preparation match in
  pixels, visible bounds, alpha set, dimensions, and 300-DPI metadata;
- a frozen runner/rehearsal package covering pre-migration failure, migration
  failure, source-swap failure, candidate-check failure, post-reopen failure,
  and rollback with the additive schema retained.

Production Phase 1 must then add the private release receipt, exact absolute
pretend output, unchanged before/after schema and ledger fingerprints, and
staging evidence. No production staging evidence is claimed by this review-only
commit.
