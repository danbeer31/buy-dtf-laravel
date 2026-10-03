# V4 replacement validation record

Status: **local validation passed; independent review required; NO-GO for
production access, restricted staging, cutover, recovery, or deployment**.

| Check | Result | Evidence |
|---|---|---|
| Operations-control-only scope | pass | `preparation-scope-verification.json` |
| Current live FPM required before mutation | pass | runner and environment tests |
| Staged envelope rechecked immediately before mutation | pass | runner integration tests |
| Missing/malformed frozen emergency evidence rejected | pass | runner tests |
| Post-mutation FPM timeout with original live | pass | installs gate with frozen receipt and invokes rollback |
| Interrupted emergency wait | pass | a fresh complete monotonic wait is required |
| Post-mutation HTTP gate failure | pass | exact gate retained; boot-independent rollback invoked |
| Frozen-state assertion replaced with `DeploymentError` | pass | source/static review and tests |
| Nginx `/index.php` socket identity | pass | exact `/run/php/php8.2-fpm.sock` required |
| Nginx `SCRIPT_FILENAME` identity | pass | exact `/var/www/buy-dtf/public/index.php` required |
| Nginx socket/filename drift rejection | pass | 15 nginx identity tests |
| Shared post-fsync monotonic barrier | pass | 28 gate scenarios; 48 complete waits |
| Local nginx/PHP-FPM OPcache rehearsal | pass | three independent formal runs |
| Immediate stale original HTTP 200 reproduced | pass | each local rehearsal |
| Waited gate route verification | pass | 503/503/503 on each run |
| Immediate stale gate after restore reproduced | pass | each local rehearsal |
| Waited original health restoration | pass | 200/200 on each run |
| Cache-buster uniqueness/private raw evidence | pass | 9 unique nonces; mode `0600` |
| Root deployment-control discovery | pass | 123 tests; 121 pass; 2 expected skips |
| UID/GID 1000 discovery | pass | 123 tests; 120 pass; 3 expected skips |
| Atomic cutover/rollback/recovery rehearsal | pass | 25 scenarios |
| One-package Laravel lock delta | pass | Laravel 12.69.0 to 12.69.1 only |
| Two deterministic candidate builds | pass | exact path/content/mode/ownership identities |
| Candidate vendor structure | pass | 6,460 files; 925 dirs; 26,481,661 bytes |
| Composer strict validation | pass | both build logs |
| Locked `--no-dev` audit | pass | zero advisories in both builds |
| PHP 8.2.30 platform proof | pass | `php-8.2.30-platform-receipt.json` |
| Package and route discovery | pass | both builds; 178 routes |
| UID/GID 33 vendor read/no-write | pass | both builds |
| Stale remember-cookie regression/control | pass | 2 tests; 10 assertions |
| Complete application suite | pass | 110 tests; 718 assertions |
| Npm clean install/frontend build | pass | both exit 0 |
| Database-envelope drift rejection | pass | 9 tests |
| Laravel complete-entry log parser | pass | 22 tests; benign 56-entry fixture accepted |
| Genuine/stale/severe/invalid/unparsed logs | pass | all rejected |
| Python/PHP/JSON syntax | pass | `syntax-validation.txt` |
| Transparency pre-freeze state | pass | clean at `3db18d1...`; freeze remains false |
| Raw cookie/header privacy | pass | no raw HTTP evidence committed |
| Replacement correction production/network access | none | local summaries and scope receipt |

## Frozen replacement identities

| Control | SHA-256 |
|---|---|
| Runner | `464bd6a28c8bed84c90176d42bc88d22eea5977c2698d5cddb7fe3eca50f9558` |
| Gate helper | `b93c08f58a08333120369c1cc75c60631d621c3a8099ca3967065721c45679f5` |
| Nginx identity helper | `1243fea2757aca89f586ec4b322b0d23ee1e19b2d027c21bd6523e71e6e6e8e0` |
| FPM probe | `b8b34f87d45a0c000cc0df7917496631320cfbdcca1ff44bc41741ce0d569262` |
| Runtime helper | `7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2` |
| Database validator | `e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3` |
| Log parser | `b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179` |
| Handoff | `6539058cf602fc23b03552665faf9a32c6975e29e6cb11fb5b2deb2c7e02afa9` |

The local OPcache rehearsal uses disposable PHP-FPM 8.3.6 to exercise stale
path behavior with timestamp validation and a nonzero revalidation frequency.
The separate locked PHP 8.2.30 receipt proves the deployment candidate's
platform compatibility. A future restricted stage must capture the effective
production FPM and nginx route identities again and bind them into a new
release receipt.

The earlier cumulative four-session read-only boundary incident remains fully
disclosed. It produced no eligible staging evidence. This replacement
correction added no production or external-network access. The branch remains
local and unpushed.

`evidence-manifest.json` and `SHA256SUMS` are the final byte inventories.
Restricted staging and every later mutation remain separate review and
authorization gates.
