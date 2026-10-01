# Incoming-order v1 failed cutover and automatic rollback evidence

Date: 2026-10-01 UTC

## Result

The authorized receiver cutover did **not** complete. The exact reviewed runner
stopped after executing and verifying the single additive migration, but before
source installation began. Its reviewed automatic rollback/containment path
completed and restored the original application source and front controller.

The database migration was not reversed by the runner. Production therefore
has the two new, empty tables and one new migration-ledger row, while still
running the original application code. All capabilities remain disabled and
the artwork-host allowlist remains empty.

Do not describe this operation as a successful receiver deployment and do not
retry runner `569f8aec08b8493d1544a9c1c84b0dca2e0efd74cd8385091cbff13796c6119c`.

## Frozen inputs

- Receiver target: `0799440b7cbb0bad364fc2a65b41285f20245658`
- Runner SHA-256: `569f8aec08b8493d1544a9c1c84b0dca2e0efd74cd8385091cbff13796c6119c`
- Release receipt: `/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-releases/0799440b-20261001T013235Z/release-receipt.json`
- Release receipt SHA-256: `e08e969c97065cc7e387acbcf5544355b6270e55b095d4d9fa5d8bf06e33a9ed`
- Production operation directory: `/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-rollbacks/0799440b-20261001T020405Z`

## Timeline

- `02:04:05Z`: deployment state initialized after a fresh, passing preflight.
- `02:04:07Z`: reviewed source and database backups completed.
- `02:04:12Z`: the exact static gate was installed and verified at origin and public routes.
- `02:05:21Z`: the exact single migration completed and the post-migration runtime probe passed its schema checks.
- `02:05:21Z`: receipt serialization raised `TypeError: keys must be str, int, float, bool or None, not tuple`.
- `02:05:21Z`: automatic rollback/containment began.
- `02:05:27Z`: the exact rollback gate was verified.
- `02:05:34Z`: the exact original front controller was restored.
- `02:05:35Z`: state became `rolled_back` with `rollback_complete: true`.
- `02:11:49Z` through `02:42:58Z`: 30 independent post-rollback read-only samples all passed.

## Failure cause

`verify_post_migration()` successfully validates the installed schema and then
returns `ascii_bin_columns` as a Python dictionary keyed by `(table, column)`
tuples. `atomic_json()` cannot encode those tuple keys. The exception occurred
while writing `post-migration-verification.json`, after the migration had been
recorded and before `source_install_started` was persisted.

The raw post-migration probe is retained. A consolidated
`post-migration-verification.json` does not exist because its creation is the
operation that failed.

## Final production state

- Deployment state: `rolled_back`; automatic rollback complete.
- Source installation: never started and never completed.
- Reviewed 37-path live-source CAS: `9c0b081853feed397cc61be4b7b6d7c302df2298a87cca30e69e80f067cda6db`.
- Original front controller: `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9`, mode `0644`, owner `dan:dan`.
- Maintenance: inactive.
- Static gate: inactive.
- Receiver deployment lock: free.
- Dependency deployment lock: free.
- Receiver capability: disabled.
- Job-label capability: disabled.
- Retention capability: disabled.
- Allowed artwork hosts: zero.
- Queue connection: `sync`; queued jobs `0`; failed jobs `0`.
- PHP: `8.2.30`; Laravel: `12.69.0`.

Dependency identities remain unchanged:

- Composer lock: `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`
- Vendor tree: `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`
- Bootstrap cache: `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`
- `packages.php`: `21da8f9ed19687e708cc7bc5cc59394c6fcdf9b9deadf617ae70526f815a1db0`
- `services.php`: `1f7623b2b4ffd2c4099fb34ad86fc96c1479e27bf81b1b0ba328c988cc4ffcb5`

## Database state

Before mutation:

- Schema SHA-256: `8e35bf9ad473e78578d29315a74ad9b87e5007f585b0d85807feb1681e605476`
- Migration ledger: 19 rows, SHA-256 `867eda60246e2beb8cb86b927408284e2fdc4c6066d3485fe779523c68e7c8f9`
- Target migration entries: `0`
- Target tables: absent

After migration and after automatic source rollback:

- Schema SHA-256: `4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed`
- Migration ledger: 20 rows, SHA-256 `3168a7da9ca4aad0a81e673ec61c1647242916d054768f4dd48ff4b9d7eb28d4`
- Target migration entries: `1`
- `incoming_order_jobs`: exists, `0` rows
- `api_asset_records`: exists, `0` rows
- Existing audited row counts remained `businesses=46`, `dtforders=1581`, and `dtfimages=19405`.

