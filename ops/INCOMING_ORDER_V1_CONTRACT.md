# BuyDTF Incoming Order v1 Contract Proposal

Status: **final proposal for review; not implemented or deployed**

Consumers: ShopNLTees and BuyDTF

Transport boundary: HTTPS API only. Shared databases and direct filesystem coupling are prohibited even when both applications run on the same infrastructure.

## Compatibility Rule

The existing endpoint remains:

```text
POST /api/incomingorder
```

A legacy request that contains neither `idempotency_key` nor `job_label` must follow the current code path and preserve its current validation, persistence, status codes, and response shape exactly. No additive `job_label`, capability, or receiver field may appear in that legacy response.

An opt-in v1 request contains `idempotency_key`, `job_label`, or both. A key-only v1 request opts into receiver idempotency but otherwise uses the same artwork/job behavior as the legacy path. ShopNLTees must not send either field until BuyDTF advertises both required capabilities.

## Authentication and Signing

- Content type for an opt-in v1 request is `application/json; charset=utf-8`.
- The current HMAC-SHA256 shared-secret mechanism remains the authentication method for this version.
- Legacy signing and verification remain unchanged for legacy requests.
- For an opted-in v1 request, `signature` is excluded from the signing object; every other top-level field, including `idempotency_key` and the complete `job_label` object, is included.
- ShopNLTees signs the RFC 8785 JSON Canonicalization Scheme serialization of that signing object. The signature is a lowercase, 64-character hexadecimal HMAC-SHA256.
- BuyDTF verifies the signature before validation, network fetches, filesystem writes, or database work.
- The receiver must never log a signature, shared secret, raw payload, image URL query string, or raw label text. It may log a request correlation ID, hashed idempotency key, payload fingerprint, status, and enumerated reason code.

## Request Contract

Existing fields retain their current meaning. The v1 additions are `idempotency_key` and `job_label`.

```json
{
  "source_order_id": "1725",
  "file_name": "production-art.png",
  "shop": "urey.localschoolgear.com",
  "idempotency_key": "shopnltees:print-snapshot:31",
  "design": {
    "image_url": "https://example.invalid/signed-art-url",
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
  "signature": "hex-encoded-hmac-sha256"
}
```

For opted-in v1 requests, the complete envelope has these constraints:

| Field | Type | Required | Limit/rule |
|---|---|---:|---|
| `source_order_id` | string or integer | yes | Normalized to a 1-64 character string; production order identifier only |
| `file_name` | string | yes | 1-255 characters; basename/display value only, never a filesystem path |
| `shop` | string or null | no | Lowercase ASCII/IDNA hostname under the same rules as `shop_domain` |
| `idempotency_key` | string | yes for receiver idempotency or an accepted label | Rules below |
| `design` | object | yes | No unknown fields in v1 |
| `design.image_url` | string | yes | Valid HTTPS URL on an approved host; maximum 2,048 characters |
| `design.width` | decimal string or JSON number | yes | Greater than 0 and at most 120 inches; normalized to four decimals |
| `design.height` | decimal string or JSON number | yes | Greater than 0 and at most 120 inches; normalized to four decimals |
| `design.quantity` | integer | yes | 1-10,000 |
| `job_label` | object or absent | no | Exact schema below |
| `signature` | string | yes | Lowercase 64-character hexadecimal HMAC-SHA256 |

At least one of the two artwork dimensions must be no greater than the production sheet width of 21.9000 inches so the artwork can be oriented to fit. Decimal strings may not use exponential notation. NaN and infinity are invalid.

### `idempotency_key`

- Required for receiver idempotency and for any label to be accepted.
- String length: 1-128 ASCII characters.
- Pattern: `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`.
- Stable for the lifetime of one ShopNLTees production-print snapshot submission.
- Scoped to the authenticated integration client. The database uniqueness key is `(integration_client, idempotency_key)`.
- Must not contain a customer name, email, phone, address, or other PII.

If a label is supplied without a valid idempotency key:

