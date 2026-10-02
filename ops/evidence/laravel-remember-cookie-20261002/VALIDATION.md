# Validation record

All results below belong to the review-only Laravel `12.69.1` candidate. No
stage or deployment command was run.

| Check | Result | Evidence |
|---|---|---|
| Exact-live lock resolution | two fresh runs produced `77055fc8…`; one package updated | `composer-resolution.txt`, `composer-resolution-replay.txt`, `composer-lock.diff` |
| Exact `12.69.0` regression | stale cookie reproduced HTTP 500 / `hash_equals()` TypeError; valid cookie passed | `baseline-regression.txt` |
| Candidate regression | 2 tests, 10 assertions passed | `candidate-regression.txt` |
| Full application suite | 110 tests, 718 assertions passed | `phpunit-full.txt` |
| Composer strict validation | passed | `composer-validation-audit.txt` |
| Composer locked audit | full and no-dev each report zero advisories | `composer-validation-audit.txt` |
| Local platform check | passed on PHP `8.3.6` | `composer-validation-audit.txt` |
| PHP `8.2.30` lock compatibility | no locked package prohibits it | `php-8.2.30-prohibits.txt` |
| Exact production platform check | required during a future authorized stage | staging plan |
| Deterministic vendor/cache | two empty builds have byte-identical receipts | `deterministic-build-a.json`, `deterministic-build-b.json` |
| Runner unit suite | 6 tests passed | `runner-unit-tests.txt` |
| Atomic failure rehearsal | 23 scenarios passed | `local-atomic-rehearsal-receipt.json` |
| PHP/Python syntax | passed | `syntax-validation.txt` |
| npm production audit | zero vulnerabilities | `frontend-validation.txt` |
| Vite build | 112 modules transformed; existing Sass warnings only | `frontend-validation.txt` |
| npm development audit | unchanged lock reports 14 advisories: 1 low, 2 moderate, 9 high, 2 critical | `npm-ci.txt` |

The runner rehearsal covers success, failure between vendor/cache and
cache/lock transitions, a completely unbootable candidate, interruption at all
eight cutover transitions, interruption at all eight rollback transitions,
stale gate state, stale dev-provider cache replacement, and rollback health
failure. Every injected cutover failure restores the retained lock, vendor,
cache, and front controller.

The future 30-minute monitor checks health and runtime identity. It does not
parse Laravel logs. Independent cutover acceptance must therefore also review
a read-only Laravel log delta for the `SessionGuard` / `hash_equals()` failure
and for new exceptions, traces, fatal errors, `SQLSTATE`, missing classes, or
missing views.
