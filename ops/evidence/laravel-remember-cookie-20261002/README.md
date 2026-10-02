# Laravel 12.69.1 remember-cookie dependency candidate

Date: 2026-10-02 (America/Chicago)

Status: **ready for independent review; NO-GO for staging or deployment**.

This is the dependency-only correction for the stale remember-cookie HTTP 500.
The candidate changes `laravel/framework` from `v12.69.0` to `v12.69.1` and
adds regression tests and a reviewed atomic deployment runner. It does not
patch `vendor/` and it does not include transparency source work.

The controlling handoff is `buy-dtf-codie-handoff-2026-10-02.md`, SHA-256
`ba9fd4dcf5fa5854b2e23418e0cd6ed8799874494a0341c726302b92a5acc127`.

## Exact baseline and candidate

- Exact-live Composer parent commit:
  `631db9fbd8d126ab6e98a17b49d391118c9e2152`.
- Parent `composer.json`: `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872`.
- Parent `composer.lock`: `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`.
- Candidate lock: `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`.
- Lock change: one update, zero additions, zero removals, zero unrelated moves.
- Updated package: `laravel/framework` `v12.69.0` / `335429f2…` to
  `v12.69.1` / `0c07b0b1…`.
- Portable deterministic lock artifact:
  `buy-dtf-laravel-12.69.1-lock-77055fc8.tar.gz`, SHA-256
  `e87f4bc7a7d1dc5f79df99b0cb2873b7a749e5c8000e5014aef4495c48e6ed3e`.

Two fresh resolutions from the exact live Composer JSON and lock produced the
same candidate lock bytes. Composer content hash and all other 115 package
records remained unchanged.

## Regression proof

The feature tests construct the actual web guard recaller value and pass its
encrypted cookie through Laravel's web middleware.

- Exact `12.69.0`: the stale cookie reproduces HTTP 500 with the
  `SessionGuard.php:235` `hash_equals(null, ...)` TypeError; the valid cookie
  authenticates. Transcript SHA-256: `d094ec81bdd77ef0b2f4645aa70f5edd71422cff96de14c455a2428d42404959`.
- Candidate `12.69.1`: the stale cookie returns HTTP 200 as a guest with
  `viaRemember()` false, and the valid cookie authenticates with
  `viaRemember()` true. Transcript SHA-256:
  `e8c79ee52e118eaad16ba4085849457d8d50309000d770949dc25d0b1f5b144d`.

The full suite passes: 110 tests and 718 assertions.

## Deterministic runtime identities

Two independent empty native-Linux installs used Composer `2.9.3`, the exact
live `composer.json`, and the candidate lock. Their complete receipts are
byte-identical at SHA-256
`c54374d21a8b5c981b5c3b396fc743ea5a8cd0c4f31e43ff208f383f2ab3bdd2`.

- Vendor: 6,465 files, 925 directories, 26,482,354 bytes, SHA-256
  `b8e0e3afa65171a66ad3d1875404fe209d7598c9b3f690e494d40c4fde4408f8`.
- Bootstrap cache: two files, 21,768 bytes, SHA-256
  `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.
- Laravel Pail and all other development packages are absent.

The lock has no PHP `8.2.30` prohibition. Exact platform validation on the
production PHP `8.2.30` runtime remains mandatory in a future authorized
staging run; the local platform check ran on PHP `8.3.6`.

## Runner and future acceptance

The runner is SHA-256
`2cae23d816e358c91ce512da4b3db3ee4e7fdff268c51afddafb0995b2feef9e`.
Its unit suite passes 6/6 and its disposable atomic-exchange rehearsal passes
23/23, including failure and interruption recovery. It pins the current live
source identity and copies no source.

A future separately authorized cutover retains the old lock/vendor/cache,
atomically exchanges vendor and bootstrap cache under a boot-independent gate,
changes only `composer.lock`, verifies runtime identity twice, then performs a
30-minute health/runtime monitor. During and immediately after that monitor,
an independent operator must perform a read-only Laravel log-delta review for
the exact stale-cookie signature and genuine new failures. The runner itself
does not parse Laravel logs.

The current source snapshot, vendor, cache, runtime, Composer files, and all
disabled capability flags were observed read-only. No remote file was created
or changed. No staging, deployment, migration, maintenance, service restart,
ShopNLTees action, retention action, customer deletion, or customer-artwork
change occurred.
