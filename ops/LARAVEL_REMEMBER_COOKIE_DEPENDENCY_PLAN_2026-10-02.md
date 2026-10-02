# Laravel 12.69.1 remember-cookie dependency repair

Date: 2026-10-02 (America/Chicago)

Status: **ready for independent review; NO-GO for staging or deployment**.

This package addresses the active stale remember-cookie HTTP 500 by changing
one production dependency: `laravel/framework` `v12.69.0` to `v12.69.1`.
It does not patch `vendor/`, change application behavior directly, or combine
this dependency cutover with the transparency source package.

The controlling handoff is `buy-dtf-codie-handoff-2026-10-02.md`, SHA-256
`ba9fd4dcf5fa5854b2e23418e0cd6ed8799874494a0341c726302b92a5acc127`.

## Exact production parent

Branch `fix/laravel-12.69.1-remember-cookie-20261002` starts from the completed
dependency cutover line at `967691e7b003ba54cc42bfc5d18afc1d0a6e4d12`.
That Git tree carried the right live lock but retained the repository's older
Composer script bytes. Baseline commit
`631db9fbd8d126ab6e98a17b49d391118c9e2152` synchronizes only
`composer.json` to the exact live bytes. Its committed Composer identities are:

| File | SHA-256 |
|---|---|
| `composer.json` | `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872` |
| `composer.lock` | `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9` |

The candidate commit is a child of that exact-live Composer parent. The
Composer content hash remains `a72b3c22fc3bec98130fd5133da242a1`.

## Lock resolution

The lock was resolved twice from fresh copies of those exact production bytes:

```text
composer update laravel/framework:12.69.1 \
  --with-dependencies --minimal-changes \
  --no-install --no-scripts --no-interaction
```

Both runs produced lock SHA-256
`77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`.
The diff contains one package update, zero additions, zero removals, and zero
unrelated package changes:

| Package | Live | Candidate | Candidate source |
|---|---:|---:|---|
| `laravel/framework` | `v12.69.0` | `v12.69.1` | `0c07b0b1f88af44d8558ffadf66900a860f93c23` |

All other 115 locked packages and their references are byte-identical.

## Regression proof

Two feature tests construct Laravel's real
`id|remember_token|password-hmac` recaller value and send it as an encrypted
cookie through the web middleware and `/` home view.

- The exact `12.69.0` baseline reproduces HTTP 500 and the production
  `hash_equals()` `TypeError` when the matching user row has disappeared. The
  valid remember cookie still authenticates.
- With `12.69.1`, the stale cookie renders HTTP 200 as a guest with
  `viaRemember()` false. The valid cookie authenticates the matching user with
  `viaRemember()` true.

The red and green transcripts are in the evidence directory. Composer created
both disposable vendors; no vendor file was edited.

## Current production envelope

Read-only checks on 2026-10-02 observed the following live identities:

| Item | Identity |
|---|---|
| Laravel | `12.69.0`, source `335429f28612e3a7810db0c8508b2cddbcc0fda0` |
| Vendor manifest | `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed` |
| Bootstrap cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Runtime source | `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` over 326 files |
| PHP / Composer | `8.2.30` / `2.9.3` |

The current live source is a 326-file snapshot at `3909bdc…`; the September
dependency cutover recorded a 302-file snapshot at `46f6a1…`. The reason for
that delta was not established as part of this dependency review. Current live
source is managed outside this package: the runner freezes it byte-for-byte,
copies none of it, and stops if any source byte changes before staging or
cutover.

The live receiver, job-label, and retention flags are false, and the incoming
artwork host allowlist is empty. The runtime probe requires the same state
before staging, immediately before cutover, after candidate activation,
through monitoring, and during rollback verification.

## Deterministic production candidate

Two independent empty native-Linux builds used Composer `2.9.3`, the exact
live Composer JSON, the candidate lock, `--no-dev --prefer-dist
--optimize-autoloader --no-scripts`, and the read-only current production
source snapshot for package discovery. Both produced identical identities:

| Item | Files | Directories | Bytes | SHA-256 |
|---|---:|---:|---:|---|
| Candidate vendor | 6,465 | 925 | 26,482,354 | `b8e0e3afa65171a66ad3d1875404fe209d7598c9b3f690e494d40c4fde4408f8` |
| Candidate bootstrap cache | 2 | 0 | 21,768 | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |

Laravel Pail and every other dev-only package are absent. The exact production
PHP `8.2.30` platform check remains a mandatory future staging step; current
preparation proves the candidate lock has no PHP `8.2.30` prohibition and
passes platform checks on the validation PHP `8.3.6` runtime.

## Staging plan — separate authorization required

1. Independently review the candidate commit, lock archive, runner, runtime
   helper, deterministic identities, 23-scenario rehearsal, and checksums.
2. Copy the reviewed runner, helper, and lock artifact only into a new private
   production operations directory. This is not authorized by this handoff.
3. Run the runner's read-only preflight. It must match the exact live Composer
   JSON/lock, source, vendor, cache, database config, front controller,
   PHP/Composer toolchain, package versions and paths, empty queues, health,
   and disabled incoming-order capabilities.
4. Under a separate staging authorization, use the exact staging token
   `STAGE-BUYDTF-LARAVEL-REMEMBER-77055fc8acf89149`. Staging builds a restricted
   sibling shadow release and runs strict validation, locked production audit,
   production PHP platform checks, package discovery, and route discovery.
5. The stage must reproduce vendor `b8e0…` and cache `468c…`, emit a restricted
   release receipt, and stop. Review that receipt before requesting cutover.

Staging does not enter maintenance or change the live lock, vendor, cache,
source, configuration, database, front controller, services, or capability
flags.

## Cutover and rollback plan — not authorized

A later cutover requires separate approval of the exact stage receipt and the
token `DEPLOY-BUYDTF-LARAVEL-REMEMBER-77055fc8acf89149`.

The runner installs its reviewed boot-independent static 503 gate, drains
active FPM connections, and atomically exchanges the live and staged
`vendor/` directories with `renameat2(RENAME_EXCHANGE)`. It then atomically
exchanges `bootstrap/cache`, replaces only `composer.lock`, runs two PHP-FPM
identity probes, opens the gate, checks the public health matrix, and monitors
for 30 minutes. It does not run `composer update`, Git, migrations, source or
configuration copies, or service restarts.

During and immediately after that monitor, an independent operator must take a
read-only Laravel log delta and review it for recurrence of the exact
`SessionGuard` / `hash_equals()` failure and for genuine new exceptions,
traces, fatal errors, `SQLSTATE`, missing classes, or missing views. The runner's
health monitor does not parse Laravel logs, so this review remains a separate
cutover acceptance step.

Before mutation it retains the exact `22af…` lock, `739994…` vendor, `468c…`
cache, and front controller. Any failure or interruption reasserts the static
gate, atomically returns the retained vendor and cache, restores the exact old
lock, verifies the `12.69.0` runtime twice through FPM, and reopens only after
health succeeds. Explicit recovery is pinned to the state receipt and token
`RECOVER-BUYDTF-LARAVEL-REMEMBER-22af12c7e58fcfe8`.

No staging, cutover, maintenance mode, migration, source/configuration change,
service restart, ShopNLTees action, retention action, customer deletion, or
customer-artwork change was performed while preparing this review package.
