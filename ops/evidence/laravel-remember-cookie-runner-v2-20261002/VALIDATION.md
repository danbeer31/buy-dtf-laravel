# Validation record

All checks apply to the local review-only Laravel 12.69.1 replacement. No
stage or deployment command was run.

| Check | Result | Evidence |
|---|---|---|
| One-package lock delta | pass; only Laravel `12.69.0` to `12.69.1` | `lock-delta-receipt.json` |
| Clean Build A | pass; system unzip | `build-a.json`, `build-a-logs/` |
| Clean Build B | pass; PHP ZipArchive, no unzip | `build-b.json`, `build-b-logs/` |
| Complete inventory comparison | pass; byte-identical, 7,386 entries | `two-build-comparison.json`, `vendor-inventory-*.jsonl` |
| Composer strict validation | pass in both builds | build receipts and logs |
| Locked `--no-dev` audit | pass; zero advisories in both builds | build receipts and logs |
| Optimized application autoload | pass; 126 matching entries in each file | build receipts |
| Unix Composer proxies | pass; zero `vendor/bin/*.bat` | build receipts and inventories |
| Vendor structure | pass; 6,460 files, 925 directories, 26,481,661 bytes | comparison receipt |
| Ownership and modes | pass; `1000:1000`, dirs `0775`, 6,450 files `0664`, ten executables `0775` | comparison receipt and inventories |
| Actual UID/GID 33 access | pass; Laravel loaded/readable; create and append denied | both build receipts and logs |
| Exact PHP 8.2.30 NTS platform | pass | `php-8.2.30-platform-receipt.json` |
| Package discovery | pass in both builds | build receipts and logs |
| Route discovery | pass; exactly 178 in both builds | build receipts and logs |
| Remember-cookie regression | pass; 2 tests, 10 assertions | `remember-cookie-regression.txt` |
| Full PHP suite | pass; 110 tests, 718 assertions | `phpunit-full.txt` |
| Runner unit suite | pass; 10 tests | `runner-unit-tests.txt` |
| Atomic/failure rehearsals | pass; 25 of 25 scenarios | `atomic-rehearsal-receipt.json` |
| Python/PHP syntax | pass | `syntax-validation.txt` |

The build source was copied from two previously captured local ext4 trees.
Both independently revalidated to the approved 326-file CAS before and after
each build, and each final shadow revalidated after Composer and Laravel
discovery. Neither preparation nor validation connected to production.

The exact Laravel 12.69.0 lock, vendor, and cache frozen in the runner remain
the rollback set. Their last production immutability proof, together with
unchanged source, schema, 21-row ledger, front controller, configuration,
services, queues, capability flags, and public health, is the independently
accepted evidence commit `ac959e0fbf6ad9c6ae71531dbeb09ae2b9309917`.

Fresh restricted staging authorization is required. A successful v2 stage
receipt must stop for independent review, and cutover requires another
separate authorization.