- `required=true`: return 422 before any job/order/file is created.
- `required=false`: continue the existing artwork job, return `job_label.status="ignored"`, and set `reason="idempotency_key_required"`.

### `job_label`

`job_label` is optional. When present, only the following fields are allowed; unknown fields invalidate the complete label.

| Field | Type | Required | Limit/rule |
|---|---|---:|---|
| `version` | integer | yes | Must equal `1` |
| `required` | boolean | no | Defaults to `false` |
| `mode` | string | yes | `metadata_only` or `printed_strip` |
| `order_number` | string | yes | 1-64 characters |
| `order_item_id` | integer | yes | Positive signed 64-bit integer |
| `production_print_snapshot_id` | integer | yes | Positive signed 64-bit integer |
| `product_name` | string | yes | 1-160 characters; catalog/production description only |
| `product_sku` | string or null | no | Null or 1-80 characters |
| `color` | string | yes | 1-80 characters |
| `size` | string | yes | 1-40 characters |
| `placement` | string | yes | 1-80 characters |
| `quantity` | integer | yes | 1-10,000 and must equal `design.quantity` |
| `shop_domain` | string | yes | Lowercase ASCII/IDNA hostname, maximum 253 characters; no scheme, path, query, fragment, credentials, or port |

Text is normalized to Unicode NFC. NUL, C0/C1 controls, newlines, invalid UTF-8, bidi override/isolate controls, and unpaired surrogates are rejected. Values are always rendered as escaped text, never interpreted as HTML, XML, Blade, shell syntax, a filename, or a filesystem path.

Allowed metadata is production-only. Customer names, email addresses, phone numbers, shipping/billing addresses, free-form customer notes, and personalization rosters are prohibited. ShopNLTees must source `product_name`, `color`, `size`, and `placement` from catalog/production fields rather than customer-entered text. BuyDTF rejects unknown keys and obvious email/phone/address payload patterns, but the sender remains responsible for not supplying PII that cannot be reliably inferred by software.

## Validation and Atomicity

For an opt-in v1 request, processing order is fixed:

1. Parse JSON and verify HMAC.
2. Validate the idempotency key and envelope types.
3. Validate the v1 envelope and complete label, including PII/escaping/length/mode rules. For an optional invalid label, retain only an invalid-label hash and enumerated reason, not rejected raw metadata.
4. Canonicalize the semantic payload and compute its fingerprint. The canonical fingerprint includes every supplied label key/value, including unknown values that caused an optional label to be ignored.
5. Resolve an existing idempotency record under a unique key/transaction lock.
6. Fetch the artwork into a non-public temporary file using the bounded fetch policy.
7. Decode and normalize/trim the artwork without writing a BuyDTF job.
8. Validate physical dimensions and aspect ratio from the normalized pixels.
9. For `required=true`, confirm the requested label mode can be honored.
10. In one database transaction, create/reuse the open order as required, create the distinct `dtfimages` job row, persist the frozen incoming-job/label snapshot, and store the response snapshot.
11. Atomically move the immutable original artwork into its final storage path. Compensate/clean temporary artifacts on failure.

No order, image/job row, label row, or permanent file may exist after a required-label validation failure. The database design must enforce the idempotency uniqueness constraint so concurrent identical deliveries cannot create two jobs.

### Bounded artwork fetch

The new v1 path must replace unrestricted native URL fetching with a controlled client:

- HTTPS only.
- Host allowlist configured for approved ShopNLTees storefront/artifact hosts.
- DNS resolution checked against loopback, link-local, private, multicast, and metadata-network ranges on every connection/redirect.
- At most three redirects, each revalidated and restricted to an approved host.
- 10-second connect timeout and 30-second total timeout.
- Maximum 50 MiB response, streamed to a temporary file.
- Declared MIME, decoded format, pixel dimensions, and actual content validated before persistence.

These restrictions apply only to the opted-in v1 path; legacy requests remain unchanged until separately migrated.

## Canonical Payload Fingerprint

BuyDTF computes a SHA-256 fingerprint; ShopNLTees does not supply it. The fingerprint input is an RFC 8785 JSON Canonicalization Scheme serialization of this semantic object for a valid request:

