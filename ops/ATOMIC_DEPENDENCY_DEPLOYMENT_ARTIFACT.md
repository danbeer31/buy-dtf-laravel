# Atomic Dependency Deployment Artifact

Status: **implemented and rehearsed on disposable local Linux directories; not copied to, staged on, or executed against production**

Scope: stage the already reviewed Composer lock, atomically exchange only `vendor/`, atomically replace only `composer.lock`, verify PHP-FPM loaded the new dependencies, and retain the exact former vendor/lock/cache for automatic rollback.

The artifact contains no Git command, general migration command, `composer update`, Composer self-update, source/config replacement, asset deployment, database write, shared-service restart, or database-consolidation action.

## Reviewed Files and Hashes

| File/artifact | SHA-256 |
|---|---|
| `ops/deployment/atomic_dependency_deploy.py` | `238e6294ee3542d04d69ed9acf5b5e3d412412d12eff43aa65295739332ab342` |
| `ops/deployment/dependency_runtime_probe.php` | `deb44c9c1bccc24ec91ee4ea504184000f30525763aa497b415611509d711dae` |
| Candidate `composer.lock` | `eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831` |
| Live `composer.json` to retain | `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872` |
| Live pre-cutover `composer.lock` to retain | `16eef909889a727717fccf52e9c7c23e8a0d2cc661777f6044abde97713d2579` |
| Live `config/database.php` to retain | `d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9` |
| Current retained `vendor/` manifest | `738c326e7f8e9199d36d0bb754eff031c38c5f69603bb56baa3cd189c98dbdcc` |
| Required post-payout runtime-source manifest | `46f6a1ffa03364b550395c89111a0d69a844d1379f3c5aba6ed5c1e17616abca` |

The source manifest is intentionally the exact current production runtime manifest **plus** the reviewed payout migration with SHA-256 `6bdd43d63d2427af19a2fb65afd1b295b12759ac916d2803d245de2c6f7c1e0c`. Consequently the dependency artifact cannot stage or cut over before the payout artifact has been installed exactly as reviewed. Any other live source, view, route, configuration, migration, build asset, Composer file, or vendor drift is a hard stop.

## Production Capabilities Confirmed Read-Only

The live host currently provides Linux 5.15 x86-64, Python 3.10.12, PHP 8.2.30, Composer 2.9.3, MySQL client/dump 8.0.46, `flock`, `sha256sum`, `curl`, `ss`, and `cgi-fcgi`. The application and vendor reside on the same ext filesystem. PHP-FPM exposes `/run/php/php8.2-fpm.sock` to the application owner's `www-data` group. No production file was created to collect this information.

Availability is rechecked at execution time. Prior observation is not a substitute for the script's fail-closed checks.

## Phase 1: Staging Only

Staging is a production-filesystem write but does not replace a live dependency. It requires separate approval and has **not** been run.

The stage command will be:

```text
python3 atomic_dependency_deploy.py \
  --stage \
  --candidate-lock /absolute/reviewed/bundle/composer.lock \
  --approval-token STAGE-BUYDTF-DEPS-eeac4637272ca2b9
```

The script acquires an exclusive application deployment lock and then:

1. Verifies owner/group, fixed paths, non-symlink files/directories, the exact source/config/Composer hashes, current vendor manifest, health baseline, and absence of scoped Artisan/payout processes.
2. Creates a mode-0700 release beneath `/var/www/buy-dtf/storage/app/private/operations/dependency-releases/` on the live filesystem.
3. Copies the exact live `composer.json` and reviewed candidate lock into the release. It never replaces production `composer.json`.
4. Uses an allowlisted environment with no inherited Composer vendor/config overrides.
5. Runs Composer 2.9.3 with plugins and scripts disabled: strict validate, locked no-dev audit, `install --no-dev --prefer-dist --optimize-autoloader`, and no-dev platform check. It never resolves or updates dependencies.
6. Copies the exact live runtime source/config into a no-`.env` shadow application, uses non-network testing drivers, and runs package discovery plus route discovery against the staged vendor.
7. Requires Laravel 12.61.1 and Guzzle 7.15.2, computes a deterministic candidate-vendor manifest, and writes a restricted `release-receipt.json` containing all hashes and command-output hashes.

Staging exits without a cutover. Its receipt SHA-256 and staged-vendor manifest must be independently reviewed before phase 2.

## Phase 2: Atomic Cutover

Only an independently approved release receipt can be supplied:

```text
python3 atomic_dependency_deploy.py \
  --cutover \
  --release-receipt /absolute/release/release-receipt.json \
  --release-receipt-sha256 <independently-approved-receipt-sha256> \
  --approval-token DEPLOY-BUYDTF-DEPS-eeac4637272ca2b9
```

The script then:

