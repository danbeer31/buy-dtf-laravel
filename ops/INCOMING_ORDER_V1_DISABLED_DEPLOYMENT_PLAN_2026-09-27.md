# BuyDTF Incoming-Order v1 Disabled-Capability Deployment Plan

Date: 2026-09-27 (America/Chicago)

Status: **The 2026-09-30 cutover attempt stopped before maintenance, migration, or source installation after the static gate inherited mode `0600`. Production was restored to its exact original front controller and independently confirmed healthy. Runner `2a7bf3966c593532af1e22db0f03d8cec1c6aecfde0902629b9f2328016c1138` is permanently NO-GO. The phase-aware containment runner and local fault-injection rehearsal below are NO-GO pending independent review, a new staging receipt, and separate authorization.**

Nothing in this plan authorizes a migration, source deployment, service restart, capability change, ShopNLTees sender change, or retention action.

## Phase 0 execution result

The authorized read-only preflight on 2026-09-27 stopped before any Phase 1 production write. `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` hashes to `690243adfefe0ce154b547db6205794bd30ac4277275179517a90994f4980648` on production, not the reviewed renderer identity `ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280`. Because the exact pinned font was a Phase 0 hard stop, no release directory was created and Artisan `migrate --pretend` was not invoked.

The complete historical stop receipt remains unchanged at `ops/evidence/incoming-order-v1-phase0-20260927/preflight-receipt.json`. All other completed Phase 0 checks passed, including all 35 then-current source CAS conditions, dependency/cache identities, Fuel connection and ledger proof, target-table absence, capability defaults, queue counts, locks, and the public health matrix. Production remained unchanged.

The correction packages that exact reviewed font as the versioned application asset `resources/fonts/job-card-v2/DejaVuSans.ttf`, packages its license notice beside it, and makes renderer `separate-job-card-v2` use only that immutable application file. The renderer no longer depends on `/usr/share/fonts` and its path/hash cannot be overridden by environment configuration. The two files are reviewed additions: Phase 0 requires them to be absent from live source, Phase 1 verifies them inside the staged archive, and post-install checks require the exact font, license, renderer identity, dimensions, DPI, and readiness. This correction has not been staged or run on production.

## Objective and fixed boundary

Deploy the additive schema and runtime source from receiver commit `0799440b7cbb0bad364fc2a65b41285f20245658` while preserving the current production dependency tree and keeping all new behavior disabled:

- `INCOMING_ORDER_V1_ENABLED`: absent or `false`;
- `INCOMING_ORDER_JOB_LABEL_ENABLED`: absent or `false`;
- `INCOMING_ORDER_RETENTION_ENABLED`: absent or `false`;
- `INCOMING_ORDER_ALLOWED_HOSTS`: absent or empty for this rollout.

No production environment value is changed by this deployment. An existing value that resolves any of the three enablement flags to true is a hard stop, not permission to edit `.env` during the window.

The deployment adds the capability-discovery route, guarded receiver code, frozen metadata/schema, separate-card production code, and the report-only retention command. It does not send a v1 job, generate or upload a job card, run the retention report, delete an asset, backfill a legacy row, or change ShopNLTees.

## Frozen identities

