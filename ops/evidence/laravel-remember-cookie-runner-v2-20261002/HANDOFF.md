# BuyDTF Laravel 12.69.1 Runner Correction Handoff

Independent review accepts the failed-stage evidence and the production immutability proof at evidence commit `ac959e0fbf6ad9c6ae71531dbeb09ae2b9309917`. There are no evidence-package blockers. Production remained on Laravel 12.69.0 and is healthy.

The deployment remains NO-GO. Do not retry or modify the failed partial release.

## Permanently retired artifacts

- Runner: `2cae23d816e358c91ce512da4b3db3ee4e7fdff268c51afddafb0995b2feef9e`
- Reviewed vendor identity: `b8e0e3afa65171a66ad3d1875404fe209d7598c9b3f690e494d40c4fde4408f8`
- Partial-shadow vendor identity: `a3aa7915d64281bbe5ef318a9e36723d68fda46c95fd7a717cb142d829d63655`
- Partial release: `/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-releases/77055fc8acf8-20261003T000251Z`

The partial release has no release receipt or staging token and is permanently ineligible for cutover. Leave it untouched.

## Confirmed root cause

1. The runner generated optimized Composer autoload files before copying `app/` into the shadow. This omitted 126 application entries from each of `composer/autoload_classmap.php` and `composer/autoload_static.php`, accounting for 28,566 bytes.
2. The reviewed WSL build contained five Windows `.bat` proxies that native Linux did not generate, accounting for 693 bytes.
3. All 7,385 shared paths had different modes. The shadow was owned by UID/GID 1000 and used `0700/0600`. PHP-FPM runs as `www-data:www-data`; that tree would be unreadable after exchange and could cause an outage.

The complete 29,259-byte difference is accounted for.

## Authorized work

Prepare a replacement candidate and runner for independent review. Do not access production, stage, cut over, deploy, restart services, run migrations, alter configuration, enable capabilities, or modify the retained partial release.

The replacement must:

1. Copy the exact CAS-verified runtime source into the build shadow before Composer generates optimized autoload files. A final optimized dump after the source copy is acceptable only if it produces one clearly defined canonical result.
2. Assert that both optimized Composer files contain the expected 126 application entries.
3. Pin Composer proxy generation to the Unix result. The candidate must contain no `vendor/bin/*.bat` files. Do not install unzip/7z or preserve Windows proxies merely to reproduce the retired WSL identity.
4. Normalize the completed vendor tree before hashing:
   - Owner/group: `1000:1000`
   - 925 directories: `0775`
   - 6,450 ordinary files: `0664`
   - Only the exact ten approved executable paths: `0775`
5. Freeze and enforce the exact ten-path executable allowlist. Reject symlinks, special files, unexpected executables, and any ownership or mode mismatch.
6. Keep the vendor manifest mode-sensitive. Add a complete UID/GID/mode assertion rather than weakening the existing identity check.
7. Freeze a new deterministic vendor identity. Before hashing, the corrected structural totals should be:
   - 6,460 files
   - 925 directories
   - 26,481,661 bytes
8. Prove with an actual UID/GID 33 process in a safe rehearsal location that PHP can traverse and read the candidate autoloader and load Laravel, while it cannot write to `vendor`.

## Required validation

- Two clean builds in the reviewed environments reproduce the exact path, content, mode, ownership, and new vendor identity.
- Candidate is Laravel 12.69.1 with the same one-package lock change already reviewed.
- Composer strict validation passes.
- Locked `--no-dev` audit reports zero advisories.
- PHP 8.2.30 platform checks pass.
- Package discovery passes and route discovery returns the expected 178 routes.
- The stale remember-cookie regression and valid-cookie control tests pass.
- Source CAS, schema, ledger, front controller, configuration, capabilities, queues, and dependencies remain unchanged during preparation.
- All dependency atomic cutover, interruption, rollback, and recovery rehearsals pass.
- The old Laravel 12.69.0 lock, vendor, and cache remain the exact rollback set.

Return the replacement branch and commit, runner hash, new vendor/cache/lock identities, executable allowlist hash, ownership/mode manifest, build receipts, test results, rehearsal receipts, and updated staging/cutover/rollback plan for independent review.

Do not stage or deploy under this handoff. A fresh restricted-stage authorization must follow independent review. Cutover requires separate authorization after a successful stage receipt.

## Transparency repair

Keep transparency commit `3db18d1fff3f599299eecd2aae21b9102fc45540` non-stageable with `DEPENDENCY_ENVELOPE_FROZEN = False`.

Make no transparency, ShopNLTees, migration, retention, customer-deletion, or capability changes.

After Laravel 12.69.1 is deployed and its monitor passes, refreeze the exact production dependency envelope and repeat the transparency validation and review gates.
