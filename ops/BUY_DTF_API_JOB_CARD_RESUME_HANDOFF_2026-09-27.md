# BuyDTF API Job Card Resume Handoff

Date: 2026-09-27 (America/Chicago)

Audience: BuyDTF Codie

This handoff supersedes the earlier proposal to append a printed label strip to the artwork. Do not implement the old `printed_strip` design.

Review delta: the independent review dated 2026-09-27 supersedes this handoff's customer-deletion implementation items. The receiver rollout keeps API asset records, permanent retention defaults, and the report-only retention command; customer deletion requires a separate future contract and rollout review and is not implemented here.

## Verified starting point

- BuyDTF production security dependencies were successfully cut over on 2026-09-18 at 9:45 p.m. Central.
- The successful production receipt records `status: success` after a 30-minute monitoring window.
- Production currently runs Laravel 12.61.1, CommonMark 2.10.0, and Guzzle 7.15.2.
- `composer audit --locked --no-dev` reports no security advisories.
- BuyDTF home, `/up`, `/login`, and the `www` domain were healthy when rechecked on 2026-09-27.
- Continue from branch `security/stabilize-step1-step2-20260918`, commit `f11a941`.
- GitHub `origin/main` remains older at `fe9e97e`; do not base this work on `origin/main` alone.
- No job-card receiver, schema, renderer, capability endpoint, or ShopNLTees sender has been implemented.
- The useful idempotency, integrity, and compatibility rules are documented in `ops/INCOMING_ORDER_V1_CONTRACT.md`, but its appended `printed_strip` sections are superseded by this handoff.

## Final job-card behavior

1. The customer/API artwork must remain byte-for-byte separate from the job card.
2. API receipt validates and freezes the production metadata. It does not add pixels to the artwork.
3. When an operator uses **Add to Production**, BuyDTF generates:
   - the normal production artwork PNG/JHDR using the requested artwork dimensions and quantity; and
   - a separate job-card PNG/JHDR with quantity `1`.
4. Upload the job card alongside its artwork during the production handoff.
5. The job card contains the displayed order number, product, SKU when available, color, size, placement, originating `shop_domain` labeled **Shop**, and total quantity. It must contain no customer name, email, phone number, address, notes, or personalization roster.
6. The job card does not change artwork dimensions, artwork pricing, copy count, or material calculations.
7. Use stable correlated filenames and idempotent overwrite/retry behavior. Do not mark the production handoff complete until both required files are successfully generated and uploaded.
8. Working scope: one job card per unique API print job/production group. Jobs with different card metadata must never be grouped together.
9. The generated card and other API derivatives follow the API asset-retention record. The original artwork remains unchanged.

## Retention and compatibility rules

The fail-safe retention behavior is **keep forever**.

- Every existing `dtfimages` and `savedimages` record remains permanent.
- Artwork uploaded directly through the BuyDTF cart remains permanent in this rollout.
- Saved customer artwork remains permanent in this rollout.
- Missing, unknown, or unclassified retention data means permanent retention.
- Do not infer origin from filenames. Both the cart uploader and current API use `DTF_API_` filenames.
- Automatic expiration applies only to future API assets that have an explicit API retention record.
- Existing API artwork remains permanent unless a later reviewed migration can identify it from authoritative data.
- Retention durations must be configurable and must remain disabled until Daniel selects and enables them.

Deferred future customer deletion must, after its own contract and rollout review:

1. Remove the artwork from Saved Images and prior-order artwork search results for that customer.
2. Defer physical deletion while an open cart or active production job uses the file.
3. Check every database reference before deleting a shared physical path.
4. Delete the source file, thumbnail, and applicable derivatives after active references clear.
5. Preserve historical order metadata and record `customer_deleted_at` and `purged_at`.

## Required implementation order

1. Create a new feature branch from `f11a941`.
2. Update the incoming-order contract to replace `printed_strip` with a separate `job_card` production artifact.
3. Add the shared pinned canonical-JSON/HMAC vectors required by both repositories.
4. Add the additive incoming-job/idempotency schema and models. Do not alter or backfill legacy jobs.
5. Implement strict v1 request validation, RFC 8785 signing, artwork SHA-256 verification, durable idempotency, bounded artwork fetching, and safe logging.
6. Add a capability endpoint with every new capability disabled by default.
7. Add frozen job-card metadata and display it in BuyDTF admin/production views.
8. Generate and upload the separate card during **Add to Production** with retry-safe state tracking.
9. Add explicit asset-origin and retention state for new API jobs. Implement the cleanup command in report-only/dry-run mode first.
10. Add customer artwork removal separately, preserving all legacy artwork by default.
11. Run the existing stabilization suite plus the new compatibility, idempotency, grouping, rendering, and retention tests.
12. Deploy BuyDTF schema/code with capabilities disabled. Smoke-test with non-production jobs.
13. Enable receiver idempotency first. Implement and activate the ShopNLTees sender only after BuyDTF verifies the receiver.

## Acceptance requirements

- Legacy `/api/incomingorder` requests retain their existing response and persistence behavior.
- Original artwork bytes and requested dimensions remain unchanged.
- The job card is a separate file with quantity one.
- Different job-card metadata cannot merge into one production group.
- A required card failure leaves the production handoff retryable and incomplete.
- Existing and direct-cart customer artwork can never be selected by the automatic cleanup command.
- Cleanup has dry-run output showing candidate rows, files, and bytes before deletion is enabled.
- Logs contain no shared secret, signature, signed URL query, raw label/card text, or customer PII.

## Do not do yet

- Do not deploy job-card capability as enabled.
- Do not modify ShopNLTees sends until BuyDTF receiver behavior is deployed and verified.
- Do not implement or deploy customer artwork deletion in this receiver rollout.
- Do not purge or backfill any existing artwork.
- Do not implement the old appended `0.3500`-inch strip.
