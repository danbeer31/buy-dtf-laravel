# V4 validation record

Status: **local validation passed; independent review required; NO-GO for
production access, restricted staging, cutover, or deployment**.

The four-session read-only preparation boundary incident is disclosed in
`ROOT_CAUSE.md`; it made no production mutation and produced no eligible stage
evidence. Every validation result below is local.

| Check | Result | Evidence |
|---|---|---|
| Operations-only scope from reviewed base | pass | `preparation-scope-verification.json` |
| V3 runner/helper/release retirement enforced | pass | `laravel_remember_cookie_retired_controls.json`, runner tests |
| Shared post-fsync monotonic wait | pass | gate helper tests and gate rehearsal |
| Initial install, reassertion, containment, restoration, recovery coverage | pass | 28-scenario gate receipt; 48 wait records |
| Interrupted wait cannot authorize probe | pass | root/UID1000 suites |
| FPM SAPI directive shape and conflict validation | pass | environment-control receipt; 6 tests |
| `validate_timestamps=0` and unsafe values rejected pre-mutation | pass | environment and gate policy tests |
| Exact nginx route/root parser | pass | environment-control receipt; 10 tests |
| Nginx raw capture private and summary redacted | pass | environment-control tests |
| Two origin probes plus public probe use unique identities | pass | gate tests and OPcache rehearsal |
| Raw HTTP evidence mode `0600` and cookie redaction | pass | gate tests and privacy receipt |
| Warmed original immediate stale HTTP 200 reproduced | pass | production-like OPcache receipt |
| Waited exact gate responses | pass | production-like receipt: 503/503/503 |
| Warmed gate immediate stale 503 after restoration reproduced | pass | production-like receipt |
| Waited original health restored | pass | production-like receipt: 200/200 |
| Hardened 11-second formula repeatability | pass | primary plus two repeats; stable invariant match |
| One-package Laravel lock delta | pass | `lock-delta.json` |
| Two deterministic candidate builds | pass | build A/B and comparison receipts |
| Candidate vendor/mode/inventory/autoload/cache identities | pass | build and vendor policy receipts |
| Composer strict validation | pass | both build logs |
| Locked `--no-dev` audit | pass | both builds: zero advisories |
| PHP 8.2.30 platform proof | pass | platform receipt and captured outputs |
| Package discovery and route discovery | pass | both builds; 178 routes |
| UID/GID 33 vendor read/no-write | pass | both builds |
| Stale remember cookie falls through as guest | pass | 2-test authentication receipt |
| Valid remember-me authentication | pass | 2-test authentication receipt |
| Complete application suite | pass | 110 tests, 718 assertions |
| Npm clean install and frontend build | pass | frontend receipt; both exit 0 |
| Database envelope drift rejection | pass | database receipt; 9 tests |
| Complete-entry Laravel log policy | pass | parser receipt; 22 tests |
| Redacted benign 56-entry fixture | pass | parser receipt |
| Severe/genuine/stale-cookie/invalid/unparsed failures rejected | pass | parser receipt |
| Root control suite | pass | 114 tests, 112 passed, 2 expected skips |
| UID 1000 control suite | pass | 114 tests, 111 passed, 3 expected root-only skips |
| Atomic dependency rehearsal | pass | 25 scenarios |
| Python/PHP/JSON syntax | pass | `syntax-validation.txt` |
| Transparency pre-freeze state | pass | `transparency-prefreeze-verification.txt` |

## Frozen control identities

| Control | SHA-256 |
|---|---|
| Runner | `e2d735c9c9c86c8bd38be3085b3372a2d2079ada9866d87487e8aa486dfc79f0` |
| Gate helper | `ae542dbe387406d5b0e0d379f074251d30e93d066f330c1badb16b11caf776bc` |
| FPM probe | `b8b34f87d45a0c000cc0df7917496631320cfbdcca1ff44bc41741ce0d569262` |
| Nginx identity helper | `4beb1fd5e4fabb8d74d2de50b8c96f452ecb6de242ed411c7c0a97304037d192` |
| Runtime helper | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| Database validator | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| Log parser | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |
| Handoff | `8ee888883bf2330c7a5c7d70efe48244122b600067ba030976a53cbe0009e4c1` |

The production-like rehearsal uses local PHP-FPM 8.3.6 to exercise stale
OPcache behavior. The distinct PHP 8.2.30 receipt proves the candidate platform.
Future production FPM values and nginx route identity must be captured fresh in
a separately authorized restricted stage; no current production capture is
claimed.

`evidence-manifest.json` and `SHA256SUMS` are the final inventories. Restricted
staging and every later mutation remain separately authorized review gates.
