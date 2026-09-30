# Dependency-only security candidate

Date: 2026-09-30 (America/Chicago)

Status: **ready for independent review; NO-GO for staging or deployment**.

This candidate starts from the exact current production Composer files: lock SHA-256 `eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831` and live Composer JSON SHA-256 `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872`. The live JSON bytes are retained in Git history at `10a2dfca5d734ea329ce251a295a355a46dff6f6`; production was not accessed during preparation. The candidate branch starts at `f11a9413d9040b4562064ee02fda002b317e0de9` and changes only the lock.

## Review identities

- Branch: `security/dependency-advisories-20260930`.
- Dependency-only commit: `c07c29332adcc9fa41f2c3b4f14bf6f35cf28c3c`.
- Commit diff: only `composer.lock`, 22 insertions and 22 deletions.
- Candidate lock SHA-256: `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`.
- Candidate receipt SHA-256: `3aff7d1c9a061c6818283664d019232d45ed62d6d33c526431a6a9450d48b0cb`.
- Composer content hash remains `a72b3c22fc3bec98130fd5133da242a1`.
- Package count remains 116; there are four updates, zero additions, zero removals, and zero unrelated changes.

## Exact changes

| Package | Before | Candidate |
|---|---:|---:|
| `laravel/framework` | `v12.61.1` | `v12.69.0` |
| `league/commonmark` | `2.10.0` | `2.10.2` |
| `league/flysystem` | `3.30.2` | `3.35.3` |
| `league/flysystem-local` | `3.30.2` | `3.35.3` |

The lock was resolved with exact temporary constraints plus `--with-dependencies --minimal-changes`. A clean replay using the exact production Composer JSON and lock bytes produced the same candidate lock bytes. The repository Composer JSON remains unchanged at SHA-256 `12359b3c25459a78578c67ac542bc72b7148c16d0a1ff51c351b150aed75676c`; a deployment must preserve the byte-exact live JSON rather than install that repository file. The first isolated-worktree invocation completed the four-package resolution and wrote the lock, then its normal post-update Artisan hook failed because that new worktree did not yet have `vendor/autoload.php`; the raw transcript preserves this. The clean exact-baseline replay used `--no-scripts`, exited zero, and matched the candidate SHA-256.

## Validation

- PHPUnit: 108 tests and 714 assertions passed on PHP 8.2.0.
- Composer strict validation passed.
- Full and production Composer audits both report zero advisories.
- Production platform requirements passed.
- npm production audit reports zero vulnerabilities.
- Vite production build passed with 112 modules and the existing Sass warnings.
- `npm ci` continues to report 14 development-only Node advisories. `package-lock.json` is unchanged, and those advisories remain a separate future change.

## Scope boundary

The candidate artifact is the exact `composer.lock` at dependency-only commit `c07c293…`, supported by `candidate-receipt.json` and the raw evidence in this directory. It is not a staged vendor tree and is not cutover authorization. A future deployment artifact must independently pin this candidate hash, use the already reviewed atomic vendor/cache/front-controller design, rehearse on a disposable production-filesystem path, stage into a new release path, and stop for receipt review before any cutover.

No production access, dependency staging, cutover, migration, maintenance, live-file change, restart, capability enablement, ShopNLTees change, retention action, or customer deletion occurred.
