# Laravel 12.69.1 remember-cookie dependency plan v4

Status: **independent review required; NO-GO for further production access,
restricted staging, cutover, deployment, or recovery**.

One delegated audit exceeded the local-only boundary on 2026-10-03 with four
short read-only SSH sessions. It ran UID/GID checks and plain `nginx -T` with
configuration stdout discarded. No sudo, application request, retained config
dump, secret/cookie/customer data, mutation, deployment, reload/restart,
migration, source/dependency exchange, or capability action occurred; normal
SSH/audit logging may have recorded the connections. The access was stopped
and disclosed. All remaining implementation and evidence work is local.

Branch: `fix/laravel-12.69.1-remember-cookie-v4-20261003`

Reviewed base: `e7c839947a5bdf49776dd184926a28d0756196ae`

Immediate reviewed predecessor:
`25fa7c737e969f8dffa251fd5170f6c7064c69f5`

This revision corrects the PHP-FPM OPcache revalidation control exposed by
the failed v3 cutover. It does not change the accepted Laravel 12.69.1
dependency candidate, application source, production schema, configuration,
or capabilities.

Independent review accepted that predecessor's OPcache timing control but
found one post-mutation containment defect: a missing live FPM probe while the
original front controller was serving could stop before installing the gate or
rolling dependencies back. This replacement keeps live FPM proof mandatory
before mutation and adds a receipt-bound emergency path after mutation.

## Permanently retired controls

The following controls are historical evidence only and are permanently
ineligible for staging, cutover, finalization, rollback mutation, recovery
mutation, or release promotion:

| Artifact | SHA-256 | Reason |
|---|---|---|
| v1 runner | `2cae23d816e358c91ce512da4b3db3ee4e7fdff268c51afddafb0995b2feef9e` | Failed restricted stage; previously retired |
| v2 runner | `a7657bbfea760be186301503c567042f76739c2954fffbfc76f31c9f4eefede5` | Superseded after independent control review |
| v3 runner | `97cb4e8d702b7ceb1b9efde26dba93e6e0f4a833bb55650843fed1c0746f0307` | Missing shared FPM OPcache revalidation wait |
| v3 gate helper | `1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80` | Missing shared FPM OPcache revalidation wait |
| v3 release receipt | `ec16a6d017847401ee51a923afe9391a94a82f906f68e69db496db6f617f3b21` | Bound to retired v3 controls |

The v3 release at
`/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-v3-releases/77055fc8acf8-20261003T043715Z`
may remain untouched as private evidence. It cannot be reused, altered,
promoted, or accepted by v4. The consumed v3 cutover authorization cannot be
reused, and this preparation does not issue a v4 staging or cutover token.

The earlier failed-stage partial release at
`/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-releases/77055fc8acf8-20261003T000251Z`
has no release receipt or staging token. It also remains untouched and is
permanently ineligible for cutover, recovery, reuse, alteration, deletion, or
promotion. Neither retained release is an input to v4.

The authoritative machine-readable record is
`ops/deployment/laravel_remember_cookie_retired_controls.json`. The future v4
runner, describe output, evidence manifest, and release receipt must bind its
SHA-256 and fail closed if a retired receipt or control identity is supplied.

## Accepted candidate identities

These identities remain unchanged and must be reproduced by two clean v4
builds:

| Candidate component | Accepted identity |
|---|---|
| Laravel | `12.69.1` |
| Composer lock | `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d` |
| Vendor content/mode manifest | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Vendor ownership/mode identity | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Complete vendor inventory | `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5` |
| Executable allowlist | `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154` |
| Application autoload set | `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91` |
| Bootstrap cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Runtime source CAS | `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f` |

The sole lock movement remains `laravel/framework` 12.69.0 to 12.69.1. The
candidate vendor remains 6,460 files, 925 directories, and 26,481,661 bytes,
with 126 application entries in each optimized Composer file, ten approved
executables, no `.bat` proxies, and the accepted UID/GID and mode policy.

