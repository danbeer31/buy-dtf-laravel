#!/usr/bin/env python3
"""Read-only verification of the reviewed production 37-path source CAS."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat


APP_ROOT = Path("/var/www/buy-dtf")
MANIFEST = Path(
    "/var/www/buy-dtf/storage/app/private/operations/"
    "incoming-order-v1-releases/0799440b-20261001T013235Z/inputs/"
    "incoming_order_v1_runtime_0799440.manifest"
)
EXPECTED_MANIFEST_SHA256 = (
    "b6efbd5463c82f895ca8d359b665a145d88c0d363ce7f97b247eae9080853bb6"
)
EXPECTED_SOURCE_CAS_SHA256 = (
    "9c0b081853feed397cc61be4b7b6d7c302df2298a87cca30e69e80f067cda6db"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if sha256(MANIFEST) != EXPECTED_MANIFEST_SHA256:
    raise SystemExit("manifest identity mismatch")

rows = []
for raw_line in MANIFEST.read_text("utf-8").splitlines():
    line = raw_line.rstrip("\r")
    if not line or line.startswith("#"):
        continue
    action, expected, _target, relative = line.split("\t")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise SystemExit("unsafe manifest path")
    live = APP_ROOT / relative
    if action == "A":
        if live.exists() or live.is_symlink():
            raise SystemExit(f"reviewed addition is no longer absent: {relative}")
        rows.append({"path": relative, "state": "absent", "matches": True})
        continue
    if action != "M" or live.is_symlink() or not live.is_file():
        raise SystemExit(f"reviewed replacement is unavailable: {relative}")
    actual = sha256(live)
    if actual != expected:
        raise SystemExit(f"reviewed replacement hash mismatch: {relative}")
    metadata = live.stat()
    rows.append(
        {
            "path": relative,
            "state": "file",
            "sha256": actual,
            "bytes": metadata.st_size,
            "metadata": {
                "kind": "file",
                "mode": stat.S_IMODE(metadata.st_mode),
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
            },
            "matches": True,
        }
    )

canonical = (
    json.dumps(rows, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
).encode("utf-8")
source_cas = hashlib.sha256(canonical).hexdigest()
if len(rows) != 37 or source_cas != EXPECTED_SOURCE_CAS_SHA256:
    raise SystemExit("reviewed aggregate source CAS mismatch")

print(
    json.dumps(
        {
            "status": "pass",
            "scope": "read_only_production_source_cas",
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "paths": len(rows),
            "additions_absent": sum(row["state"] == "absent" for row in rows),
            "replacements_exact": sum(row["state"] == "file" for row in rows),
            "source_cas_sha256": source_cas,
            "filesystem_mutation": False,
        },
        indent=2,
        sort_keys=True,
    )
)
