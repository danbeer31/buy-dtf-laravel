# BuyDTF Incoming Order v1 and Separate Job Card Contract

Date: 2026-09-27 (America/Chicago)

Status: implemented on a review branch only. Nothing in this document authorizes a production deployment, migration, capability enablement, retention purge, or ShopNLTees sender change.

This contract supersedes every earlier `printed_strip` proposal. BuyDTF never appends a label to artwork. The wire field remains named `job_label` for integration compatibility, but an accepted label becomes frozen production metadata and, later, a completely separate job-card artifact.

## Endpoint and compatibility boundary

- Receipt endpoint: `POST /api/incomingorder`
- Capability endpoint: `GET /api/incomingorder/capabilities`
- Legacy requests remain on the existing controller path with their existing response and persistence behavior.
- A request is treated as v1 when it contains `idempotency_key`, `job_label`, or `design.sha256`.
- A v1-shaped request never falls through to the legacy receiver. If v1 is disabled it receives an explicit `503 capability_disabled` response.
- `integration_client` is receiver configuration, not a caller-controlled request field. The initial configured identity is `shopnltees`.
- Existing sender semantics are retained explicitly:
  - `source_order_id` is ShopNLTees' database order ID, not the displayed order number.
  - `shop` is the existing human-readable shop name.
  - `sent_at` remains a signed transport timestamp.
  - `job_label.order_number` is the displayed order number.

## Signing and JSON rules

V1 requests use exactly `Content-Type: application/json`, with optional valid media-type parameters such as `charset=UTF-8`. Prefix/suffix media types such as `application/jsonx` and `application/json-patch+json` are rejected. The body must be one JSON object.

1. Reject invalid JSON and duplicate keys at every object depth.
2. Reject unknown v1 envelope, `design`, and `job_label` fields.
3. Remove the top-level `signature` member.
4. Canonicalize the remaining object using RFC 8785 JSON Canonicalization Scheme semantics.
5. Compute lowercase hexadecimal `HMAC-SHA256(canonical_bytes, shared_secret)`.
6. Compare the result with the 64-character lowercase top-level `signature` in constant time.

Both applications must pin and run `contracts/incoming_order_v1_vectors.json`. Its repository companion file records the fixture SHA-256. The test secret is synthetic and must never be used outside tests.

## Request contract

```json
{
  "source_order_id": 853,
  "file_name": "production-art.png",
  "shop": "Urey Local School Gear",
  "sent_at": "2026-09-27T12:00:00Z",
  "idempotency_key": "shopnltees:dispatch:00000000-0000-4000-8000-000000000001",
  "design": {
    "image_url": "https://shopnltest.com/api/production-artifacts/example?temporary-token=...",
    "sha256": "0101010101010101010101010101010101010101010101010101010101010101",
    "width": "10.7500",
    "height": "11.1220",
    "quantity": 1
  },
  "job_label": {
    "version": 1,
    "required": false,
    "mode": "metadata_only",
    "order_number": "1725",
    "order_item_id": 1671,
    "production_print_snapshot_id": 31,
    "product_name": "Urey Cheer Port Authority Jacket",
    "product_sku": null,
    "color": "Black/Light Oxford",
    "size": "S",
    "placement": "Full Back",
    "quantity": 1,
    "shop_domain": "urey.localschoolgear.com"
  },
  "signature": "lowercase-hex-hmac-sha256"
}
```

### Envelope

| Field | Rule |
| --- | --- |
| `source_order_id` | Required positive JSON integer. This is the ShopNLTees database order ID. |
| `file_name` | Required UTF-8 NFC string, 1-255 characters, basename only. |
| `shop` | Optional nullable UTF-8 NFC human-readable shop name, at most 160 characters. |
| `sent_at` | Optional nullable RFC 3339 timestamp, at most 64 characters. Signed but not used for semantic idempotency. |
| `idempotency_key` | Required, case-sensitive ASCII, 1-128 characters, pattern `[A-Za-z0-9][A-Za-z0-9._:-]*`. |
| `design` | Required object described below. |
| `job_label` | Optional object described below. |
| `signature` | Required 64-character lowercase hexadecimal HMAC. |

### Design

| Field | Rule |
| --- | --- |
| `image_url` | Required HTTPS URL, maximum 2048 bytes, no credentials or fragment, exact host allowlist match. It is transport information and may be refreshed on a retry. |
| `sha256` | Required lowercase SHA-256 of the exact downloaded artwork bytes. This is immutable artwork identity. |
| `width` | Required positive decimal inches, normalized and persisted to four decimal places. Maximum 120 inches. |
| `height` | Required positive decimal inches, normalized and persisted to four decimal places. Maximum 120 inches. |
| `quantity` | Required positive JSON integer, maximum 10,000. |