```json
{
  "contract": "incoming_order_v1",
  "source_order_id": "1725",
  "file_name": "production-art.png",
  "shop": "urey.localschoolgear.com",
  "design": {
    "image_url": "https://example.invalid/signed-art-url",
    "width_in": "10.7500",
    "height_in": "11.1220",
    "quantity": 1
  },
  "job_label": {
    "color": "Black/Light Oxford",
    "mode": "metadata_only",
    "order_item_id": 1671,
    "order_number": "1725",
    "placement": "Full Back",
    "product_name": "Urey Cheer Port Authority Jacket",
    "product_sku": null,
    "production_print_snapshot_id": 31,
    "quantity": 1,
    "required": false,
    "shop_domain": "urey.localschoolgear.com",
    "size": "S",
    "version": 1
  }
}
```

Rules:

- `signature` and transport-only fields are excluded.
- `idempotency_key` is the lookup key and is excluded from its associated payload fingerprint.
- Strings use validated NFC form; `shop` and `shop_domain` are lowercase IDNA ASCII.
- IDs are normalized as shown by their contract types.
- Dimensions are decimal strings rounded half-up to exactly four fractional digits; exponential notation, NaN, and infinity are invalid.
- Missing optional values are represented explicitly as `null` in the canonical object.
- Object keys are canonicalized by RFC 8785; array ordering, if introduced by a future contract version, is significant.
- For an ignored optional label, the fingerprint covers its complete supplied RFC 8785 representation so changing any rejected key/value under the same idempotency key produces a conflict. Rejected raw metadata is not retained after its fingerprint and reason are recorded.

Idempotency behavior:

- New key: process once and freeze the normalized request/label snapshot.
- Existing key plus identical fingerprint and completed job: return the original job IDs, files, dimensions, label snapshot, and outcome; set only `receiver.replayed=true`.
- Existing key plus identical fingerprint still processing: return 202 with `receiver.status="processing"` and a `Retry-After` header; create nothing new.
- Existing key plus different fingerprint: return 409 `idempotency_conflict`; create/change nothing and do not refetch artwork.
- Retryable first-attempt failure: retain the reservation/error state; an identical retry may safely resume under a lock, but it must never replace the frozen metadata of a completed job.

## Physical-Dimension Contract

- Store and calculate all v1 physical dimensions as `DECIMAL(10,4)` or higher precision.
- Return dimension values as fixed four-decimal strings in inches.
- Decode the source and complete existing normalization/trimming before validating label rendering.
- Let `source_ratio = normalized_pixel_width / normalized_pixel_height` and `requested_ratio = width_in / height_in`.
- The request is aspect-compatible only when `abs(requested_ratio / source_ratio - 1) <= 0.001` (0.10%).
- Values must also map to positive integer pixel dimensions at 300 DPI.
- The v1 production path must preserve a single uniform scale. Independent width/height scaling, stretching, squashing, and hard distortion are prohibited.
- An aspect-incompatible required request returns 422 without a job. For an optional label, the label is ignored with `reason="dimension_mismatch"`; the existing artwork path may continue, but it must not claim label rendering occurred.

The original submitted file remains immutable and separately addressable. Normalized artwork and any labeled output are derived assets with their own path, SHA-256, renderer version, dimensions, and timestamps. No derived render may overwrite the original.

## Mode Semantics

### `metadata_only`

- Freeze and display the validated metadata on the BuyDTF job/admin production view.
- Do not alter printable pixels.
- `art_width_in == output_width_in`.
- `art_height_in == output_height_in`.
- `label_height_in == "0.0000"`.
- Status is `accepted` once the job and immutable metadata snapshot are committed.

### `printed_strip`