| Item | Required identity |
|---|---|
| Feature base | `f11a9413d9040b4562064ee02fda002b317e0de9` |
| Reviewed receiver target | `0799440b7cbb0bad364fc2a65b41285f20245658` |
| Runtime CAS manifest | `ops/deployment/incoming_order_v1_runtime_0799440.manifest` |
| Runtime CAS manifest SHA-256 | `b6efbd5463c82f895ca8d359b665a145d88c0d363ce7f97b247eae9080853bb6` |
| Runtime paths | 37 total: 26 additions and 11 replacements |
| Deterministic source archive SHA-256 | `ed1df143d219fa073efb2707508c3eb81ba17b777597cebc20a72d3c546522c2` |
| Final deployment runner | `ops/deployment/incoming_order_v1_deploy.py` |
| Phase-aware containment runner SHA-256 | `53723435a2d56d2736746a5a6d1e98fddeda660acbcf3a45f57b662b06b4adfd` |
| Permanently retired runner SHA-256 | `2a7bf3966c593532af1e22db0f03d8cec1c6aecfde0902629b9f2328016c1138` |
| Local gate rehearsal script | `ops/deployment/rehearse_incoming_order_v1_gate.py` |
| Local gate rehearsal script SHA-256 | `c3b2e2b79986650a6d27625ae18372057d987ac61eebf42e8a08fb6d40232e5d` |
| Local gate rehearsal receipt SHA-256 | `063a006ac173baf789bb0d1dd9da859f9805b3ef63a0906e2ec7382a08b6adfa` |
| Later-phase failure receipts SHA-256 | `56095d4dcc3c183ee3d7fb9cc1e199faed598c980f2d0a88384d8a567cc8df4c` |
| Local correction validation receipt SHA-256 | `be0c021d405cfc899f0604a3045eb48bcc8e24690c62e52a9ce919495e3e141f` |
| Runtime/schema helper | `ops/deployment/incoming_order_v1_runtime_probe.php` |
| Runtime/schema helper SHA-256 | `1b37d3a38834ef633cee5caa784d909b2f5be41ae6e22766f817f80f9f4a20bd` |
| Exact migration | `database/migrations/2026_09_27_120000_create_incoming_order_v1_tables.php` |
| Migration SHA-256 | `79fa911b0b2ad9bb79c33080725446093dffd4df3e01c3cb3888d508087c9f9d` |
| Contract-vector fixture SHA-256 | `5cae7f7af7636f891c39aea7d958aa73caf8f3f289175d156ba02088ffc7fd8b` |
| Bundled DejaVu Sans | `resources/fonts/job-card-v2/DejaVuSans.ttf` |
| Bundled DejaVu Sans SHA-256 | `ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280` |
| Bundled font license | `resources/fonts/job-card-v2/LICENSE.txt` |
| Bundled font license SHA-256 | `bc88ec457a574842b8f28c20e97a1fe91ecca69db14840484a22c694f2ffb6da` |
| Current Composer lock | `eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831` |
| Current vendor manifest | `97cd0bb104c42b57fbf90204ee74837ec1359b0ab1cbf8dac7d6929a154922d7` |
| Current bootstrap-cache manifest | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Current front controller | `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9` |
| Reviewed static 503 gate | `94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03` |

The runtime manifest is the complete source allowlist. Do not deploy `.env.example`, tests, contracts, evidence images, review scripts, `ops/` documentation, `composer.json`, `composer.lock`, `vendor/`, `bootstrap/cache/`, frontend assets, uploads, or any path absent from that manifest.

The September 28 staged release receipt records the permanently retired runner and must not be used for another cutover. The failed-operation directory at `/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-rollbacks/0799440b-20260930T220235Z` and every receipt beneath it remain immutable evidence. A future attempt requires a new sibling release, a new staging receipt containing the corrected runner, independent review, and separate authorization.

## Corrected front-controller transition primitive

The corrected primitive is shared by initial cutover gating, rollback gating, failure containment, normal reopening, and rollback reopening:

1. Require the original front controller to match its reviewed SHA-256, UID `1000`, GID `1000`, and mode `0644`.
2. Build the replacement beside the live path, then explicitly `chown` and `chmod 0644` and verify bytes plus metadata before any swap. The process-wide `umask 077` cannot reduce the prepared file's final mode.
3. Persist and fsync a `replacement_pending` transition before `os.replace`.
4. Atomically replace and fsync the directory, verify the live identity, then persist and fsync `installed` before any HTTP verification.
5. Validate the gate first through a direct loopback origin request that bypasses Cloudflare, then through a separate public Cloudflare request. Both must return the reviewed header, body sentinel, and HTTP `503`.
6. Before migration or source installation begins, any installation or verification failure restores the exact original atomically, writes exact-restoration and gate-failure receipts, and records a post-restoration normal-health result.
7. Once either `migration_executed` or `source_install_started` is durable, any gate verification failure retains or reinstalls the exact reviewed `0644` gate, records durable gated containment and a containment receipt, and never restores the original front controller.
8. Recovery classifies the actual live front-controller SHA-256 and validates the durable transition history. It never decides from `static_gate_active` alone. Rollback gate installation is an explicit containment phase before recovery work.
9. A pending transition with live gate bytes is reconciled as installed before verification. A live gate with the historical `0600` failure mode is identified by bytes; before mutation it is restored exactly, while later-phase recovery normalizes it to the reviewed `0644` gate and remains closed.

