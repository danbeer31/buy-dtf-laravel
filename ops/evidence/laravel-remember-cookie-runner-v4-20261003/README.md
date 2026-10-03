# Laravel 12.69.1 v4 emergency-rollback correction evidence

Status: **local correction and complete validation passed; independent review
required; NO-GO for production access, restricted staging, gate installation,
cutover, deployment, recovery, migration, service restart, configuration
change, or capability change**.

Branch: `fix/laravel-12.69.1-remember-cookie-v4-20261003`

Reviewed base: `e7c839947a5bdf49776dd184926a28d0756196ae`

Immediate unapproved predecessor:
`25fa7c737e969f8dffa251fd5170f6c7064c69f5`

The final local commit is reported outside this package because a commit cannot
contain its own identity. The controlling handoff is `HANDOFF.md`, SHA-256
`6539058cf602fc23b03552665faf9a32c6975e29e6cb11fb5b2deb2c7e02afa9`.

## Corrected post-mutation behavior

The predecessor could stop with Laravel 12.69.1 dependencies live if PHP-FPM
became unavailable after dependency mutation while the original front
controller was serving. This replacement keeps every pre-mutation gate
transition strict: a current live PHP-FPM probe must exactly match the staged
envelope.

Immediately before the durable dependency-mutation boundary, the runner now
rechecks the live envelope and writes a private, fsynced receipt binding the
release receipt, FPM helper, normalized settings, derived OPcache policy, and
exact equality with the staged envelope. Only after dependency mutation has
started may the emergency path use that receipt when the live FastCGI probe is
unavailable. Reachable drift or malformed FPM output cannot use the fallback.
Missing, malformed, relocated, nonprivate, or altered frozen evidence raises an
explicit `DeploymentError`.

The emergency path accepts only the reviewed original front controller or the
reviewed gate with exact metadata. It installs or reasserts the gate, completes
the full shared monotonic OPcache wait, and proceeds with the boot-independent
Laravel 12.69.0 rollback. Origin or public gate-verification failure retains the
exact gate and no longer prevents rollback.

The nginx identity now also proves that `buy-dtf.com` selects `/index.php`,
passes it to `unix:/run/php/php8.2-fpm.sock`, and resolves
`SCRIPT_FILENAME` to `/var/www/buy-dtf/public/index.php`. Its route identity is
bound into any future staging release receipt. Socket, handler, selector, or
filename mismatch fails closed.

## Frozen controls

| Control | SHA-256 |
|---|---|
| Replacement runner | `464bd6a28c8bed84c90176d42bc88d22eea5977c2698d5cddb7fe3eca50f9558` |
| Shared gate helper | `b93c08f58a08333120369c1cc75c60631d621c3a8099ca3967065721c45679f5` |
| Nginx route-identity helper | `1243fea2757aca89f586ec4b322b0d23ee1e19b2d027c21bd6523e71e6e6e8e0` |
| PHP-FPM OPcache probe | `b8b34f87d45a0c000cc0df7917496631320cfbdcca1ff44bc41741ce0d569262` |
| Runtime helper | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| Database validator | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| Laravel log parser | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |
| Handoff | `6539058cf602fc23b03552665faf9a32c6975e29e6cb11fb5b2deb2c7e02afa9` |

Runner `97cb4e8d...`, gate helper `1269a277...`, and release receipt
`ec16a6d...` remain permanently retired. Earlier v1/v2 runners and both
retained failed releases remain untouched and ineligible for staging, cutover,
recovery, reuse, alteration, deletion, or promotion.

## Candidate and rollback identities

The accepted one-package dependency candidate did not change:

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

Two clean builds reproduced Laravel 12.69.1, the sole Laravel framework lock
change, 6,460 files, 925 directories, 26,481,661 bytes, exact UID/GID and
modes, ten executable paths, no Windows proxies, 126 application entries in
each optimized autoload file, PHP 8.2.30 compatibility, package discovery, 178
routes, zero advisories, and UID/GID 33 read/no-write behavior.

Application tests used an isolated copy of Build A. The receipt explicitly
records the unchanged `public/assets` test-only supplement, which is outside
the runtime-source CAS, and the local SQLite definitions for the already
installed and disabled incoming-order tables. Build A remained unchanged and
continued to verify the 326-file source CAS.

