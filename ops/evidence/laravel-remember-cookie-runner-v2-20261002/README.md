# Laravel 12.69.1 replacement runner review evidence

Status: **review only; no production access, stage, cutover, deployment,
service restart, migration, configuration change, or capability change was
performed**.

This directory contains the final local evidence for the replacement runner
requested after the failed v1 restricted stage. The controlling instruction is
`HANDOFF.md` at SHA-256
`f198e8658848f64ac003528e45d925a606ef6788769e81b5d7269ec8be345dcb`.

The candidate dependency delta is unchanged from the prior review:
`laravel/framework` `v12.69.0` to `v12.69.1`, with candidate lock
`77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`.
`lock-delta-receipt.json` proves it is the only package change.

## Frozen candidate

| Identity | SHA-256 |
|---|---|
| Vendor content and mode | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Complete UID/GID/mode identity | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Complete JSONL inventory | `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5` |
| Executable allowlist | `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154` |
| Bootstrap cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Application autoload entry set | `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91` |
| Runtime source CAS | `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` |

The full inventories contain 7,386 records each: the vendor root, 925
directories, and 6,460 files. Every record includes path, kind, UID, GID, and
mode; every file also includes size and content SHA-256. The two inventory
files are byte-identical.

## Reviewed executable artifacts

| Artifact | SHA-256 |
|---|---|
| Deployment runner | `a7657bbfea760be186301503c567042f76739c2954fffbfc76f31c9f4eefede5` |
| Clean-build harness | `8331e5bb8bf83341fc2b46cbc78688177a6e176599bed3cce4c1440045a9ab8b` |
| Two-build comparator | `1e99628adcd823db2136d0e98de4d0a0718515a959ab543bc646b9851e08a37f` |
| PHP 8.2.30 verifier | `15477459c189f8e07145122cd2b55f3076dfeb6fe032142c336149cfd1c572a2` |
| Lock-delta verifier | `515566bd2bf5835bbacc7b4eb3f8024a370caaee9b0a52d4984bacf9c5536bba` |
| Runtime helper | `74ae751d18f0396e86c066e908a006b1a170e223b1ad56c59168c94491925362` |

## Evidence index

- `build-a.json`, `build-b.json`: clean-build receipts bound to the final
  runner and builder, including Composer checks, 178 routes, 126 autoload
  entries per optimized file, and actual UID/GID 33 read/no-write results.
- `build-a-logs/`, `build-b-logs/`: command transcripts for both builds.
- `vendor-inventory-a.jsonl`, `vendor-inventory-b.jsonl`: complete
  path/content/ownership/mode inventories.
- `two-build-comparison.json`: fail-closed comparison of both environments and
  both complete inventories.
- `php-8.2.30-platform-*`: exact PHP 8.2.30 NTS platform proof against the
  fully identified installed candidate.
- `lock-delta-receipt.json`: exact one-package lock proof.
- `remember-cookie-regression.txt`: 2 tests and 10 assertions for stale and
  valid remember cookies.
- `phpunit-full.txt`: full 110-test, 718-assertion application suite.
- `runner-unit-tests.txt`: final 10-test runner suite.
- `atomic-rehearsal-receipt.json`: all 25 cutover, rollback, recovery,
  interruption, identical-cache, and metadata-drift scenarios.
- `runner-describe.json`: frozen runner constants and operations.
- `syntax-validation.txt`: Python compilation and PHP syntax results.
- `vendor-mode-ownership-policy.json`: exact structural and executable policy.
- `transparency-prefreeze-verification.txt`: clean transparency worktree at
  `3db18d1...` with the dependency envelope still explicitly false.
- `VALIDATION.md`: human-readable result matrix and production-boundary notes.
- `SHA256SUMS`: hashes for the complete review package.

The accepted evidence commit
`ac959e0fbf6ad9c6ae71531dbeb09ae2b9309917` remains the source of truth for
production immutability after the failed stage. No new production observation
is claimed here. The retained partial release and all retired artifacts were
left untouched.
