# Incoming-order v1 receiver re-freeze evidence

Date: 2026-09-30 (America/Chicago; evidence generated 2026-10-01 UTC)

Status: local re-freeze and validation passed. This evidence authorizes no receiver migration or deployment.

The receiver payload remains exact commit `0799440b7cbb0bad364fc2a65b41285f20245658`. The deployment runner is re-frozen from artifact branch tip `33337116556c28ce217869f74f66936b48a276ff` against the dependency identities already live after the separately reviewed security cutover:

- Composer lock: `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`.
- Vendor manifest: `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`.
- Bootstrap-cache manifest: `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.
- Re-frozen runner: `569f8aec08b8493d1544a9c1c84b0dca2e0efd74cd8385091cbff13796c6119c`.

`--describe` now explicitly says that a pre-mutation gate failure restores and health-checks the exact original front controller, while a failure after migration or source mutation retains the exact mode-`0644` gate in durable rollback containment.

All eight gate rehearsals passed under `umask 077`, including the separate UID/GID `33` reader, the unreadable mode-`0600` negative control, pre-mutation restoration paths, recovery paths, later-phase rollback gating, and the later-phase public-verification failure that retains the exact gate without writing an original-restoration receipt.

The full receiver suite passed against a disposable checkout containing the exact post-cutover Composer lock/vendor: 170 tests, 1,099 assertions, and the existing single Imagick-dependent skip under native PHP 8.2. The exact PHP extension lists are retained. Composer validation passed, the production dependency audit found no advisories, the npm production audit found no vulnerabilities, and the Vite production build transformed 112 modules. A real Linux/Imagick rerender reproduced both reviewed PNG hashes at 1500x900 and approximately 300 DPI.

No production access, staging, backup, maintenance, migration, live-source change, service restart, capability enablement, ShopNLTees change, retention action, or customer deletion occurred while this local receipt was generated.
