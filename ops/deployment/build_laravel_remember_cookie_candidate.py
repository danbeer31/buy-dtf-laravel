#!/usr/bin/env python3
"""Build and attest the review-only Laravel 12.69.1 dependency candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from typing import Any

import laravel_remember_cookie_dependency_deploy as runner


EVIDENCE_DIRECTORY_NAME = "laravel-remember-cookie-runner-v2-20261002"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.chmod(path, mode)


def write_exclusive(path: Path, content: bytes, mode: int = 0o644) -> None:
    parent = runner.require_real_directory(path.parent)
    if path.exists() or path.is_symlink():
        raise runner.DeploymentError(f"Evidence output already exists: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, mode)
        runner.fsync_directory(parent)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def run_logged(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    logs: Path,
    timeout: int = 900,
) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    stdout_path = logs / f"{name}.stdout"
    stderr_path = logs / f"{name}.stderr"
    write_bytes(stdout_path, completed.stdout.encode("utf-8"))
    write_bytes(stderr_path, completed.stderr.encode("utf-8"))
    receipt = {
        "command": command,
        "exit_code": completed.returncode,
        "seconds": round(time.monotonic() - started, 3),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
    }
    if completed.returncode != 0:
        raise runner.DeploymentError(
            f"Clean-build command {name} failed with exit {completed.returncode}."
        )
    return {"receipt": receipt, "stdout": completed.stdout, "stderr": completed.stderr}


def full_vendor_manifest(root: Path, destination: Path) -> dict[str, Any]:
    root = runner.require_real_directory(root)
    records: list[dict[str, Any]] = []
    root_metadata = root.lstat()
    records.append(
        {
            "gid": root_metadata.st_gid,
            "kind": "directory",
            "mode": stat.S_IMODE(root_metadata.st_mode),
            "path": ".",
            "uid": root_metadata.st_uid,
        }
    )
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        metadata = path.lstat()
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(metadata.st_mode):
            kind = "directory"
            record: dict[str, Any] = {
                "gid": metadata.st_gid,
                "kind": kind,
                "mode": stat.S_IMODE(metadata.st_mode),
                "path": relative,
                "uid": metadata.st_uid,
            }
        elif stat.S_ISREG(metadata.st_mode):
            kind = "file"
            record = {
                "bytes": metadata.st_size,
                "gid": metadata.st_gid,
                "kind": kind,
                "mode": stat.S_IMODE(metadata.st_mode),
                "path": relative,
                "sha256": sha256_file(path),
                "uid": metadata.st_uid,
            }
        else:
            raise runner.DeploymentError(f"Vendor inventory found a non-regular path: {path}")
        records.append(record)
    payload = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for record in records
    )
    write_exclusive(destination, payload)
    return {
        "entries": len(records),
        "sha256": sha256_file(destination),
        "bytes": destination.stat().st_size,
    }


def uid33_read_only_probe(shadow: Path, php: Path, logs: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise runner.DeploymentError("UID/GID 33 proof requires a root-owned safe rehearsal.")
    if not Path("/usr/bin/setpriv").is_file():
        raise runner.DeploymentError("The reviewed setpriv executable is unavailable.")
    os.chmod(shadow.parent, 0o755)
    os.chmod(shadow, 0o755)
    probe_path = shadow.parent / "uid33-vendor-probe.php"
    probe_path.write_text(
        """<?php