The local Linux rehearsal runs under `umask 077`, executes the gate as a separate UID/GID `33` process, proves a `0600` negative control is unreadable, and covers success, failures before/after replacement, pre-mutation public verification failure with exact restoration and recorded health, recovery of the historical `0600` gate, recovery from pending state with live gate bytes, later-phase rollback gating, and later-phase public verification failure with exact gated containment and no original-restoration receipt. It does not access production.

The expected-live column is deliberately based on raw production bytes, not Git-normalized blobs. Eight replaced files currently contain mixed CRLF/LF line endings; converting them to LF produces an exact match with feature base `f11a9413d9040b4562064ee02fda002b317e0de9`. Their raw hashes are nevertheless the compare-and-swap authority. The candidate target hashes remain the exact bytes from receiver commit `0799440b7cbb0bad364fc2a65b41285f20245658`, and rollback must restore the original raw production bytes and line endings.

## Risk assessment

Data risk is low because the only database change creates two new tables and both capabilities remain disabled. Operational risk is moderate because 37 runtime paths must become consistent as one release and several modified legacy files are in active cart/admin/production flows.

The principal controls are:

1. exact per-file compare-and-swap against the manifest;
2. a boot-independent static HTTP 503 gate plus Laravel maintenance state;
3. the guarded, single-path Fuel migration before candidate application code is exposed;
4. same-filesystem atomic file installation with a complete source backup;
5. no dependency, cache-layout, environment, queue-worker, or service change;
6. fail-closed rollback that restores source while retaining the additive schema and frozen evidence.

## Phase 0: read-only preflight and hard stops

Run during a separately approved low-traffic window, away from the hourly Stripe payout sync and the `01:30` accounting task. Begin just after a scheduler boundary so the source exchange can finish before the next minute.

Stop before staging or mutation unless all conditions pass:

1. Production resolves to `/var/www/buy-dtf`, is not a symlink, and remains on filesystem device `64513` unless an independently reviewed update explains the change.
2. Public home, `/up`, `/login`, protected redirects, `www` home and `/up`, the Vite manifest, and its current CSS/JS assets match the healthy baseline.
3. There is no active deployment, migration, payout sync, Composer install/update, checkout, upload, or production-handoff process.
4. Queue remains `sync`; queued and failed-job counts have not unexpectedly increased. Do not start or restart a worker.
5. The successful v2 dependency state remains exact: Composer lock, vendor tree, `packages.php`, `services.php`, and front controller match the frozen identities above. The deployment lock is free, maintenance is inactive, and the static gate is inactive.
6. Every `M` path in the runtime CAS manifest matches its raw expected-live SHA-256. Every `A` path is absent. Eight expected-live values intentionally differ from their Git-base hashes only because of production line endings; do not normalize bytes during preflight or backup. Any later raw-byte mismatch requires a new drift review; never overwrite it.
7. No path in the candidate, backup, evidence, or application roots is a symlink. All resolved paths stay beneath their fixed roots.
8. `bootstrap/cache` contains only the currently reviewed package/service files. In particular, no config or route cache exists. Do not introduce config or route caching in this rollout.
9. Composer's live autoloader is not class-map authoritative, so the new PSR-4 classes do not require `composer dump-autoload`. If it is authoritative, stop.
10. The three capability/retention flags resolve false and the allowed-host list resolves empty. The probe may print only these booleans/counts; it must not print secrets or other environment values.
11. PHP, FPM, and Imagick are available. The bundled font and license paths are absent before deployment exactly as required for manifest additions; no system-font identity is a prerequisite. Renderer readiness becomes a mandatory exact check only after the candidate source is installed, while label capability remains disabled.
12. The active migration connection selected by `--database=fuelmysql` equals `config('database.fuel_connection')`, and both resolve to the audited current Fuel database. The obsolete `remotefuel` connection is not used.
13. Fuel tables `businesses`, `dtforders`, `dtfimages`, and its migration ledger exist. Both `incoming_order_jobs` and `api_asset_records` and the exact migration-ledger entry are absent. Any partial or mixed state is a stop requiring dedicated reconciliation.
14. Available disk space is sufficient for the candidate, exact source backups, schema/ledger dumps, logs, and retained evidence.

The preflight receipt must contain timestamps, non-secret configuration classifications, process/queue counts, health results, file identities, schema/ledger state, owners/modes, and disk/device results.

## Phase 1: stage source and produce read-only pretend evidence

Use a clean local checkout and export files from the target commit, not the working directory. Resolve the path list only from the reviewed manifest. A representative deterministic build is:

