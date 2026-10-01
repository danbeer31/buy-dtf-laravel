# Production alpha transparency repair deployment plan

Status: review only; do not deploy.

## Scope

This is a source-only repair. It changes the cart upload, team-customization,
and ordinary production preparation paths. It has no migration, dependency,
environment, cache, service, ShopNLTees, retention, customer-deletion, or
incoming-order capability action. Incoming-order receiver, job-label, and
retention capabilities remain disabled and the artwork-host allowlist remains
empty.

Reviewed production source paths:

- `app/Helpers/ImageHelper.php`
- `app/Helpers/ProductionHelper.php`
- `app/Http/Controllers/CartController.php`
- `app/Http/Controllers/TeamCustomizationController.php`
- `app/Models/DtfImage.php`

New cart uploads preserve the exact PNG, SVG, or PDF bytes under private local
storage. The public cart PNG remains an alpha-preserving preview. A versioned
item policy applies threshold 128 only while creating the temporary production
PNG. Team-customization source renders are likewise left unchanged. Existing
records without that policy retain the legacy production call signature and
behavior. Incoming-order production continues through its separate
aspect-safe derivative path and is not opted into this policy.

## Reviewed deployment sequence

1. Freeze and independently review the exact commit and a manifest covering
   the five changed application paths. Confirm a clean branch, full tests,
   audits, frontend build, fixture manifest, and render-evidence manifest.
2. Run a read-only production preflight: exact source CAS and dependency
   identities, healthy authenticated/public endpoints, queues, failed jobs,
   scheduler/Stripe status, free deployment locks, static gate inactive,
   capabilities disabled, and artwork hosts empty. Stop on drift.
3. Stage only the reviewed application files in a new private release
   directory. Verify owner, mode, byte count, SHA-256, PHP syntax, and the
   staged test receipt. Do not stage `vendor`, Composer locks, configuration,
   bootstrap cache, or migrations.
4. Create exact backups and a receipt for the five live application paths.
   Recheck each expected-live hash immediately before mutation.
5. During a separately approved low-traffic window, install the reviewed 0644
   boot-independent static gate and verify it locally and through the public
   endpoint.
6. Atomically replace only the five reviewed application files on the same
   filesystem. Record installed hashes before any Laravel command or probe.
7. Run PHP syntax and FPM/runtime probes, then restore the exact original front
   controller and verify home, `/up`, login, cart, authenticated order views,
   queues, and capabilities. Do not enable a capability or alter configuration.
8. Complete a 30-minute monitor with invariant health, zero unexpected queue
   growth, gate/maintenance inactive, and the deployment lock free. A real
   customer upload is not part of the deployment authorization; any synthetic
   write smoke test requires separate explicit approval.

## Rollback

Before public reopening, any failure retains the static gate and restores the
exact five backed-up files with hash verification; no database or customer
asset rollback is needed. After public reopening, first identify any new
`dtfimages` rows carrying `alpha_processing.version=1`. Preserve those rows and
their private originals; never delete customer data as rollback. Restore the
five files under the static gate, verify exact hashes, and place any such new
rows on production hold for manual review because legacy code will ignore the
deferred policy. Reopen only after source identity and health checks pass.

No rollback step drops tables, changes the incoming-order ledger, removes
original customer files, changes dependencies, or restarts services.