declare(strict_types=1);
$shadow = $argv[1];
require $shadow . '/vendor/autoload.php';
$createPath = $shadow . '/vendor/.uid33-write-probe';
$create = @file_put_contents($createPath, 'denied');
$append = @fopen($shadow . '/vendor/autoload.php', 'ab');
$appendOpened = is_resource($append);
if ($appendOpened) {
    fclose($append);
}
echo json_encode([
    'euid' => posix_geteuid(),
    'egid' => posix_getegid(),
    'laravel_class_loaded' => class_exists(Illuminate\\Foundation\\Application::class),
    'laravel_version' => Illuminate\\Foundation\\Application::VERSION,
    'vendor_is_readable' => is_readable($shadow . '/vendor/autoload.php'),
    'vendor_is_writable' => is_writable($shadow . '/vendor'),
    'create_result' => $create,
    'append_opened' => $appendOpened,
    'probe_residue' => file_exists($createPath),
], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), PHP_EOL;
""",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(probe_path, 0o644)
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    residue = shadow / "vendor/.uid33-write-probe"
    try:
        result = run_logged(
            "uid33-vendor-read-only",
            [
                "/usr/bin/setpriv",
                "--reuid=33",
                "--regid=33",
                "--clear-groups",
                str(php),
                str(probe_path),
                str(shadow),
            ],
            cwd=shadow.parent,
            environment=environment,
            logs=logs,
            timeout=60,
        )
        try:
            payload = json.loads(result["stdout"])
        except json.JSONDecodeError as exception:
            raise runner.DeploymentError("UID/GID 33 proof returned invalid JSON.") from exception
        expected = {
            "euid": 33,
            "egid": 33,
            "laravel_class_loaded": True,
            "laravel_version": "12.69.1",
            "vendor_is_readable": True,
            "vendor_is_writable": False,
            "create_result": False,
            "append_opened": False,
            "probe_residue": False,
        }
        if residue.exists():
            raise runner.DeploymentError("UID/GID 33 unexpectedly wrote into candidate vendor.")
        if payload != expected:
            raise runner.DeploymentError(f"UID/GID 33 proof failed: {payload}")
        return {"result": payload, "command": result["receipt"]}
    finally:
        residue.unlink(missing_ok=True)
        probe_path.unlink(missing_ok=True)


def installed_versions(shadow: Path) -> dict[str, str | None]:
    installed = json.loads((shadow / "vendor/composer/installed.json").read_text(encoding="utf-8"))
    packages = installed.get("packages", installed) if isinstance(installed, dict) else installed
    versions = {
        package.get("name"): runner.normalize_package_version(package.get("version"))
        for package in packages
        if isinstance(package, dict)
    }
    return {name: versions.get(name) for name in runner.NEW_PACKAGE_VERSIONS}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--vendor-inventory", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--php", default=Path("/usr/bin/php8.3"), type=Path)
    parser.add_argument("--composer", default=Path("/usr/local/bin/composer"), type=Path)
    parser.add_argument(
        "--extraction",
        choices=("system-unzip", "php-zip-only"),
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    source = runner.require_real_directory(args.source)
    php = runner.require_regular_file(args.php)
    composer = runner.require_regular_file(args.composer)
    if os.geteuid() != 0:
        raise runner.DeploymentError("Clean deterministic build must run as root on Linux ext4.")
    if args.output.exists() or args.output.is_symlink():
        raise runner.DeploymentError("Clean-build output already exists.")
    evidence_parent = runner.require_real_directory(args.receipt.parent)
    inventory_parent = runner.require_real_directory(args.vendor_inventory.parent)
    if evidence_parent != inventory_parent:
        raise runner.DeploymentError("Receipt and inventory must share one reviewed evidence directory.")
    if evidence_parent.name != EVIDENCE_DIRECTORY_NAME:
        raise runner.DeploymentError("Evidence outputs must use the reviewed v2 evidence directory.")
    if args.receipt.exists() or args.receipt.is_symlink():
        raise runner.DeploymentError("Clean-build receipt already exists.")
    if args.vendor_inventory.exists() or args.vendor_inventory.is_symlink():
        raise runner.DeploymentError("Clean-build inventory already exists.")
    args.output.mkdir(mode=0o755, parents=False)
    os.chmod(args.output, 0o755)
    shadow = args.output / "shadow"
    shadow.mkdir(mode=0o755)
    logs = args.output / "logs"
    logs.mkdir(mode=0o755)
    composer_home = args.output / "composer-home"
    composer_home.mkdir(mode=0o700)
    (args.output / ".home").mkdir(mode=0o700)

    source_before = runner.source_manifest(source)
    if source_before != runner.EXPECTED_SOURCE_MANIFEST:
        raise runner.DeploymentError(
            f"Clean-build source CAS differs from the approved baseline: {source_before}"
        )
    shadow_source = runner.copy_runtime_shadow(source, shadow)
    runner.atomic_copy(source / "composer.lock", shadow / "composer.lock", 0o600)
    runner.require_regular_file(shadow / "composer.lock", runner.CANDIDATE_LOCK_SHA256)

    environment = runner.safe_environment(composer_home)
    tool_path = "/usr/local/bin:/usr/bin:/bin"
    if args.extraction == "php-zip-only":
        toolbin = args.output / "php-zip-toolbin"
        toolbin.mkdir(mode=0o755)
        (toolbin / "php").symlink_to(php)
        tool_path = str(toolbin)
    environment["PATH"] = tool_path
    unzip_path = shutil.which("unzip", path=tool_path)
    if args.extraction == "system-unzip" and unzip_path is None:
        raise runner.DeploymentError("System-unzip build environment has no unzip.")
    if args.extraction == "php-zip-only" and unzip_path is not None:
        raise runner.DeploymentError("PHP-Zip-only build environment unexpectedly exposes unzip.")

    commands: dict[str, dict[str, Any]] = {}

    def execute(name: str, command: list[str], timeout: int = 900) -> str:
        result = run_logged(
            name,
            command,
            cwd=shadow,
            environment=environment,
            logs=logs,
            timeout=timeout,
        )
        commands[name] = result["receipt"]
        return result["stdout"]

    execute(
        "composer-validate",
        [
            str(composer),
            "--no-plugins",
            "validate",
            "--strict",
            "--no-check-publish",
            "--no-interaction",
            "--no-ansi",
        ],
        120,
    )
    audit_stdout = execute(
        "composer-audit",
        [
            str(composer),
            "--no-plugins",
            "audit",
            "--locked",
            "--no-dev",
            "--format=json",
            "--no-interaction",
            "--no-ansi",
        ],
        120,
    )
    audit = json.loads(audit_stdout)
    advisories = audit.get("advisories") if isinstance(audit, dict) else None
    if advisories not in ({}, []):
        raise runner.DeploymentError("Locked no-dev Composer audit did not report zero advisories.")
    execute(
        "composer-install",
        [
            str(composer),
            "--no-plugins",
            "install",
            "--no-dev",
            "--prefer-dist",
            "--no-autoloader",
            "--no-interaction",
            "--no-scripts",
            "--no-ansi",
        ],
    )
    execute(
        "composer-dump-autoload",
        [
            str(composer),
            "--no-plugins",
            "dump-autoload",
            "--no-dev",
            "--optimize",
            "--no-scripts",
            "--no-interaction",
            "--no-ansi",
        ],
        300,
    )
    execute(
        "composer-platform",
        [
            str(composer),
            "--no-plugins",
            "check-platform-reqs",
            "--no-dev",
            "--no-interaction",
            "--no-ansi",
        ],
        120,
    )
    autoload_identity = runner.application_autoload_identity(shadow)
    if autoload_identity["sha256"] != runner.EXPECTED_APPLICATION_AUTOLOAD_SHA256:
        raise runner.DeploymentError("Clean-build application autoload identity differs from review.")
    execute(
        "package-discovery",
        [str(php), "artisan", "package:discover", "--no-interaction", "--no-ansi"],
        120,
    )
    route_stdout = execute(
        "route-discovery",
        [str(php), "artisan", "route:list", "--json", "--no-ansi"],
        120,
    )
    routes = json.loads(route_stdout)
    if not isinstance(routes, list) or len(routes) != runner.EXPECTED_ROUTE_COUNT:
        raise runner.DeploymentError("Clean build did not discover exactly 178 routes.")

    vendor_identity = runner.normalize_candidate_vendor(shadow / "vendor")
    if vendor_identity["manifest"] != runner.EXPECTED_CANDIDATE_VENDOR_MANIFEST:
        raise runner.DeploymentError("Clean-build vendor content/mode manifest differs from review.")
    if vendor_identity["metadata_sha256"] != runner.EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256:
        raise runner.DeploymentError(
            "Clean-build vendor ownership/mode manifest differs from review: "
            f"{vendor_identity['metadata_sha256']}"
        )
    cache_identity = runner.normalize_candidate_cache(shadow / "bootstrap/cache")
    if cache_identity != runner.EXPECTED_CANDIDATE_CACHE_IDENTITY:
        raise runner.DeploymentError("Clean-build bootstrap cache differs from review.")
    versions = installed_versions(shadow)
    if versions != runner.NEW_PACKAGE_VERSIONS:
        raise runner.DeploymentError("Clean-build package versions differ from the reviewed candidate.")
    if (shadow / "vendor/laravel/pail").exists():
        raise runner.DeploymentError("Clean no-dev build contains Laravel Pail.")

    uid33 = uid33_read_only_probe(shadow, php, logs)
    if runner.candidate_vendor_identity(shadow / "vendor") != vendor_identity:
        raise runner.DeploymentError("UID/GID 33 proof changed candidate vendor.")
    inventory = full_vendor_manifest(shadow / "vendor", args.vendor_inventory)
    source_after = runner.source_manifest(source)
    if source_after != source_before:
        raise runner.DeploymentError("Source CAS changed during clean-build preparation.")
    shadow_source_after = runner.source_manifest(shadow)
    if shadow_source_after != shadow_source:
        raise runner.DeploymentError("Shadow source CAS changed during clean-build preparation.")

    php_version = subprocess.run(
        [str(php), "-r", "echo PHP_VERSION;"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        env=environment,
    ).stdout
    composer_version = subprocess.run(
        [str(composer), "--version", "--no-ansi"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        env=environment,
    ).stdout.strip()
    receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-clean-build-v2",
        "artifact_review_status": runner.ARTIFACT_REVIEW_STATUS,
        "builder_sha256": sha256_file(Path(__file__).resolve(strict=True)),
        "runner_sha256": sha256_file(Path(runner.__file__).resolve(strict=True)),
        "handoff": {
            "filename": runner.HANDOFF_FILENAME,
            "sha256": runner.HANDOFF_SHA256,
        },
        "label": args.label,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_manifest_before": source_before,
        "source_manifest_after": source_after,
        "shadow_source_manifest": shadow_source,
        "shadow_source_manifest_after": shadow_source_after,
        "composer_json_sha256": sha256_file(shadow / "composer.json"),
        "composer_lock_sha256": sha256_file(shadow / "composer.lock"),
        "composer_bin_compat": environment["COMPOSER_BIN_COMPAT"],
        "extraction": args.extraction,
        "unzip_path": unzip_path,
        "php_version": php_version,
        "php_sha256": sha256_file(php),
        "composer_version": composer_version,
        "composer_sha256": sha256_file(composer),
        "commands": commands,
        "audit_advisory_count": 0,
        "package_versions": versions,
        "route_count": len(routes),
        "application_autoload_identity": autoload_identity,
        "vendor_identity": vendor_identity,
        "vendor_inventory": inventory,
        "cache_identity": cache_identity,
        "uid33_read_only_probe": uid33,
        "laravel_pail_present": False,
        "status": "pass",
    }
    write_exclusive(
        args.receipt,
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (runner.DeploymentError, subprocess.TimeoutExpired, OSError, ValueError) as exception:
        print(f"STOP: {exception}", file=sys.stderr)
        raise SystemExit(1)
