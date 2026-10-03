# Laravel 12.69.1 remember-cookie dependency repair v3

Date: 2026-10-02 (America/Chicago)

Status: **preparation and independent review only; NO-GO for production
access, restricted staging, or deployment**.

This plan covers the control corrections requested after review of commit
`cfaadedfda941e593a1ff7f1729ad8a461fdc0e7`. It does not authorize a
production connection, stage, cutover, migration, service restart,
configuration change, capability change, or modification of either retained
partial release. Runner
`a7657bbfea760be186301503c567042f76739c2954fffbfc76f31c9f4eefede5`
is retired and cannot be staged.

The controlling v3 handoff is
`ops/evidence/laravel-remember-cookie-runner-v3-20261002/HANDOFF.md`, SHA-256
`305127ee8dc6c578ea8a8a1901a455b2e18378c481c8c726b3b120917e62a984`.
The replacement runner and its helper modules are complete local review
artifacts. Their frozen hashes and local validation receipts are recorded
below. They remain **NO-GO** until this package passes independent review and
a new, separately authorized restricted stage is issued.

## Scope and frozen dependency identities

The dependency delta remains exactly one package: `laravel/framework`
`v12.69.0` to `v12.69.1`. No application source, migration, ShopNLTees,
retention, customer-deletion, customer-artwork, or capability change belongs
to this repair.

| Item | Frozen identity |
|---|---|
| Live rollback lock | `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9` |
| Live rollback vendor | `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed` |
| Live and candidate cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Candidate lock | `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d` |
| Candidate vendor | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Vendor ownership and mode | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Complete vendor inventory | `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5` |
| Executable allowlist | `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154` |
| Application autoload entry set | `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91` |
| Runtime source CAS | `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` |

The v3 control identities are:

| Control | SHA-256 |
|---|---|
| Dependency runner | `97cb4e8d702b7ceb1b9efde26dba93e6e0f4a833bb55650843fed1c0746f0307` |
| PHP runtime helper | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| Database-envelope validator | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| Static-gate helper | `1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80` |
| Static-gate rehearsal | `2d52ec99a3d57c8c8534db7283f43bd54debcfca8349370058662631523e0b3e` |
| Laravel log-delta parser/collector | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |
| Candidate builder | `e6974c9963864cd11dde2f09d6fffd24485e879564dfd81d5977f2b1b1b66eb4` |
| Two-build comparator | `5706f9ba19ca2a68820a552efb6b59b679c4bc5775ab093712d11b5fbbf21c16` |
| PHP 8.2.30 verifier | `baaa77a1c5a5a41a3cfe37c2ac74d362c8c431d8c5c6d5371947514a1619fef4` |

The release receipt and rollback state bind the runner, runtime helper,
database validator, gate helper, log parser, handoff, source CAS,
front-controller identity, candidate identities, rollback identities, and the
reviewed database envelope.

## Database envelope

The PHP runtime probe gathers credential-free, read-only database facts. The
database-envelope validator applies one deterministic policy to those facts.
The runner never writes to the database and contains no migration operation.

The fixed database contract is:

- schema SHA-256
  `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`;
- exactly 21 migration-ledger rows with SHA-256
  `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`;
- exactly one
  `2026_10_01_120000_add_item_meta_to_savedimages_table` ledger entry;
- `savedimages.item_meta` present at ordinal 12 as nullable `TEXT`, with the
  reviewed charset, collation, default, and extra fields;
- zero non-null `savedimages.item_meta` values throughout this dependency-only
  stage, cutover, monitor, independent-review finalization, rollback, and
  recovery flow;
- `incoming_order_jobs` and `api_asset_records` present with their complete
  reviewed table, column, constraint, and index definitions, and zero rows;
- the incoming-order migration recorded exactly once;
- `jobs` and `failed_jobs` present and empty, queue connection `sync`, and all
  incoming-order receiver, job-label, retention, and host-allowlist
  capabilities disabled.

The schema, ledger, column definition, table definitions, row counts, queues,
and capability state remain fixed throughout this dependency repair. Because
this repair deploys no source, every runner path uses the
`pre_source_exactly_zero` policy and any non-null `savedimages.item_meta` row
fails closed. Legitimate growth is allowed only by a later, separately
reviewed transparency source cutover after Laravel 12.69.1 is deployed and
its monitor passes; it is outside this plan.

