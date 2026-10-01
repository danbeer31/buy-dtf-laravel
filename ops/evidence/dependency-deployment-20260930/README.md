# Dependency deployment evidence

This directory identifies the 2026-09-30 four-package dependency deployment artifact. The local validation receipt records the observed PHPUnit count and the complete PHP extension inventory, as required for future receipts. The local rehearsal receipt records all 23 passing atomic-exchange scenarios.

The exact artifact commit is `27f455ea16325ae336c686757d59a7a81af81c64`. The production-filesystem rehearsal passed 23/23, the read-only production preflight passed after a scheduled Stripe sync caused the first attempt to stop safely, and the candidate was staged at:

`/var/www/buy-dtf/storage/app/private/operations/dependency-releases/22af12c7e58f-20261001T000259Z`

`production-evidence-manifest.json` indexes every receipt and complete staging log. The copied files retain the exact production hashes. The release receipt hash is `98cb72f1d1aca02e94a5cad2989f981782551d7d7c5cb254f7defc6fbeba79d3`; the candidate vendor manifest is `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`.

Production remains on the old lock/vendor/cache identities and is healthy, out of maintenance, and unlocked. No receipt in this directory authorizes cutover.
