#!/usr/bin/env python3
"""Compare the two complete Laravel 12.69.1 candidate build inventories."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


EVIDENCE_DIRECTORY_NAME = "laravel-remember-cookie-runner-v3-20261002"
EXPECTED_VENDOR_MANIFEST = {
    "bytes": 26_481_661,
    "directories": 925,
    "files": 6_460,
    "sha256": "7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8",
}
EXPECTED_METADATA_SHA256 = "db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d"
EXPECTED_INVENTORY_SHA256 = "c646726893e4d74b42343218f891409e925541d9bf8ab0563ff98a9c998b8fd5"
EXPECTED_ALLOWLIST_SHA256 = "551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154"
EXPECTED_EXECUTABLES = {
    "bin/carbon",
    "bin/patch-type-declarations",
    "bin/php-parse",
    "bin/psysh",
    "bin/var-dump-server",
    "nesbot/carbon/bin/carbon",
    "nikic/php-parser/bin/php-parse",
    "psy/psysh/bin/psysh",
    "symfony/error-handler/Resources/bin/patch-type-declarations",
    "symfony/var-dumper/Resources/bin/var-dump-server",
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Input is not a regular file: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RuntimeError(f"Input is not a JSON object: {path}")
    return document


def read_inventory(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Inventory is not a regular file: {path}")
    raw = path.read_bytes()
    if sha256_bytes(raw) != EXPECTED_INVENTORY_SHA256:
        raise RuntimeError(f"Inventory checksum differs from review: {path}")
    records = [json.loads(line) for line in raw.splitlines()]
    if not all(isinstance(record, dict) for record in records):
        raise RuntimeError(f"Inventory contains a non-object record: {path}")
    return raw, records


def validate_inventory(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) != 7_386:
        raise RuntimeError("Complete inventory does not contain exactly 7,386 records.")
    paths = [record.get("path") for record in records]
    if len(set(paths)) != len(paths) or paths[0] != ".":
        raise RuntimeError("Complete inventory paths are duplicated or lack the root record.")
    if paths[1:] != sorted(paths[1:]):
        raise RuntimeError("Complete inventory paths are not canonical.")

    root = records[0]
    if root != {"gid": 1000, "kind": "directory", "mode": 0o775, "path": ".", "uid": 1000}:
        raise RuntimeError("Vendor root ownership or mode differs from review.")
    directories = [record for record in records[1:] if record.get("kind") == "directory"]
    files = [record for record in records[1:] if record.get("kind") == "file"]
    if len(directories) != 925 or len(files) != 6_460:
        raise RuntimeError("Complete inventory structural totals differ from review.")
    if any(
        record.get("uid") != 1000
        or record.get("gid") != 1000
        or record.get("mode") != 0o775
        for record in directories
    ):
        raise RuntimeError("A vendor directory ownership or mode differs from review.")

    executable_paths = {record["path"] for record in files if record.get("mode") == 0o775}
    ordinary = [record for record in files if record.get("mode") == 0o664]
    if executable_paths != EXPECTED_EXECUTABLES or len(ordinary) != 6_450:
        raise RuntimeError("Vendor executable or ordinary-file modes differ from review.")
    if any(record.get("uid") != 1000 or record.get("gid") != 1000 for record in files):
        raise RuntimeError("A vendor file ownership differs from review.")
    if any(record.get("mode") not in (0o664, 0o775) for record in files):
        raise RuntimeError("A vendor file has an unapproved mode.")
    if any(record["path"].startswith("bin/") and record["path"].lower().endswith(".bat") for record in files):
        raise RuntimeError("Complete inventory contains a Windows Composer proxy.")
    if sum(record.get("bytes", 0) for record in files) != EXPECTED_VENDOR_MANIFEST["bytes"]:
        raise RuntimeError("Complete inventory byte total differs from review.")
    return {
        "entries_including_root": len(records),
        "files": len(files),
        "directories_excluding_root": len(directories),
        "ordinary_files": len(ordinary),
        "executable_files": len(executable_paths),
        "bytes": sum(record["bytes"] for record in files),
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-a", required=True, type=Path)
    parser.add_argument("--receipt-b", required=True, type=Path)
    parser.add_argument("--inventory-a", required=True, type=Path)
    parser.add_argument("--inventory-b", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    parent = args.output.parent.resolve(strict=True)
    if parent.name != EVIDENCE_DIRECTORY_NAME:
        raise RuntimeError("Comparison receipt target is outside the reviewed evidence root.")
    if args.output.exists() or args.output.is_symlink():
        raise RuntimeError("Comparison receipt already exists.")
    inputs = {
        "receipt-a": args.receipt_a.resolve(strict=True),
        "receipt-b": args.receipt_b.resolve(strict=True),
        "inventory-a": args.inventory_a.resolve(strict=True),
        "inventory-b": args.inventory_b.resolve(strict=True),
    }
    for name, path in inputs.items():
        if path.parent != parent:
            raise RuntimeError(f"{name} is outside the reviewed evidence root.")
    receipt_a = read_json(inputs["receipt-a"])
    receipt_b = read_json(inputs["receipt-b"])
    raw_a, inventory_a = read_inventory(inputs["inventory-a"])
    raw_b, inventory_b = read_inventory(inputs["inventory-b"])
    if raw_a != raw_b:
        raise RuntimeError("The two complete vendor inventories are not byte-identical.")
    summary = validate_inventory(inventory_a)

    for receipt in (receipt_a, receipt_b):
        if receipt.get("artifact") != "buy-dtf-laravel-remember-cookie-clean-build-v3" or receipt.get("status") != "pass":
            raise RuntimeError("A clean-build receipt is not a passing v3 artifact.")
        identity = receipt.get("vendor_identity", {})
        if identity.get("manifest") != EXPECTED_VENDOR_MANIFEST:
            raise RuntimeError("A clean build has an unexpected vendor manifest.")
        if identity.get("metadata_sha256") != EXPECTED_METADATA_SHA256:
            raise RuntimeError("A clean build has an unexpected ownership/mode identity.")
        if identity.get("executable_allowlist_sha256") != EXPECTED_ALLOWLIST_SHA256:
            raise RuntimeError("A clean build has an unexpected executable allowlist.")
        if receipt.get("vendor_inventory", {}).get("sha256") != EXPECTED_INVENTORY_SHA256:
            raise RuntimeError("A clean-build receipt does not bind the complete inventory.")
        if not receipt.get("runner_sha256") or not receipt.get("builder_sha256"):
            raise RuntimeError("A clean-build receipt does not bind its runner and builder.")

    deployment_directory = Path(__file__).resolve(strict=True).parent
    actual_runner_sha256 = sha256_bytes(
        (deployment_directory / "laravel_remember_cookie_dependency_deploy.py").read_bytes()
    )
    actual_builder_sha256 = sha256_bytes(
        (deployment_directory / "build_laravel_remember_cookie_candidate.py").read_bytes()
    )
    if (
        receipt_a["runner_sha256"] != receipt_b["runner_sha256"]
        or receipt_a["runner_sha256"] != actual_runner_sha256
        or receipt_a["builder_sha256"] != receipt_b["builder_sha256"]
        or receipt_a["builder_sha256"] != actual_builder_sha256
    ):
        raise RuntimeError("The clean builds used different runner or builder bytes.")
    if receipt_a.get("extraction") != "system-unzip" or receipt_a.get("unzip_path") != "/usr/bin/unzip":
        raise RuntimeError("Build A is not the reviewed system-unzip environment.")
    if receipt_b.get("extraction") != "php-zip-only" or receipt_b.get("unzip_path") is not None:
        raise RuntimeError("Build B is not the reviewed PHP-Zip-only environment.")

    equal_fields = (
        "source_manifest_before",
        "source_manifest_after",
        "shadow_source_manifest",
        "shadow_source_manifest_after",
        "composer_json_sha256",
        "composer_lock_sha256",
        "composer_bin_compat",
        "php_version",
        "php_sha256",
        "composer_version",
        "composer_sha256",
        "handoff",
        "package_versions",
        "route_count",
        "application_autoload_identity",
        "vendor_identity",
        "vendor_inventory",
        "cache_identity",
        "laravel_pail_present",
    )
    for field in equal_fields:
        if receipt_a.get(field) != receipt_b.get(field):
            raise RuntimeError(f"Clean-build receipts disagree on {field}.")

    result = {
        "artifact": "buy-dtf-laravel-remember-cookie-two-build-comparison-v3",
        "status": "pass",
        "verifier_sha256": sha256_bytes(Path(__file__).resolve(strict=True).read_bytes()),
        "runner_sha256": actual_runner_sha256,
        "builder_sha256": actual_builder_sha256,
        "environments": {
            "build-a": {"extraction": "system-unzip", "unzip_path": "/usr/bin/unzip"},
            "build-b": {"extraction": "php-zip-only", "unzip_path": None},
        },
        "complete_inventory_sha256": EXPECTED_INVENTORY_SHA256,
        "complete_inventories_byte_identical": True,
        "vendor_manifest": EXPECTED_VENDOR_MANIFEST,
        "vendor_metadata_sha256": EXPECTED_METADATA_SHA256,
        "executable_allowlist_sha256": EXPECTED_ALLOWLIST_SHA256,
        "structure": summary,
        "equal_receipt_fields": list(equal_fields),
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exception:
        print(f"STOP: {exception}", file=sys.stderr)
        raise SystemExit(1)
