# Atomic Dependency Deployment Artifact v2

Status: **revised after the 2026-09-18 failed cutover; local rehearsal passes; another cutover is forbidden until the new script, production-filesystem rehearsal, and new staging receipt receive independent approval.**

The first candidate cutover failed because the live `bootstrap/cache` referenced the dev-only `Laravel\Pail\PailServiceProvider` while the correctly staged production vendor excluded dev packages. The reviewed rollback restored the exact old vendor, Composer lock, and bootstrap cache. This revision treats candidate cache files as release artifacts and uses a boot-independent static front controller during every mutation and recovery.

The artifact contains no Git command, general migration command, `composer update`, Composer self-update, source/config deployment, asset deployment, database write, shared-service restart, or database-consolidation action. Production installation remains `--no-dev`; Pail and other development packages are expressly rejected.

## Reviewed Files and Fixed Production Identities

| File/artifact | SHA-256 |
|---|---|
| `ops/deployment/atomic_dependency_deploy.py` | `6f4b481a486883190304659ec6b448aab9e8bb52a1d185ccbe7143c3835bdb38` |
| `ops/deployment/dependency_runtime_probe.php` | `e664bbff0af18ba07763bfb0fd1f2f4d2f4a5f7f2f2e378caed8daeea3ca31b7` |
| Embedded static maintenance front controller | `94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03` |
| Candidate `composer.lock` | `eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831` |
| Live `composer.json` to retain | `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872` |
| Live pre-cutover `composer.lock` to retain | `16eef909889a727717fccf52e9c7c23e8a0d2cc661777f6044abde97713d2579` |
| Live `config/database.php` to retain | `d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9` |
| Live `public/index.php` to retain | `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9` |
| Current retained `vendor/` manifest | `738c326e7f8e9199d36d0bb754eff031c38c5f69603bb56baa3cd189c98dbdcc` |
| Required post-payout runtime-source manifest | `46f6a1ffa03364b550395c89111a0d69a844d1379f3c5aba6ed5c1e17616abca` |

The exact production source remains the authority. Any unexplained source, configuration, front-controller, Composer, vendor, or bootstrap-cache drift is a hard stop.

## Retained Evidence That Must Not Change

The following deterministic production directory manifests were recorded before this revision:

| Evidence | Manifest SHA-256 |
|---|---|
| Failed staged release `eeac4637272c-20260919T000728Z` | `80abaeb5f0a317aa7500b19085191261f4bf3ff70abf98820c02d7fe7a111878` |
| Failed-cutover rollback `eeac4637272c-20260919T002812Z` | `b03e0b443649209974f6c1c9cb9e7c12445997ce9019f1ed54bcda070abf75c6` |
| Reviewed v1 artifact bundle | `1c9959648be7c37d101577d7c03b35176a906543a78ba3befc7c9ab402782053` |
| Payout-notes execution evidence | `5f2417d8e6fb914b82d94f7f7372e259e26b215ec14cf46909608be305a06541` |

New rehearsals and releases must use new sibling paths. The script deletes neither old nor new evidence.

## Read-only Environment Finding

The live application currently resolves:

- `APP_ENV=local`
- `APP_DEBUG=false`

The runtime helper records both values, and the deployment fails closed if they change after staging. This artifact does not edit `.env`, application configuration, or either setting.

## Phase 1: Staging Only

The stage command is:

```text
python3 atomic_dependency_deploy.py \
  --stage \
  --candidate-lock /absolute/reviewed/bundle/composer.lock \
  --approval-token STAGE-BUYDTF-DEPS-eeac4637272ca2b9
```

Staging:

1. Verifies the exact source, configuration, front controller, old lock, old vendor, current bootstrap-cache identity, health matrix, queue state, PHP/Composer toolchain, and absence of scoped Artisan or payout processes.
2. Records the effective application environment and debug setting without changing them.
3. Runs locked Composer validation and audit, then `composer install --no-dev --prefer-dist --optimize-autoloader --no-scripts`. It never resolves dependencies.
4. Builds a no-`.env`, non-network shadow application and runs package and route discovery there.
5. Requires Laravel 12.61.1 and Guzzle 7.15.2; rejects an installed `laravel/pail` package or directory.
6. Requires exactly `bootstrap/cache/packages.php` and `bootstrap/cache/services.php`, rejects any Pail reference, normalizes their production-readable metadata, and records their individual hashes, sizes, owners, groups, modes, aggregate tree hash, and root metadata.
7. Records the candidate vendor manifest, retained old vendor manifest, retained old cache identity, candidate cache identity, front-controller identity, static-gate hash, command-result hashes, and exact script/helper hashes in a restricted v2 release receipt.