The runner enforces the envelope at these boundaries:

1. the read-only production preflight that precedes any restricted stage;
2. after candidate construction, before a release receipt can be issued;
3. at cutover entry against the independently reviewed stage receipt;
4. after the static-gate drain and again immediately before the durable
   dependency-mutation boundary;
5. after candidate activation and in every 30-minute monitor sample;
6. at monitor completion and again immediately before independent-review
   finalization can mark success;
7. before reopening after rollback; and
8. during explicit recovery.

Every boundary above requires `savedimages.item_meta` non-null rows to remain
exactly zero.

The stage release contains a database-envelope receipt covering the pre-build
and post-build observations. The cutover state contains a separately fsynced
immediate-pre-mutation receipt. Drift in any individual invariant fails
closed. Tests must independently alter the schema hash, schema section counts,
ledger row count, ledger hash, target migration count, `item_meta` definition,
pre-source `item_meta` count, each incoming-order table definition and count,
queue state, and disabled capability state.

## Restricted staging sequence

Restricted staging is prohibited under this handoff. It may occur only after
this v3 branch, commit, hashes, validation package, and plan pass independent
review and the operator supplies a fresh v3 restricted-stage authorization.
The retired v1 and v2 tokens are invalid.

When separately authorized, the runner performs this sequence:

1. Acquire the deployment lock and run the complete read-only baseline,
   including exact live lock, vendor, cache, source, front controller,
   configuration, PHP/Composer toolchain, services/process exclusions,
   public health, queues, disabled capabilities, and database envelope.
2. Create only a new private v3 shadow under the fixed operations root. Do
   not use or modify either retained partial release.
3. Copy the exact CAS-verified runtime source before Composer generates the
   one canonical optimized autoload result. Install the approved lock with
   `--no-dev`, preserve Unix-only proxy generation, and reject `.bat` files,
   symlinks, special files, hard links, unexpected executable files, or any
   ownership/mode mismatch.
4. Reproduce the reviewed 6,460-file, 925-directory, 26,481,661-byte vendor,
   126 application entries in both optimized autoload files, ten-path
   executable allowlist, exact UID/GID and mode identity, candidate cache,
   package discovery, 178 routes, and PHP 8.2.30 platform result.
5. Re-run the source, live dependency, front-controller, configuration,
   health, queue, capability, and database checks after construction.
6. Write a v3 release receipt that binds every input, output, helper, command
   receipt, and database-envelope receipt, then stop.

Staging does not install the static gate, enter Laravel maintenance, exchange
vendor or cache, replace `composer.lock`, deploy source, restart a service,
or run a migration. The successful release receipt and its SHA-256 require a
new independent review before a cutover authorization may be issued.

## Durable static-gate transition

Cutover uses the reviewed fixed static front controller rather than Laravel
maintenance mode. Before replacement, the runner verifies the exact gate
bytes and SHA-256, owner/group `1000:1000`, and mode `0644`, along with the
exact original front-controller backup and metadata.

The gate transition is durable in this order:

1. Append and fsync a `replacement_pending` transition in the rollback state.
2. Atomically replace `public/index.php` and fsync its parent directory.
3. Verify the live file identity, then append and fsync `installed` before any
   HTTP probe.
4. Probe the origin through the direct loopback route and separately probe the
   public Cloudflare route. Each must identify its expected route and return
   HTTP 503, the reviewed maintenance header, and the exact body sentinel.
5. Append and fsync `verified`, including both probe receipts.

The rehearsals run under umask `077` and must prove the gate remains readable
by an actual UID/GID 33 process. They cover failure and abrupt interruption
before replacement, after every durable transition, during origin
verification, during public verification, stale-state/live-gate recovery,
later-phase rollback, and byte-for-byte original restoration.

If installation or either verification fails before dependency mutation is
durably armed, the runner atomically restores the exact original front
controller and metadata, emits gate-failure and restoration receipts, and
verifies normal health. If dependency mutation has begun, it retains or
reasserts the reviewed gate, records durable containment, and performs the
reviewed rollback. It never reopens on a partially changed dependency set.

Recovery examines the actual front-controller bytes and metadata together
with the complete durable transition history and dependency-mutation fields.
It does not trust a cached `gate_active` boolean. An exact live gate leads to
containment and rollback when mutation might have begun. An exact original
front controller can reopen only after the dependency orientation and all
rollback invariants have been proved.

