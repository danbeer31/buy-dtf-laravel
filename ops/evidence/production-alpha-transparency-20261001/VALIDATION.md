# Validation receipt

Date: 2026-10-01 (America/Chicago)

## Runtime used

- PHP 8.3.6
- Laravel 12.69.0 from the exact approved production dependency generation
- Imagick extension 3.7.0
- ImageMagick 6.9.12-98 Q16
- GD 2.3.3
- PHPUnit 11.5.50

The repair worktree's ignored `vendor` directory was a physical local copy of
the approved dependency worktree vendor. It was not committed.

## Results

- `php vendor/bin/phpunit`: 189 tests, 1,799 assertions, PASS in one invocation.
- Focused transparency, admin-comparison, Saved Image, and migration matrix:
  20 tests, 724 assertions, PASS.
- Real admin comparison parity: PASS for policy and legacy records, including
  exact RGBA pixels, visible bounds, alpha set, pixel dimensions, and PNG
  300-PPI metadata against `ProductionHelper` output.
- Durable Saved Image policy: PASS for upload -> save -> delete only source row
  -> reuse, same-path cross-business isolation, deterministic newest owner-row
  fallback, and legacy no-policy behavior.
- Migration matrix: PASS for guarded/idempotent addition, wrong-connection
  refusal, data-preserving `down()`, isolated pretend, and exact MySQL grammar.
- PHP syntax: all eight candidate application/migration files and all three new
  regression files, PASS.
- Laravel Pint check: the five new/touched modern-style files, PASS. The
  legacy-style controllers and `DtfImage` were kept narrowly diffed rather than
  mechanically reformatting unrelated code.
- `composer validate --strict`: PASS.
- Exact approved live Composer lock
  `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`:
  zero production advisories.
- `npm audit --omit=dev`: zero vulnerabilities.
- `npm run build`: PASS (existing Sass deprecation and stale Browserslist-data
  warnings only).
- `git diff --check`: PASS.
- Fixture manifest: 8/8 PASS.
- Fresh deterministic render-evidence manifest: PASS with the approved visual
  comparison SHA-256
  `3cfb2f36cb51b8cf42f16ec8a8809658c38fd5bdb706bf3c38c23aff29387054`.

## Local runner freeze validation

The final local artifact freeze repeated the complete direct PHPUnit run:
**189 tests, 1,799 assertions, PASS** in 12:06.995. The Composer wrapper again
reached its documented 300-second process timeout during the long native-image
tests; the direct run completed every test without changing the test bootstrap
or skipping an assertion.

- Deployment-runner unit suite: 17 tests, PASS.
- Disposable rehearsal: 7/7 scenarios, PASS under umask `077` on a native
  Linux filesystem.
- Required failure matrix: pre-migration, migration, source swap, candidate
  check, post-reopen, and schema-preserving rollback, all PASS.
- Separate static-gate readability checks under `www-data`: PASS in every
  scenario.
- Candidate archive extraction and all eight target identities: PASS.
- PHP syntax for the seven replacement files, migration, and runtime probe:
  PASS.
- Fixture hashes: 8/8 PASS.
- Fresh render hashes: unchanged; comparison remains
  `3cfb2f36cb51b8cf42f16ec8a8809658c38fd5bdb706bf3c38c23aff29387054`.
- `composer validate --strict`: PASS.
- Exact approved production lock `22af12c7...`: zero production advisories.
- `npm audit --omit=dev`: zero vulnerabilities.
- `npm run build`: PASS with existing Sass/Browserslist warnings only.
- Sorted PHP extension evidence:
  `4c91e93322f2362e73ab2913a4b7d5118c84e671c0b5a5dbb471876880b9f4ef`.
- `git diff --check`: PASS.

The first filesystem rehearsal intentionally used the Windows-mounted local
workspace and stopped before mutation because its reported `0777` mode could
not satisfy the exact reviewed `0644` gate requirement. That fail-closed
evidence is preserved outside Git. The successful run used a disposable native
Linux filesystem and its raw 279-file evidence package is also preserved
outside Git; the committed receipts contain hashes and no logs, dumps, source
backups, credentials, customer data, or payment data.

The Composer `test` script delegates to PHPUnit but retains Composer's
300-second process timeout. The real maximum-field job-card render takes about
five minutes by itself on this Windows-mounted WSL workspace, so the wrapper
times out before the complete suite finishes. Direct PHPUnit is explicitly
allowed by `agent.md` and completed the entire suite in one invocation after
native-image tests were isolated from Imagick's process-global resource limit.
No assertion was skipped or weakened.

## Dependency-lock reconciliation note

The accepted receiver branch still carries historical lock
`eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831`.
That historical lock now reports four advisories. This repair intentionally
does not edit or deploy dependencies. Production already runs the separately
reviewed lock `22af12c7...`, whose audit is clean. Any future source deployment
must pin and preserve that exact live lock; it must not install the historical
branch lock.

## Safety assertions

- No migration, deployment, production access, configuration change, service
  restart, capability enablement, ShopNLTees change, retention action, or
  customer-deletion action occurred.
- `config/incoming_order.php` is unchanged: receiver and job-label defaults are
  false, retention defaults to false, and an unset artwork-host variable yields
  an empty allowlist.
- Existing records without the versioned alpha policy continue to call the
  legacy production-preparation signature.
- Incoming-order derivatives continue through the separate aspect-safe path;
  no incoming job receives the cart/team alpha policy.
- Incoming-order receiver, job-label, and retention capabilities remain
  disabled; the artwork-host default remains empty.
- `APPLICATION_MANIFEST.json` is local review evidence only. No production
  preflight, staging, migration pretend, backup, migration, source install, or
  deployment was performed.