The exact rollback set remains Laravel 12.69.0 lock
`22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`,
vendor
`7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`,
and bootstrap cache
`468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.
The original front controller remains
`eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9`,
mode `0644`, UID/GID `1000:1000`.

## Preserved production envelope

The v4 operations correction does not alter the database, queues,
capabilities, or their reviewed invariants. A future restricted stage,
cutover, monitor, rollback, or recovery check must require all of these exact
conditions:

- schema SHA-256
  `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`,
  database-name SHA-256
  `9566898c6940c2248e1e0ee02d8460bfb42d6b407d3108ad60044bab86ac4567`,
  with 36 tables, 411 columns, 76 statistics, 46 table constraints, 49 key
  column usages, and 2 referential constraints;
- a 21-row migration ledger with SHA-256
  `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`;
- `2026_10_01_120000_add_item_meta_to_savedimages_table` recorded exactly
  once, with `savedimages.item_meta` at ordinal position 12 as nullable
  `TEXT`, no default, no extra or generation expression, `utf8mb4` character
  set, `utf8mb4_unicode_ci` collation, and zero non-null rows;
- `2026_09_27_120000_create_incoming_order_v1_tables` recorded exactly once;
- `incoming_order_jobs` and `api_asset_records` matching definition SHA-256
  `aa0a038110dc355ffcd0ed12768c2adb7b0954ecbcc9aeb0fc4ef0efb5d287dc`,
  with zero rows in both tables and exactly these indexes: `PRIMARY`,
  `incoming_order_jobs_dtfimage_id_unique`,
  `incoming_jobs_client_key_unique`, `incoming_jobs_state_lease_index`,
  `incoming_jobs_label_status_index`,
  `incoming_jobs_production_state_index`,
  `incoming_jobs_production_lease_index`,
  `api_assets_job_role_path_unique`, `api_assets_retention_index`, and
  `api_assets_path_hash_index`;
- queue and failed-job counts of zero;
- the incoming-order receiver, job-label, and retention capabilities disabled;
  and
- an empty artwork-host allowlist.

Any drift fails closed before mutation. Preparation must not query production
again; these conditions are frozen inputs for a separately authorized future
stage.

## V4 control boundary

Only operations-control files, their local review evidence, and the
`.gitattributes` rules needed to preserve the v4 evidence bytes may change.
The final scope receipt must compare v4 with commit
`e7c839947a5bdf49776dd184926a28d0756196ae` and prove no changes to
`composer.json`, `composer.lock`, application source, configuration,
database definitions or migrations, public assets, routes, dependency
manifests, frontend source, customer artwork, or capability flags.

During preparation:

- do not access production, stage, deploy, cut over, recover, migrate, run
  migration pretend, restart services, or alter configuration;
- do not modify, delete, reuse, or promote any retained release;
- keep the incoming-order receiver, job-label, and retention capabilities
  disabled and the artwork-host allowlist empty;
- make no ShopNLTees, retention, customer-deletion, customer-artwork, or
  transparency change; and
- keep transparency commit
  `3db18d1fff3f599299eecd2aae21b9102fc45540` clean, unstaged, and
  non-stageable with `DEPENDENCY_ENVELOPE_FROZEN = False`.

## PHP-FPM OPcache envelope

A dedicated hash-bound PHP helper must run through the reviewed PHP-FPM
socket and prove `PHP_SAPI` is `fpm-fcgi`. It reads and freezes these effective
SAPI values:

- `opcache.enable`;
- `opcache.validate_timestamps`;
- `opcache.revalidate_freq`; and
- `opcache.file_update_protection`.

The probe must reject missing, malformed, negative, or contradictory values.
Both `opcache.enable` and `opcache.validate_timestamps` must be enabled. If the
effective FPM settings cannot guarantee path revalidation, the runner stops
before installing the gate and requires a separately reviewed PHP-FPM reload
plan. A CLI OPcache operation is never accepted as evidence for the FPM
instance.

For integer SAPI values, the reviewed conservative delay is:

```text
max(5, 2 * opcache.revalidate_freq + opcache.file_update_protection + 1) seconds
```

The second frequency window ensures that a first timestamp check which still
observes a protected replacement cannot authorize an HTTP probe. The
additional second is the reviewed integer-clock safety margin. A larger known
interval is acceptable only when the calculated delay exceeds it and the exact
values and calculation are frozen in the restricted-stage receipt. Unknown
values fail closed.

Every front-controller transition uses one shared wait primitive. The wait
starts only after all of these events have completed:

1. replacement bytes, UID/GID, and `0644` mode are verified;
2. `os.replace` completes and the parent directory is fsynced;
3. the live replacement identity is re-read and matches; and
4. the durable `installed` transition is atomically written and fsynced.

The wait receipt records the configured and calculated delay, monotonic
start/end and elapsed duration, UTC start/end, earliest allowed probe time,
the frozen FPM envelope, transition sequence, and exact front-controller
identity before and after the wait. An interrupted or incomplete wait cannot
authorize a probe; recovery begins a new complete wait.

The same primitive applies to initial gate installation, gate reassertion,
rollback containment, pre-mutation original restoration, post-rollback
restoration, and explicit recovery. Original health is never probed before
the restoration wait and final identity check complete.

### Post-mutation emergency envelope

The staged FPM envelope is checked again immediately before the durable
dependency-mutation boundary. The runner writes and fsyncs a private receipt
that binds the staged release receipt, FPM probe helper, complete normalized
envelope, derived policy, and exact equality with the current live FPM SAPI.
Dependency mutation cannot begin until that receipt exists.

Pre-mutation gate installation always re-reads FPM and never uses frozen-only
evidence. After mutation, a separate emergency primitive may fall back to the
staged and immediately rechecked envelope only when the live FastCGI probe is
unavailable. It rejects a reachable but changed or malformed response. It also
rejects missing, malformed, mismatched, nonprivate, relocated, or altered
receipt evidence with an explicit `DeploymentError`.

The emergency path accepts only the exact reviewed original front controller
or exact reviewed gate with `1000:1000/0644` metadata. It installs or reasserts
the exact gate, performs the complete shared monotonic wait, records durable
containment, and continues the boot-independent rollback. If gate HTTP
verification fails after mutation, it retains the exact gate and still restores
the Laravel 12.69.0 lock, vendor, and cache set.

## Gate and HTTP verification

After the wait, the runner verifies the exact v4 gate bytes, SHA-256,
UID/GID, and mode before network traffic. It then performs:

1. direct-origin probe 1 through loopback, bypassing Cloudflare;
2. independent direct-origin probe 2 through loopback; and
3. a public Cloudflare probe.

Each request has a unique cryptographic cache buster bound into its receipt.
Each result must identify its expected route and its own cache buster, return
HTTP 503, and contain the exact reviewed maintenance header and body
sentinel. A cached Laravel response, a response from another route, or a
reused probe identity fails. Direct-origin peers must be exactly
`127.0.0.1:443`; the public peer must be global port 443 and carry exactly one
Cloudflare `Server` and `Cf-Ray` identity. Curl configuration and proxy
environment are disabled, and all PHP-FPM, PHP CLI, nginx, and health probes
receive fixed child environments without inherited application, ini, cookie,
proxy, or loader overrides. After both route classes pass, the runner reads
and verifies the exact live gate identity again.

HTTP evidence lives beneath the private operations directory. Raw headers
and bodies are regular files at mode `0600`. A review derivative preserves
status and header names while replacing the values of every `Cookie` and
`Set-Cookie` header. Raw cookie values may never appear in Git, review notes,
chat, or the redacted evidence manifest.

## Effective nginx route identity

The future restricted stage captures the effective nginx configuration
read-only with the exact noninteractive command
`/usr/bin/sudo -n -- /usr/sbin/nginx -T`; the runner itself remains non-root.
The receipt freezes root-owned, non-writable sudo/nginx executable metadata,
nginx version/build identity, the complete effective-configuration hash,
selected HTTPS server-block identity, server name, listen route, document-root
text, and resolved path. It also proves that the effective `buy-dtf.com`
`/index.php` request selects a PHP handler with
`fastcgi_pass unix:/run/php/php8.2-fpm.sock` and resolves its exact-case
`SCRIPT_FILENAME` parameter to `/var/www/buy-dtf/public/index.php`. The receipt
binds the location selector and order, handler-block hash, socket, source
expression, resolved filename, and route-identity hash. No sudoers change is
part of this candidate. Existing
noninteractive permission is a stage prerequisite; its absence fails closed
before candidate construction or an initial gate installation. The accidental
read-only probe used plain non-root `nginx -T`, captured no configuration, and
is not staging evidence.

Exactly one reviewed production route for `buy-dtf.com` must resolve its
effective document root to:

```text
/var/www/buy-dtf/public
```

The parser reconstructs dumped include context and requires TLS on the same
IPv4 wildcard or loopback port-443 listener used by the direct-origin probe.
An absent, ambiguous, variable, aliased, nested, included, or different root
fails before gate installation. Raw nginx output remains private at mode `0600`;
the review package contains only its hashes and normalized redacted result.
The cutover preflight repeats the proof and requires equality with the staged
release receipt.

Initial installs require that proof before mutation. If a capture becomes
unavailable only after dependency mutation, emergency containment first
installs or reasserts the exact gate and completes its OPcache barrier. The
route-proof failure is recorded, the gate stays closed, and boot-independent
rollback continues.

## Required local validation

The v4 review package must include:

- a production-like nginx/PHP-FPM rehearsal with OPcache enabled, timestamp
  validation enabled, and a nonzero revalidation frequency;
- proof that a warmed original can return the immediate stale 200 after an
  atomic gate install, while waiting the reviewed interval produces the exact
  gate 503/header/sentinel;
- proof that restoring the original after FPM executed the gate, then waiting
  the same interval, produces normal application health;
- pre-install rejection of `opcache.enable=0`,
  `opcache.validate_timestamps=0`, unknown values, and an inadequately
  calculated larger interval;
- monotonic-delay coverage for initial cutover, rollback containment, gate
  reassertion, pre-mutation restoration, and recovery;
- two unique direct-origin probes plus the unique public probe, with negative
  controls for cached Laravel, reused cache busters, and a gate response from
  the wrong route;
- private mode-`0600` raw HTTP evidence, complete cookie redaction, and a scan
  proving raw cookie values are absent from every tracked artifact;
- every existing interruption, durable-transition, exact-restoration,
  ownership/mode, UID/GID 33 readability, rollback, recovery,
  database-envelope, Laravel-log parser, and candidate-validation test; and
- a deterministic rehearsal receipt and complete checksum manifest.

Re-run both clean candidate builds and reproduce every accepted candidate
identity. Re-run PHP 8.2.30 platform validation, Composer strict validation,
the locked `--no-dev` zero-advisory audit, package discovery, 178-route
discovery, UID/GID 33 vendor access, remember-cookie regression tests, the
complete application suite, npm clean install, frontend build, runner tests,
gate tests, database-envelope tests, log-parser tests, and all atomic
cutover/rollback/recovery rehearsals.

The local evidence directory is
`ops/evidence/laravel-remember-cookie-runner-v4-20261003/`. It must contain
the root-cause receipt, retired-control identity, FPM probe and policy proof,
nginx parser proof, production-like gate rehearsal, deterministic gate and
atomic receipts, build receipts, complete tests, scope proof, artifact
identities, validation notes, an evidence manifest, and final `SHA256SUMS`.
No production-derived raw header or cookie value belongs in that directory.

## Future restricted Phase 1

Restricted staging remains prohibited until the v4 branch, commit, runner,
gate helper, FPM probe, nginx proof, evidence package, and checksum manifest
pass independent review. A later written authorization must bind the exact
reviewed v4 commit and staging token.

When separately authorized, Phase 1 will:

1. prove the remote tip, clean worktree, and every reviewed control hash;
2. run the complete read-only production preflight against Laravel 12.69.0,
   including source, lock, vendor, cache, front controller, configuration,
   services, processes, health, database envelope, queues, disabled
   capabilities, empty allowlist, and free locks;
3. capture and freeze the effective PHP-FPM OPcache envelope and calculated
   wait without changing FPM;
4. capture and validate the effective nginx route and exact document root;
   bind the reviewed PHP-FPM socket and resolved `SCRIPT_FILENAME` identity in
   the release receipt;
5. create only a new private v4 shadow release beneath a new v4 release root;
6. reproduce the exact accepted Laravel 12.69.1 lock, vendor, ownership/mode,
   inventory, autoload, cache, source, platform, discovery, route, and audit
   identities; and
7. write new v4 database-envelope and release receipts, prove production
   remained unchanged, and stop for independent review.

Phase 1 does not install the gate, enter maintenance, exchange dependencies,
replace the live lock, deploy source, restart services, run migrations, or
enable capabilities. The v3 release and receipt are rejected even if their
bytes remain intact.

## Future cutover, rollback, and recovery

A v4 cutover requires a second independent review and a separate written
authorization bound to the exact new v4 release receipt. No cutover token is
issued by this plan.

The future cutover repeats the complete baseline, FPM envelope, nginx root,
release, database, queue, capability, process, and health checks before any
front-controller mutation. It installs the exact reviewed v4 gate, performs
the shared monotonic wait, requires the two origin probes and public probe,
drains active requests, and repeats the source, dependency, and database
checks under the gate. It then exchanges only the reviewed vendor, skips the
identical cache exchange, replaces only `composer.lock`, performs candidate
CLI and two FPM proofs, restores the original through the same wait control,
and verifies the complete health matrix.

The 30-minute monitor and rotation-safe Laravel log review remain unchanged
in policy. Automated success stops at `awaiting_independent_log_review`.
Finalization requires a separate evidence-bound independent review and
authorization.

Before dependency mutation, any failure restores the exact original through
the shared wait and verifies normal health. After mutation begins, failure
uses the validated staging envelope and immediately pre-mutation receipt if a
fresh FPM probe is unavailable, retains or reasserts the exact gate through the
same wait, records durable containment, and runs the reviewed boot-independent
rollback to Laravel 12.69.0 even when HTTP gate verification is unavailable.
Recovery uses only the exact v4 durable state and a separately reviewed
recovery authorization. A reachable changed FPM envelope fails closed; the
emergency fallback never substitutes CLI OPcache manipulation.

The transparency dependency envelope may be frozen only after Laravel
12.69.1 is successfully deployed, its monitor passes, and independent log
review finalizes the dependency deployment.