- Complete normal artwork normalization/trimming first.
- Preserve the artwork region's exact normalized pixels, physical width, physical height, and aspect ratio.
- Create a new derived output canvas at 300 DPI.
- Copy the artwork region pixel-for-pixel at `(0, 0)` without resampling.
- Append a fixed `0.3500` inch (105 pixel at 300 DPI) identification strip beneath the artwork, never over it.
- Output width equals artwork width. Output height equals artwork height plus `0.3500` inch.
- Render escaped production metadata plus a clear `CUT OFF LABEL STRIP` instruction inside the strip. Text/layout may be reduced or wrapped, but the renderer must reject rather than clip or overlap content.
- Supported artwork width for v1 printed strips is `3.0000` through `21.9000` inches. Outside that range, a required label returns 422; an optional label is ignored with `reason="printed_strip_width_out_of_range"`.
- Store the derived file separately from both the immutable original and normalized unlabeled artwork.
- Status is `accepted` before the production derivative exists and `rendered` only after the derived asset, checksum, renderer version, and output dimensions are persisted successfully.
- Production layout/material calculations use output dimensions. Initial v1 customer pricing remains based on artwork dimensions only; billing for strip material requires a future reviewed contract version.

## Persistence and Production Grouping

Use a dedicated additive Fuel-database table named `incoming_order_jobs`, rather than overloading `dtfimages.item_meta`. It is one-to-one with the BuyDTF `dtfimages` job. The reviewed implementation migration must create these fields:

- `id` unsigned big integer primary key;
- `dtfimage_id` unsigned integer/big integer matching the audited live key type, nullable until commit, then unique;
- `integration_client` ASCII `VARCHAR(64)`;
- `idempotency_key` ASCII case-sensitive `VARCHAR(128)`;
- `request_fingerprint` ASCII `CHAR(64)`;
- `state` `VARCHAR(32)` (`processing`, `completed`, or `retryable_failure`);
- `response_payload` JSON nullable, containing only the frozen non-PII response;
- `label_version` unsigned small integer nullable;
- `label_required` boolean nullable;
- `label_mode` `VARCHAR(32)` nullable;
- `label_status` `VARCHAR(32)` nullable;
- `label_reason` `VARCHAR(64)` nullable;
- `label_metadata` JSON nullable, populated only with validated allowlisted metadata;
- `label_fingerprint` ASCII `CHAR(64)` nullable;
- `art_width_in`, `art_height_in`, `output_width_in`, `output_height_in`, and `label_height_in` as `DECIMAL(10,4)`;
- immutable original, normalized artwork, and derived label paths as bounded strings plus separate ASCII `CHAR(64)` SHA-256 columns;
- `renderer_version` `VARCHAR(64)` nullable;
- `last_error_code` `VARCHAR(64)` nullable;
- `rendered_at`, `created_at`, and `updated_at` timestamps.

Required indexes are a unique case-sensitive `(integration_client, idempotency_key)` index, a unique nullable `dtfimage_id` index, and operational indexes on `state`, `label_status`, and `rendered_at`. Do not add a foreign key until the audited engine/type of the legacy `dtfimages` table proves it is compatible.

The v1 exact dimensions in `incoming_order_jobs` are authoritative. Legacy `dtfimages` dimension columns remain untouched by the additive migration. Every v1 pricing, grouping, layout, production, response, and admin-display code path must read the exact v1 values and pass them explicitly to rendering helpers; legacy jobs continue using `dtfimages.width` and `dtfimages.height` exactly as today.

Schema changes are additive. The old application must safely ignore the new table. Once any v1 job exists, rollback must disable the capability and revert code without dropping this table, deleting derived files, or discarding label snapshots.

Artwork-byte deduplication may reuse one immutable blob, but it never reuses or merges a job row. Different idempotency keys always produce distinct BuyDTF job records, even when the artwork hash is identical.

Production grouping rules:

- Legacy/no-label grouping key remains exactly `image path + width + height`.
- A labeled v1 grouping key additionally contains label mode, immutable label fingerprint, renderer version, and output dimensions.
- Different labels can never merge or share the representative job's metadata.
- Identical labeled jobs may group only when all grouping fields match; every constituent job retains its own frozen metadata and production audit record.

## Success Response

Legacy success responses remain byte-for-byte structurally unchanged. An opted-in v1 success adds `receiver` and, when supplied, `job_label`:

