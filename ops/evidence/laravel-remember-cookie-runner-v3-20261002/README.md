# Laravel 12.69.1 v3 runner review evidence

Status: **local preparation complete; independent review required; NO-GO for
production access, restricted staging, cutover, deployment, migration,
service restart, configuration change, or capability change**.

The branch under review is
`fix/laravel-12.69.1-remember-cookie-v3-20261002`. Its controlling instruction
is `HANDOFF.md`, SHA-256
`305127ee8dc6c578ea8a8a1901a455b2e18378c481c8c726b3b120917e62a984`.
The candidate commit is reported after the final evidence commit is created;
it cannot be embedded in files that are themselves part of that commit. The
operating plan is
`ops/LARAVEL_REMEMBER_COOKIE_DEPENDENCY_PLAN_V3_2026-10-02.md`.

No production connection, stage, deploy, cutover, migration, service restart,
configuration change, or capability change occurred while producing this
package. The accepted evidence commit
`ac959e0fbf6ad9c6ae71531dbeb09ae2b9309917` remains the latest production
immutability proof. Both retained partial releases remain untouched.

## Frozen dependency identities

| Identity | SHA-256 |
|---|---|
| Candidate lock | `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d` |
| Candidate vendor | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Vendor ownership/mode | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Complete vendor inventory | `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5` |
| Executable allowlist | `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154` |
| Live/candidate cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Application autoload entries | `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91` |
| Runtime source CAS | `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` |

