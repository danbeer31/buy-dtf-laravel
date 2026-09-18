# BuyDTF Incoming Order v1 Contract Proposal

Status: **revised proposal for final review; not implemented or deployed**

Consumers: ShopNLTees and BuyDTF

Transport boundary: HTTPS API only. Shared databases and direct filesystem coupling are prohibited even when both applications run on the same infrastructure.

## Compatibility Rule

The existing endpoint remains:

```text
POST /api/incomingorder
```

A legacy request contains none of the v1-only fields: no top-level `idempotency_key`, no `design.sha256`, and no top-level `job_label`. It must follow the current code path and preserve its current validation, persistence, status codes, and response shape exactly. No additive `job_label`, capability, or receiver field may appear in that legacy response.

The presence of any v1-only field opts the complete request into v1 validation. Every v1 request must then contain both a valid top-level `idempotency_key` and a valid `design.sha256`; `job_label` remains optional. A request cannot fall back to legacy processing after opting into v1. A key-only v1 request opts into receiver idempotency and artwork-integrity protections while otherwise preserving the legacy job semantics. ShopNLTees may adopt key-only requests once `receiver_idempotency_v1` is enabled. It may send `job_label` only after both `receiver_idempotency_v1` and `job_label_metadata_v1` are enabled.

## Authentication and Signing

- Content type for an opt-in v1 request is `application/json; charset=utf-8`.
- Reject a v1 document before HMAC verification if it contains a duplicate JSON object key at any nesting level. The receiver must use a parser capable of detecting duplicates rather than silently keeping the first or last value.
- The current HMAC-SHA256 shared-secret mechanism remains the authentication method for this version.
- Legacy signing and verification remain unchanged for legacy requests.
- For an opted-in v1 request, `signature` is excluded from the signing object; every other top-level field, including `idempotency_key` and the complete `job_label` object, is included.
- ShopNLTees signs the RFC 8785 JSON Canonicalization Scheme serialization of that signing object. The signature is a lowercase, 64-character hexadecimal HMAC-SHA256.
- BuyDTF verifies the signature before validation, network fetches, filesystem writes, or database work.
- The receiver must never log a signature, shared secret, raw payload, image URL query string, or raw label text. It may log a request correlation ID, hashed idempotency key, payload fingerprint, status, and enumerated reason code.

## Request Contract

Existing sender semantics are intentionally preserved. `source_order_id` is the ShopNLTees database order ID, not the displayed order number. `shop` is the existing human-readable shop name, not a hostname. `sent_at` remains a signed transport timestamp. The v1 additions are `idempotency_key`, `design.sha256`, and optional `job_label`.

```json
{
  "source_order_id": 853,
  "file_name": "production-art.png",
  "shop": "Urey Local School Gear",
  "sent_at": "2026-09-18T21:15:30Z",
  "idempotency_key": "shopnltees:dispatch:01995f6a-2ba1-7b22-a1c4-12f25b48f291",
  "design": {
    "image_url": "https://example.invalid/signed-art-url",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
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
  "signature": "0000000000000000000000000000000000000000000000000000000000000000"
}
```

For opted-in v1 requests, the complete envelope has these constraints:

| Field | Type | Required | Limit/rule |
|---|---|---:|---|
| `source_order_id` | positive integer | yes | Existing ShopNLTees database order ID; not the displayed order number |
| `file_name` | string | yes | 1-255 characters; basename/display value only, never a filesystem path |
| `shop` | string or null | no | Existing human-readable shop name, 1-160 NFC characters; it is not treated as a hostname |
| `sent_at` | string or null | no | Existing signed RFC 3339 transport timestamp, maximum 64 characters; excluded from the semantic fingerprint |
| `idempotency_key` | string | yes | Required for every v1 request; rules below |
| `design` | object | yes | No unknown fields in v1 |
| `design.image_url` | string | yes | Valid HTTPS URL on an approved host; maximum 2,048 characters |
| `design.sha256` | string | yes | Lowercase 64-character SHA-256 of the exact immutable submitted artwork bytes |
| `design.width` | decimal string or JSON number | yes | Greater than 0 and at most 120 inches; normalized to four decimals |
| `design.height` | decimal string or JSON number | yes | Greater than 0 and at most 120 inches; normalized to four decimals |
| `design.quantity` | integer | yes | 1-10,000 |
| `job_label` | object or absent | no | Exact schema below |
| `signature` | string | yes | Lowercase 64-character hexadecimal HMAC-SHA256 |