At least one requested dimension must fit the configured 21.9-inch sheet width so rotation remains possible. The target 300-DPI area and decoded source image must remain within advertised limits.

### Optional `job_label`

Allowed metadata is production-only. Customer name, email, phone, postal address, notes, personalization rosters, and unknown fields are prohibited.

| Field | Rule |
| --- | --- |
| `version` | Required integer `1`. |
| `required` | Optional boolean, default `false`. Invalid type fails closed. |
| `mode` | Required literal `metadata_only`. `printed_strip` is unsupported. |
| `order_number` | Required UTF-8 NFC string, 1-64 characters. Displayed order number. |
| `order_item_id` | Required positive JSON integer. |
| `production_print_snapshot_id` | Required positive JSON integer. |
| `product_name` | Required UTF-8 NFC string, 1-160 characters. |
| `product_sku` | Optional nullable UTF-8 NFC string, at most 80 characters. |
| `color` | Required UTF-8 NFC string, 1-80 characters. |
| `size` | Required UTF-8 NFC string, 1-40 characters. |
| `placement` | Required UTF-8 NFC string, 1-80 characters. |
| `quantity` | Required positive JSON integer, maximum 10,000, exactly equal to `design.quantity`. |
| `shop_domain` | Required lowercase hostname, at most 253 characters. |

Control characters, bidirectional override/isolate characters, malformed UTF-8, recognized email addresses, phone-like values, and address-like values are rejected. These checks are defense in depth; ShopNLTees must also allowlist fields before sending.

If `required=false`, a label-specific validation or capability failure does not block the artwork job. BuyDTF freezes an `ignored` result and a reason; it never silently omits the result. If `required=true`, BuyDTF validates label support before creating the `dtfimages` row and returns `422` atomically if it cannot honor the label. Artwork-integrity failures are never relaxed by `required=false`.

## Semantic fingerprint and idempotency

The server-scoped tuple `(integration_client, idempotency_key)` uses a case-sensitive `ascii_bin` database collation.

The semantic fingerprint is SHA-256 over RFC 8785 canonical JSON containing:

- contract identifier;
- `source_order_id`, `file_name`, and `shop`;
- immutable artwork SHA-256, four-decimal requested dimensions, and quantity; and
- normalized valid label metadata (including the default `required:false`) regardless of whether the label capability is enabled, `null` when absent, or the submitted invalid optional label when its ignored result must remain reproducible.

The fingerprint deliberately excludes `idempotency_key`, `sent_at`, `design.image_url`, and `signature`. A sender may refresh an expired signed URL while retaining the same dispatch key and immutable artwork hash.

The key identifies one durable ShopNLTees dispatch operation:

- transport retry: reuse the same key;
- explicit reprint: create a new dispatch and use a new key;
- same key and same fingerprint: replay the original frozen response;
- same key and different fingerprint: return `409 idempotency_conflict` and create nothing new.

Processing has a database-time lease, heartbeat, attempt count, bounded stale-owner recovery, and maximum-attempt state. A live owner returns `202` plus `Retry-After`; a stale owner can be reclaimed. Completed responses and permanent failures are frozen. Once attempts are exhausted, every later request returns the same `503 receiver_unavailable / idempotency_attempts_exhausted` outcome. Database completion occurs only after the immutable original has been durably promoted and its hash reverified, preventing a completed job from pointing to a failed move.

## Artwork transport and integrity

The receiver:

- rejects v1 request bodies larger than the advertised 128 KiB default before canonicalization;
- permits only HTTPS and exact configured hosts;
- rejects URL credentials and fragments;
- normalizes IPv4, IPv6, and IPv4-mapped IPv6; denies private, loopback, link-local metadata, multicast, reserved, documentation, transition, and NAT64 prefixes before destination pinning;
- revalidates every redirect, with at most three redirects;
- streams into an owner-scoped temporary path with a 10-second connection cap, 30-second transfer cap, one monotonic 60-second cumulative receiver deadline across DNS, redirects, HTTP, streaming, inspection, promotion, and completion, and a 50 MiB default byte limit;
- accepts single-frame PNG, JPEG, or WebP only;
- enforces declared/detected MIME agreement;
- enforces default limits of 30,000 pixels per side and 100,000,000 decoded pixels;
- verifies downloaded bytes against `design.sha256`; and
- preserves the exact original bytes in a content-addressed source asset.

The sender timeout must be at least 75 seconds. Source access responses (including `401`, `403`, and `404`), redirect exhaustion, empty bodies, DNS failure, destination changes, and cumulative-deadline failures are retryable within the attempt limit so a sender can provide a refreshed URL. URL-policy, hash, format, frame, dimension, size, or aspect failures are permanent for that semantic request.

