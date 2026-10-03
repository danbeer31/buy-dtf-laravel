# Laravel 12.69.1 restricted staging evidence

Date: 2026-10-02 (America/Chicago); production timestamps in this bundle are
UTC on 2026-10-03.

Status: **failed closed; staging did not complete; no cutover-eligible release
receipt exists**.

The reviewed production preflight passed and the runner created one private
shadow under the fixed release root. The shadow passed Composer validation,
the locked no-development audit, Composer installation, the PHP 8.2.30
platform check, package discovery, and discovery of 178 routes. Its bootstrap
cache exactly matched the reviewed cache identity. The runner then rejected
the shadow because its vendor identity did not match the reviewed identity.
It exited with status 1 before writing `release-receipt.json`.

No retry was attempted. The partial shadow remains private, incomplete, and
ineligible for cutover pending independent review.

## Reviewed inputs

- Branch: `fix/laravel-12.69.1-remember-cookie-20261002`
- Candidate commit: `6a98c74686f1ceffded8012d332318ac075b444e`
- Runner SHA-256:
  `2cae23d816e358c91ce512da4b3db3ee4e7fdff268c51afddafb0995b2feef9e`
- Runtime helper SHA-256:
  `74ae751d18f0396e86c066e908a006b1a170e223b1ad56c59168c94491925362`
- Live lock SHA-256:
  `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`
- Candidate lock SHA-256:
  `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`
- Portable lock archive SHA-256:
  `e87f4bc7a7d1dc5f79df99b0cb2873b7a749e5c8000e5014aef4495c48e6ed3e`
- Expected vendor SHA-256:
  `b8e0e3afa65171a66ad3d1875404fe209d7598c9b3f690e494d40c4fde4408f8`
- Expected cache SHA-256:
  `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`

The exact staging token was accepted by the reviewed runner but is not
recorded in this evidence bundle.

## Attempt result

The single authorized `--stage` invocation ran from
`2026-10-03T00:02:50Z` through `2026-10-03T00:03:02Z` and stopped with:

```text
STOP: Staged vendor differs from the deterministic reviewed candidate.
```

The partial release path is:

```text
/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-releases/77055fc8acf8-20261003T000251Z
```

Path evidence shows the release root, release, and shadow are real
directories, the release and shadow are mode `0700`, there are no symbolic
links anywhere in the partial release, no rollback root was created, and
Laravel maintenance remains inactive.