The only permitted v1 envelope keys are `source_order_id`, `file_name`, `shop`, `sent_at`, `idempotency_key`, `design`, `job_label`, and `signature`. The only permitted `design` keys are `image_url`, `sha256`, `width`, `height`, and `quantity`. Unknown envelope/design fields are a 422 error for every v1 request; `required=false` does not relax envelope or artwork-integrity validation.

At least one of the two artwork dimensions must be no greater than the production sheet width of 21.9000 inches so the artwork can be oriented to fit. Decimal strings may not use exponential notation. NaN and infinity are invalid. After download, BuyDTF computes SHA-256 over the exact received bytes and compares it with `design.sha256` before decoding or persistence. A mismatch returns 422 `artwork_hash_mismatch` and creates no job.

### `idempotency_key`

- Required for every v1 request and for any label to be accepted.
- String length: 1-128 ASCII characters.
- Pattern: `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`.
- Identifies one durable ShopNLTees **dispatch/send operation**, not merely an order item or production-print snapshot.
- Transport retry of the same dispatch uses the same key. An explicit reprint, including a reprint of the same `production_print_snapshot_id`, creates a new dispatch record and uses a new key. A changed semantic payload under the same key returns 409.
- Scoped to the authenticated integration client. The database uniqueness key is `(integration_client, idempotency_key)`.
- Must not contain a customer name, email, phone, address, or other PII.

Missing or invalid `idempotency_key` or `design.sha256` is a core v1 envelope failure: return 422 before any fetch, file, order, or job creation, regardless of `job_label.required`. It is not an optional label-specific failure and must never fall through to the legacy artwork path.

The recommended key is `shopnltees:dispatch:<immutable dispatch UUID>`. A snapshot-derived key such as `shopnltees:print-snapshot:31` is invalid operational practice because it cannot distinguish a deliberate reprint from a transport retry.

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

1. Parse JSON with duplicate-key detection, validate the exact v1 envelope/design key allowlists, and verify HMAC.
2. Validate the idempotency key, core types, and complete label. For an optional label-specific failure, retain only an invalid-label hash and enumerated reason, not rejected raw metadata.
3. Canonicalize the semantic payload and compute its fingerprint.
4. Atomically insert or claim the idempotency row and its processing lease. Resolve completed, conflicting, actively processing, stale, and retryable states as specified below.
5. Fetch the artwork into an owner-specific non-public temporary file using the bounded fetch policy.
6. Compute SHA-256 over the exact downloaded bytes and compare it with signed `design.sha256`. On mismatch, delete the temporary file and return 422 without a job.
7. Decode, enforce pixel/frame/resource limits, normalize, and trim the artwork without creating an order or DTF image/job.
8. Validate physical dimensions and aspect ratio from the normalized pixels. An artwork-integrity failure is always 422 for v1, irrespective of `job_label.required`.
9. Confirm that the requested label mode can be honored. `required=false` relaxes only label-specific failures.
10. Uniformly resample the normalized artwork to the requested 300-DPI dimensions. Never scale width and height independently.
11. If `printed_strip` is required, render and validate the strip derivative before a success response can be committed. Optional printed strips may be rendered synchronously or remain `accepted` for the production stage.
12. Fsync and atomically promote immutable/content-addressed original, normalized, and any required rendered temporary assets. Re-read their sizes/hashes after promotion.
13. In one database transaction, create/reuse the open order as required, create the distinct `dtfimages` job row, attach the frozen incoming-job/label snapshot, verify that every referenced required asset exists with the expected hash, and mark the idempotency row `completed` with its frozen response.

A completed database job may never reference a file that failed to promote. If asset promotion fails, no order/job completion transaction runs. If the database transaction fails after a content-addressed asset was promoted, the job remains incomplete and the unreferenced asset is safe to reuse by hash or remove later through a grace-period garbage collector. Required-label or artwork validation failures create no order, `dtfimages` row, permanent job-specific file, label record, or completed idempotency result; the receiver may retain the non-PII reservation/error code for retry control.

### Bounded artwork fetch

The new v1 path must replace unrestricted native URL fetching with a controlled client:

- HTTPS only.
- Host allowlist configured for approved ShopNLTees storefront/artifact hosts.
- DNS resolution checked against loopback, link-local, private, multicast, and metadata-network ranges on every connection/redirect.
- At most three redirects, each revalidated and restricted to an approved host.
- 10-second connect timeout and 30-second total timeout.
- Maximum 50 MiB response, streamed to a temporary file.
- Exactly one image/frame/page; animated or multi-page content is rejected.
- Maximum decoded width or height of 30,000 pixels and maximum decoded area of 100,000,000 pixels.
- Maximum normalized or printed-strip output area of 100,000,000 pixels.
- Initial v1 formats are single-frame PNG, JPEG, and WebP. Declared MIME, detected format, decoded dimensions, and actual content must agree.
- Decoder/Imagick memory, map, disk, thread, and execution resource limits are set explicitly so compressed-image bombs fail closed.

These restrictions apply only to the opted-in v1 path; legacy requests remain unchanged until separately migrated.

The complete receiver request budget is 60 seconds. Without a verified durable background owner, the request stops starting new phases before that deadline, records `retryable_failure`, releases its lease, cleans owner-scoped temporary files, and returns 503 plus `Retry-After`; it must not return 202 after abandoning the lease. ShopNLTees uses a minimum 75-second client timeout and retries an ambiguous transport failure with the same dispatch key.

## Canonical Payload Fingerprint

BuyDTF computes a SHA-256 fingerprint; ShopNLTees does not supply it. The fingerprint input is an RFC 8785 JSON Canonicalization Scheme serialization of this semantic object for a valid request:

```json
{
  "contract": "incoming_order_v1",
  "source_order_id": 853,
  "file_name": "production-art.png",
  "shop": "Urey Local School Gear",
  "design": {
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
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

- `signature`, `sent_at`, and `design.image_url` are transport-only and excluded. They remain covered by the request HMAC.
- `idempotency_key` is the lookup key and is excluded from its associated payload fingerprint.
- `design.sha256` is the immutable artwork identity included in the semantic fingerprint. A refreshed signed URL with the same expected hash does not change the fingerprint; changing the expected hash does.
- Strings use validated NFC form; `shop_domain` is lowercase IDNA ASCII while `shop` retains its normalized human-readable value.
- IDs are normalized as shown by their contract types.
- Dimensions are decimal strings rounded half-up to exactly four fractional digits; exponential notation, NaN, and infinity are invalid.
- Missing optional values are represented explicitly as `null` in the canonical object.
- Object keys are canonicalized by RFC 8785; array ordering, if introduced by a future contract version, is significant.
- For an ignored optional label, the fingerprint covers its complete supplied RFC 8785 representation so changing any rejected key/value under the same idempotency key produces a conflict. Rejected raw metadata is not retained after its fingerprint and reason are recorded.

Before either capability is enabled, both repositories must contain the same versioned `contracts/incoming_order_v1_vectors.json` fixture and assert its file SHA-256 in CI. Each vector contains raw JSON, expected duplicate-key decision, expected RFC 8785 signing bytes, expected HMAC for a clearly synthetic fixed test secret, expected semantic-fingerprint object/bytes, and expected SHA-256. Required vectors cover key reordering, integer/decimal normalization, NFC Unicode, escaping, an unknown field, a duplicate key, changed `sent_at`, a refreshed `image_url` with the same artwork hash, and a changed artwork hash. The refreshed URL/timestamp vectors must change the request HMAC but retain the same semantic fingerprint; a changed artwork hash must change the fingerprint.

Idempotency behavior:

- New dispatch key: atomically insert `processing`, set `attempt_count=1`, assign a random lease-owner token, and set a 90-second lease expiry.
- The owner heartbeats at least every 20 seconds during fetch/normalization/rendering, extending the lease to 90 seconds from heartbeat time using a compare-and-swap on its owner token.
- Existing key plus identical fingerprint and completed job: return the original job IDs, files, dimensions, label snapshot, and outcome; set only `receiver.replayed=true`.
- Existing key plus identical fingerprint and an unexpired processing lease owned by another request: return 202 with `receiver.status="processing"`, a bounded `Retry-After` value, and create nothing new.
- Existing key plus identical fingerprint and an expired processing lease: a new request may recover it only through an atomic conditional update on the old owner/expiry. It assigns a new owner, increments `attempt_count`, cleans only temporary files namespaced to the expired owner, and resumes from the first durable incomplete phase.
- Existing key plus `retryable_failure`: a new identical request may atomically claim a new lease and resume. A completed job/response and frozen label metadata are immutable.
- Existing key plus `permanent_failure`: return the frozen non-PII failure without retrying unless an operator performs a separately audited recovery.
- Existing key plus different fingerprint: return 409 `idempotency_conflict`; create/change nothing and do not fetch artwork.
- Cap automatic attempts at 10. Exceeding the cap records `permanent_failure` and returns a stable 503 `idempotency_attempts_exhausted` for operator review; it never silently creates a new key/job.
- A transport retry reuses the dispatch key. An explicit reprint creates a new ShopNLTees dispatch operation and a new key even when its snapshot and artwork hash are unchanged.

The 90/20-second values and attempt limit are advertised by `receiver_idempotency_v1`. Clock comparisons use the database server's UTC time. Every lease transition, completion, and failure is a single conditional database statement or transaction; an application-memory lock is insufficient.

## Physical-Dimension Contract

- Store and calculate all v1 physical dimensions as `DECIMAL(10,4)` or higher precision.
- Return dimension values as fixed four-decimal strings in inches.
- Decode the source and complete existing normalization/trimming before validating label rendering.
- Let `source_ratio = normalized_pixel_width / normalized_pixel_height` and `requested_ratio = width_in / height_in`.
- The request is aspect-compatible only when `abs(requested_ratio / source_ratio - 1) <= 0.001` (0.10%).
- Values must also map to positive integer pixel dimensions at 300 DPI.
- The v1 production path must preserve a single uniform scale. Independent width/height scaling, stretching, squashing, and hard distortion are prohibited.
- Every aspect-incompatible opt-in v1 request returns 422 `artwork_dimension_mismatch` without a job, including requests with no label or `job_label.required=false`. Artwork integrity is not a label-specific fallback.
- `required=false` may ignore only label-specific problems such as unsupported label mode/content, strip readability limits, or unavailable optional rendering. It never allows hash, decode, pixel-limit, physical-dimension, aspect-ratio, or uniform-scaling validation to fall through to the legacy hard-resize path.

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

- Preserve the immutable original bytes first.
- Complete normal artwork normalization and trimming.
- Uniformly resample the artwork region once to its requested 300-DPI dimensions. The aspect check must already have passed, and width/height may not be scaled independently.
- Create a new derived output canvas at 300 DPI and copy that final artwork region pixel-for-pixel at `(0, 0)` without any further resampling.
- Append the proposed `0.3500` inch (105 pixel at 300 DPI) identification strip beneath the artwork, never over it.
- Output width equals artwork width. Output height equals artwork height plus `0.3500` inch.
- Render escaped production metadata plus a clear `CUT OFF LABEL STRIP` instruction inside the strip. Text/layout may be reduced or wrapped, but the renderer must reject rather than clip or overlap content.
- Supported artwork width for v1 printed strips is `3.0000` through `21.9000` inches. Outside that range, a required label returns 422; an optional label is ignored with `reason="printed_strip_width_out_of_range"`.
- Store the derived file separately from both the immutable original and normalized unlabeled artwork.
- For `required=true`, a 200 success is forbidden until the derived strip exists, its checksum/dimensions/renderer version are verified, and the database completion transaction is committed with `job_label.status="rendered"`. An active concurrent owner may return 202 `processing`; `accepted` is not a required-label success state.
- For `required=false`, `accepted` may represent frozen metadata awaiting the ordinary production stage. Rendering changes it to `rendered`; a label-specific rendering failure changes it to `ignored` without changing artwork integrity.
- Without a verified durable background renderer, the owning request renders synchronously. A 202 response is not permission to abandon work without a live lease owner; crash recovery follows the lease state machine.
- Production layout/material calculations use output dimensions. Initial v1 customer pricing remains based on artwork dimensions only; billing for strip material requires a future reviewed contract version.

The `0.3500`-inch value is a candidate, not yet an enabled production promise. Before `printed_strip` may appear in the capability's `modes`, BuyDTF must print at least a minimum-width production sample on the actual printer/media and record operator sign-off that all required text and `CUT OFF LABEL STRIP` are readable, the strip measures 0.3500 inch within one 300-DPI pixel, and the artwork region's measured dimensions are unchanged. If it fails, revise this contract/capability value and repeat review rather than silently increasing or shrinking the strip.

## Persistence and Production Grouping

Use a dedicated additive Fuel-database table named `incoming_order_jobs`, rather than overloading `dtfimages.item_meta`. It is one-to-one with the BuyDTF `dtfimages` job. The reviewed implementation migration must create these fields:

- `id` unsigned big integer primary key;
- `dtfimage_id` unsigned integer/big integer matching the audited live key type, nullable until commit, then unique;
- `integration_client` ASCII `VARCHAR(64) COLLATE ascii_bin`;
- `idempotency_key` ASCII `VARCHAR(128) COLLATE ascii_bin` so MySQL uniqueness is explicitly byte-for-byte case-sensitive;
- `request_fingerprint` ASCII `CHAR(64)`;
- `expected_art_sha256` and `actual_art_sha256` ASCII `CHAR(64)`;
- `state` `VARCHAR(32)` (`processing`, `completed`, `retryable_failure`, or `permanent_failure`);
- `lease_owner` ASCII `CHAR(36) COLLATE ascii_bin` nullable, `lease_expires_at` and `heartbeat_at` UTC timestamps nullable;
- `attempt_count` unsigned integer defaulting to zero and `last_attempt_at` UTC timestamp nullable;
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

Required indexes are a unique case-sensitive `(integration_client, idempotency_key)` index, a unique nullable `dtfimage_id` index, and operational indexes on `(state, lease_expires_at)`, `label_status`, and `rendered_at`. Do not add a foreign key until the audited engine/type of the legacy `dtfimages` table proves it is compatible.

Do not persist a signed artwork URL or `sent_at` in the semantic snapshot. Store only safe transport diagnostics such as approved host, response size, actual content hash, and enumerated error code; URLs with query strings are secrets and must not enter logs or frozen responses.

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
  "job_id": 853,
  "file_size": 123456,
  "sha256": "hex-sha256",
  "orig_width_in": 10.75,
  "orig_height_in": 11.122,
  "width_ratio": 1,
  "height_ratio": 1,
  "receiver": {
    "contract": "incoming_order_v1",
    "idempotency_key": "shopnltees:dispatch:01995f6a-2ba1-7b22-a1c4-12f25b48f291",
    "request_fingerprint": "hex-sha256",
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
    "reason": "rendering_unavailable",
    "art_width_in": "10.7500",
    "art_height_in": "11.1220",
    "output_width_in": "10.7500",
    "output_height_in": "11.1220",
    "label_height_in": "0.0000"
  }
}
```