```bash
target=0799440b7cbb0bad364fc2a65b41285f20245658
manifest=ops/deployment/incoming_order_v1_runtime_0799440.manifest
mapfile -t paths < <(awk -F '\t' '/^[AM]\t/ {print $4}' "$manifest")
git archive --format=tar --output=incoming-order-v1-0799440.tar "$target" -- "${paths[@]}"
sha256sum incoming-order-v1-0799440.tar "$manifest"
```

Before production staging, verify the archive contains exactly the 37 manifest paths and that every extracted file matches its target SHA-256. Require the candidate font and license to match their frozen hashes and record their byte counts in the release receipt.

Stage only beneath a new restricted path such as:

```text
/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-releases/0799440b-<UTC timestamp>/
```

The stage must:

1. use mode `0700` for directories and `0600` for receipts/logs;
2. retain the uploaded archive, manifest, archive hash, extraction log, and candidate tree;
3. verify the candidate tree against the target column of the manifest;
4. PHP-lint every candidate PHP file;
5. reject extra files, symlinks, devices, sockets, hard-link surprises, absolute paths, and `..` paths;
6. record the candidate owner/group/mode plan without touching live files;
7. create no Git checkout and run no Git command on production;
8. perform no Composer operation and no Artisan, database, cache, or HTTP mutation; the only Artisan call permitted in this phase is the reviewed `--pretend` invocation below after the ledger-existence proof.

After the candidate is verified, produce the migration pretend evidence before any live source, front-controller, maintenance, cache, schema, ledger, or configuration mutation:

1. Use a reviewed read-only probe to resolve the Fuel connection and migration-ledger table without printing credentials. Require the connection name to be exactly `fuelmysql`, require it to equal `config('database.fuel_connection')`, and require the configured ledger table to exist on that connection. Stop without invoking Artisan if the ledger is absent; this prevents Laravel from calling `migrate:install`.
2. Record deterministic pre-pretend identities:
   - a sorted schema fingerprint from non-volatile `information_schema` table, column, index, and constraint definitions for the audited Fuel database;
   - a sorted hash of every Fuel migration-ledger `(migration, batch)` row;
   - explicit absence of `incoming_order_jobs`, `api_asset_records`, and the exact incoming-order migration ledger entry.
3. Run the migration from its absolute restricted candidate path. Do not copy it into the live source tree:

   ```bash
   /usr/bin/php artisan migrate \
     --database=fuelmysql \
     --path=/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-releases/0799440b-<UTC timestamp>/candidate/database/migrations/2026_09_27_120000_create_incoming_order_v1_tables.php \
     --realpath --pretend --force --no-interaction
   ```

4. Capture stdout, stderr, exit status, exact command identity, staged migration SHA-256, connection/ledger proof, and a normalized statement-set hash. Stop unless every statement targets only `incoming_order_jobs` or `api_asset_records`, uses only the reviewed create/index definitions, and contains no unrelated DDL or DML.
5. Recompute the same schema and ledger identities immediately afterward. Require byte-identical fingerprints, both target tables still absent, the incoming-order ledger entry still absent, and unchanged ledger row count. Any difference is a hard stop and invalidates the evidence.

Staging ends with a restricted source-stage receipt and a separate read-only pretend receipt containing all of the above hashes and proofs. Those receipts and the final deployment runner hash require independent review and separate authorization before Phase 2. The staging authorization does not permit backup creation, maintenance, migration execution, or live source installation.

## Phase 2: backups and rollback receipt

Under an exclusive receiver-deployment lock, repeat the full preflight/CAS and then create a new restricted operation directory on the application filesystem. Before changing a live source path:

1. Copy all 11 replaced files with their relative paths, exact raw bytes, owners, groups, modes, and line endings into `rollback/source/`. Do not normalize the eight mixed-line-ending files.
2. Record all 26 added paths, including the bundled font and license, as required-absent rollback entries.
3. Copy and hash the exact current `public/index.php` and record the complete bootstrap-cache identity. Do not modify or rebuild dependency cache files.
4. Take a schema-only logical dump of the audited Fuel database with `--single-transaction --skip-lock-tables --no-tablespaces --routines --triggers --events --no-data`.
5. Take a separate logical dump of the Fuel migration ledger including its data.
6. Supply database credentials through a temporary mode-`0600` client file created and removed by a trap. Never place a password in a command line, log, receipt, or process argument.
7. Verify both dumps with `gzip -t`, record their SHA-256 values and byte counts, and record the pre-migration ledger and required-table schemas/row counts.
8. Verify the source backup byte-for-byte against the expected-live manifest column.

