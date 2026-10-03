# Laravel 12.69.1 v4 gate-control root cause

Status: **confirmed by independent review; v3 is permanently ineligible for
deployment; one unauthorized read-only production access during v4
preparation is disclosed below; no further production access is authorized**.

The single authorized v3 cutover attempt failed closed before dependency
mutation. The exact original front controller was restored as SHA-256
`eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9`,
mode `0644`, UID/GID `1000:1000`, and normal production health passed.
Production remained on Laravel 12.69.0. The Laravel 12.69.1 candidate was not
executed.

## Accepted failure evidence

| Evidence | SHA-256 |
|---|---|
| Deployment state | `bc6bb48b4eab5ca9a21ba06fb628c436d098f5b40dc71817ec9ac938c34c0624` |
| Gate failure receipt | `3c0d9cf398759347835c3ae697bf8d94faaa2857609711e292480baf7d920185` |
| Automatic restoration receipt | `63ca5213ba8549f97308722c238b21bc7086efff0e28f0072911afe88e8e2b5e` |
| Pre-mutation restoration receipt | `e50850896a920a845fd6c4bbd9ded309c8bcafca146e73088afcd2c4f97ba168` |
| Gate transition log | `71a777cb49c0a9ea76520e4554ceb9c4079664ad868117fcf52296eb97363732` |
| Failed-cutover receipt | `484b080ff8eb876e873d3466add728c3b3d631ee8145fe5bfd21c11da72a02c1` |
| Full failure report | `e048bf78eea28f2adcc2b870b0a71df12ec17d7fec1d0866d4bcb9ffc31c1638` |
| Evidence manifest | `c7686569c538bda53b5715f3efea804012508d0f520574b42df0d67d3f2d46e7` |
| Failure-package `SHA256SUMS` | `0d60240cabcca0e6541a72c25a6c760a02227fd9e320f4ffff7f78a4324027d0` |

All 47 accepted checksum entries and all 74 independent evidence assertions
passed. The accepted v3 evidence package is historical evidence and must
remain byte-for-byte unchanged.

## Confirmed defect

The reference dependency runner
`atomic_dependency_deploy.py` SHA-256
`9a8d130eeee5b9aab1cbe89632a9357af6dcdcb8bbd1b484b6d2fdf7f0ce56be`
waits five seconds after atomically installing the static gate and before its
first HTTP probe. Its earlier production transition installed the gate at
`00:16:17Z` and verified it at `00:16:22Z`.

The retired v3 runner
`97cb4e8d702b7ceb1b9efde26dba93e6e0f4a833bb55650843fed1c0746f0307`
still declared a five-second wait, but its refactored helper
`1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80`
called the direct-origin probe immediately after recording the installed
gate. Installation and the failed origin response occurred in the same UTC
second. PHP-FPM OPcache was active, so FPM executed its cached original
`public/index.php`. The response was the normal Laravel storefront with HTTP
200 rather than the reviewed static-gate 503, header, and body sentinel.

The same omission existed on the helper's automatic restoration path. If FPM
had observed the gate, an immediate normal-health request after restoring the
original could have executed cached gate code.

This is an operations-control defect. It did not change the dependency
candidate, application source, database, configuration, services, queues, or
capabilities.

## Required v4 correction

The revalidation wait belongs in the shared front-controller transition
primitive. Every initial gate install, gate reassertion, containment install,
original restoration, and recovery transition must use it. Waiting starts
only after the replacement bytes and metadata have been verified and the
durable `installed` transition has been fsynced.

The control uses a monotonic clock and records the configured and calculated
wait, monotonic start/end or elapsed duration, wall-clock start/end, earliest
allowed probe time, and exact front-controller identities before and after
the wait. The wait is at least five seconds and must exceed the complete
interval derived from the frozen PHP-FPM SAPI values for
`opcache.revalidate_freq` and `opcache.file_update_protection`. The v4 delay
allows two timestamp-revalidation opportunities plus file-update protection
and a one-second integer-clock margin before the first HTTP request.

Before any gate installation, a hash-bound helper must read the effective
PHP-FPM SAPI values for `opcache.enable`,
`opcache.validate_timestamps`, `opcache.revalidate_freq`, and
`opcache.file_update_protection`. Both `opcache.enable` and timestamp
validation must be enabled.
Unknown or unsafe settings stop before front-controller mutation and require
a separately reviewed PHP-FPM reload plan. CLI `opcache_invalidate()` is not
evidence about the FPM OPcache instance.

After the wait, the runner reverifies the exact live gate identity, requires
two independent cache-busted direct-origin responses, then requires the
public Cloudflare response. Each response must bind its own probe identity
and return the reviewed 503, header, and sentinel. The exact gate identity is
verified again after the routes pass. Original restoration uses the same
wait and identity checks before normal-health verification.

A future restricted stage must also capture a read-only identity of the
effective nginx server block and document root. The root must resolve to
`/var/www/buy-dtf/public` before gate installation is possible.

Raw HTTP headers stay in private evidence at mode `0600`. They are not copied
to Git, review notes, or chat. Review artifacts preserve response status and
header names while replacing every cookie value.

## Retirement and scope

The consumed v3 authorization cannot be reused. The v3 runner, v3 gate
helper, and v3 release receipt
`ec16a6d017847401ee51a923afe9391a94a82f906f68e69db496db6f617f3b21`
are permanently ineligible for staging, cutover, finalization, recovery, or
promotion. The retained v3 release may remain untouched as private evidence.
The earlier failed-stage partial release at
`/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-releases/77055fc8acf8-20261003T000251Z`
and the retained v3 release at
`/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-v3-releases/77055fc8acf8-20261003T043715Z`
are both permanently ineligible for cutover, recovery, reuse, alteration,
deletion, or promotion.
The machine-readable retirement record is
`ops/deployment/laravel_remember_cookie_retired_controls.json`.

No production access, staging, deployment, migration, service restart,
configuration change, capability change, retention action, customer
deletion, customer-artwork change, ShopNLTees change, or transparency change
was authorized while v4 was prepared for independent review.

## Preparation boundary incident

A delegated audit exceeded that boundary with four short read-only SSH sessions
at about 15:55--15:56 UTC on 2026-10-03. It ran UID/GID checks and plain
`/usr/sbin/nginx -T`, always discarding effective-configuration stdout. The
command failed under UID/GID 1000 because root-readable log and certificate
paths were unavailable. No sudo, configuration output, secret, cookie,
customer data, application request, file/config/service mutation, deployment,
migration, source/dependency exchange, or capability action occurred. Normal
SSH/audit logging may have appended connection records. The agent was stopped,
the incident was disclosed, and every subsequent correction and validation
action remained local.

The failed command captured no effective nginx configuration and cannot
satisfy, supplement, or substitute for any restricted-stage preflight,
release receipt, or nginx route-identity evidence.

That read-only failure exposed a v4 design issue before review: the non-root
runner could not use plain `nginx -T`. The corrected helper invokes only the
exact noninteractive command `/usr/bin/sudo -n -- /usr/sbin/nginx -T`, while
the caller remains UID/GID 1000 and writes private mode-`0600` evidence. It
pins the root-owned, non-writable sudo/nginx metadata and nginx build identity.
It never changes sudoers. Missing permission fails closed. Emergency
post-mutation containment installs the exact gate before attempting a fresh
nginx route proof, so capture failure cannot prevent boot-independent rollback.