Reasons are enumerated machine codes and never echo rejected input. Initial codes are:

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
- `printed_strip_width_out_of_range`
- `rendering_unavailable`

For `status="ignored"`, `mode` is the normalized supported requested mode or `null` when the supplied mode is missing, malformed, or unsupported. Accepted/rendered labels always return one of the two supported mode strings.

## Error Responses

### Artwork-integrity or required-label validation failure: 422

```json
{
  "success": false,
  "error": {
    "code": "artwork_invalid",
    "reason": "artwork_dimension_mismatch"
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
    "idempotency_key": "shopnltees:dispatch:01995f6a-2ba1-7b22-a1c4-12f25b48f291"
  }
}
```

No existing record is changed and no artwork is fetched.

### Existing active lease: 202

```json
{
  "success": false,
  "receiver": {
    "contract": "incoming_order_v1",
    "idempotency_key": "shopnltees:dispatch:01995f6a-2ba1-7b22-a1c4-12f25b48f291",
    "status": "processing",
    "attempt_count": 1
  }
}
```

The response includes `Retry-After: 5` (or the smaller whole-second remainder of the live lease, clamped to 1-15 seconds). It exposes neither the lease owner token nor internal paths. For `printed_strip` with `required=true`, clients treat 202 as not yet successful and retry the same signed semantic request/key; only a later 200 with `job_label.status="rendered"` is success.

Initial artwork error reasons include `artwork_hash_mismatch`, `artwork_decode_failed`, `artwork_limits_exceeded`, `artwork_dimension_mismatch`, and `artwork_format_unsupported`. They are never converted into optional-label `ignored` outcomes.