Staging never enters maintenance or changes the live vendor, lock, cache, source, front controller, configuration, or database.

## Phase 2: Independently Approved Cutover Only

```text
python3 atomic_dependency_deploy.py \
  --cutover \
  --release-receipt /absolute/release/release-receipt.json \
  --release-receipt-sha256 <independently-approved-receipt-sha256> \
  --approval-token DEPLOY-BUYDTF-DEPS-eeac4637272ca2b9
```

The v2 cutover sequence is:

1. Repeat every checksum/CAS, release, health, queue, process, environment, cache, and old PHP-FPM runtime check.
2. Create a restricted rollback directory containing verified copies of the old lock, complete old bootstrap-cache content/modes, and original front controller. The exact old cache directory—including its ownership—is retained by the later atomic exchange because the non-root deploy user cannot impersonate `www-data` ownership on a copy.
3. Atomically replace `public/index.php` with an embedded PHP front controller that has no autoload or Laravel dependency. After the OPcache revalidation interval, require HTTP 503, a unique response header, and a fixed response-body sentinel on both `/` and a random application route.
4. Drain for 65 seconds, prove business activity did not change, require zero connected FastCGI requests, and repeat the full source/vendor/cache/lock CAS while the static gate remains active.
5. Atomically exchange `vendor/` with the staged candidate using one `renameat2(RENAME_EXCHANGE)` call.
6. Atomically exchange the entire live and staged `bootstrap/cache/` directories using a second `renameat2(RENAME_EXCHANGE)` call. This installs candidate-compatible `packages.php` and `services.php` before any candidate Laravel command can run.
7. Atomically replace only `composer.lock`, then run the first candidate boot through the reviewed runtime helper. No live `package:discover` is needed or run.
8. Verify candidate Laravel/Guzzle versions and paths twice through PHP-FPM after the OPcache interval.
9. Atomically restore the exact original front controller, run the public health matrix, and monitor HTTP/runtime/queue state for 30 minutes with rollback still armed.
10. Retain the old vendor and exact old cache (including ownership and modes) at the staged release paths plus the independent restricted cache evidence copy and all rollback evidence.

## Boot-independent Automatic Rollback and Recovery

Every caught error, SIGINT, or SIGTERM after rollback state creation first atomically reinstalls and verifies the static 503 front controller. Recovery never trusts a saved gate flag and does not call candidate Laravel.

Rollback then identifies state by manifests rather than transition flags:

1. Atomically exchange the retained old vendor back when required.
2. Atomically exchange the retained exact old bootstrap cache back when required.
3. Atomically restore the exact old Composer lock.
4. Verify all three old identities before booting any application code.
5. Boot and probe only the restored old runtime.
6. Atomically restore the original front controller and reopen only after the health matrix passes.
7. If any post-open rollback check fails, immediately reinstall and verify the static gate again.

Explicit recovery remains available through the exact reviewed state file and token:

```text
python3 atomic_dependency_deploy.py \
  --recover \
  --state /absolute/reviewed/deployment-state.json \
  --approval-token RECOVER-BUYDTF-DEPS-16eef909889a7277
```

Recovery validates that every backup and staged path belongs to the referenced v2 receipt and rollback directory, and that the state was created by the same script/helper hashes.

## Rehearsal Coverage

The real `renameat2(RENAME_EXCHANGE)` and atomic-file primitives are exercised in 23 disposable scenarios:

- stale dev-provider cache replaced before candidate boot;
- failure between vendor and cache exchange;
- failure between cache exchange and lock replacement;
- completely unbootable candidate with automatic rollback;
- interruption after each cutover transition: gate, vendor, cache, lock, candidate runtime, PHP-FPM probes, front-controller restoration, and public health;
- automatic recovery without invoking an unbootable candidate;
- interruption after each recovery transition: gate, vendor, cache, lock, restored runtime, PHP-FPM probes, front-controller restoration, and public health;
- stale persisted gate state while modeled public;
- rollback health failure that reinstalls the static gate.

GitHub CI runs this rehearsal on every push. The same exact script/hash must also pass on a disposable child of the production filesystem before staging.

## Current Decision

Dependency cutover: **NO-GO**. A new production-filesystem rehearsal and new v2 staging receipt must be generated in new paths, independently reviewed, and separately authorized. The failed v1 candidate must never be retried.