The shadow contains 80 non-development packages and Laravel `v12.69.1`.
Laravel Pail is absent. The candidate cache is an exact match at two files,
21,768 bytes, and SHA-256
`468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.

## Vendor gate and root cause

| Identity | Files | Directories | Bytes | SHA-256 |
|---|---:|---:|---:|---|
| Reviewed expected | 6,465 | 925 | 26,482,354 | `b8e0e3afa65171a66ad3d1875404fe209d7598c9b3f690e494d40c4fde4408f8` |
| Production shadow | 6,460 | 925 | 26,453,095 | `a3aa7915d64281bbe5ef318a9e36723d68fda46c95fd7a717cb142d829d63655` |

The 29,259-byte difference is fully accounted for:

1. The reviewed runner runs `composer install --optimize-autoloader` before
   `copy_runtime_shadow()` copies `app/`. The production shadow therefore
   lacks exactly 126 application class entries in both generated Composer
   files. Removing those entries from the retained reviewed build produces
   the exact production-shadow size and SHA-256 for each file:

   - `composer/autoload_classmap.php`: 13,401 bytes absent; expected
     621,995 bytes / `5236a6ef...`; actual 608,594 bytes / `d3e0efdc...`.
   - `composer/autoload_static.php`: 15,165 bytes absent; expected 685,023
     bytes / `1e82d08d...`; actual 669,858 bytes / `2de7f5f3...`.

2. Composer `bin-compat=auto` generated five `.bat` proxy files in the
   reviewed WSL build. Native production Linux did not generate them. Their
   combined size is 693 bytes.

3. All 7,385 shared paths differ in mode. The reviewed build has directories
   at `0755` and files at `0644` or `0755`. The production shadow has
   directories at `0700` and files at `0600` or `0700`. The production
   Composer transcript records that neither `unzip` nor `7z` was installed,
   so PHP ZipArchive lost archive permissions; the restricted invocation also
   produced private modes.

All other shared file content and sizes are identical. The detailed proof is
in `vendor-mismatch-analysis.json`; both complete inventories and the scripts
used to derive the proof are included.

The existing reviewed runner cannot reproduce the reviewed vendor identity on
production. A valid replacement must put source in the shadow before optimized
autoload generation, freeze a vendor identity in a production-equivalent
environment, and receive a fresh independent review. Installing host tools,
altering the shadow out of band, accepting the observed identity, or retrying
the same runner would fall outside this authorization.

## Production remained unchanged

The post-attempt preflight passed. The complete preflight documents differ
only in `checked_at_utc`; the complete schema probes differ only in
`generated_at_utc`; and the configuration and service snapshots are
byte-identical.

| Production item | Unchanged identity/state |
|---|---|
| Laravel | `12.69.0` on PHP `8.2.30` |
| Live lock | `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9` |
| Live vendor | 6,460 files / 925 directories / 26,453,056 bytes / `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed` |
| Live cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Source | 326 files / `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` |
| Front controller | `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9` |
| Config tree | 12 files / `f3da71a4f125e1b73742d5d52c02ca83fd95ab6bc4e2f678ab0c9ad83f660343` |
| Schema | `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da` |
| Migration ledger | 21 rows / `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53` |
| `savedimages.item_meta` | Present, nullable text, zero non-null rows |
| Queues | `sync`; jobs 0; failed jobs 0 |
| Services | Same state, PIDs, start identities, and restart counts |
| Public health | `/`, `/up`, `/login` 200; `/admin`, `/checkout` 302 |
| Maintenance | Inactive |

The incoming-order receiver, job-label, retention, and allowed-host flags
remain disabled (`false`, `false`, `false`, and zero hosts). No scoped worker
process was present. The before/after preflight also preserves the business
activity counts and hashed latest-row fingerprints.

No static gate was installed; no maintenance mode, cutover, recovery, live
lock replacement, vendor/cache exchange, service restart, migration, source
deployment, ShopNLTees action, retention action, customer deletion,
customer-artwork change, or production-schema change occurred.

The transparency worktree remains clean at
`3db18d1fff3f599299eecd2aae21b9102fc45540`, and its runner still contains
`DEPENDENCY_ENVELOPE_FROZEN = False`. It was neither staged nor deployed.

## Evidence index

- `FAILED_STAGE_RECEIPT.json`: controlling failed-closed receipt.
- `POST_FAILURE_IMMUTABILITY.json`: machine-readable before/after proof.
- `preflight-before.json` and `preflight-after-failed-stage.json`: reviewed
  production preflight and postflight.
- `schema-ledger-before.json` and `schema-ledger-after-failed-stage.json`:
  complete schema, ledger, capability, and queue probes.
- `configuration-*.txt` and `services-*.txt`: exact before/after snapshots.
- `stage-command-*`: timestamps, exit status, and fail-closed output.
- `failed-stage-logs/`: validation, audit, install, PHP 8.2.30 platform,
  package-discovery, and route-discovery transcripts.
- `failed-stage-shadow-identities.json`: expected and observed vendor/cache
  identities.
- `partial-shadow-package-identity.json`: installed candidate versions.
- `reviewed-build-vendor-inventory.json` and
  `failed-stage-vendor-inventory.json`: complete path/mode/size/hash records.
- `vendor-mismatch-analysis.json`: exact content, mode, and byte accounting.
- `runner-stage-order.txt`: hash-bound runner excerpt proving Composer runs
  before runtime source is copied into the shadow.
- `path-safety-*`, `remote-artifact-receipt*`, and environment files: private
  path, permissions, transfer hashes, and build-environment evidence.
- `partial-release-receipt*`: remote permissions and hashes for every staged
  command transcript and key shadow input/output.
- `transparency-prefreeze-verification.txt`: separate candidate remained
  clean and pre-freeze.
- `SHA256SUMS`: hashes of every other evidence file.

This bundle contains no staging token, credentials, customer addresses,
emails, phone numbers, payment data, or private keys. Keep it private because
it contains production paths, route names, service metadata, schema counts,
and hashed business-activity fingerprints.
