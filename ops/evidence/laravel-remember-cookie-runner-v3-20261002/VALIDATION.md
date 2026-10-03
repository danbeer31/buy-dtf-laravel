# V3 validation record

Status: **local validation passed; independent review required; NO-GO for
production access, restricted staging, cutover, or deployment**.

Every `pass` below is backed by the named local receipt. No production system
was contacted. `SHA256SUMS` was generated after these documentation files
were frozen and passed a complete checksum verification.

| Check | Result | Evidence |
|---|---|---|
| One-package lock delta | pass | `lock-delta.json`: only `laravel/framework` 12.69.0 to 12.69.1 |
| Clean Build A | pass | `build-a.json` and `build-a-logs/` |
| Clean Build B | pass | `build-b.json` and `build-b-logs/` |
| Complete inventory comparison | pass | `two-build-comparison.json`; both complete JSONL inventories byte-identical |
| Accepted vendor identity reproduced | pass | `build-a.json`, `build-b.json`: `7df0a101…`; 6,460 files, 925 directories, 26,481,661 bytes |
| Mode/ownership identity reproduced | pass | `vendor-mode-ownership-policy.json`: `db8aba0a…`; UID/GID 1000, 0775 directories, 0664 ordinary files |
| Executable policy reproduced | pass | `vendor-mode-ownership-policy.json`: exact ten paths, `551df886…`; zero Windows proxies, symlinks, special files, or hard links |
| Cache, autoload, and source identities reproduced | pass | both build receipts and `two-build-comparison.json` |
| Optimized application entries | pass | both build receipts: 126 entries in each Composer optimized file, set `342f417d…` |
| Composer strict validation | pass | both build receipts and `composer-validate.*` logs |
| Locked `--no-dev` audit | pass | both build receipts and `composer-audit.*` logs: zero advisories |
| PHP 8.2.30 platform check | pass | `php-8.2.30-platform-receipt.json` and associated version/INI/module/stdout/stderr files |
| Package discovery | pass | both build receipts and `package-discovery.*` logs |
| Route discovery | pass | both build receipts and `route-discovery.*` logs: 178 routes each |
| Actual UID/GID 33 vendor read/no-write proof | pass | both build receipts and `uid33-vendor-read-only.*` logs |
| Stale remember-cookie guest fallback | pass | `remember-cookie-regression.txt` |
| Valid remember-cookie authentication | pass | `remember-cookie-regression.txt` |
| Focused authentication suite | pass | 2 tests, 10 assertions |
| Full application suite | pass | `phpunit-full.txt`: 110 tests, 718 assertions |
| Runtime-helper database facts and syntax | pass | `database-envelope-validation-receipt.json` and `syntax-validation.txt` |
| Exact schema and 21-row ledger envelope | pass | `database-envelope-validation-receipt.json` |
| Schema/section drift rejection | pass | database validator suite |
| Ledger/hash/target-migration drift rejection | pass | database validator suite |
| `savedimages.item_meta` definition drift rejection | pass | database validator suite |
| `savedimages.item_meta` non-null row rejection | pass | database validator suite; exact zero remains required through dependency finalization/rollback |
| Incoming table definition/count drift rejection | pass | database validator suite |
| Queue, connection, and disabled-capability drift rejection | pass | database validator suite |
| Static-gate transition unit tests | pass | `runner-unit-tests-root.txt` |
| Umask `077` gate transition rehearsals | pass | `gate-transition-rehearsal-receipt.json`: 26 scenarios |
| Separate origin/public gate verification | pass | gate transition receipt |
| UID/GID 33 gate readability and 0600 negative control | pass | gate transition receipt and `test-results.json` |
| Exact original restoration and stale-state/live-gate recovery | pass | gate transition receipt |
| Benign reviewed 56-entry log fixture | pass | `log-parser-validation-receipt.json`: 56 complete `ERROR` entries, zero fatal findings |
| Stale-cookie signature rejection | pass | log parser receipt |
| Exceptions, traces, fatal, SQLSTATE, missing class/view rejection | pass | log parser receipt |
| CRITICAL, ALERT, and EMERGENCY rejection | pass | log parser receipt |
| Invalid UTF-8 and orphan/unparsed rejection | pass | log parser receipt |
| Rotation, truncation, copytruncate, and continuity checks | pass | log parser receipt |
| Private raw evidence and redacted summaries | pass | parser/collector tests; no raw production log in Git |
| Independent log-review binding validation | pass | log parser receipt and UID/GID 1000 control suite |
| Monitor cannot mark success before independent review | pass | v3 control tests in both runner test receipts |
| Finalization rejects an absent or invalid receipt without mutation | pass | v3 control tests |
| Valid receipt still requires live candidate and exact-zero envelope proof | pass | v3 control tests |
| Root runner/control suite | pass | `runner-unit-tests-root.txt`: 63 tests, 2 UID/GID 1000-specific skips |
| UID/GID 1000 private-evidence suite | pass | `runner-unit-tests-uid1000.txt`: 33 tests, no skips |
| Atomic cutover/rollback/recovery rehearsals | pass | `atomic-rehearsal-receipt.json`: 25 scenarios |
| Equal-cache and metadata-drift rehearsals | pass | atomic rehearsal receipt |
| Python and PHP syntax | pass | `syntax-validation.txt` |
| Runner description and receipt-schema checks | pass | `runner-describe.json` and runner/control test receipts |
| Transparency pre-freeze preserved | pass | `transparency-prefreeze-verification.txt`: commit `3db18d1…` clean; two false-freeze matches |
| Complete evidence manifest | pass | `SHA256SUMS`, generated after documentation freeze and verified against every listed file |