The rollback set remains Laravel 12.69.0, lock
`22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`,
vendor `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`,
and cache `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.

## Validation results

- Root control discovery: 123 tests, 121 passed, two expected UID-1000-only
  skips.
- Actual UID/GID 1000 discovery: 123 tests, 120 passed, three expected
  root-only skips.
- New regressions cover post-mutation FPM timeout with the original live,
  frozen-envelope gate installation and rollback, missing/malformed evidence,
  interrupted emergency waits, nginx socket and `SCRIPT_FILENAME` mismatch,
  and HTTP gate-verification failure with rollback continuing.
- Gate state-machine rehearsal: 28 scenarios and 48 complete monotonic waits.
- Atomic cutover/rollback/recovery rehearsal: 25 scenarios.
- Production-like local nginx/PHP-FPM rehearsal: three passes. Each reproduced
  immediate stale original HTTP 200, waited 11 seconds, obtained two origin and
  one public 503 gate response, restored the original, reproduced immediate
  stale gate 503, waited 11 seconds, then obtained two HTTP 200 responses.
- Every rehearsal used nine unique nonces; all 26 raw entries per run remained
  private mode `0600`; no raw headers or cookie values were committed.
- Application suite: 110 tests, 718 assertions.
- Remember-cookie controls: 2 tests, 10 assertions.
- Database envelope: 9 tests; environment controls: 21 tests; log parser: 22
  tests.
- Composer strict validation, locked `--no-dev` audit, package discovery,
  PHP 8.2.30 platform proof, npm clean install, frontend build, and syntax
  validation all passed.

## Evidence index

| Evidence | SHA-256 |
|---|---|
| Artifact identities | `fef4ab04c37b98ec875551728326257b850aa90731cc6fc65335fb79878b59fc` |
| Root-cause receipt | `8c2b7be2279d22d8b190a8b31d6a1743c59f6562eaff6202ecd342965fe41260` |
| Build A | `52877a50e6d4e0253cea8cbfaab76e55d9a910cfa55b410096dd6f363429317e` |
| Build B | `44a54c40a10d8ed961c524548f6cbd06607f32873520c1030e6fccf422487ff6` |
| Two-build comparison | `91bde6b79bd4f273b808e352a9b66a36835dd8556751a63ab88144e3a9cfb45a` |
| Local build summary | `8a459b35eeeac51c92a42b63ae2606b14fdc9728f3295c734e05474975c60b09` |
| PHP 8.2.30 platform receipt | `da3c0d23e120c8ff5ee7be95949cd260be08e943101dbf3249aaf9caf2d0da23` |
| Local rehearsal summary | `f3af437c653bbb5c09af01534e8a949d84b098746315b5dec1b09f158b048fcb` |
| Gate transition rehearsal | `3a49fb00ce4e7958bf8c6c26fe5b60e993e5768458c5bd6f66b4eb5d85f2e8f8` |
| Atomic rehearsal | `b443b302333ef162f757053ccc5fe24b213f6e3e5f8a06439b7b8ba2c1585891` |
| OPcache primary rehearsal | `086273a502fe579ae1f63043ca487ba2a550b039b593bc108fd764ffce59d413` |
| OPcache repeatability | `0fb685001e1ec5701c693ea80b6213d0a666629f25a88e58b3753b003b0197d4` |
| Database validation | `40094be593bd9704adc31e9fce1a536b645335d2996c44c0cd34cd1fad9fe1d9` |
| Environment controls | `c422cdd6d5604a655bdd21315f68fc239889ff440b43363901a7207236d2ee04` |
| Log parser | `2b492cc3b9e616e34d1e5e01840872ea5af9cdd0fb71eaff8fc5f4ec872f5b6c` |
| Frontend validation | `a6372b80cab337b43d5be9a2f3ccd5228669169bf21005fc530ab8b4bfa4520a` |
| Complete test results | `b73e90a8f5e09d19acf5744c01a5f73f62c89b92d06de9a8cf6804253e933d24` |

`evidence-manifest.json` and `SHA256SUMS` are generated last after every package
byte is frozen.

## Scope and next review gate

A delegated audit during the earlier v4 preparation exceeded the local-only
boundary with four read-only SSH sessions. It captured no usable production
configuration or application data and made no production mutation. The full
disclosure remains in `ROOT_CAUSE.md` and `root-cause-receipt.json`. This
replacement correction performed no production or external-network access and
remains local and unpushed.

A new independent review must accept the local commit, controls, and evidence.
Only a later, separately authorized restricted Phase 1 may push that exact
commit, capture the live FPM/nginx identities, and create a new private v4
release receipt. Any cutover requires another evidence-bound authorization.

No stage, deploy, cutover, recovery, migration, restart, source/configuration
change, capability change, ShopNLTees change, retention action, customer
deletion, customer-artwork action, or transparency action occurred. Receiver,
job-label, and retention capabilities remain disabled; the artwork-host
allowlist remains empty. Transparency commit
`3db18d1fff3f599299eecd2aae21b9102fc45540` remains clean and non-stageable
with `DEPENDENCY_ENVELOPE_FROZEN = False`.
