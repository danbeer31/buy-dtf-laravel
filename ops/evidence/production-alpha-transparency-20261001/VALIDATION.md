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

- `php vendor/bin/phpunit`: 181 tests, 1,717 assertions, PASS.
- Focused transparency/flow matrix: 12 tests, 642 assertions, PASS.
- PHP syntax: 12 changed/new PHP files, PASS.
- Laravel Pint check: 10 in-scope formatted files, PASS. The two legacy-style
  application files were kept narrowly diffed rather than mechanically
  reformatting unrelated code.
- `composer validate --strict`: PASS.
- Exact approved live Composer lock
  `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`:
  zero production advisories.
- `npm audit --omit=dev`: zero vulnerabilities.
- `npm run build`: PASS (existing Sass deprecation and stale Browserslist-data
  warnings only).
- `git diff --check`: PASS.
- Fixture manifest: 8/8 PASS.
- Render-evidence manifest: PASS.

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