1. Repeats the complete checksum/CAS, vendor, health, queue, process, staged-release, and receipt checks. It also requires the receipt to have been created by the exact same deployment-script SHA-256.
2. Before creating rollback artifacts, entering maintenance, or changing any live dependency/cache/lock path, runs a PHP-FPM socket probe that must prove the currently running Laravel 12.46.0 and Guzzle 7.10.0 with reflection paths under the live `vendor/`. Failure stops before cutover.
3. Creates a mode-0700 rollback directory and verifies byte-exact copies of the old lock and complete `bootstrap/cache` snapshot.
4. Enters Laravel maintenance with a random private bypass, verifies the exact maintenance marker and a cache-busted public HTTP 503, saves a mode-0600 copy of that marker for fail-closed recovery, waits 65 seconds for request drain, proves business-activity aggregates did not change, requires zero connected FastCGI requests on the reviewed PHP-FPM socket, and repeats the full CAS immediately before exchange.
5. Performs one libc `renameat2(AT_FDCWD, live_vendor, AT_FDCWD, staged_vendor, RENAME_EXCHANGE)` call. Both directory names exist throughout; sequential renames are not a fallback.
6. Verifies candidate and retained vendor manifests, then replaces only `composer.lock` using a same-directory temporary file, `fsync`, and atomic `rename(2)`.
7. Runs only the fixed `package:discover` Artisan operation and verifies CLI runtime versions/paths.
8. Waits beyond the observed OPcache revalidation/file-protection window, then runs two probes at least three seconds apart through the local PHP-FPM socket. Both must prove Laravel 12.61.1, Guzzle 7.15.2, and reflection paths under the live vendor. The mode-0640 probe is outside the public root and is removed after each call.
9. Leaves maintenance, runs the public health matrix, and keeps automatic rollback armed during 30 minutes of repeated HTTP/runtime/queue checks. The state is not marked public until that first health matrix succeeds.
10. Retains the old vendor at the reviewed staged-vendor path and records the final state/receipt. It deletes neither the rollback data nor failed candidate evidence.

## Automatic Rollback and Recovery

After maintenance begins, every ordinary exception, failed check, SIGINT, or SIGTERM enters rollback. The script:

- immediately re-enters maintenance before recording a cutover failure;
- unconditionally re-enters and verifies maintenance again at the beginning of every rollback/recovery, ignoring any persisted `maintenance_active` value;
- requires both a valid Laravel maintenance marker and a cache-busted public HTTP 503 before changing vendor, lock, or cache during rollback; if `artisan down` cannot boot, it may restore only the checksummed marker saved by this run and must still prove HTTP 503;
- identifies vendor identities by their manifests and atomically exchanges the retained old vendor back;
- atomically restores the exact old lock;
- validates and restores the exact old cache snapshot;
- runs fixed old-vendor package discovery as a boot check, then restores the byte-exact cache snapshot again;
- verifies old Laravel/Guzzle versions through two PHP-FPM probes;
- leaves maintenance only after public health passes; if rollback `artisan up`, its health check, or its state write fails, it immediately re-enters and re-verifies maintenance before recording the failure.

A restricted state file is fsynced before and after each live mutation. For an uncatchable process/host failure, the same manifest-driven rollback is available through:

```text
python3 atomic_dependency_deploy.py \
  --recover \
  --state /absolute/reviewed/deployment-state.json \
  --approval-token RECOVER-BUYDTF-DEPS-16eef909889a7277
```

Recovery refuses unknown vendor/lock/cache identities. A verified failed rollback records `rollback_failed_maintenance_verified`. If public maintenance cannot be re-established and verified, the script stops before any subsequent rollback step and records `rollback_failed_maintenance_unverified`; it never reports that maintenance was retained based only on stale state.

## Rehearsal Evidence

The exact script was exercised on disposable WSL2 Linux ext directories using the real libc `renameat2(RENAME_EXCHANGE)` path. It passed:

- successful atomic exchange and lock replacement;
- injected failure immediately after vendor exchange;
- injected failure after lock replacement;
- injected package-discovery/cache failure;
- simulated interruption after exchange;
- double-exchange recovery;
- stale saved state claiming maintenance while the modeled site is public;
- interruption immediately after candidate `artisan up`;
- interruption immediately after rollback `artisan up`;
- rollback public-health failure after `artisan up`.

All ten scenarios passed. Final rehearsal script SHA-256: `238e6294ee3542d04d69ed9acf5b5e3d412412d12eff43aa65295739332ab342`.

GitHub CI repeats the payout artifact self-check and atomic disposable-directory rehearsal on every push.

Before deployment GO, this same exact script/hash must also run `--rehearse --rehearsal-parent <approved-disposable-directory>` on the actual `/var/www/buy-dtf` filesystem. That creates and removes only its uniquely named disposable child. This production-filesystem rehearsal is a write and was intentionally **not** performed without separate approval.

## Current Decision

Dependency deployment: **NO-GO** until the payout repair is completed, this script receives independent review, its exact hash passes CI, a same-production-filesystem disposable rehearsal succeeds, the generated release receipt/vendor manifest are independently approved, and a low-traffic cutover window is authorized.
