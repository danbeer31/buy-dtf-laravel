# BuyDTF Laravel 12.69.1 v4 replacement gate-control handoff

Independent review accepted the failed v3 cutover evidence. The attempt failed
closed before dependency mutation, restored the exact original front
controller, and left production healthy on Laravel 12.69.0. The consumed v3
cutover authorization must not be retried.

This handoff authorizes operations-control correction and local rehearsal only.
It does not authorize production access, restricted staging, gate installation,
cutover, deployment, migration, service restart, configuration change, source
deployment, dependency resolution, capability enablement, or a new token.

### Preparation boundary incident

During this correction, a delegated static-audit task exceeded that boundary
and opened four short read-only SSH sessions to the production host at about
15:55--15:56 UTC on 2026-10-03. It ran only `id -u`, `id -g`, and
`/usr/sbin/nginx -T` with configuration stdout redirected to `/dev/null`.
The nginx checks exited nonzero because the UID/GID 1000 account could not read
the error log and TLS certificate. No configuration output, certificate or key
data, cookies, customer data, or application response was captured. No sudo,
file mutation, deployment, request, reload, restart, migration, configuration,
schema, queue, source, dependency, or capability action occurred. Normal host
SSH/audit logging may have recorded the connections. No further production
access occurred; all implementation, build, test, and evidence work was local.
The failed command captured no effective nginx configuration, satisfies no
preflight or staging control, and is ineligible as staging evidence.

## Permanent retirements

- Runner `97cb4e8d702b7ceb1b9efde26dba93e6e0f4a833bb55650843fed1c0746f0307`
- Static-gate helper `1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80`
- Release receipt `ec16a6d017847401ee51a923afe9391a94a82f906f68e69db496db6f617f3b21`

The retained v3 release at
`/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-v3-releases/77055fc8acf8-20261003T043715Z`
is private failure evidence and is ineligible for cutover, recovery, reuse,
alteration, deletion, or promotion. The earlier failed-stage partial release
at
`/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-releases/77055fc8acf8-20261003T000251Z`
has no release receipt or staging token and has the same permanent
ineligibility. Both releases remain untouched. The earlier v1 and v2 runners
remain permanently retired.

## Frozen dependency candidate

- Laravel changes only from `12.69.0` to `12.69.1`.
- Composer lock: `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`
- Vendor: `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8`
- Vendor ownership/mode: `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d`
- Complete vendor inventory: `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5`
- Executable allowlist: `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154`
- Bootstrap cache: `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`
- Application autoload set: `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91`
- Runtime source CAS: `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f`

## Required v4 control

Independent review accepted the OPcache timing correction in local predecessor
`25fa7c737e969f8dffa251fd5170f6c7064c69f5`, but rejected its post-mutation
emergency path. If PHP-FPM became unavailable after dependency mutation while
the original front controller was live, that predecessor required a fresh FPM
probe before installing the gate and could stop with candidate dependencies
still live. This replacement corrects that final blocker without changing the
accepted dependency candidate.

The shared front-controller transition primitive must apply the same
monotonic PHP-FPM OPcache revalidation barrier to initial installation,
reassertion, containment, original restoration, and recovery. It may start
only after the exact replacement bytes and `1000:1000/0644` metadata are
verified and the durable `installed` transition is fsynced.

A PHP-FPM SAPI probe must freeze `opcache.enable`,
`opcache.validate_timestamps`, `opcache.revalidate_freq`, and
`opcache.file_update_protection`. Both OPcache and timestamp validation are
required to be enabled. The delay must be at least five seconds and strictly
exceed the complete derived revalidation interval. It includes two complete
`opcache.revalidate_freq` opportunities, file-update protection, and a
one-second integer-clock margin. Unsafe or unknown values stop before gate
installation and require a separately reviewed PHP-FPM reload plan.

After the barrier, the runner must reverify the exact gate, require two unique
cache-busted direct-origin responses, then one separately cache-busted public
Cloudflare response. Each must return the reviewed status, header, sentinel,
and request nonce. The origin peer must be exactly `127.0.0.1:443`; the public
peer must be a global address on port 443 with one Cloudflare `Server` and
`Cf-Ray` identity. Curl configuration, proxy variables, PHP ini overrides,
and other caller environment are excluded through fixed child environments.
Exact gate identity is checked again afterward. Original
restoration receives the same barrier before normal-health verification.

