# Laravel 12.69.1 remember-cookie dependency repair v2

Date: 2026-10-02 (America/Chicago)

Status: **ready for independent review; NO-GO for staging or deployment**.

This replacement corrects only the Laravel `v12.69.0` to `v12.69.1`
dependency repair and its deployment runner. It does not patch `vendor/`,
change any other package, deploy source, run migrations, restart services, or
enable capabilities.

The controlling handoff is
`ops/evidence/laravel-remember-cookie-runner-v2-20261002/HANDOFF.md`, SHA-256
`f198e8658848f64ac003528e45d925a606ef6788769e81b5d7269ec8be345dcb`.
The failed v1 runner, both retired vendor identities, and the retained partial
release remain permanently ineligible for reuse or cutover.

## Exact dependency delta

The branch retains the reviewed application change at
`6a98c74686f1ceffded8012d332318ac075b444e` and starts its v2 runner work from
the accepted failed-stage evidence commit
`ac959e0fbf6ad9c6ae71531dbeb09ae2b9309917`.

| Item | SHA-256 or value |
|---|---|
| Exact live rollback lock | `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9` |
| Candidate lock | `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d` |
| Exact live `composer.json` | `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872` |
| Production packages | 80 before and after |
| Development packages | 36, unchanged |
| Changed package | `laravel/framework` only, `v12.69.0` to `v12.69.1` |

The only changed Laravel lock fields are version, time, source reference, dist
reference, and dist URL. Package membership and all top-level lock data remain
unchanged.

## Canonical build

The runner copies the exact 326-file runtime source CAS into a private shadow
before Composer runs. Composer installs without an autoloader, then performs
one canonical optimized dump after the source copy. Both optimized Composer
files must contain the same 126 application entries confined to `app/`.

`COMPOSER_BIN_COMPAT=proxy` pins Unix proxy generation. Any top-level
`vendor/bin/*.bat`, symlink, special file, hard link, unexpected executable,
or ownership/mode mismatch fails closed.

After Composer, package discovery, and route discovery, the runner normalizes
and verifies the complete vendor tree:

| Property | Frozen result |
|---|---|
| Vendor files | 6,460 |
| Vendor directories, excluding root | 925 |
| Vendor bytes | 26,481,661 |
| Ordinary files | 6,450 at `0664` |
| Approved executable files | 10 at `0775` |
| Directories and vendor root | `0775` |
| Owner/group | `1000:1000` on every vendor path |
| Vendor content/mode SHA-256 | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Ownership/mode SHA-256 | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Complete JSONL inventory SHA-256 | `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5` |
| Executable allowlist SHA-256 | `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154` |

The optimized entry-set SHA-256 is
`342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91`.
The individual file hashes are
`5236a6ef5a0803719a2cb9b24d525946342063421aac9c6bec3914f1a9d9d893`
for `autoload_classmap.php` and
`1e82d08d78ebc0936284cf10cd7aca90b1753e0b7868627b2dda13bb67e54dc5`
for `autoload_static.php`.

Two clean ext4 builds used the same PHP 8.3.6 and Composer 2.9.3 binaries but
different extraction paths: Build A used `/usr/bin/unzip`; Build B hid unzip
and used PHP ZipArchive. Their complete path, content, UID, GID, and mode
inventories are byte-identical. Both actual UID/GID 33 probes loaded Laravel
12.69.1 through the candidate autoloader, read it, failed both vendor create
and append attempts, and left no residue.

The exact PHP 8.2.30 NTS platform check also passes against the final installed
candidate and is bound to the exact source, vendor, cache, autoload, runner,
lock, PHP executable, PHP archive, and Composer identities.

## Validation

- Composer strict validation passes in both clean builds.
- Locked `--no-dev` audit reports zero advisories in both builds.
- Package discovery passes and route discovery returns exactly 178 routes in
  both builds.
- The stale-cookie and valid-cookie tests pass: 2 tests, 10 assertions.
- The full application suite passes: 110 tests, 718 assertions.
- Runner unit tests pass: 10 tests.
- All 25 atomic success, interruption, rollback, recovery, identical-cache,
  and metadata-drift rehearsal scenarios pass.
- Python and PHP syntax validation passes.

No production connection was made during v2 preparation. The accepted
before/after evidence at `ac959e0...` remains the controlling proof that the
live Laravel 12.69.0 lock/vendor/cache, source, front controller,
configuration, schema, 21-row ledger, services, queues, health, and capability
flags were unchanged after the failed stage. The v2 preparation only read the
two previously captured, matching local source CAS copies.

## Restricted staging plan

Staging requires fresh written authorization and a newly reviewed v2 token.
The runner must first re-run its read-only production preflight and require the
exact live Laravel 12.69.0 lock, vendor, cache, 326-file source CAS, front
controller, database configuration, PHP/Composer toolchain, schema and
21-row ledger, empty queues, public health, and disabled incoming-order
receiver, job-label, retention, and host-allowlist capabilities.

The stage command may then create only a new private v2 shadow. Its fixed v2
operations root must be a real directory at the fixed private parent with
owner/group `1000:33` and mode `0700`; symlinks and path redirection fail
closed. The exact source is copied into that shadow solely so optimized
autoload generation and discovery operate on the live source CAS. Staging
does not install a static gate, enter maintenance, alter the live lock, exchange
vendor/cache, deploy source, restart services, or run migrations.

The stage must reproduce every frozen identity, emit a v2 release receipt,
and stop. That receipt receives a separate independent review before any
cutover request.

## Cutover and rollback plan

Cutover requires separate written authorization tied to the exact successful
v2 stage receipt and its SHA-256. The runner revalidates the complete baseline,
installs the reviewed static gate, drains active FPM work, and atomically
exchanges only `vendor/`. Because the frozen live and candidate bootstrap
caches are identical, it verifies both copies and deliberately skips the cache
exchange. It then atomically replaces only `composer.lock`, proves the
candidate through runtime and two FPM probes, restores the front controller,
checks public health, and performs the 30-minute monitor.

Before mutation, the runner retains the exact Laravel 12.69.0 lock and vendor;
the unchanged live cache remains the rollback cache. Any failure reasserts the
static gate, identifies both vendor orientations using the old manifest and
the full candidate ownership/mode identity, atomically restores the old
vendor, restores the old lock, verifies the unchanged cache, and proves the
old runtime twice before reopening. Explicit recovery is bound to the exact
state, receipt, runner, helper, handoff, source, vendor, cache, autoload, gate,
and front-controller identities. Repeated recovery with identical cache
identities is rehearsed as idempotent.

The transparency commit
`3db18d1fff3f599299eecd2aae21b9102fc45540` remains non-stageable with
`DEPENDENCY_ENVELOPE_FROZEN = False`. It must be refrozen and revalidated only
after this dependency repair is separately deployed and monitored.