```json
{
  "success": true,
  "duplicate": false,
  "file": "/uploads/images/immutable-original.png",
  "order_id": 1444,
  "dtfimage_id": 17262,
  "job_id": "1725",
  "file_size": 123456,
  "sha256": "hex-sha256",
  "orig_width_in": 10.75,
  "orig_height_in": 11.122,
  "width_ratio": 1,
  "height_ratio": 1,
  "receiver": {
    "contract": "incoming_order_v1",
    "idempotency_key": "shopnltees:print-snapshot:31",
    "request_fingerprint": "hex-sha256",
    "status": "completed",
    "replayed": false
  },
  "job_label": {
    "status": "accepted",
    "version": 1,
    "mode": "metadata_only",
    "reason": null,
    "art_width_in": "10.7500",
    "art_height_in": "11.1220",
    "output_width_in": "10.7500",
    "output_height_in": "11.1220",
    "label_height_in": "0.0000"
  }
}
```

`duplicate` continues to mean that the immutable artwork blob was reused. It never means the new job or its metadata was merged.

For an optional invalid label, the artwork job succeeds and the response includes:

```json
{
  "job_label": {
    "status": "ignored",
    "version": 1,
    "mode": "printed_strip",
    "reason": "dimension_mismatch",
    "art_width_in": "10.7500",
    "art_height_in": "11.1220",
    "output_width_in": "10.7500",
    "output_height_in": "11.1220",
    "label_height_in": "0.0000"
  }
}
```

Reasons are enumerated machine codes and never echo rejected input. Initial codes are:

- `idempotency_key_required`
- `unsupported_version`
- `unsupported_mode`
- `missing_field`
- `unknown_field`
- `invalid_type`
- `invalid_value`
- `unsafe_characters`
- `contains_pii`
- `too_long`
- `quantity_mismatch`
- `dimension_mismatch`
- `printed_strip_width_out_of_range`
- `rendering_unavailable`

For `status="ignored"`, `mode` is the normalized supported requested mode or `null` when the supplied mode is missing, malformed, or unsupported. Accepted/rendered labels always return one of the two supported mode strings.

## Error Responses

### Required validation failure: 422

```json
{
  "success": false,
  "error": {
    "code": "job_label_invalid",
    "reason": "dimension_mismatch"
  }
}
```

No order, DTF image/job, permanent file, label row, or derived asset is created.

### Idempotency conflict: 409

```json
{
  "success": false,
  "error": {
    "code": "idempotency_conflict",
    "message": "This idempotency key was already used with a different payload."
  },
  "receiver": {
    "contract": "incoming_order_v1",
    "idempotency_key": "shopnltees:print-snapshot:31"
  }
}
```

No existing record is changed and no artwork is fetched.

Existing authentication failures remain 401. Malformed v1 JSON is 400. Internal errors remain non-success and must not leak stack traces, filesystem paths, provider responses, secrets, or payload values.

## Capability Discovery

New endpoint:

```text
GET /api/incomingorder/capabilities
```

It is read-only, contains no tenant/customer information, requires no shared-secret signature, and returns `Cache-Control: public, max-age=60`.

```json
{
  "endpoint": "/api/incomingorder",
  "capabilities": {
    "receiver_idempotency_v1": {
      "enabled": true,
      "key_max_length": 128,
      "fingerprint": "sha256-rfc8785",
      "conflict_status": 409
    },
    "job_label_metadata_v1": {
      "enabled": true,
      "version": 1,
      "modes": ["metadata_only", "printed_strip"],
      "optional_failure_status": "ignored",
      "dimension_precision_decimals": 4,
      "aspect_ratio_max_relative_error": "0.0010",
      "printed_strip": {
        "dpi": 300,
        "label_height_in": "0.3500",
        "min_art_width_in": "3.0000",
        "max_art_width_in": "21.9000"
      },
      "limits": {
        "order_number": 64,
        "product_name": 160,
        "product_sku": 80,
        "color": 80,
        "size": 40,
        "placement": 80,
        "quantity_max": 10000,
        "shop_domain": 253
      }
    }
  }
}
```