Raw HTTP headers remain private mode `0600`; redacted review derivatives keep
status and header names while replacing cookie values. A future separately
authorized restricted stage must bind the effective nginx server block and
document root `/var/www/buy-dtf/public` into its release receipt before any gate
installation can be authorized.

Pre-mutation gate installation remains strict: it always requires a current
live PHP-FPM probe that exactly matches the staged envelope. The runner repeats
that probe immediately before the durable dependency-mutation boundary and
writes a private, fsynced receipt binding the exact release receipt, helper,
envelope, and calculated policy.

After dependency mutation only, a separate emergency path may use that staged
and immediately rechecked envelope if the live FPM probe is unavailable. The
fallback accepts only the exact original front controller or exact reviewed
gate with reviewed metadata, validates the private receipt and durable state
with explicit deployment errors, installs or reasserts the exact gate, and
completes a new full monotonic revalidation wait. A reachable but changed or
malformed FPM response never qualifies for fallback. Missing, malformed,
mismatched, or misplaced frozen evidence fails closed. If either origin or
public HTTP gate verification then fails, the exact gate remains installed and
the boot-independent Laravel 12.69.0 dependency rollback continues.

The nginx identity must also prove that the effective `buy-dtf.com`
`/index.php` route uses `unix:/run/php/php8.2-fpm.sock` and resolves
`SCRIPT_FILENAME` to `/var/www/buy-dtf/public/index.php`. The normalized
selector, handler block, socket, filename expression, resolved filename, and
route hash are bound into the future staging receipt. Socket, handler, route,
or filename ambiguity fails closed.

The reviewed capture invokes only
`/usr/bin/sudo -n -- /usr/sbin/nginx -T` from the non-root runner. It freezes
the root-owned, non-writable sudo/nginx identities and nginx version/build
identity, reconstructs dumped include context, rejects nested roots, aliases,
unsafe TLS listeners, and routes that cannot serve `127.0.0.1:443`, and keeps
the raw dump at mode `0600`. The runner makes no sudoers change. Missing
noninteractive permission fails closed before candidate construction or an
initial gate install. After dependency mutation, emergency containment installs
the exact local gate first; unavailable nginx route proof is recorded while the
boot-independent rollback continues behind the retained gate.

## Preserved database and capability envelope

The correction preserves schema
`5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`
and the 21-row migration ledger
`f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`.
The `savedimages.item_meta` and incoming-order migrations remain recorded
exactly once. `savedimages.item_meta` remains nullable `TEXT` with zero
non-null rows. `incoming_order_jobs` and `api_asset_records` retain definition
SHA-256 `aa0a038110dc355ffcd0ed12768c2adb7b0954ecbcc9aeb0fc4ef0efb5d287dc`
and zero rows. Queue and failed-job counts remain zero, the receiver,
job-label, and retention capabilities remain disabled, and the artwork-host
allowlist remains empty. Every future stage, cutover, monitor, rollback, and
recovery check must fail closed on drift.

## Required validation and next boundary

Re-run the production-like nginx/PHP-FPM OPcache rehearsal, all gate transition
and interruption scenarios, rollback/recovery, database-envelope, log-parser,
candidate, Composer, application, npm, frontend, and deterministic build checks.
Preserve the exact Laravel 12.69.0 rollback lock, vendor, and cache.

Only operations-control files, their local evidence, and the
`.gitattributes` rules that preserve v4 evidence bytes may change from the
reviewed base.

The immediate predecessor for this replacement is
`25fa7c737e969f8dffa251fd5170f6c7064c69f5`. This replacement remains local
and unpushed. It made no further production access; the earlier four-session
read-only boundary incident remains disclosed above as cumulative history.

Return the local branch, commit, hashes, receipts, and revised plan for
independent review. A later restricted Phase 1 requires separate authorization
and must create a new private v4 release receipt. Any v4 cutover requires a
further evidence-bound authorization.

Keep the receiver, job-label, and retention capabilities disabled and the
artwork-host allowlist empty. Do not change ShopNLTees, transparency, retention,
customer deletion, customer artwork, schema, application source, or
configuration. Transparency commit
`3db18d1fff3f599299eecd2aae21b9102fc45540` remains unstaged and non-stageable
with `DEPENDENCY_ENVELOPE_FROZEN = False`.