## Separately authorized cutover

Cutover remains prohibited until an independently reviewed successful v3
stage receipt receives a separate written authorization bound to the exact
receipt SHA-256 and reviewed v3 runner.

The authorized runner would revalidate the complete baseline and release
receipt, install and independently verify the static gate, drain active FPM
work, and enforce the database envelope twice under the gate. It then durably
arms dependency mutation, atomically exchanges only `vendor/`, verifies and
skips the cache exchange because the frozen live and candidate cache
identities are identical, and atomically installs only the candidate
`composer.lock`.

The first candidate boot occurs only after vendor, cache identity, and lock
are mutually consistent. The runner verifies Laravel 12.69.1 through the CLI
runtime probe and two FPM probes, rechecks the database envelope, restores the
exact original front controller, verifies public health, and begins the
30-minute monitor. Source, configuration, schema, services, and capabilities
remain unchanged throughout.

Before candidate traffic is admitted, the rotation-safe Laravel log collector
records its initial cursor and continuity anchors in the private rollback
directory. Each monitor sample verifies public health, candidate runtime,
fixed database-envelope identity, and log continuity.

## Laravel log-delta and independent finalization

The collector follows the active Laravel log inode across rename rotation,
captures all newly observed bytes into private evidence, and rejects a
disappeared segment, truncation, rewritten continuity anchor, symlink, special
file, size race, or configured delta limit. Raw log bytes remain only in the
private operations directory with directory mode `0700` and evidence-file
mode `0600`; raw logs are never committed to Git.

The parser decodes strict UTF-8 and parses complete Laravel entries, including
all continuation lines. It fails closed on:

- the `SessionGuard` / `hash_equals()` stale remember-cookie signature;
- `CRITICAL`, `ALERT`, or `EMERGENCY` entries;
- genuine exceptions, stack traces, fatal errors, `SQLSTATE`, missing
  classes/interfaces/traits, and missing views;
- a candidate-related error;
- invalid UTF-8; or
- any nonempty unparsed or orphan data.

The reviewed redacted 56-entry checkout and Shippo diagnostic fixture remains
nonfatal because classification is based on complete entries rather than the
literal `.ERROR` level. The Git evidence contains only message-free counts,
levels, signal names, identities, and hashes.

A clean 30-minute parse changes the durable state only to an awaiting-review
status. It does not mark the deployment final. An independent reviewer must
read the private evidence without modifying it and issue a pass receipt bound
to the deployment state, stage receipt, runner, runtime helper, parser, raw
manifest, redacted analysis, monitor samples, and database-envelope hashes.
The runner validates that receipt and its separately supplied SHA-256 before
the explicit `--finalize-monitor` action revalidates the candidate lock,
vendor, cache, autoload, source, configuration, front controller, runtime,
health, rollback set, and exact-zero database envelope. Only then can it mark
success. A failed parser review, an invalid binding, or any later invariant
failure leaves rollback available and fails closed.

Tests cover an empty delta, append-only data, rename rotation, truncation,
continuity loss, the 56-entry benign fixture, the exact stale-cookie failure,
every genuine-error category, all three fatal log levels, invalid UTF-8, and
orphan/unparsed data.

## Rollback and recovery

