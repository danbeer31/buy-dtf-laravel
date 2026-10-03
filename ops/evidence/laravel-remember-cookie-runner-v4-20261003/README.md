# Laravel 12.69.1 v4 gate-control review evidence

Status: **local correction and validation complete; independent review required;
NO-GO for production access, restricted staging, gate installation, cutover,
deployment, recovery, migration, service restart, configuration change, or
capability change**.

Branch: `fix/laravel-12.69.1-remember-cookie-v4-20261003`

Reviewed base: `e7c839947a5bdf49776dd184926a28d0756196ae`

The final commit is reported after this evidence package is committed; embedding
that commit inside files in the same commit would be self-referential. The
controlling handoff is `HANDOFF.md`, SHA-256 `8ee888883bf2330c7a5c7d70efe48244122b600067ba030976a53cbe0009e4c1`. The full
future staging, cutover, monitoring, rollback, and recovery plan is
`ops/LARAVEL_REMEMBER_COOKIE_DEPENDENCY_PLAN_V4_2026-10-03.md`.

## Preparation boundary incident

A delegated audit exceeded the local-only authorization with four short
read-only SSH sessions at about 15:55--15:56 UTC on 2026-10-03. It ran only
UID/GID checks and plain non-sudo `/usr/sbin/nginx -T` with configuration stdout
discarded. The nginx command failed under UID/GID 1000. No configuration,
HTTP response, cookie, customer data, or application data was captured. No
file, schema, dependency, source, configuration, capability, queue, or service
mutation occurred; normal SSH/audit connection records may have appended. The
result is ineligible as staging evidence. No later production access occurred.
`ROOT_CAUSE.md` and `root-cause-receipt.json` contain the complete disclosure.

## Corrected and retired controls

| Control | SHA-256 |
|---|---|
| v4 runner | `e2d735c9c9c86c8bd38be3085b3372a2d2079ada9866d87487e8aa486dfc79f0` |
| Shared gate helper | `ae542dbe387406d5b0e0d379f074251d30e93d066f330c1badb16b11caf776bc` |
| PHP-FPM OPcache probe | `b8b34f87d45a0c000cc0df7917496631320cfbdcca1ff44bc41741ce0d569262` |
| Nginx route-identity helper | `4beb1fd5e4fabb8d74d2de50b8c96f452ecb6de242ed411c7c0a97304037d192` |
| Runtime helper | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| Database validator | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| Laravel log parser | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |
| Retirement registry | `622655e74dea16699cd4ffb714460a934ce2aa1abee1f130cdd7b1228a0e2163` |

The v3 runner `97cb4e8d...`, gate helper `1269a277...`, and release receipt
`ec16a6d...` are permanently retired. The v1 and v2 runners remain retired.
Neither retained failed release was read, changed, reused, deleted, or promoted.

The shared transition primitive now waits only after exact replacement bytes
and `1000:1000/0644` metadata are verified and the durable `installed`
transition is fsynced. It uses a monotonic deadline and the conservative formula
`max(5, 2 * revalidate_freq + file_update_protection + 1)`. Initial install,
reassertion, rollback containment, exact-original restoration, and recovery all
use the same primitive. An incomplete wait is not accepted after interruption.

The future stage must capture the effective PHP-FPM SAPI settings and nginx
route identity before any gate installation. Timestamp validation is mandatory,
and the selected nginx route must resolve to `/var/www/buy-dtf/public`. After a
completed barrier, the gate requires two unique direct-origin probes and one
unique public Cloudflare probe, then another exact live-gate identity check.
Raw headers remain private mode `0600`; cookie values are redacted from review
artifacts.

## Candidate and rollback identities

The accepted dependency candidate did not change:

| Identity | SHA-256 |
|---|---|
| Candidate lock | `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d` |
| Candidate vendor | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Vendor ownership/mode | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Complete vendor inventory | `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5` |
| Executable allowlist | `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154` |
| Bootstrap cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Application autoload set | `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91` |
| Runtime source CAS | `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` |

Both clean builds reproduced Laravel 12.69.1, the single-package lock delta,
6,460 files, 925 directories, 26,481,661 bytes, exact UID/GID and modes, ten
executables, no Windows proxies, 126 application entries in each optimized
autoload file, zero advisories, package discovery, and 178 routes. Actual
UID/GID 33 processes loaded Laravel while vendor writes failed.