The migration does not alter existing business rows, so schema plus migration-ledger backup is the required narrow database backup. Do not take or retain unnecessary customer data in this operation bundle.

## Phase 3: gated schema and source cutover

The final runner must have fixed absolute paths, restrictive umask, reviewed hashes, an exclusive lock, append-only step/state receipts, signal/error traps, and no caller-supplied command text.

1. Atomically install and verify the exact reviewed static front controller. After the FPM revalidation interval, first require its unique header, body sentinel, and HTTP `503` through a direct loopback origin probe that bypasses Cloudflare, then require the same through a separate public Cloudflare probe.
2. While the static gate is active, use the still-running old Laravel runtime to enter maintenance mode. Wait 65 seconds, require no active scoped PHP/Artisan/FastCGI request, and repeat every source/dependency/schema CAS.
3. Reconfirm that the Fuel ledger exists and recapture its row hash and the deterministic schema fingerprint. Repeat the reviewed pretend command from the exact staged absolute path while the gate is active:

   ```bash
   /usr/bin/php artisan migrate \
     --database=fuelmysql \
     --path=/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-releases/0799440b-<approved timestamp>/candidate/database/migrations/2026_09_27_120000_create_incoming_order_v1_tables.php \
     --realpath --pretend --force --no-interaction
   ```

4. Require the repeated statement set to match the independently reviewed statement-set hash. Recompute the schema and ledger identities and require them to remain identical to the pre-pretend values.
5. Run the same absolute staged-path command without `--pretend`. Never run unrestricted `php artisan migrate`, `migrate:fresh`, `migrate:refresh`, or a rollback command.
6. Verify the exact Fuel ledger entry, table engines/collations, all columns/indexes, `ascii_bin` idempotency/owner columns, zero rows in both new tables, and unchanged required-table row counts.
7. Install all 37 runtime files, including the now-recorded migration file and the exact bundled font/license pair. Install additions before modified consumers and routes; replace each file through a same-directory temporary file plus atomic `rename(2)`. After every rename, verify target SHA-256, owner, group, and mode. The static gate and Laravel maintenance marker remain active throughout.
8. Verify the complete live runtime tree against the target column of the manifest. No file outside the manifest may differ from the preflight receipt.
9. Run `/usr/bin/php artisan view:clear` only. Do not run `optimize:clear`, `package:discover`, `composer dump-autoload`, any dependency command, or any cache-building command.
10. PHP-lint all deployed PHP files and run candidate CLI boot, `about`, route discovery limited to `api/incomingorder`, and command discovery. Confirm the legacy POST route and the new GET capability route each appear once.
11. Run a redacted runtime probe proving receiver, label, and retention flags are false; allowed-host count is zero; queue is `sync`; database default under the targeted migration invocation is the audited Fuel connection; and the two new tables are empty. Require renderer `separate-job-card-v2` to be ready with the exact application font hash, 1500-by-900 pixels, and 300 DPI. Do not execute the retention command.
12. Confirm the existing dependency/cache/front-controller identities are still exact. No dependency file may have changed.

If any step after the migration fails, do not drop the new tables or delete the migration ledger entry. Begin source rollback under the static gate.

## Phase 4: reopen and smoke checks

1. While the static gate still serves `503`, run candidate `artisan up` and verify the Laravel maintenance marker is absent.
2. Wait at least five seconds for FPM OPcache revalidation, then atomically restore the original front controller and verify its SHA-256.
3. Run the public matrix twice, at least three seconds apart:
   - `https://buy-dtf.com/` -> `200`;
   - `https://buy-dtf.com/up` -> `200`;
   - `https://buy-dtf.com/login` -> `200`;
   - protected admin/checkout routes -> expected login redirect;
   - `https://www.buy-dtf.com/` and `/up` -> `200`;
   - current Vite manifest/CSS/JS -> `200`;
   - `GET /api/incomingorder/capabilities` -> `200` with `Cache-Control: public, max-age=60`.