BuyDTF must not advertise either capability until its migration, code, tests, production rendering, admin display, rollback safeguards, and production deployment are complete. During rollback, disable the capability response first; retained v1 data remains readable.

## Required Acceptance Tests

1. A legacy payload without v1 fields has identical status, response shape, persistence, image result, and production behavior.
2. Metadata-only submission is validated, frozen, displayed, and returned without changing printable bytes or dimensions.
3. Printed-strip output preserves artwork pixel bytes/region, width, height, and aspect ratio and reports the 0.3500-inch derived extension.
4. Optional invalid metadata creates the ordinary distinct artwork job and returns explicit `ignored` plus an enumerated reason.
5. Required invalid metadata leaves no order, image/job, permanent file, idempotency completion, or label artifact.
6. The same artwork bytes under two idempotency keys and different labels create two DTF image/job rows and two frozen metadata records, even if the immutable blob is reused.
7. Same-key/same-fingerprint retry returns the original job and frozen metadata; concurrent retries create only one job.
8. Same-key/different-fingerprint retry returns 409 and changes nothing.
9. Four-decimal dimensions round-trip; incompatible ratios cannot reach a hard-distortion resize.
10. Length boundaries, Unicode normalization, output escaping, controls, bidi characters, path/shell/template strings, and malicious input are safe.
11. Unknown/PII fields and obvious PII values are rejected or explicitly ignored according to `required`.
12. Label-aware grouping never combines different label fingerprints; identical groups retain per-job audit metadata.
13. Original, normalized, and printed-strip assets have distinct immutable paths/checksums; regeneration from the frozen snapshot is deterministic.
14. Capability signals are absent before readiness, correct after enablement, and disabled safely on rollback.
15. Code rollback leaves legacy jobs working and retains v1 rows/assets; migration rollback never drops production metadata.
16. HMAC covers the idempotency key and label; logs contain no raw signature, URL query, label text, or customer PII.
17. URL fetch tests cover timeout, size cap, redirect validation, DNS/private-network denial, MIME mismatch, and cleanup.

## Deployment and Rollback Sequence

1. Review this contract jointly in BuyDTF and ShopNLTees.
2. Implement additive schema, receiver service, controlled fetcher, persistence, production grouping, renderer, admin display, capability endpoint, and tests on a new branch.
3. Run all existing stabilization tests plus the acceptance matrix; inspect migrations and rollback manually.
4. Deploy BuyDTF schema/code with capabilities disabled.
5. Backfill nothing and alter no legacy response.
6. Smoke metadata-only and printed-strip behavior using non-production test jobs.
7. Enable and verify `receiver_idempotency_v1`, then `job_label_metadata_v1`.
8. Only after ShopNLTees observes both capabilities may it begin sending v1 fields, initially with `required=false`.
9. Rollback begins by disabling capabilities and stopping new ShopNLTees v1 sends. Revert code if needed, but retain additive tables, frozen metadata, and original/derived files.

## ShopNLTees Requirements

- Probe capabilities and require both enabled signals before sending `idempotency_key` or `job_label`.
- Generate one stable idempotency key per production-print snapshot submission and persist it with the exact payload.
- Reuse that key only for byte/semantically identical retries; generate a new key for a deliberate changed job.
- Sign the exact transmitted JSON, including the idempotency key and full label.
- Persist the BuyDTF response, receiver fingerprint, BuyDTF job ID, and label outcome.
- Treat 202 as retryable with `Retry-After`; treat 409 as a data-integrity error requiring operator resolution, not an automatic new key.
- Initially send `required=false`.
- Supply only the allowed production fields from immutable snapshot/catalog data and never customer PII or personalization rosters.
- Keep the source artwork available by HTTPS through an approved host long enough for the first successful receipt; do not depend on shared storage.
- Use four-decimal dimension strings and ensure requested dimensions match the submitted normalized artwork aspect ratio.

## Stop Point

This document defines the proposed contract only. No route, controller, schema, model, rendering, capability, or production behavior has been implemented. Implementation and deployment require separate approval.