The runner's rollback implementation restores source and the front controller;
it does not reverse the additive migration. No manual database change was made.

## HTTP and monitoring result

The final health matrix passed:

- `https://buy-dtf.com/`: 200
- `https://buy-dtf.com/up`: 200
- `https://buy-dtf.com/login`: 200
- `https://buy-dtf.com/admin`: 302 to login
- `https://buy-dtf.com/checkout`: 302 to login
- `https://www.buy-dtf.com/`: 200
- `https://www.buy-dtf.com/up`: 200
- Both reviewed Vite assets: 200

All 30 post-rollback monitoring samples passed. Every sample observed the same
schema hash, 20-row ledger, one target migration entry, empty target tables,
empty queues, disabled capabilities, empty host allowlist, original front
controller, inactive maintenance, absent receiver source, and healthy routes.

## Evidence availability

Present:

- Fresh cutover preflight receipt
- Source-backup receipt and source files
- Database-backup receipt, schema dump, and migration-ledger dump
- Repeated cutover pretend receipt and raw output
- Single-migration stdout/stderr
- Raw post-migration runtime probe
- Durable deployment state and event log
- Source-rollback receipt
- Rollback runtime probe
- Exact original-front-controller restoration receipt
- Final independent runtime and identity snapshots
- All 30 post-rollback monitoring samples

Not present because the runner stopped before those phases:

- Successful final deployment receipt
- Serializable post-migration verification receipt
- Source-install receipt
- Candidate-check receipt
- Runner-generated success monitoring receipt

## Key hashes

- Deployment state: `c28a4d901548dca2d1f0528dfa317833804d92e4aa6820843650f89ce211364b`
- Event log: `134924e5545c8f456d60b590ff185e7926d3a21b0b9ccdc86d162a03bb1cf437`
- Cutover preflight: `afce8f1213bc46191263098cd68665e9722c6578fd49a79dfd01965592ce1bb7`
- Source backup: `cad98ab03cf46075b9ec2fab4806056820048e240c6ae512bbd1877f8bc755d3`
- Database backup: `53917f7ceab89866d38f9b1ddf07ca47f7912cc476c8025dfcd965a061f0daed`
- Schema dump: `f7dfccbd949e83afc0c0f9cbb247f05242a671888aa76371d4b2553995f2cf14`
- Migration-ledger dump: `6f38f9d2bdaac8834937c5ca946e569e30a8338dd153178316b7a37b8d57e7b1`
- Cutover pretend: `dc3f71b5f566bc4dbf1e48d2f4b88cbd2f4e5ad239c77fa669e5537fbdf2bbb6`
- Migration stdout: `fe80c226bb5dfbbdb6dc06947b1fa97db1908701c7d8a7be4fe67dc3563b80c3`
- Post-migration runtime probe: `bde2ce40594e08eb5bde719414a69524f1638db2854e5a4a35847081aaece19f`
- Source rollback: `8e0782284148fdbe656aabacb7af2b1d12daff7f6db5a131eab7e7a1f2728a16`
- Rollback runtime probe: `f6846f3636a1e849bb1ec195572afed265ffcb047b2451ae04aa293cd80b0935`
- Front-controller restoration: `6c893cb31a24d51926c0704fa6f78a7b5e858ac5677ddcfc2ed342ffc0f4a9b2`
- Final runtime probe: `dab68b40b24c8ae38cb62833247a3d2331b2ff6a3b01330ecc42d57e2287ce83`
- Final identity snapshot: `711e54db3615af7dfa34ac344bc1128365b394a0abb41c37a5badf776dcce7b0`
- Post-rollback monitoring: `837c5a9e7767702f761f49a8431c5aa603fbd09bd15d455637e6d1ac032d2629`

The copied production operation directory contains 57 files. Its files were
compared byte-for-byte by SHA-256 with the retained production evidence before
this report was created.

The evidence-local `.gitattributes` disables text conversion for this subtree.
Several raw HTTP-header and production-source artifacts contain CRLF bytes;
those bytes are intentionally preserved. Consequently, a Git whitespace check
against the evidence commit can report the retained carriage returns as
trailing whitespace. Do not normalize those files.

No retry, manual production edit, dependency/bootstrap-cache/configuration
change, service restart, capability enablement, ShopNLTees change, retention
action, or customer-artwork action occurred. The reviewed automatic rollback
did execute `artisan view:clear`; its stdout/stderr are retained in the
operation directory.