The exact Laravel 12.69.0 rollback set remains lock
`22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`,
vendor
`7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`,
and cache
`468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.

## Frozen controls

| Artifact | SHA-256 |
|---|---|
| `ops/deployment/laravel_remember_cookie_dependency_deploy.py` | `97cb4e8d702b7ceb1b9efde26dba93e6e0f4a833bb55650843fed1c0746f0307` |
| `ops/deployment/laravel_remember_cookie_runtime_probe.php` | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| `ops/deployment/laravel_dependency_database_envelope.py` | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| `ops/deployment/laravel_dependency_gate.py` | `1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80` |
| `ops/deployment/rehearse_laravel_dependency_gate.py` | `2d52ec99a3d57c8c8534db7283f43bd54debcfca8349370058662631523e0b3e` |
| `ops/deployment/laravel_log_delta.py` | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |
| `ops/deployment/build_laravel_remember_cookie_candidate.py` | `e6974c9963864cd11dde2f09d6fffd24485e879564dfd81d5977f2b1b1b66eb4` |
| `ops/deployment/compare_laravel_candidate_builds.py` | `5706f9ba19ca2a68820a552efb6b59b679c4bc5775ab093712d11b5fbbf21c16` |
| `ops/deployment/verify_php_8230_platform.py` | `baaa77a1c5a5a41a3cfe37c2ac74d362c8c431d8c5c6d5371947514a1619fef4` |

The reviewed static gate is SHA-256
`94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03`.
The database envelope fixes schema SHA-256
`5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`,
21 migration rows, ledger SHA-256
`f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`,
and one target-migration entry. Because this package deploys no source,
`savedimages.item_meta` must remain nullable `TEXT` with exactly zero non-null
rows at stage, cutover, every monitor sample, independent-review finalization,
rollback, and recovery. Legitimate growth belongs only to a later separately
reviewed transparency source cutover.

## Reproduced results

Two clean builds used distinct reviewed extraction paths: Build A used system
`unzip`, and Build B used PHP Zip without `unzip`. Each reproduced the exact
6,460-file, 925-directory, 26,481,661-byte vendor, the complete mode-sensitive
inventory, 126 application entries in each optimized Composer file, ten
approved executable paths, zero `.bat` proxies, zero symlinks or special
files, Laravel 12.69.1, the accepted cache/source identities, package
discovery, and 178 routes. Composer strict validation and the locked
`--no-dev` audit passed with zero advisories. An actual UID/GID 33 process
loaded Laravel and read the autoloader while both create and append attempts
in `vendor/` failed.

The exact PHP 8.2.30 platform proof passed. The remember-cookie regression
passed 2 tests and 10 assertions, including stale-cookie guest fallback and
valid-cookie authentication. The full application suite passed 110 tests and
718 assertions.

The root control suite passed 63 tests with two private-log tests skipped
because they require UID/GID 1000. The UID/GID 1000 suite passed all 33 tests,
including those two checks. The database validator passed nine tests covering
independent schema, ledger, target-migration, column-definition, table,
row-count, queue, connection, and capability drift. The log parser/collector
passed 22 tests, accepted the redacted 56-entry benign fixture, and failed
closed on the stale-cookie signature, severe levels, genuine exceptions and
traces, fatal errors, SQLSTATE, missing classes/views, invalid UTF-8,
truncation, continuity loss, and orphan/unparsed data.

The static-gate rehearsal passed 26 scenarios under umask `077`, including
pre-replacement failure, every transition interruption, separate origin and
public verification failures, stale-state/live-gate recovery, later-phase
containment, UID/GID 33 readability, and exact original restoration. The
dependency atomic rehearsal passed 25 cutover, interruption, rollback,
recovery, equal-cache, and metadata-drift scenarios.

## Evidence index

All filenames below are relative to this directory.

| Receipt or evidence | SHA-256 | Purpose |
|---|---|---|
| `lock-delta.json` | `152d35298e9ae349c2c6b4799ba7e37e0ae23fd4f197d60c758eb8c83d483262` | Exact one-package lock delta |
| `build-a.json` | `977c0c54b4d223a400cccc4e946fe7d4d75118ecadf1ceda32b9a588e8fa9c42` | Clean system-unzip build receipt |
| `build-b.json` | `b79f0db1c6b81285d7f3714ac1ed5e50b93e46d4a6db1675c300e2b64aa068c1` | Clean PHP-zip-only build receipt |
| `two-build-comparison.json` | `8dad280c240ceb8b723ed12cbd933b6985981c7d217f898bd601b1cd9dc1eeb9` | Byte-identical complete inventory proof |
| `vendor-mode-ownership-policy.json` | `1db4163d1b7cfcd135efeedec126536c712ee75db332dff150eda3f8ba4fda29` | UID/GID, mode, structure, and executable allowlist |
| `php-8.2.30-platform-receipt.json` | `7a93d09bba65cf3c30dc0b91e4d263dc009caba8fcaab25ef10d37c1dd3e7478` | Exact platform proof |
| `database-envelope-validation-receipt.json` | `678f1008378ebe5ec17d07a144ff541ea8606b6d8e40324d4db804ade507ddaa` | Synthetic local envelope and drift tests |
| `gate-transition-rehearsal-receipt.json` | `7b0ec64767dfa828bacf5d7695d4d9b8c6a0014baeea7c412619b0762522a553` | Durable static-gate rehearsal |
| `log-parser-validation-receipt.json` | `71bdb782e8ae5a3ca136c09173a09b1221f4ee810d7f80b231feef2947db6ea3` | Redacted parser, collector, and binding validation |
| `atomic-rehearsal-receipt.json` | `6ccaba8a17642cf77d6e82110f870e1fcfbb6a5b929f76d619e114890c45d6d7` | Dependency cutover/rollback/recovery rehearsal |
| `test-results.json` | `a819dc2dbcc3bb5d1f792c5cc5e4613f5ad81f1ee4110715496065a4b18f0d0d` | Consolidated test result |
| `runner-describe.json` | `69a835b2f9cf6b107d191c8d581a2b4204e4d86fc6ed0fe633f0fc694a337046` | Frozen runner scope and identity |
| `runner-unit-tests-root.txt` | `bcdfaf3b8325612a5a7de9c2a05bd9b9ca45e4db542cac4d07d30d0812512438` | Root control suite |
| `runner-unit-tests-uid1000.txt` | `182ab97e2f3187f03b3badc8c42f760fb5897ff0dd3e894b493d2d9749f2b70f` | UID/GID 1000 private-evidence checks |
| `remember-cookie-regression.txt` | `c911852ef379deaa9a7f4b00f447079264c34637243ebebdb73128d5e3ea6945` | Focused authentication regression |
| `phpunit-full.txt` | `bd37d4ad8661b0dd7b4fb9b9bb0be24517cd951168400c0f48f2d0d970df45b3` | Full application suite |
| `syntax-validation.txt` | `ff75b7568db42667681d10662b641c33019cf53609aec5b789e5434cba2a06be` | Python/PHP syntax validation |
| `transparency-prefreeze-verification.txt` | `86d076162ad3b4cfe49e766e0fc31a4fb6f377550809bd84b8a4d51f1750be34` | Transparency commit and false freeze flag proof |

The supporting evidence includes `vendor-inventory-a.jsonl`,
`vendor-inventory-b.jsonl`, all files under `build-a-logs/` and
`build-b-logs/`, `php-8.2.30-version.txt`, `php-8.2.30-ini.txt`,
`php-8.2.30-modules.txt`, `php-8.2.30-platform.stdout`, and
`php-8.2.30-platform.stderr`. `SHA256SUMS` was generated after these documents
were frozen and is the final verified inventory of every other evidence file.

## Future stage, monitor, and finalization

A separately authorized restricted stage can create only a new private v3
shadow. It must emit `database-envelope-receipt.json` and
`release-receipt.json`, then stop for independent review. Cutover requires a
separate authorization bound to that exact release receipt.

During a separately authorized cutover, the private rollback directory binds
`deployment-state.json`,
`database-envelope-before-mutation-receipt.json`, and the durable gate
transition/restoration receipts. The 30-minute monitor writes
`monitor-samples-private.json`, `database-envelope-monitor-final.json`, and a
private `laravel-log-private/` set containing `raw-manifest.json`,
`redacted-analysis.json`, and `capture-state.json`. It then writes
`deployment-state-monitor-complete.json` and
`independent-log-review-request.json`, leaves the mutable state at
`awaiting_independent_log_review`, and expects
`independent-log-review-receipt.json` at the fixed path.

The runner cannot report success from the monitor. The separate
`--finalize-monitor` action first validates the independent receipt and its
supplied SHA-256, replays and hashes all private evidence, and rechecks the
live candidate, exact rollback set, public health, and exact-zero database
envelope. A failed binding cannot mutate state. A later live invariant failure
reasserts containment and runs rollback. Raw Laravel logs remain private at
mode `0700`/`0600`; no raw log message, customer address, or carrier payload
belongs in Git.

Runner `a7657bbfea760be186301503c567042f76739c2954fffbfc76f31c9f4eefede5`
remains retired. Transparency commit
`3db18d1fff3f599299eecd2aae21b9102fc45540` remains non-stageable with
`DEPENDENCY_ENVELOPE_FROZEN = False`. Incoming-order receiver, job-label, and
retention capabilities remain disabled.