## Physical dimensions and no-distortion rule

Requested dimensions are persisted to four decimal places. Before creating the business job, BuyDTF compares the decoded artwork aspect ratio with `width / height`. Relative error greater than `0.0010` returns `422 artwork_dimension_mismatch` for every v1 request, regardless of label optionality.

The immutable original is never changed. Production artwork is generated separately by uniform resampling onto the exact requested 300-DPI transparent canvas. There is no independent X/Y stretch. The job card is another independent file and never contributes to artwork dimensions, pricing, copy count, grouping dimensions, or material calculations.

## Persistence and grouping

The additive migration creates:

- `incoming_order_jobs`: idempotency state, artwork identity, four-decimal dimensions, frozen label result/metadata, renderer version, production grouping, and owner-scoped production lease/heartbeat state; and
- `api_asset_records`: explicit origin, role, path identity, checksums, sizes, and fail-safe retention state.

Legacy rows are neither altered nor backfilled. The migration refuses to run unless Laravel's active/default migration connection exactly matches the audited Fuel connection. Its `down()` intentionally retains data so code rollback cannot discard frozen idempotency, label, or asset records. Customer artwork deletion schema and behavior are expressly outside this rollout.

Different accepted label fingerprints produce different production grouping keys even when artwork bytes and dimensions are identical. Physical artwork deduplication may share immutable bytes, but it cannot merge or discard incoming-job metadata.

## Production job-card workflow

Receipt validates and freezes metadata; it does not render a card. When an operator selects **Add to Production** for an accepted job:

1. Lock and verify the incoming job and its label-aware production group, assigning an opaque owner token and database-time lease.
2. Hash the immutable source artwork again and compare it with the frozen receipt hash.
3. Uniformly render the normal production artwork to the requested 300-DPI dimensions without distortion.
4. Render a separate job-card PNG using the frozen metadata and pinned renderer version.
5. Create a normal artwork JHDR using the requested artwork quantity.
6. Create a separate job-card JHDR using quantity `1`.
7. Upload artwork and card using stable correlated filenames and idempotent overwrite/retry behavior.
8. Heartbeat the owner-scoped claim during rendering and around every upload. Every heartbeat, completion, and failure update is conditional on both owner and group key; an expired worker cannot overwrite its successor.
9. Reuse a derived file only when its bytes match a previously frozen hash. Otherwise regenerate to a temporary file and publish it with a same-filesystem atomic rename.
10. Record both derived assets and mark the handoff complete only after every required local render and remote upload succeeds.

The card displays only order number, product, SKU when present, color, size, placement, **Shop** (`shop_domain`), and total quantity. Grapheme-aware wrapping and deterministic adaptive type sizing keep every accepted maximum-length field inside the printable border. A required card failure leaves the production handoff incomplete and retryable. It never falls back to artwork without its card.

The provisional card is 5 by 3 inches (1500 by 900 pixels) with a verified PNG `pHYs` value of 11,811 pixels/metre on both axes (300 PPI). Renderer `separate-job-card-v2` uses the application-owned `resources/fonts/job-card-v2/DejaVuSans.ttf`, pinned in code to SHA-256 `ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280`; neither the font path nor hash is environment-configurable. A font or layout change requires a new renderer version. The capability readiness result verifies Imagick and this exact asset. Physical readability still requires an operator-approved sample before label enablement.

## Success response

The existing success fields remain available. V1 adds `receiver`; a request containing `job_label` also receives an explicit `job_label` result.

```json
{
  "success": true,
  "duplicate": false,
  "file": "/uploads/images/api/v1/01/01/0101....png",
  "order_id": 42,
  "dtfimage_id": 9001,
  "job_id": 853,
  "file_size": 123456,
  "sha256": "0101010101010101010101010101010101010101010101010101010101010101",
  "orig_width_in": 10.75,
  "orig_height_in": 11.1233,
  "width_ratio": 1,
  "height_ratio": 0.999883,
  "receiver": {
    "contract": "incoming_order_v1",
    "idempotency_key": "shopnltees:dispatch:00000000-0000-4000-8000-000000000001",
    "request_fingerprint": "64-character-sha256",
    "status": "completed",
    "attempt_count": 1,
    "replayed": false
  },
  "job_label": {
    "status": "accepted",
    "version": 1,
    "mode": "metadata_only",
    "reason": null,
    "art_width_in": "10.7500",
    "art_height_in": "11.1220",
    "artwork_modified": false,
    "job_card": {
      "artifact": "separate",
      "status": "pending_production",
      "quantity": 1
    }
  }
}
```