The exact rollback set is Laravel 12.69.0 lock
`22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`,
vendor
`7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`,
and cache
`468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.
The cache exchange is skipped for these frozen equal identities, but both live
and shadow copies are verified.

After any post-mutation failure, including a monitor or log-parser failure,
the runner first reasserts the exact reviewed static gate and records
containment. It identifies the actual vendor orientation through complete
manifests and candidate UID/GID/mode identity, restores the old vendor with
the atomic exchange, restores the exact old lock, verifies the unchanged old
cache, and proves Laravel 12.69.0 through CLI and two FPM probes. It rechecks
the database envelope before restoring the exact original front controller
and verifying normal public health. If rollback proof or health fails, the
gate remains installed.

Explicit recovery requires its separately reviewed recovery authorization and
the exact durable state. It binds the release receipt, all helper hashes,
front-controller transition history, database receipts, and live path
identities. It chooses containment, rollback, or exact restoration from the
observed dependency and front-controller orientation and is idempotent for
the equal-cache case.

No stage, cutover, finalization, or recovery command may be invoked while this
plan is under review.

## Completed local review evidence

The local preparation checks passed without production access, staging, or
deployment. Exact receipt filenames are relative to
`ops/evidence/laravel-remember-cookie-runner-v3-20261002/`.

| Receipt | SHA-256 | Result |
|---|---|---|
| `lock-delta.json` | `152d35298e9ae349c2c6b4799ba7e37e0ae23fd4f197d60c758eb8c83d483262` | One package changed: Laravel 12.69.0 to 12.69.1 |
| `build-a.json` | `977c0c54b4d223a400cccc4e946fe7d4d75118ecadf1ceda32b9a588e8fa9c42` | Pass; system-unzip clean build |
| `build-b.json` | `b79f0db1c6b81285d7f3714ac1ed5e50b93e46d4a6db1675c300e2b64aa068c1` | Pass; PHP-zip-only clean build |
| `two-build-comparison.json` | `8dad280c240ceb8b723ed12cbd933b6985981c7d217f898bd601b1cd9dc1eeb9` | Pass; complete inventories byte-identical |
| `php-8.2.30-platform-receipt.json` | `7a93d09bba65cf3c30dc0b91e4d263dc009caba8fcaab25ef10d37c1dd3e7478` | Exact PHP 8.2.30 platform proof passed |
| `database-envelope-validation-receipt.json` | `678f1008378ebe5ec17d07a144ff541ea8606b6d8e40324d4db804ade507ddaa` | Nine tests passed against local synthetic fixtures; no database writes |
| `gate-transition-rehearsal-receipt.json` | `7b0ec64767dfa828bacf5d7695d4d9b8c6a0014baeea7c412619b0762522a553` | 26 umask `077` scenarios and UID/GID 33 readability passed |
| `log-parser-validation-receipt.json` | `71bdb782e8ae5a3ca136c09173a09b1221f4ee810d7f80b231feef2947db6ea3` | 22 parser/collector/review-binding tests passed |
| `atomic-rehearsal-receipt.json` | `6ccaba8a17642cf77d6e82110f870e1fcfbb6a5b929f76d619e114890c45d6d7` | 25 cutover, rollback, interruption, and recovery scenarios passed |
| `test-results.json` | `a819dc2dbcc3bb5d1f792c5cc5e4613f5ad81f1ee4110715496065a4b18f0d0d` | Consolidated local validation passed |
| `runner-describe.json` | `69a835b2f9cf6b107d191c8d581a2b4204e4d86fc6ed0fe633f0fc694a337046` | Frozen v3 scope and identities |
| `vendor-mode-ownership-policy.json` | `1db4163d1b7cfcd135efeedec126536c712ee75db332dff150eda3f8ba4fda29` | Complete mode, ownership, and ten-path executable policy |

Both builds reproduced the 6,460-file, 925-directory, 26,481,661-byte vendor,
all accepted vendor/cache/autoload/source identities, 126 entries in each
optimized application autoload file, zero Windows proxies, Composer strict
validation, a zero-advisory locked `--no-dev` audit, package discovery, 178
routes, and actual UID/GID 33 read/no-write behavior. The focused regression
passed 2 tests and 10 assertions; the full application suite passed 110 tests
and 718 assertions. The root control suite passed 63 tests with the two
UID/GID 1000-only private-log checks skipped there; the UID/GID 1000 suite
then passed all 33 tests, including those checks.

The parser accepted the redacted 56-entry benign diagnostic fixture and
rejected the stale-cookie signature, severe levels, genuine errors, invalid
UTF-8, truncation, and orphan/unparsed data. No raw production log or customer
data is in Git. `transparency-prefreeze-verification.txt` confirms commit
`3db18d1fff3f599299eecd2aae21b9102fc45540` remains clean and non-stageable
with `DEPENDENCY_ENVELOPE_FROZEN = False`.

`SHA256SUMS` was generated after the documentation was frozen, includes every
other evidence file, and passed a complete checksum verification.

The accepted production immutability evidence remains commit
`ac959e0fbf6ad9c6ae71531dbeb09ae2b9309917`. Local v3 preparation must not
claim a newer production observation. Incoming-order receiver, job-label, and
retention capabilities remain disabled. The transparency repair may be
refrozen only after Laravel 12.69.1 is separately deployed and its monitor and
independent log review pass.
