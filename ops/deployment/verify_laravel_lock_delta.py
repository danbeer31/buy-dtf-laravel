#!/usr/bin/env python3
"""Prove the candidate lock is the reviewed one-package Laravel update."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


CANDIDATE_COMMIT = "6a98c74686f1ceffded8012d332318ac075b444e"
EXPECTED_LIVE_LOCK_SHA256 = "22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9"
EXPECTED_CANDIDATE_LOCK_SHA256 = "77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def package_map(document: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    packages = document.get(key)
    if not isinstance(packages, list):
        raise RuntimeError(f"Lock has no {key} array.")
    result = {}
    for package in packages:
        if not isinstance(package, dict) or not isinstance(package.get("name"), str):
            raise RuntimeError(f"Lock contains an invalid {key} package.")
        result[package["name"]] = package
    return result


def changed_fields(old: Any, new: Any, prefix: str = "") -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        fields: list[str] = []
        for key in sorted(set(old) | set(new)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in old or key not in new:
                fields.append(path)
            else:
                fields.extend(changed_fields(old[key], new[key], path))
        return fields
    if old != new:
        return [prefix]
    return []


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    repository = args.repository.resolve(strict=True)
    output_parent = args.output.parent.resolve(strict=True)
    if output_parent.name != "laravel-remember-cookie-runner-v2-20261002":
        raise RuntimeError("Lock-delta receipt target is outside the reviewed evidence root.")
    git = shutil.which("git.exe") or shutil.which("git")
    if git is None:
        raise RuntimeError("Git is unavailable for the lock-delta proof.")
    repository_argument = str(repository)
    if Path(git).name.lower() == "git.exe":
        converted = subprocess.run(
            ["/usr/bin/wslpath", "-w", str(repository)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if converted.returncode != 0:
            raise RuntimeError("Could not convert the repository path for Git.")
        repository_argument = converted.stdout.strip()
    baseline = subprocess.run(
        [git, "-C", repository_argument, "show", f"{CANDIDATE_COMMIT}^:composer.lock"],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if baseline.returncode != 0:
        raise RuntimeError("Could not read the exact live lock from Git history.")
    candidate_bytes = (repository / "composer.lock").read_bytes()
    if sha256_bytes(baseline.stdout) != EXPECTED_LIVE_LOCK_SHA256:
        raise RuntimeError("Historical live lock hash differs from review.")
    if sha256_bytes(candidate_bytes) != EXPECTED_CANDIDATE_LOCK_SHA256:
        raise RuntimeError("Candidate lock hash differs from review.")

    old = json.loads(baseline.stdout)
    new = json.loads(candidate_bytes)
    old_prod = package_map(old, "packages")
    new_prod = package_map(new, "packages")
    old_dev = package_map(old, "packages-dev")
    new_dev = package_map(new, "packages-dev")
    if set(old_prod) != set(new_prod) or old_dev != new_dev:
        raise RuntimeError("Candidate lock changed package membership or development packages.")
    changed_packages = sorted(name for name in old_prod if old_prod[name] != new_prod[name])
    if changed_packages != ["laravel/framework"]:
        raise RuntimeError(f"Candidate lock changed unexpected packages: {changed_packages}")
    old_without_packages = {key: value for key, value in old.items() if key != "packages"}
    new_without_packages = {key: value for key, value in new.items() if key != "packages"}
    if old_without_packages != new_without_packages:
        raise RuntimeError("Candidate lock changed top-level data outside production packages.")

    old_laravel = old_prod["laravel/framework"]
    new_laravel = new_prod["laravel/framework"]
    if old_laravel.get("version") != "v12.69.0" or new_laravel.get("version") != "v12.69.1":
        raise RuntimeError("Laravel lock versions are not the exact reviewed pair.")
    receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-lock-delta-v2",
        "status": "pass",
        "verifier_sha256": sha256_bytes(Path(__file__).resolve(strict=True).read_bytes()),
        "candidate_commit": CANDIDATE_COMMIT,
        "live_lock_sha256": EXPECTED_LIVE_LOCK_SHA256,
        "candidate_lock_sha256": EXPECTED_CANDIDATE_LOCK_SHA256,
        "production_package_count": len(new_prod),
        "development_package_count": len(new_dev),
        "changed_packages": changed_packages,
        "laravel_versions": {"before": "12.69.0", "after": "12.69.1"},
        "laravel_changed_fields": changed_fields(old_laravel, new_laravel),
        "package_membership_unchanged": True,
        "development_packages_unchanged": True,
        "top_level_lock_data_unchanged": True,
    }
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exception:
        print(f"STOP: {exception}", file=sys.stderr)
        raise SystemExit(1)