Existing authentication failures remain 401. Malformed JSON or duplicate keys are 400. Unknown v1 envelope/design fields and other semantic validation failures are 422. Internal errors remain non-success and must not leak stack traces, filesystem paths, provider responses, secrets, or payload values.

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
      "key_collation": "ascii_bin",
      "fingerprint": "sha256-rfc8785-semantic",
      "artwork_sha256_required": true,
      "conflict_status": 409,
      "lease_seconds": 90,
      "heartbeat_seconds": 20,
      "max_attempts": 10,
      "fetch_timeout_seconds": 30,
      "receiver_request_timeout_seconds": 60,
      "sender_minimum_timeout_seconds": 75
    },
    "job_label_metadata_v1": {
      "enabled": true,
      "version": 1,
      "modes": ["metadata_only"],
      "optional_failure_status": "ignored",
      "dimension_precision_decimals": 4,
      "aspect_ratio_max_relative_error": "0.0010",
      "printed_strip": {
        "enabled": false,
        "physical_readability_verified": false,
        "dpi": 300,
        "candidate_label_height_in": "0.3500",
        "min_art_width_in": "3.0000",
        "max_art_width_in": "21.9000"
      },
      "limits": {
        "download_bytes": 52428800,
        "decoded_width_px": 30000,
        "decoded_height_px": 30000,
        "decoded_area_px": 100000000,
        "frames": 1,
        "formats": ["png", "jpeg", "webp"],
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

The example is the safe state after metadata-only support but before physical strip sign-off. After the physical readability gate passes, BuyDTF may advertise `printed_strip.enabled=true`, `physical_readability_verified=true`, add `printed_strip` to `modes`, and replace `candidate_label_height_in` with the tested contractual `label_height_in`.

BuyDTF may advertise `receiver_idempotency_v1` independently once its schema/state machine is deployed and verified. It must not advertise `job_label_metadata_v1` until label persistence, admin display, grouping, rollback safeguards, and at least `metadata_only` are ready. During rollback, disable affected capability flags first; retained v1 data remains readable.

## Required Acceptance Tests

1. A legacy payload without v1 fields has identical status, response shape, persistence, image result, and production behavior.
2. Existing sender semantics are locked: `source_order_id` remains the database ID, `shop` remains the human-readable name, and signed `sent_at` remains transport-only; the label `order_number` is separately the displayed number.
3. Metadata-only submission is validated, frozen, displayed, and returned without changing printable bytes or dimensions.
4. Printed-strip output follows preserve -> normalize/trim -> uniform 300-DPI resample -> pixel-for-pixel canvas copy -> append strip, with unchanged artwork-region dimensions/aspect.
5. `printed_strip.required=true` cannot return 200/accepted before its derived file/hash/dimensions are persisted and status is `rendered`.
6. Optional label-specific invalid metadata creates the ordinary distinct artwork job and returns explicit `ignored`; optional or absent labels do not relax artwork hash/aspect/pixel validation.
7. Required invalid metadata leaves no order, DTF image/job, permanent job-specific file, completed idempotency result, or label artifact.
8. Every v1 aspect mismatch, including `required=false`, returns 422 and never reaches the legacy independent width/height resize.
9. A correct `design.sha256` is verified; wrong bytes return 422. A refreshed signed URL/`sent_at` with the same expected hash/key has the same semantic fingerprint, while a changed expected hash under the key returns 409.
10. The same artwork bytes under two dispatch keys and different labels create two DTF image/job rows and frozen metadata records, even if the immutable blob is reused.
11. A transport retry uses one dispatch key and returns the original job. An explicit reprint of the same snapshot uses a new dispatch key and creates a new job.
12. Same-key/different-fingerprint retry returns 409 and changes nothing.
13. Concurrent requests create one job; active leases return bounded 202, heartbeats extend ownership, stale leases are conditionally reclaimed, attempt counts increment, and an expired/crashed owner cannot leave 202 forever.
14. Failure injection before/after asset promotion and before database commit proves no completed job references a missing file; unreferenced content-addressed assets are safely reusable/collectible.
15. Four-decimal dimensions round-trip and a single uniform scale is used.
16. Length boundaries, NFC normalization, escaping, controls, bidi characters, path/shell/template strings, and malicious input are safe.
17. Duplicate JSON keys are 400; unknown v1 envelope/design fields are 422; label unknown/PII fields follow only the documented required/optional label policy.
18. `ascii_bin` uniqueness is proven with mixed-case keys, boundary lengths, and concurrent insert races.
19. Both repositories pass the same pinned RFC 8785 signing/fingerprint vector file, including refreshed-URL and Unicode cases.
20. Label-aware grouping never combines different label fingerprints; identical groups retain per-job audit metadata.
21. Original, normalized, and printed-strip assets have distinct immutable paths/checksums; regeneration from the frozen snapshot is deterministic.
22. URL fetch tests cover connect/total timeout, size cap, redirect/DNS/private-network denial, hash mismatch, MIME mismatch, 30,000-pixel dimension, 100-megapixel area, multi-frame rejection, decoder resource limits, and cleanup.
23. Capability tests prove key-only adoption, label dual-capability gating, metadata-only pre-strip state, the 60-second cache rollback wait, and sender-observed disablement.
24. A documented physical printer/media test passes before `printed_strip` and a contractual strip height are advertised.
25. Code rollback leaves legacy jobs working and retains v1 rows/assets; migration rollback never drops production metadata.
26. HMAC covers idempotency key, transport URL/timestamp, artwork hash, and label; logs contain no raw signature, URL query, label text, or customer PII.
27. The presence of any v1-only field activates v1; a missing/invalid dispatch key or artwork SHA-256 returns 422 with no fetch or persistence and never falls through to legacy resizing.

## Deployment and Rollback Sequence

1. Review this contract jointly in BuyDTF and ShopNLTees.
2. Implement additive schema, receiver service, controlled fetcher, persistence, production grouping, renderer, admin display, capability endpoint, and tests on a new branch.
3. Run all existing stabilization tests plus the acceptance matrix; inspect migrations and rollback manually.
4. Deploy BuyDTF schema/code with capabilities disabled.
5. Backfill nothing and alter no legacy response.
6. Smoke idempotency and metadata-only behavior using non-production test jobs.
7. Enable and verify `receiver_idempotency_v1`. ShopNLTees may then adopt key-only v1 requests while continuing to omit `job_label`.
8. Complete and record the physical strip-readability test. Advertise `printed_strip` only if it passes; otherwise keep metadata-only mode and revise the proposed dimensions before further review.
9. Enable `job_label_metadata_v1` only after both applications observe receiver idempotency and BuyDTF's label modes are ready. ShopNLTees initially sends labels with `required=false`.
10. Rollback begins by disabling the affected capability flags. Wait at least 90 seconds (greater than the public 60-second cache lifetime), then verify ShopNLTees has fetched/observed the disabled state and stopped creating affected sends before removing receiver code support. Retain additive tables, frozen metadata, and original/derived files.

## ShopNLTees Requirements

- Probe capabilities. `receiver_idempotency_v1` alone permits key-only requests; sending `job_label` requires both receiver and label capabilities, and the requested mode must be listed.
- Create and persist a durable dispatch/send-operation record with a UUID. Derive one stable idempotency key from that dispatch, not from only the production snapshot.
- Reuse that key for transport retries, including retries with a refreshed signed URL for the same immutable artwork hash. Create a new dispatch/key for every explicit reprint, even from the same snapshot.
- Preserve current sender meaning: `source_order_id` is the database order ID, `shop` is the human-readable shop name, `sent_at` is RFC 3339 transport metadata, and `job_label.order_number` is the displayed order number.
- Supply lowercase `design.sha256` from the frozen artwork and retain it with the dispatch.
- Sign RFC 8785 canonical request content including the idempotency key, artwork hash, URL, timestamp, and full label.
- Persist the BuyDTF response, receiver fingerprint, BuyDTF job ID, and label outcome.
- Treat 202 as retryable with `Retry-After`; treat 409 as a data-integrity error requiring operator resolution, not an automatic new key.
- Initially send `required=false`.
- Supply only the allowed production fields from immutable snapshot/catalog data and never customer PII or personalization rosters.
- Keep the source artwork available by HTTPS through an approved host long enough for the first successful receipt; do not depend on shared storage.
- Use four-decimal dimension strings and ensure requested dimensions match the submitted normalized artwork aspect ratio.
- Configure a minimum 75-second HTTP timeout (with a 10-second connect timeout) so the sender does not abandon a receiver that legitimately spends up to 30 seconds fetching and up to 60 seconds on the complete request. After any ambiguous timeout, retry with the same dispatch key.
- Consume the shared pinned RFC 8785 test vectors in CI and fail release if the vector file hash or any expected HMAC/fingerprint differs from BuyDTF.

## Stop Point

This document defines the proposed contract only. No route, controller, schema, model, rendering, capability, or production behavior has been implemented. Implementation and deployment require separate approval.