4. The capability response must report:
   - `receiver_idempotency_v1.enabled === false`;
   - `job_label_metadata_v1.enabled === false`;
   - `job_label_metadata_v1.modes === []`;
   - `artwork_hosts === []`;
   - `renderer_version === "separate-job-card-v2"`;
   - `renderer_font_sha256 === "ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280"`;
   - renderer readiness is true with no reason, the same renderer/font identities, 1500-by-900 pixels, and 300 DPI.
5. Confirm `incoming_order_jobs` and `api_asset_records` remain at zero rows. Do not submit a production v1 or legacy incoming-order request as a smoke test.
6. Perform an authenticated read-only admin/order-page check to catch Blade/relation errors. Do not use **Add to Production** for an API job.
7. Verify logs contain no new 5xx, autoload, route, SQL, view, queue, webhook, checkout, upload, or production errors and no secrets, signatures, signed query strings, or raw card metadata.
8. Monitor for at least 30 minutes and through the next scheduler boundary. Record all samples, queue/failed counts, new-table counts, maintenance/gate state, deployment-lock state, and source/dependency identities.

No PHP-FPM, nginx, scheduler, queue, or other shared service restart is planned or permitted. Any condition that appears to require one is a stop for separate review.

## Rollback procedure

Rollback is source-only and schema-preserving:

1. Enter explicit rollback containment by unconditionally reinstalling and verifying the boot-independent static `503` gate. Do not trust a saved maintenance flag. If validation fails after migration or source installation began, retain the exact `0644` gate and durable gated state; never reopen partially changed application code.
2. Re-enter Laravel maintenance with whichever reviewed runtime still boots. If neither runtime boots, keep the static gate and continue with file-identity rollback only.
3. Restore the 11 replaced files from the verified source backup using same-directory atomic renames, preserving their original raw bytes and mixed line endings exactly.
4. Remove only an added path whose current bytes still match the reviewed target hash and whose preflight state was `ABSENT`. An unknown or modified path is preserved and causes rollback to stop for adjudication.
5. Restore the exact pre-deployment source manifest. Clear compiled views with the restored old runtime; do not change package/service/config/route caches.
6. Leave `incoming_order_jobs`, `api_asset_records`, their Fuel migration-ledger entry, and any retained evidence intact. The reviewed migration `down()` is intentionally non-destructive. Do not run a general rollback or manually drop tables.
7. Reverify old source identities and the unchanged Composer lock, vendor, bootstrap cache, configuration, and original front controller before booting old application code.
8. Bring Laravel out of maintenance while the static gate remains active, verify old-runtime CLI health, wait for OPcache revalidation, then atomically restore the original front controller.
9. Run the complete public/admin health matrix and monitoring checks. If any post-open rollback check fails, immediately reinstall the static gate and report the site as gated, not healthy.
10. Preserve candidate, backup, schema/ledger dump, state, logs, and failure receipts unchanged for independent incident review.

Because capabilities are required to remain disabled, a normal rollback should find zero v1 job/asset rows. Any unexpected row is evidence to preserve and is a hard stop; it is never authorization to delete data.

## Required receipts for post-deployment review

Return all of the following before considering the rollout complete:

- final deployment status and state-receipt SHA-256;
- source archive, manifest, stage-receipt, runner, and log hashes;
- pre/post source manifests and all file owner/mode results;
- schema dump, migration-ledger dump, pretend output, migration output, and schema-verification hashes;
- exact migration batch/ledger receipt and zero-row counts;
- unchanged lock/vendor/cache/front-controller identities;
- redacted capability/config results proving all three capabilities remain disabled;
- public/FPM/admin health matrices and 30-minute monitoring samples;
- queue and failed-job counts, deployment-lock state, and maintenance/static-gate state;
- explicit confirmation that no dependency, environment, service, ShopNLTees, production-job, or retention action occurred.

## Later gates, outside this deployment

1. Receiver idempotency requires a separate enablement review and explicit configuration authorization.
2. ShopNLTees sender work begins only after the disabled BuyDTF receiver/schema deployment is verified.
3. Job-label metadata requires both receiver and label capabilities plus an approved physical 5-by-3-inch production print.
4. The initial artwork allowlist remains exactly `shopnltest.com`, but it is not configured until the reviewed sender artifact endpoint exists.
5. Customer artwork deletion and any automatic retention/purge remain separate future rollouts.

## Stop point

This plan stops before production staging, backup, migration, maintenance, source deployment, capability enablement, monitoring, or rollback execution. Independent review and separate authorization are required before any production write.
