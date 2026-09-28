# Incoming-order v1 Phase 0 stop receipt

The authorized read-only preflight stopped before Phase 1 because the production DejaVu Sans file does not match the font identity pinned by receiver commit `3c38427f77d3a5ce9a9df7ec2b68f6ac7595b1c6` and the reviewed deployment plan.

- Reviewed font SHA-256: `ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280`
- Production file SHA-256: `690243adfefe0ce154b547db6205794bd30ac4277275179517a90994f4980648`
- Production file: `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`

All other completed Phase 0 checks passed: the 35 live CAS conditions, dependency and cache identities, Fuel connection and migration-ledger proof, target-table and migration-entry absence, capability defaults, queue counts, locks, public health matrix, and disk check. Three queue-worker processes seen during the first generic process scan belong to `shopnltees-queue.service`, `shopnltees-imports.service`, and `nlcustomtees-queue.service`; cgroup classification confirmed that none is a BuyDTF process. The final runner scopes process conflicts to `/var/www/buy-dtf` or a BuyDTF cgroup.

No production release directory or Phase 2 backup was created. No artifact was uploaded, no Artisan command was invoked, and no pretend or real migration ran. Production source, dependencies, cache, front controller, configuration, schema, ledger, maintenance state, services, capabilities, ShopNLTees, and retention state remained unchanged.

The deterministic local source archive was still prepared and verified against all 35 target hashes. It is intentionally stored beneath ignored private storage and is not part of the documentation commit.

Frozen evidence identities:

- Preflight receipt SHA-256: `6030e6293e71985e74b24bd6b0e89b0ad470669102dd3de9c60de74a8784894d`
- Final runner SHA-256: `c40ba24695f06302dae1ee8d2b48a2d4a4a559bca832aae901e1e83adbf34b44`
- Runtime helper SHA-256: `2887987036e874699e67b03dc3146f4a39d5b6d2eda25bbdbc76152ff2be29ee`
- Local archive SHA-256: `e71e5357d4895ec3bd3882e9e45ddbe3d41deb9641f69486e030b27b023b250a`
- Local-validation receipt SHA-256: `9bd328148ae3e83f08573204504f705718132409073252a700c463e4d41368ed`
