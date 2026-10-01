#!/usr/bin/env python3
"""Read-only verification of the successful production dependency cutover."""

import hashlib
import json
import os
from pathlib import Path
import stat


APP_ROOT = Path("/var/www/buy-dtf")
EXPECTED = {
    "composer_lock_sha256": "22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9",
    "vendor_manifest_sha256": "7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed",
    "bootstrap_cache_manifest_sha256": "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9",
    "packages_sha256": "21da8f9ed19687e708cc7bc5cc59394c6fcdf9b9deadf617ae70526f815a1db0",
    "services_sha256": "1f7623b2b4ffd2c4099fb34ad86fc96c1479e27bf81b1b0ba328c988cc4ffcb5",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_manifest(root: Path) -> dict:
    records = []
    files = 0
    directories = 0
    byte_count = 0
    for current_root, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)
        for name in directory_names:
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise SystemExit(f"invalid dependency directory: {path}")
            relative = path.relative_to(root).as_posix()
            records.append(
                f"d\0{relative}\0{stat.S_IMODE(path.stat().st_mode):o}\n".encode()
            )
            directories += 1
        for name in file_names:
            path = current / name
            if path.is_symlink() or not path.is_file():
                raise SystemExit(f"invalid dependency file: {path}")
            metadata = path.stat()
            relative = path.relative_to(root).as_posix()
            digest = sha256(path)
            records.append(
                f"f\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0"
                f"{metadata.st_size}\0{digest}\n".encode()
            )
            files += 1
            byte_count += metadata.st_size
    records.sort()
    return {
        "sha256": hashlib.sha256(b"".join(records)).hexdigest(),
        "files": files,
        "directories": directories,
        "bytes": byte_count,
    }


cache_names = sorted(path.name for path in (APP_ROOT / "bootstrap/cache").iterdir())
if cache_names != ["packages.php", "services.php"]:
    raise SystemExit("bootstrap cache file set mismatch")

actual = {
    "composer_lock_sha256": sha256(APP_ROOT / "composer.lock"),
    "vendor": tree_manifest(APP_ROOT / "vendor"),
    "bootstrap_cache": tree_manifest(APP_ROOT / "bootstrap/cache"),
    "packages_sha256": sha256(APP_ROOT / "bootstrap/cache/packages.php"),
    "services_sha256": sha256(APP_ROOT / "bootstrap/cache/services.php"),
}
if (
    actual["composer_lock_sha256"] != EXPECTED["composer_lock_sha256"]
    or actual["vendor"]["sha256"] != EXPECTED["vendor_manifest_sha256"]
    or actual["bootstrap_cache"]["sha256"]
    != EXPECTED["bootstrap_cache_manifest_sha256"]
    or actual["packages_sha256"] != EXPECTED["packages_sha256"]
    or actual["services_sha256"] != EXPECTED["services_sha256"]
):
    raise SystemExit("production dependency identity mismatch")

print(
    json.dumps(
        {
            "status": "pass",
            "scope": "read_only_production_dependency_identity",
            "expected": EXPECTED,
            "actual": actual,
            "cache_names": cache_names,
            "filesystem_mutation": False,
        },
        indent=2,
        sort_keys=True,
    )
)
