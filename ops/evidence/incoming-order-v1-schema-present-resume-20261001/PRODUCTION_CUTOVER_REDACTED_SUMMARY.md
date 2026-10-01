# Incoming-order v1 source-only cutover: redacted closeout

Date: 2026-10-01 (America/Chicago)

This is the review-safe closeout for the successful schema-present, source-only receiver cutover. It intentionally contains no raw logs, SQL dumps, source backups, credentials, customer information, or payment information. The raw evidence package is not tracked by Git.

## Deployment result

- Receiver target: `0799440b7cbb0bad364fc2a65b41285f20245658`
- Deployment status: `success`
- Final receipt SHA-256: `51d3dd00639c3c35263df18ac69574580be2f37c6e9691c567dd9aeea8694553`
- Final state SHA-256: `a6af7946abea33fe1af396dcbb9e2cd3525577fb893e35e5e9f307bc46e1b149`
- Monitoring receipt: 30 of 30 samples passed; SHA-256 `af8dd5b81a331261e0ba72999fd7e38d7c0f7b7a7963b630cb14c634f0247685`
- Rollback started: `false`
- Migration command invoked in this attempt: `false`
- Migration pretend invoked in this attempt: `false`
- Source paths installed: 37
- Source snapshot identity: `b3f703e205976f5df4873905681f58d615d9a419b44259491a1ea0a723d2eb35`

## Raw evidence custody

The 117 raw evidence files are preserved unchanged in both locations:

- Production private directory: `/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-rollbacks/0799440b-20261001T163603Z`
- Local private directory outside Git: `C:\Users\danie\private-buy-dtf-evidence\incoming-order-v1\0799440b-20261001T163603Z`

The two trees contain 117 files and 2,351,147 bytes each. A path-by-path comparison of relative path, byte count, and exact-file SHA-256 matched 117 of 117 files with zero missing, extra, or mismatched entries.

The tracked portable manifest is `PRODUCTION_CUTOVER_PORTABLE_MANIFEST.tsv`:

- Rows: 117
- Bytes: 11,942
- SHA-256: `266067d194c6a9a21211d6f27b0649bee549aa0ec236bb929824a0d5a6ed7562`
- Local and production generation output: byte-for-byte identical

## Portable manifest algorithm

The portable manifest is the canonical evidence-tree identity for future verification. Its exact byte-generation rules are:

1. Recursively enumerate every regular file under the evidence root. Symlinks are forbidden.
2. Express each path relative to the evidence root, encoded as UTF-8, with `/` as the separator.
3. Reject a relative path containing TAB, CR, or LF.
4. Sort records in ascending lexicographic order of the relative path's raw UTF-8 bytes.
5. For each file, hash its exact bytes with SHA-256 and render the digest as 64 lowercase hexadecimal characters.
6. Emit exactly `<sha256><TAB><decimal-byte-count><TAB><relative-path><LF>` for every record. There is no header and there is one final LF.
7. Encode the manifest as UTF-8 without a byte-order mark.
8. Hash the exact manifest bytes with SHA-256.

Equivalent reference implementation:

```python
import hashlib
from pathlib import Path

root = Path(EVIDENCE_ROOT).resolve()
records = []
for path in root.rglob("*"):
    if path.is_symlink():
        raise RuntimeError(f"symlink is not permitted: {path}")
    if not path.is_file():
        continue
    relative = path.relative_to(root).as_posix()
    if any(character in relative for character in ("\t", "\r", "\n")):
        raise RuntimeError(f"unsafe relative path: {relative!r}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records.append((relative.encode("utf-8"), path.stat().st_size, digest))

records.sort(key=lambda record: record[0])
manifest = b"".join(
    digest.encode("ascii")
    + b"\t"
    + str(size).encode("ascii")
    + b"\t"
    + relative
    + b"\n"
    for relative, size, digest in records
)
print(hashlib.sha256(manifest).hexdigest())
```

## Previously reported evidence-tree hash

The previously reported SHA-256 `d0a417a7412c8d13656db05f28e60789ebc86d9b7ee43fe95496700209a16ea2` was reproduced. It was generated on Windows PowerShell 5.1 as follows:

1. `Get-ChildItem -LiteralPath $root -Recurse -File | Sort-Object FullName` enumerated and sorted files by the default Windows PowerShell `FullName` comparison.
2. Each path was made relative to `$root` by removing the root prefix and replacing `\` with `/`.
3. Each row was `<lowercase-file-sha256><two ASCII spaces><relative-path><LF>`.
4. Rows were concatenated with a final LF and encoded as UTF-8 without a byte-order mark.
5. SHA-256 was calculated over those exact bytes.

Because that ordering depends on Windows PowerShell full-path sorting, the TSV manifest above replaces it as the portable canonical representation. Both identities describe the same verified 117-file package.

## Authenticated read-only view check

Safe order identifier: `1585`.

| Route | HTTP result | Expected heading | Application error check |
| --- | ---: | --- | --- |
| `/admin/orders/1585` | 200 | `Order Detail: #1585` | Heading rendered; no Laravel, Blade, or relationship error appeared. |
| `/admin/orders/production/1585` | 200 | `Production Order #1585` | Heading rendered; no Laravel, Blade, or relationship error appeared. |

Both checks used the existing authenticated administrator session and exact final route. No form was submitted and no Production, Add to Production, status, edit, download, or other action control was invoked.

## Post-view read-only production verification

The post-view runtime probe was generated at `2026-10-01T18:59:19Z`.

- All 37 reviewed source paths matched their target SHA-256 values; zero mismatches. The deployment source identity remains `b3f703e205976f5df4873905681f58d615d9a419b44259491a1ea0a723d2eb35`.
- Schema SHA-256: `4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed`.
- Migration ledger: 20 rows, SHA-256 `3168a7da9ca4aad0a81e673ec61c1647242916d054768f4dd48ff4b9d7eb28d4`, with exactly one target migration entry.
- `incoming_order_jobs`: present, 0 rows.
- `api_asset_records`: present, 0 rows.
- Receiver capability: disabled.
- Job-label capability: disabled.
- Retention capability: disabled.
- Allowed artwork hosts: 0.
- Queue jobs: 0; failed jobs: 0.
- Front controller SHA-256: `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9`, mode `0644`.
- Laravel maintenance: inactive; static gate: inactive.
- Receiver deployment lock: free; dependency deployment lock: free.
- Runtime: PHP 8.2.30, Laravel 12.69.0, `APP_ENV=local`, `APP_DEBUG=false`.
- Renderer readiness: ready, `separate-job-card-v2`, pinned font SHA-256 `ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280`.
- Public health checks returned 200 for `/`, `/up`, `/login`, and the `www` home page.

Dependency identities remained the reviewed production baseline:

- Composer lock SHA-256: `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`
- Vendor tree SHA-256: `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`
- Bootstrap cache SHA-256: `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`

## Scope confirmation

This closeout performed documentation and read-only verification only. It did not enable any capability, alter the artwork allowlist, change ShopNLTees, run retention or customer deletion, invoke a migration, change production source/dependencies/configuration/cache, restart a service, enter maintenance, or acquire a deployment lock for deployment work.
