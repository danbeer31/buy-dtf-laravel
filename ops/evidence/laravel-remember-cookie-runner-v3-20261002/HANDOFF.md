# BuyDTF Laravel 12.69.1 Runner Control Correction Handoff

Independent review of branch `fix/laravel-12.69.1-remember-cookie-v2-20261002`, commit `cfaadedfda941e593a1ff7f1729ad8a461fdc0e7`, accepted the deterministic Laravel 12.69.1 build and vendor permission correction. Runner `a7657bbfea760be186301503c567042f76739c2954fffbfc76f31c9f4eefede5` is retired and must not be staged.

This handoff authorizes preparation and local rehearsal only. Do not access production, stage, deploy, cut over, run migrations, restart services, change configuration, enable capabilities, or modify either retained partial release.

## Accepted frozen identities

- Candidate lock: `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`
- Sole package change: Laravel `12.69.0` to `12.69.1`
- Candidate vendor: `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8`
- Vendor ownership/mode identity: `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d`
- Complete vendor inventory: `c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5`
- Executable allowlist: `551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154`
- Candidate/live cache: `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`
- Application autoload entry set: `342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91`
- Runtime source CAS: `3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f`

## Required controls

1. Enforce the exact production database envelope during staging preflight, after candidate construction, immediately before dependency mutation under the static gate, throughout monitoring, and during rollback/recovery:
   - schema SHA-256 `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`
   - 21 migration rows with ledger SHA-256 `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`
   - one target migration entry
   - `savedimages.item_meta` present as nullable `TEXT`, with zero non-null rows throughout this dependency-only stage, cutover, monitor, independent-review finalization, rollback, and recovery; legitimate growth is reserved for a later separately reviewed transparency source cutover
   - exact installed `incoming_order_jobs` and `api_asset_records` definitions, both with zero rows
   - any drift fails closed before mutation where applicable
2. Restore the reviewed static-gate transition protocol:
   - validate replacement bytes and `1000:1000/0644` before replacement
   - durably record and fsync `replacement_pending` before `os.replace`
   - durably record and fsync `installed` before verification
   - verify separate direct origin-loopback and public Cloudflare routes for exact route identity, HTTP 503, header, and body sentinel
   - before dependency mutation, restore the exact original plus metadata automatically on installation or verification failure, issue failure/restoration receipts, and verify normal health
   - after dependency mutation, retain or reassert the exact gate, durably record containment, and run rollback
   - base recovery on actual front-controller identity and durable transition history
3. Add a rotation-safe monitoring-period Laravel log delta:
   - fail on the stale `SessionGuard` / `hash_equals()` remember-cookie signature; `CRITICAL`, `ALERT`, and `EMERGENCY`; genuine exceptions, traces, fatal errors, `SQLSTATE`, missing classes/views; invalid UTF-8; and nonempty unparsed/orphan data
   - keep the reviewed redacted 56-entry checkout/Shippo diagnostic fixture nonfatal
   - retain raw log deltas only in private operational evidence and Git only redacted summaries/fixtures
   - do not mark deployment final until parsing and an independent read-only review both pass

## Validation and scope

Re-run both deterministic builds, PHP 8.2.30 platform proof, Composer strict validation/audit, package discovery, 178-route discovery, UID/GID 33 access probe, remember-cookie tests, application suite, runner tests, gate/schema/log scenarios, and atomic cutover/rollback/recovery rehearsals. Keep the Laravel 12.69.0 lock, vendor, and cache as the exact rollback set.

Return the corrected branch and commit, runner/helper/parser hashes, candidate identities, database/gate/log receipts, test results, and revised staging/cutover/rollback plan for independent review.

Do not stage or deploy. Restricted staging requires another independent review and separate authorization; cutover requires separate authorization after successful staging.

Keep transparency commit `3db18d1fff3f599299eecd2aae21b9102fc45540` non-stageable with `DEPENDENCY_ENVELOPE_FROZEN = False`. Keep incoming-order, job-label, and retention capabilities disabled. Make no transparency, ShopNLTees, migration, retention, or customer-deletion changes.