An optional invalid or disabled label returns `status: ignored`, a stable machine-readable `reason`, `artwork_modified: false`, and `job_card.status: not_requested`. A request with no `job_label` omits the `job_label` response member.

## Errors

| HTTP | Meaning |
| --- | --- |
| `400` | Malformed JSON, duplicate key, or non-object body. |
| `401` | Missing, malformed, or mismatched signature. |
| `409` | Same integration client/key with a different semantic fingerprint. |
| `413` | V1 request body exceeds the configured receiver limit. |
| `415` | V1 body is not `application/json`. |
| `422` | Strict validation, required label, artwork integrity, format, limit, or aspect failure. No partial legacy job is created. |
| `202` | Identical request is owned by another live processing lease. Retry after the supplied interval. |
| `503` | Capability disabled, receiver unavailable, retryable fetch/processing failure, or attempts exhausted. |

Machine-readable error responses use `error.code` and `error.reason`, including signature failures as `401` with `authentication_failed / invalid_signature`. Logs for v1 contain only correlation IDs, hashes, internal IDs, state, and exception class. They do not contain the secret, signature, signed URL query, raw label/card text, or customer PII.

## Capability discovery

`GET /api/incomingorder/capabilities` is unsigned, read-only, and returns `Cache-Control: public, max-age=60`.

- `receiver_idempotency_v1.enabled` is controlled by `INCOMING_ORDER_V1_ENABLED` and defaults to `false`.
- `job_label_metadata_v1.enabled` requires the receiver flag, `INCOMING_ORDER_JOB_LABEL_ENABLED`, and successful renderer readiness; both flags default to `false`.
- The response advertises supported modes, fingerprint scheme, artwork-hash requirement, timeouts, dimension precision, aspect tolerance, image limits, metadata limits, separate-card semantics, quantity one, renderer/font identities, readiness, and configured artifact hosts.

ShopNLTees may adopt key-only v1 after `receiver_idempotency_v1` is deployed, smoke-tested, and enabled. It may send `job_label` only after both capabilities are observed enabled. On rollback, disable the capability, wait longer than the 60-second cache lifetime, verify ShopNLTees has observed the disabled state, and only then remove receiver support.

## Retention and deferred customer removal

Fail-safe retention is `forever`.

- Every legacy `dtfimages` and `savedimages` record remains permanent.
- Direct-cart and saved customer artwork remains permanent.
- Missing, unknown, or unclassified origin/retention data means permanent retention.
- Origin is never inferred from a filename.
- Automatic expiration applies only to a future API asset with an explicit API asset record and separately enabled retention policy.
- The cleanup command is report-only/dry-run in this change. Retention is disabled by default.

Customer artwork deletion is not implemented by this branch. Its route, UI, service, processor, configuration, and schema were removed from this rollout and require a separate contract and deployment review. Until then, every customer and legacy asset remains permanent. That later design must also prove that an external URL can never be interpreted as a local public-file path during physical purge.

## Deployment and rollback gates

Before production review:

1. Review the exact branch commit, migration, shared vectors, test results, and production drift.
2. Confirm approved artwork hosts, shared-secret placement, and production PHP/Imagick/font support without changing configuration.
3. Review a migration `--pretend` result against the audited Fuel connection and take an exact database backup.
4. Deploy schema and code with every new capability and retention expiration disabled.
5. Smoke-test using non-production jobs.
6. Enable receiver idempotency first; only then update ShopNLTees.
7. Enable label metadata only after receiver and sender behavior are proven and a physical job-card sample is approved.

Code rollback disables the capability flags first and preserves all additive tables and assets. No rollback path drops idempotency history or frozen metadata.

## ShopNLTees requirements

- Generate a durable dispatch-operation key. Reuse it for transport retries and use a new key for each intentional reprint.
- Compute the exact frozen artwork SHA-256 before sending and keep it stable across refreshed URLs.
- Stage every customization render and ordinary design artifact at a canonical direct `https://shopnltest.com/...` URL. Do not use tenant-derived hosts or cross-host redirects. `shopnltest.com` is the only initial allowlist entry.
- Use the shared canonicalization vectors and HMAC rules.
- Preserve current `source_order_id`, `shop`, and `sent_at` meanings.
- Send only allowlisted production metadata and no customer PII.
- Use a request timeout of at least 75 seconds and honor `202`/`503` `Retry-After`.
- Treat `409` as a non-retryable payload/key conflict requiring investigation.
- Gate idempotency and labels independently from the capability response.
- Do not send labels until both `receiver_idempotency_v1` and `job_label_metadata_v1` are enabled.

## Stop point

This branch stops before production migration, deployment, configuration changes, capability enablement, data cleanup, legacy backfill, or ShopNLTees sender changes.
