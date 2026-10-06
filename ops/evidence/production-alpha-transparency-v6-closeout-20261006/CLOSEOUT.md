V6 transparency repair: documentation-only closeout

Independent cutover and log review is accepted. The candidate remains live. This commit records the acceptance and read-only closeout verification. The existing production state remains `awaiting_independent_log_review`, byte-for-byte, as instructed. No finalization command was introduced or run.

Reviewed execution commit: `53f44905f985b4967789f6fe2e1f5aa1d4b7a127`.
Feature branch: `fix/production-alpha-transparency-activation-v6-20261005`.
Deployment state SHA-256: `c4818553b72c0da8f2df3a5f6376e737655b9e16b43e5068d7cb5e6a1bb0a9b0`.
Final receipt SHA-256: `215bd7535a7d3f08aa2893f7260d443c9f3a3979a5f72f069a3c7d734189de52`.
Acceptance comes from the user's explicit evidence-bound instruction; no new independent-review acceptance receipt was fabricated or installed.

The accepted attempt installed eleven reviewed source members, used verified static-gate transitions and full seven-second monotonic OPcache waits, passed candidate CLI and both FPM checks, and completed thirty full monitoring intervals over at least 1,800 seconds. Every sample passed seven routes, two assets, source/dependency/configuration, database, queue/capability, scheduler and log-continuity checks. The cumulative parsed log contains three INFO entries and zero fatal findings, invalid UTF-8 or orphan data. The reviewed QBO task completed normally, including the observed acquire/complete/release transition at 03:20 UTC.

Read-only closeout verification at `2026-10-06T03:50:34Z` passed all seven normal routes and both current assets. PHP remains 8.2.30 and Laravel remains 12.69.1. FPM OPcache timestamp validation is enabled, with revalidation frequency 2 seconds, file-update protection 2 seconds and the reviewed minimum wait 7 seconds. The effective nginx identity remains unchanged and maps `/index.php` to `/run/php/php8.2-fpm.sock` and `/var/www/buy-dtf/public/index.php`.

All 256 retained evidence files, 257 checksum entries and the complete retained path inventory were reverified. Ten exact original-source backups, the source-file addition's prior-absence record, and the original front controller remain retained, private and unchanged. The front controller is restored at UID/GID 1000:1000 and mode 0644; gate and maintenance are inactive. Source and dependency locks are free. The current QBO status is healthy, with matching normal attempt/success at `2026-10-06T03:50:12Z` and no active overlap mutex.

| Current identity | SHA-256 |
|---|---|
| Full 327-file source | `2c8268cdfbfd3fc294d17de7ab960ab2e1a7f8faa38acd68935af18945f1bc4f` |
| Eleven-member source CAS | `b3379cd90676d8b3214371e17ffd3278cd43ba1885a6223b12998a8b40e5ea27` |
| Composer lock | `77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d` |
| Vendor | `7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8` |
| Vendor ownership/mode | `db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d` |
| Bootstrap cache | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Original front controller | `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9` |
| Installed schema | `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da` |
| 21-row migration ledger | `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53` |
| Effective nginx configuration | `97270e7f001d71a99c2c905c233306986f2e5f18e9c46f5b8872702886624061` |
| Service identity | `792e450402ff2220dd3515433bd7b05bb211b592dacb58601122d0310f39a814` |

`savedimages.item_meta` remains nullable TEXT, with zero non-null rows at closeout. Legitimate post-cutover metadata growth remains allowed. Installed incoming-order tables, queues and failed jobs remain empty. Receiver, job-label and retention capabilities remain disabled, and artwork hosts remain empty. Customer originals, dependencies, schema, configuration and services were preserved.

This documentation package contains redacted summaries, hash receipts and a relative-path portable evidence manifest. The manifest separates committed documentation from retained private evidence; it does not embed logs, raw headers, cookie values, configuration bytes, customer data or rollback file contents. Raw evidence remains private at mode 0600 and private directories at mode 0700. Existing receipts and evidence were not rewritten.

Only documentation is committed and pushed. No deployment, recovery, migration, restart, configuration or permission change, customer-artwork action, retention, customer deletion, ShopNLTees change or finalization command occurred during closeout. No further execution is authorized by this package.
