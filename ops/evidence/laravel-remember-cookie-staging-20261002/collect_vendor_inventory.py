#!/usr/bin/env python3
"""Create the mode/content inventory used to diagnose the failed stage."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    records: dict[str, dict[str, object]] = {}
    manifest_records: list[bytes] = []
    file_count = 0
    directory_count = 0
    total_bytes = 0

    for current_root, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)

        for name in directory_names:
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise RuntimeError(f"invalid directory: {path}")
            relative = path.relative_to(root).as_posix()
            mode = stat.S_IMODE(path.stat().st_mode)
            records[relative] = {"kind": "directory", "mode": f"{mode:o}"}
            manifest_records.append(f"d\0{relative}\0{mode:o}\n".encode())
            directory_count += 1

        for name in file_names:
            path = current / name
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f"invalid file: {path}")
            relative = path.relative_to(root).as_posix()
            metadata = path.stat()
            mode = stat.S_IMODE(metadata.st_mode)
            digest = sha256_file(path)
            records[relative] = {
                "bytes": metadata.st_size,
                "kind": "file",
                "mode": f"{mode:o}",
                "sha256": digest,
            }
            manifest_records.append(
                f"f\0{relative}\0{mode:o}\0{metadata.st_size}\0{digest}\n".encode()
            )
            file_count += 1
            total_bytes += metadata.st_size

    return {
        "manifest": {
            "bytes": total_bytes,
            "directories": directory_count,
            "files": file_count,
            "sha256": hashlib.sha256(b"".join(sorted(manifest_records))).hexdigest(),
        },
        "records": records,
        "root": str(root),
    }


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: collect_vendor_inventory.py ROOT OUTPUT")
    result = collect(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