The retained rollback set remains Laravel 12.69.0, lock
`22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`,
vendor `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`,
and cache `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.
The original front controller remains `eba77cba...`, mode `0644`, UID/GID
`1000:1000`.

## Validation results

- Root deployment-control discovery: 114 tests, 112 passed, two expected
  UID-1000-only skips.
- UID 1000 discovery: 114 tests, 111 passed, three expected root-only skips.
- Application suite: 110 tests, 718 assertions.
- Remember-cookie controls: 2 tests, 10 assertions.
- Npm clean install and production frontend build: exit 0.
- PHP 8.2.30 platform check: pass. This is the candidate platform proof.
- Local production-like nginx/PHP-FPM rehearsal: three final passes on PHP-FPM
  8.3.6 with `revalidate_freq=4`, `file_update_protection=2`, and an 11-second
  barrier. PHP-FPM 8.3.6 is only the disposable rehearsal runtime; future
  production settings must be captured again during separately authorized
  restricted staging.
- Static-gate rehearsal: 28 scenarios and 48 shared monotonic waits.
- Atomic cutover/rollback/recovery rehearsal: 25 scenarios.
- Database envelope: 9 tests; Laravel log parser: 22 tests; FPM/nginx
  environment controls: 16 tests.

The rehearsal warmed the original front controller, reproduced an immediate
stale HTTP 200 after atomic gate installation, waited 11 seconds, and obtained
three exact gate responses (503/503/503). After FPM executed the gate, it
restored the original, reproduced an immediate stale 503, waited again, and
obtained two normal HTTP 200 responses. The final run and two independent
repeats have the same stable invariant hash. Earlier local seven-second runs
were timing-flaky (both passes and stale-200 failures); that pre-freeze result
caused the two-window formula and is preserved in the redacted repeatability
summary. No raw HTTP evidence was committed.

## Evidence index

| Evidence | SHA-256 |
|---|---|
| Root-cause receipt | `e377fc7a7f9cdcd47bcc0b2d1ba6859babc3820153d6f175764fb15dd63256ea` |
| Build A | `6eaaf4826db1bef6eb52b3fd98d7d71b1fe5124b3358a99ce4b972cd71277060` |
| Build B | `4a7d7dc5e20e94cda96b4b9ec7ba4175748fb48b54209d6f03166fcb9d1ed01c` |
| Two-build comparison | `f81fd96b2b28657898cf629f3cf044d58820b5209721fa4b259640b9a328836d` |
| PHP 8.2.30 platform | `19855bc41a90d6ed459d1975dbb8833ab19cf61ff654d8f2562d714c17822b6c` |
| Production-like OPcache rehearsal | `e5af0fe207c410b3aea2ec2cc5864acd4346fc31462530a35d53f13a455359d8` |
| OPcache repeatability summary | `d1c3af8b62ee08f86277ccb773e349ff90f41102a235fa3ec0772976c6baf486` |
| Gate transition rehearsal | `afae804d5737be4764f006874b7b93fa8caf79fb8d0dc3542f0d27ad8171bbf2` |
| Atomic rehearsal | `321320d93c5f41c96f522977b892a1165964a9dec9eb9a3036e0eaef4b6699ed` |
| Database validation | `f843199040f4e18c2e2d53b33e859e7daad19e1e13e27a7972b29a309963703f` |
| Log-parser validation | `4c1d2453e46d30c295d1a55ee2feadf05deea7083868352008be5d04854718af` |
| Environment-control validation | `d829f0690cce4e9658a1803a969cee04933bb4878d79a0862e9b9d2f320d906d` |
| Frontend validation | `5f1d496119eff9d084bbc9c27a84b83cb027d118ff211a6419b53c31418b06d1` |
| Complete test results | `20ba7461b4ad44940cb8d58a97eab7ec6dc0c56ffaaf7a5156e0eda5bf7a1e68` |

`evidence-manifest.json` and `SHA256SUMS` are generated after this document and
all receipts are frozen. The rehearsal artifact name ending in `v1` is the
receipt protocol/schema; this directory and aggregate receipts are package
generation v4.

## Future reviewed sequence

A new independent code review must accept this branch, commit, control hashes,
and evidence. A separate restricted Phase 1 authorization may then push the
exact reviewed commit, run read-only preflight, capture effective PHP-FPM and
nginx identities, create a fresh private v4 shadow release, emit new database
and release receipts, prove production unchanged, and stop.

A later cutover needs a new authorization bound to that exact v4 release
receipt. It repeats all envelopes, installs the gate through the shared wait,
verifies both routes, exchanges only vendor and `composer.lock`, restores the
original through the same wait, and enters the 30-minute monitor. Failure before
dependency mutation restores the original; failure after mutation retains the
gate and runs the reviewed boot-independent rollback. Final success remains
blocked at independent Laravel-log review and a separate finalize authorization.

No v4 staging token, release receipt, or cutover token exists in this package.
Transparency commit `3db18d1fff3f599299eecd2aae21b9102fc45540` remains clean
and non-stageable with `DEPENDENCY_ENVELOPE_FROZEN = False`. Receiver,
job-label, and retention capabilities remain disabled, and the artwork-host
allowlist remains empty.