## Bound identities

| Control | SHA-256 |
|---|---|
| Runner | `97cb4e8d702b7ceb1b9efde26dba93e6e0f4a833bb55650843fed1c0746f0307` |
| Runtime helper | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| Database validator | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| Gate helper | `1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80` |
| Gate rehearsal | `2d52ec99a3d57c8c8534db7283f43bd54debcfca8349370058662631523e0b3e` |
| Log parser/collector | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |

## Receipt hashes

| Filename | SHA-256 |
|---|---|
| `lock-delta.json` | `152d35298e9ae349c2c6b4799ba7e37e0ae23fd4f197d60c758eb8c83d483262` |
| `build-a.json` | `977c0c54b4d223a400cccc4e946fe7d4d75118ecadf1ceda32b9a588e8fa9c42` |
| `build-b.json` | `b79f0db1c6b81285d7f3714ac1ed5e50b93e46d4a6db1675c300e2b64aa068c1` |
| `two-build-comparison.json` | `8dad280c240ceb8b723ed12cbd933b6985981c7d217f898bd601b1cd9dc1eeb9` |
| `php-8.2.30-platform-receipt.json` | `7a93d09bba65cf3c30dc0b91e4d263dc009caba8fcaab25ef10d37c1dd3e7478` |
| `database-envelope-validation-receipt.json` | `678f1008378ebe5ec17d07a144ff541ea8606b6d8e40324d4db804ade507ddaa` |
| `gate-transition-rehearsal-receipt.json` | `7b0ec64767dfa828bacf5d7695d4d9b8c6a0014baeea7c412619b0762522a553` |
| `log-parser-validation-receipt.json` | `71bdb782e8ae5a3ca136c09173a09b1221f4ee810d7f80b231feef2947db6ea3` |
| `atomic-rehearsal-receipt.json` | `6ccaba8a17642cf77d6e82110f870e1fcfbb6a5b929f76d619e114890c45d6d7` |
| `test-results.json` | `a819dc2dbcc3bb5d1f792c5cc5e4613f5ad81f1ee4110715496065a4b18f0d0d` |
| `runner-describe.json` | `69a835b2f9cf6b107d191c8d581a2b4204e4d86fc6ed0fe633f0fc694a337046` |

Restricted staging requires a fresh independent review and separate
authorization. A successful stage receipt must stop for another independent
review. Cutover requires separate authorization. A future cutover remains at
`awaiting_independent_log_review` after the 30-minute monitor; only the
separate `--finalize-monitor` action can mark success after validating the
private receipt binding and rechecking all live identities, public health, and
the exact-zero database envelope.
