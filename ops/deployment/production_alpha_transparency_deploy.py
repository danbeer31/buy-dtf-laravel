#!/usr/bin/env python3
"""Stage, deploy, verify, and source-roll back the BuyDTF alpha repair.

The production boundary, artifact identities, source allowlist, migration, and
commands are fixed in this reviewed artifact.  Staging performs read-only live
preflight plus a single absolute-path ``artisan migrate --pretend``.  Cutover
and recovery are separate modes with separate approval tokens; staging never
invokes them.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any, Callable, Iterator


APP_ROOT = Path("/var/www/buy-dtf")
RELEASE_ROOT = APP_ROOT / "storage/app/private/operations/production-alpha-transparency-releases"
ROLLBACK_ROOT = APP_ROOT / "storage/app/private/operations/production-alpha-transparency-rollbacks"
DEPLOYMENT_LOCK = APP_ROOT / "storage/framework/production-alpha-transparency-deployment.lock"
DEPENDENCY_LOCK = APP_ROOT / "storage/framework/dependency-deployment.lock"
LARAVEL_MAINTENANCE_FILE = APP_ROOT / "storage/framework/down"
FRONT_CONTROLLER = APP_ROOT / "public/index.php"
FPM_SOCKET = Path("/run/php/php8.2-fpm.sock")

EXPECTED_APP_DEVICE = 64513
EXPECTED_APP_UID = 1000
EXPECTED_APP_GID = 1000
EXPECTED_WEB_UID = 33
EXPECTED_WEB_GID = 33
EXPECTED_FRONT_CONTROLLER_MODE = 0o644

TARGET_COMMIT = "5b2d06cd66bd599d8a7ab1f5518790d414ee9874"
ARTIFACT_BASE_COMMIT = "fca0484505348a40f31c372fa3642d1039504704"
TARGET_SHORT = TARGET_COMMIT[:8]
EXPECTED_ARCHIVE_SHA256 = "5dea236046e77a27922933b1650a318b9a685aaa19445be811dd948de156d0fb"
EXPECTED_MANIFEST_SHA256 = "26d988f87ac27b7dd034a532c22eaec207c60a32d16e890812ef5bbf0a1f5c2a"
EXPECTED_HELPER_SHA256 = "df1f627ccd2844c888373e9aa135d8e4971ac2900ccce105d3081a04e7b3ad61"
EXPECTED_MIGRATION_SHA256 = "992fbfe8086732e9bde10be89c3f52ddb4fef49edfdec12b744377c2e4181bbf"
MIGRATION_RELATIVE_PATH = Path(
    "database/migrations/2026_10_01_120000_add_item_meta_to_savedimages_table.php"
)
TARGET_MIGRATION = "2026_10_01_120000_add_item_meta_to_savedimages_table"
TARGET_TABLE = "savedimages"
TARGET_COLUMN = "item_meta"
EXPECTED_RUNTIME_PATHS = 8
EXPECTED_ADDITIONS = 1
EXPECTED_REPLACEMENTS = 7
EXPECTED_PRE_SCHEMA_SHA256 = "4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed"
EXPECTED_PRE_LEDGER_ROW_COUNT = 20
EXPECTED_PRE_LEDGER_SHA256 = "3168a7da9ca4aad0a81e673ec61c1647242916d054768f4dd48ff4b9d7eb28d4"
EXPECTED_PRE_SOURCE_CAS_SHA256 = "dd17d2cb76f227773f7faa7f830e3bf6cd4b8f152ec342190690d4baa3719cbd"
EXPECTED_TARGET_SOURCE_CAS_SHA256 = "daad3c0809ab2f295ede6d2daa75dcbfa3cb1db78d2a987b5f811516f4aa900f"
EXPECTED_PRETEND_STATEMENT = "alter table `savedimages` add `item_meta` text null"

EXPECTED_COMPOSER_LOCK_SHA256 = "22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9"
EXPECTED_VENDOR_MANIFEST_SHA256 = "7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed"
EXPECTED_CACHE_MANIFEST_SHA256 = "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9"
EXPECTED_PACKAGES_SHA256 = "21da8f9ed19687e708cc7bc5cc59394c6fcdf9b9deadf617ae70526f815a1db0"
EXPECTED_SERVICES_SHA256 = "1f7623b2b4ffd2c4099fb34ad86fc96c1479e27bf81b1b0ba328c988cc4ffcb5"
EXPECTED_FRONT_CONTROLLER_SHA256 = "eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9"

STAGE_APPROVAL_TOKEN = f"STAGE-BUYDTF-ALPHA-{TARGET_COMMIT[:16]}"
DEPLOY_APPROVAL_TOKEN = f"DEPLOY-BUYDTF-ALPHA-{TARGET_COMMIT[:16]}"
RECOVERY_APPROVAL_TOKEN = f"RECOVER-BUYDTF-ALPHA-{TARGET_COMMIT[:16]}"

DRAIN_SECONDS = 65
OPCACHE_WAIT_SECONDS = 5
MONITOR_SECONDS = 30 * 60
MONITOR_INTERVAL_SECONDS = 60

NORMAL_HEALTH_CHECKS: tuple[tuple[str, frozenset[int]], ...] = (
    ("https://buy-dtf.com/", frozenset({200})),
    ("https://buy-dtf.com/up", frozenset({200})),
    ("https://buy-dtf.com/login", frozenset({200})),
    ("https://buy-dtf.com/admin", frozenset({302})),
    ("https://buy-dtf.com/checkout", frozenset({302})),
    ("https://www.buy-dtf.com/", frozenset({200})),
    ("https://www.buy-dtf.com/up", frozenset({200})),
)

MAINTENANCE_GATE_HEADER_NAME = "X-BuyDTF-Dependency-Maintenance"
MAINTENANCE_GATE_HEADER_VALUE = "static-v2"
MAINTENANCE_GATE_SENTINEL = "BUYDTF_DEPENDENCY_MAINTENANCE_STATIC_V2"
MAINTENANCE_GATE_BYTES = f"""<?php
declare(strict_types=1);

http_response_code(503);
header('Content-Type: text/plain; charset=UTF-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Retry-After: 120');
header('{MAINTENANCE_GATE_HEADER_NAME}: {MAINTENANCE_GATE_HEADER_VALUE}');
echo '{MAINTENANCE_GATE_SENTINEL}';
""".encode("utf-8")
EXPECTED_GATE_SHA256 = "94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03"


class DeploymentError(RuntimeError):
    """A reviewed condition failed and the operation must stop closed."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    ).encode("utf-8")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(6)}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_write(path, canonical_bytes(payload), 0o600)


def require_real_directory(path: Path, *, within: Path | None = None) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise DeploymentError(f"Required directory is missing, invalid, or symbolic: {path}")
    resolved = path.resolve(strict=True)
    if within is not None:
        parent = within.resolve(strict=True)
        if not is_relative_to(resolved, parent):
            raise DeploymentError(f"Directory escapes its approved root: {path}")
    return resolved


def require_regular_file(path: Path, expected_sha256: str | None = None) -> Path:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise DeploymentError(f"Required file is missing, invalid, or symbolic: {path}")
    if expected_sha256 is not None:
        actual = sha256_file(path)
        if actual != expected_sha256:
            raise DeploymentError(
                f"Checksum mismatch for {path}: expected {expected_sha256}, got {actual}"
            )
    return path.resolve(strict=True)


def path_metadata(path: Path) -> dict[str, int | str]:
    if path.is_symlink():
        raise DeploymentError(f"Symbolic paths are not allowed: {path}")
    metadata = path.stat()
    if stat.S_ISREG(metadata.st_mode):
        kind = "file"
    elif stat.S_ISDIR(metadata.st_mode):
        kind = "directory"
    else:
        raise DeploymentError(f"Special paths are not allowed: {path}")
    return {
        "kind": kind,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def file_identity(path: Path) -> dict[str, Any]:
    path = require_regular_file(path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "metadata": path_metadata(path),
    }


def reviewed_front_controller_metadata() -> dict[str, int | str]:
    return {
        "kind": "file",
        "mode": EXPECTED_FRONT_CONTROLLER_MODE,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
    }


def require_exact_metadata(
    path: Path, expected: dict[str, Any], *, label: str
) -> dict[str, int | str]:
    actual = path_metadata(path)
    if actual != expected:
        raise DeploymentError(
            f"{label} metadata differs from the reviewed identity: "
            f"expected {expected}, got {actual}"
        )
    return actual


def tree_manifest(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    records: list[bytes] = []
    files = 0
    directories = 0
    byte_count = 0
    for current_root, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)
        for name in directory_names:
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise DeploymentError(f"Tree contains an invalid directory: {path}")
            relative = path.relative_to(root).as_posix()
            records.append(
                f"d\0{relative}\0{stat.S_IMODE(path.stat().st_mode):o}\n".encode()
            )
            directories += 1
        for name in file_names:
            path = current / name
            if path.is_symlink() or not path.is_file():
                raise DeploymentError(f"Tree contains an invalid file: {path}")
            metadata = path.stat()
            relative = path.relative_to(root).as_posix()
            digest = sha256_file(path)
            records.append(
                f"f\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0"
                f"{metadata.st_size}\0{digest}\n".encode()
            )
            files += 1
            byte_count += metadata.st_size
    records.sort()
    return {
        "sha256": sha256_bytes(b"".join(records)),
        "files": files,
        "directories": directories,
        "bytes": byte_count,
    }


def atomic_copy(source: Path, destination: Path, mode: int = 0o600) -> None:
    require_regular_file(source)
    temporary = destination.with_name(
        f".{destination.name}.tmp-{os.getpid()}-{secrets.token_hex(6)}"
    )
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, mode)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def exclusive_lock(path: Path, *, create: bool) -> Iterator[None]:
    if not create and not path.exists():
        yield
        return
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    mode = "a+b" if create else "r+b"
    with path.open(mode) as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exception:
            raise DeploymentError(f"Another operation holds lock {path}.") from exception
        yield


def lock_is_free(path: Path) -> bool:
    if not path.exists():
        return True
    if path.is_symlink() or not path.is_file():
        raise DeploymentError(f"Deployment lock path is invalid: {path}")
    with path.open("rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    return True


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def capture_command(
    command: list[str],
    *,
    cwd: Path,
    evidence_directory: Path,
    name: str,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    completed = run_command(command, cwd=cwd, timeout=timeout, env=env)
    duration = round(time.monotonic() - started, 6)
    stdout_path = evidence_directory / f"{name}.stdout.txt"
    stderr_path = evidence_directory / f"{name}.stderr.txt"
    atomic_write(stdout_path, completed.stdout.encode("utf-8"), 0o600)
    atomic_write(stderr_path, completed.stderr.encode("utf-8"), 0o600)
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_status": completed.returncode,
        "duration_seconds": duration,
        "stdout": {
            "path": str(stdout_path),
            "sha256": sha256_file(stdout_path),
            "bytes": stdout_path.stat().st_size,
        },
        "stderr": {
            "path": str(stderr_path),
            "sha256": sha256_file(stderr_path),
            "bytes": stderr_path.stat().st_size,
        },
    }


def require_command_success(result: dict[str, Any], name: str) -> None:
    if result.get("exit_status") != 0:
        raise DeploymentError(f"{name} failed with exit status {result.get('exit_status')}.")


def parse_manifest(path: Path) -> list[dict[str, Any]]:
    require_regular_file(path, EXPECTED_MANIFEST_SHA256)
    try:
        document = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exception:
        raise DeploymentError("The reviewed application manifest is invalid JSON.") from exception
    if not isinstance(document, dict) or not isinstance(document.get("paths"), list):
        raise DeploymentError("The reviewed application manifest has an invalid shape.")
    if document.get("hash_algorithm") != "sha256 over exact raw file bytes":
        raise DeploymentError("The manifest does not declare raw-byte hashing.")
    if document.get("expected_schema_sha256") != EXPECTED_PRE_SCHEMA_SHA256:
        raise DeploymentError("The manifest schema baseline differs from the runner.")
    ledger = document.get("expected_ledger", {})
    if (
        ledger.get("row_count") != EXPECTED_PRE_LEDGER_ROW_COUNT
        or ledger.get("sha256") != EXPECTED_PRE_LEDGER_SHA256
        or ledger.get("target_entry_count") != 0
    ):
        raise DeploymentError("The manifest ledger baseline differs from the runner.")
    migration = document.get("migration", {})
    if (
        migration.get("name") != TARGET_MIGRATION
        or migration.get("expected_live_state") != "absent"
        or migration.get("expected_pretend_statement") != EXPECTED_PRETEND_STATEMENT
        or migration.get("target_sha256") != EXPECTED_MIGRATION_SHA256
    ):
        raise DeploymentError("The manifest migration identity differs from the runner.")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_row in enumerate(document["paths"], start=1):
        if not isinstance(raw_row, dict):
            raise DeploymentError(f"Manifest path row {index} is not an object.")
        relative_text = raw_row.get("path")
        if not isinstance(relative_text, str):
            raise DeploymentError(f"Manifest path row {index} has no path.")
        pure = PurePosixPath(relative_text)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "." in pure.parts
            or not pure.parts
            or "\\" in relative_text
            or relative_text in seen
        ):
            raise DeploymentError(f"Unsafe or duplicate manifest path: {relative_text}")
        target = raw_row.get("target_sha256")
        if not isinstance(target, str) or not re.fullmatch(r"[0-9a-f]{64}", target):
            raise DeploymentError(f"Invalid target digest for {relative_text}.")
        target_bytes = raw_row.get("target_bytes")
        if not isinstance(target_bytes, int) or target_bytes < 1:
            raise DeploymentError(f"Invalid target byte count for {relative_text}.")
        if raw_row.get("expected_live_state") == "absent":
            action = "A"
            expected = "ABSENT"
            expected_bytes = None
        else:
            action = "M"
            expected = raw_row.get("expected_live_sha256")
            expected_bytes = raw_row.get("expected_live_bytes")
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise DeploymentError(f"Replacement has an invalid expected digest: {relative_text}")
            if not isinstance(expected_bytes, int) or expected_bytes < 1:
                raise DeploymentError(f"Replacement has no exact live byte count: {relative_text}")
        seen.add(relative_text)
        rows.append(
            {
                "action": action,
                "expected": expected,
                "expected_bytes": expected_bytes,
                "target": target,
                "target_bytes": target_bytes,
                "path": relative_text,
            }
        )
    additions = sum(row["action"] == "A" for row in rows)
    replacements = sum(row["action"] == "M" for row in rows)
    if (
        len(rows) != EXPECTED_RUNTIME_PATHS
        or additions != EXPECTED_ADDITIONS
        or replacements != EXPECTED_REPLACEMENTS
    ):
        raise DeploymentError("Manifest path/action counts differ from the reviewed identity.")
    return rows


def live_manifest_snapshot(rows: list[dict[str, Any]], *, target: bool = False) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    cas_rows: list[dict[str, Any]] = []
    for row in rows:
        relative = row["path"]
        path = APP_ROOT / Path(relative)
        if path.is_symlink():
            raise DeploymentError(f"Live manifest path is symbolic: {relative}")
        if not is_relative_to(path.resolve(strict=False), APP_ROOT.resolve(strict=True)):
            raise DeploymentError(f"Live manifest path escapes the application root: {relative}")
        expected = row["target"] if target else row["expected"]
        if expected == "ABSENT":
            if path.exists():
                raise DeploymentError(f"Manifest addition is no longer absent: {relative}")
            results.append({"path": relative, "state": "absent", "matches": True})
            cas_rows.append({"path": relative, "state": "absent"})
            continue
        require_regular_file(path)
        actual = sha256_file(path)
        if actual != expected:
            raise DeploymentError(
                f"Live source CAS mismatch for {relative}: expected {expected}, got {actual}"
            )
        expected_bytes = row["target_bytes"] if target else row["expected_bytes"]
        actual_bytes = path.stat().st_size
        if actual_bytes != expected_bytes:
            raise DeploymentError(
                f"Live source byte count mismatch for {relative}: "
                f"expected {expected_bytes}, got {actual_bytes}"
            )
        results.append(
            {
                "path": relative,
                "state": "file",
                "sha256": actual,
                "bytes": actual_bytes,
                "metadata": path_metadata(path),
                "matches": True,
            }
        )
        cas_rows.append(
            {"path": relative, "state": "file", "sha256": actual, "bytes": actual_bytes}
        )
    snapshot = {
        "expectation": "target" if target else "expected-live",
        "count": len(results),
        "rows": results,
        "cas_rows": cas_rows,
        "sha256": sha256_bytes(canonical_bytes(cas_rows)),
    }
    expected_cas = (
        EXPECTED_TARGET_SOURCE_CAS_SHA256 if target else EXPECTED_PRE_SOURCE_CAS_SHA256
    )
    if snapshot["sha256"] != expected_cas:
        label = "target" if target else "original"
        raise DeploymentError(f"The eight-path {label} source CAS differs from baseline.")
    return snapshot


def scoped_processes() -> list[dict[str, str]]:
    patterns = (
        "artisan migrate",
        "artisan stripe:sync-payouts",
        "artisan queue:",
        "artisan schedule:",
        "composer install",
        "composer update",
        "atomic_dependency_deploy.py --cutover",
        "incoming_order_v1_deploy.py --deploy",
        "production_alpha_transparency_deploy.py --deploy",
    )
    matches: list[dict[str, str]] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in {os.getpid(), os.getppid()}:
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        lowered = command.lower()
        if not any(pattern.lower() in lowered for pattern in patterns):
            continue
        scoped = str(APP_ROOT).lower() in lowered
        try:
            working_directory = (entry / "cwd").resolve(strict=True)
            scoped = scoped or working_directory == APP_ROOT or is_relative_to(
                working_directory, APP_ROOT
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError, RuntimeError):
            pass
        try:
            cgroup = (entry / "cgroup").read_text("utf-8", errors="replace").lower()
            scoped = scoped or "buy-dtf" in cgroup or "buy_dtf" in cgroup
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
        if scoped:
            matches.append({"pid": entry.name, "classification": "scoped-conflict"})
    return sorted(matches, key=lambda item: int(item["pid"]))


def active_fpm_connections() -> int:
    completed = run_command(
        ["/usr/bin/ss", "-H", "-x", "state", "connected"], cwd=APP_ROOT, timeout=15
    )
    if completed.returncode != 0:
        raise DeploymentError("Unable to inspect PHP-FPM connections.")
    return sum(1 for line in completed.stdout.splitlines() if str(FPM_SOCKET) in line)


def http_probe(url: str) -> dict[str, Any]:
    separator = "&" if "?" in url else "?"
    target = f"{url}{separator}ops_probe={secrets.token_hex(12)}"
    completed = run_command(
        [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--output",
            "/dev/null",
            "--write-out",
            "%{http_code}\t%{size_download}\t%{redirect_url}",
            "--header",
            "Cache-Control: no-cache, no-store",
            "--header",
            "Pragma: no-cache",
            "--connect-timeout",
            "5",
            "--max-time",
            "15",
            "--max-redirs",
            "0",
            target,
        ],
        cwd=APP_ROOT,
        timeout=20,
    )
    if completed.returncode != 0:
        raise DeploymentError(f"HTTP probe failed for {url}.")
    fields = completed.stdout.split("\t", 2)
    if len(fields) != 3 or not fields[0].isdigit():
        raise DeploymentError(f"HTTP probe returned an invalid result for {url}.")
    return {
        "url": url,
        "status": int(fields[0]),
        "bytes": int(fields[1]) if fields[1].isdigit() else None,
        "redirect_present": bool(fields[2]),
    }


def health_snapshot() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for url, allowed in NORMAL_HEALTH_CHECKS:
        result = http_probe(url)
        if result["status"] not in allowed:
            raise DeploymentError(f"Health probe failed for {url}: HTTP {result['status']}")
        results.append(result)

    vite_manifest_path = APP_ROOT / "public/build/manifest.json"
    require_regular_file(vite_manifest_path)
    try:
        vite_manifest = json.loads(vite_manifest_path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exception:
        raise DeploymentError("The live Vite manifest is invalid.") from exception
    asset_paths: set[str] = set()
    if not isinstance(vite_manifest, dict):
        raise DeploymentError("The live Vite manifest is not an object.")
    for item in vite_manifest.values():
        if not isinstance(item, dict):
            continue
        file_name = item.get("file")
        if isinstance(file_name, str):
            asset_paths.add(file_name)
        css = item.get("css", [])
        if isinstance(css, list):
            asset_paths.update(value for value in css if isinstance(value, str))
    asset_results = []
    for asset in sorted(asset_paths):
        result = http_probe(f"https://buy-dtf.com/build/{asset.lstrip('/')}")
        if result["status"] != 200:
            raise DeploymentError(f"Vite asset probe failed for {asset}.")
        asset_results.append(result)
    return {
        "routes": results,
        "vite_manifest_sha256": sha256_file(vite_manifest_path),
        "vite_assets": asset_results,
    }


def runtime_probe(helper: Path, evidence_directory: Path, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    result = capture_command(
        ["/usr/bin/php", str(helper), str(APP_ROOT)],
        cwd=APP_ROOT,
        evidence_directory=evidence_directory,
        name=name,
        timeout=120,
    )
    require_command_success(result, name)
    stdout_path = Path(str(result["stdout"]["path"]))
    try:
        payload = json.loads(stdout_path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exception:
        raise DeploymentError("The runtime helper returned invalid JSON.") from exception
    if not isinstance(payload, dict):
        raise DeploymentError("The runtime helper returned a non-object payload.")
    return payload, result


def validate_runtime_snapshot(
    payload: dict[str, Any],
    *,
    require_target_absent: bool,
    require_all_item_meta_null: bool = False,
) -> dict[str, Any]:
    if (
        payload.get("probe_version") != 2
        or payload.get("artifact")
        != "buy-dtf-production-alpha-transparency-runtime-probe-v1"
    ):
        raise DeploymentError("The runtime probe identity differs from the reviewed helper.")
    if payload.get("application_environment") != "local":
        raise DeploymentError("APP_ENV differs from the reviewed local value.")
    if payload.get("application_debug") is not False:
        raise DeploymentError("APP_DEBUG is not false.")
    runtime = payload.get("runtime", {})
    if runtime.get("php_version") != "8.2.30" or runtime.get("laravel_version") != "12.69.0":
        raise DeploymentError("PHP/Laravel runtime identity differs from the reviewed baseline.")
    if runtime.get("composer_classmap_authoritative") is not False:
        raise DeploymentError("Composer is unexpectedly class-map authoritative.")
    if runtime.get("imagick_loaded") is not True:
        raise DeploymentError("Imagick is unavailable.")
    connections = payload.get("connections", {})
    if (
        connections.get("configured_fuel_connection") != "fuelmysql"
        or connections.get("expected_fuel_connection") != "fuelmysql"
        or connections.get("migration_invocation_connection") != "fuelmysql"
        or connections.get("fuel_driver") != "mysql"
        or connections.get("connection_match") is not True
    ):
        raise DeploymentError("Fuel connection proof differs from the reviewed fuelmysql connection.")
    ledger = payload.get("migration_ledger", {})
    if ledger.get("exists") is not True or ledger.get("target_migration") != TARGET_MIGRATION:
        raise DeploymentError("Fuel migration ledger proof is unavailable.")
    schema = payload.get("schema", {})
    if (
        not isinstance(schema.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", schema["sha256"])
        or not isinstance(ledger.get("rows_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", ledger["rows_sha256"])
    ):
        raise DeploymentError("Schema or ledger fingerprint is malformed.")
    required = schema.get("required_tables", {})
    if any(
        required.get(name) is not True
        for name in ("businesses", "dtforders", "dtfimages", TARGET_TABLE)
    ):
        raise DeploymentError("A required Fuel table is missing.")
    item_meta = schema.get("savedimages_item_meta", {})
    data_columns = item_meta.get("data_columns_without_item_meta")
    data_sha256 = item_meta.get("data_sha256_without_item_meta")
    if (
        not isinstance(data_columns, list)
        or not data_columns
        or TARGET_COLUMN in data_columns
        or not isinstance(data_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", data_sha256)
    ):
        raise DeploymentError("The deterministic savedimages data fingerprint is unavailable.")
    if (
        schema.get("without_item_meta_sha256") != EXPECTED_PRE_SCHEMA_SHA256
        or ledger.get("without_target_row_count") != EXPECTED_PRE_LEDGER_ROW_COUNT
        or ledger.get("without_target_rows_sha256") != EXPECTED_PRE_LEDGER_SHA256
    ):
        raise DeploymentError("Schema or ledger contains drift outside the reviewed additive change.")
    if require_target_absent:
        if (
            schema.get("sha256") != EXPECTED_PRE_SCHEMA_SHA256
            or ledger.get("row_count") != EXPECTED_PRE_LEDGER_ROW_COUNT
            or ledger.get("rows_sha256") != EXPECTED_PRE_LEDGER_SHA256
            or ledger.get("target_entry_count") != 0
            or item_meta.get("exists") is not False
            or item_meta.get("definition") != []
            or item_meta.get("nonnull_rows") is not None
        ):
            raise DeploymentError("The pre-migration schema or ledger differs from baseline.")
        schema_state = "absent"
    else:
        definition = item_meta.get("definition")
        if (
            ledger.get("row_count") != EXPECTED_PRE_LEDGER_ROW_COUNT + 1
            or ledger.get("target_entry_count") != 1
            or item_meta.get("exists") is not True
            or not isinstance(definition, list)
            or len(definition) != 1
        ):
            raise DeploymentError("The guarded item_meta migration is not exactly installed.")
        column = definition[0]
        if (
            column.get("TABLE_NAME") != TARGET_TABLE
            or column.get("COLUMN_NAME") != TARGET_COLUMN
            or str(column.get("COLUMN_TYPE", "")).lower() != "text"
            or column.get("IS_NULLABLE") != "YES"
            or column.get("COLUMN_DEFAULT") is not None
            or str(column.get("EXTRA", "")) != ""
            or str(column.get("GENERATION_EXPRESSION", "")) != ""
        ):
            raise DeploymentError("savedimages.item_meta does not have the reviewed nullable TEXT definition.")
        if require_all_item_meta_null and item_meta.get("nonnull_rows") != 0:
            raise DeploymentError("A pre-existing Saved Image row has non-null item_meta metadata.")
        schema_state = "installed"
    capabilities = payload.get("capabilities", {})
    if (
        capabilities.get("receiver_enabled") is not False
        or capabilities.get("job_label_enabled") is not False
        or capabilities.get("retention_enabled") is not False
        or capabilities.get("allowed_host_count") != 0
    ):
        raise DeploymentError("An incoming-order capability or artwork host is unexpectedly enabled.")
    queue = payload.get("queue", {})
    if queue.get("connection") != "sync":
        raise DeploymentError("The queue connection is no longer sync.")
    counts = queue.get("counts", {})
    if counts.get("jobs") not in (0, None) or counts.get("failed_jobs") not in (0, None):
        raise DeploymentError("Queued or failed jobs are present.")
    scheduler = payload.get("scheduler", {})
    if (
        scheduler.get("stripe_payout_sync_event_count") != 1
        or scheduler.get("active_overlap_mutex_count") != 0
        or not isinstance(scheduler.get("overlap_mutexes"), list)
    ):
        raise DeploymentError("Scheduled work or an overlap mutex differs from baseline.")
    return {
        "status": "pass",
        "schema_state": schema_state,
        "schema_sha256": schema.get("sha256"),
        "schema_without_item_meta_sha256": schema.get("without_item_meta_sha256"),
        "ledger_row_count": ledger.get("row_count"),
        "ledger_sha256": ledger.get("rows_sha256"),
        "ledger_without_target_sha256": ledger.get("without_target_rows_sha256"),
        "target_migration_entries": ledger.get("target_entry_count"),
        "savedimages_rows": item_meta.get("savedimages_rows"),
        "savedimages_data_columns": data_columns,
        "savedimages_data_sha256": data_sha256,
        "item_meta_nonnull_rows": item_meta.get("nonnull_rows"),
    }


def verify_rollback_schema_state(
    payload: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    """Accept only the exact before or exact additive schema after a failed command."""
    item_meta = payload.get("schema", {}).get("savedimages_item_meta", {})
    ledger = payload.get("migration_ledger", {})
    if item_meta.get("exists") is False and ledger.get("target_entry_count") == 0:
        observed = "absent"
        verification = validate_runtime_snapshot(payload, require_target_absent=True)
    elif item_meta.get("exists") is True and ledger.get("target_entry_count") == 1:
        observed = "installed"
        verification = validate_runtime_snapshot(payload, require_target_absent=False)
    else:
        raise DeploymentError("Rollback observed a partial or drifted migration state.")
    if state.get("migration_executed") is True and observed != "installed":
        raise DeploymentError("A completed migration was not preserved during rollback.")
    if not state.get("migration_execution_started") and observed != "absent":
        raise DeploymentError("Schema changed before the migration execution boundary.")
    return {
        "status": "pass",
        "observed_schema_state": observed,
        "migration_execution_started": bool(state.get("migration_execution_started")),
        "migration_executed": bool(state.get("migration_executed")),
        "additive_schema_preserved": observed == "installed",
        "verification": verification,
    }


def dependency_identity() -> dict[str, Any]:
    require_regular_file(APP_ROOT / "composer.lock", EXPECTED_COMPOSER_LOCK_SHA256)
    require_regular_file(
        APP_ROOT / "bootstrap/cache/packages.php", EXPECTED_PACKAGES_SHA256
    )
    require_regular_file(
        APP_ROOT / "bootstrap/cache/services.php", EXPECTED_SERVICES_SHA256
    )
    cache_names = sorted(path.name for path in (APP_ROOT / "bootstrap/cache").iterdir())
    if cache_names != ["packages.php", "services.php"]:
        raise DeploymentError("Bootstrap cache contains an unreviewed file set.")
    vendor = tree_manifest(APP_ROOT / "vendor")
    cache = tree_manifest(APP_ROOT / "bootstrap/cache")
    if vendor["sha256"] != EXPECTED_VENDOR_MANIFEST_SHA256:
        raise DeploymentError("The live vendor tree differs from the successful v2 receipt.")
    if cache["sha256"] != EXPECTED_CACHE_MANIFEST_SHA256:
        raise DeploymentError("The live bootstrap cache differs from the successful v2 receipt.")
    return {
        "composer_lock_sha256": EXPECTED_COMPOSER_LOCK_SHA256,
        "vendor": vendor,
        "bootstrap_cache": cache,
        "packages_sha256": EXPECTED_PACKAGES_SHA256,
        "services_sha256": EXPECTED_SERVICES_SHA256,
    }


def production_preflight(
    *,
    helper: Path,
    manifest_rows: list[dict[str, Any]],
    evidence_directory: Path,
    prefix: str,
    require_target_absent: bool = True,
) -> dict[str, Any]:
    if os.geteuid() == 0:
        raise DeploymentError("Refusing to run an application deployment artifact as root.")
    if sys.version_info[:3] != (3, 10, 12):
        raise DeploymentError("Python differs from the reviewed 3.10.12 runtime.")
    for executable in (
        "/usr/bin/php",
        "/usr/bin/curl",
        "/usr/bin/cgi-fcgi",
        "/usr/bin/ss",
        "/usr/bin/mysql",
        "/usr/bin/mysqldump",
    ):
        if not Path(executable).is_file() or not os.access(executable, os.X_OK):
            raise DeploymentError(f"Required executable is unavailable: {executable}")
    if not FPM_SOCKET.is_socket():
        raise DeploymentError("The reviewed PHP-FPM socket is unavailable.")
    root = require_real_directory(APP_ROOT)
    root_stat = root.stat()
    if root_stat.st_dev != EXPECTED_APP_DEVICE:
        raise DeploymentError("Application filesystem device differs from the reviewed value.")
    if root_stat.st_uid != EXPECTED_APP_UID or root_stat.st_gid != EXPECTED_APP_GID:
        raise DeploymentError("Application root owner/group differs from the reviewed value.")
    if LARAVEL_MAINTENANCE_FILE.exists():
        raise DeploymentError("Laravel maintenance is unexpectedly active.")
    require_regular_file(FRONT_CONTROLLER, EXPECTED_FRONT_CONTROLLER_SHA256)
    front_controller_metadata = require_exact_metadata(
        FRONT_CONTROLLER,
        reviewed_front_controller_metadata(),
        label="Front controller",
    )
    require_regular_file(helper, EXPECTED_HELPER_SHA256)
    if sha256_bytes(MAINTENANCE_GATE_BYTES) != EXPECTED_GATE_SHA256:
        raise DeploymentError("Embedded static-gate bytes differ from the reviewed identity.")
    if not lock_is_free(DEPENDENCY_LOCK):
        raise DeploymentError("The dependency deployment lock is active.")
    conflicts = scoped_processes()
    if conflicts:
        raise DeploymentError("A scoped production process is active.")
    live_source = live_manifest_snapshot(manifest_rows, target=not require_target_absent)
    dependencies = dependency_identity()
    runtime, runtime_command = runtime_probe(helper, evidence_directory, f"{prefix}-runtime-probe")
    validate_runtime_snapshot(runtime, require_target_absent=require_target_absent)
    health = health_snapshot()
    disk = shutil.disk_usage(APP_ROOT)
    if disk.free < 2 * 1024 * 1024 * 1024:
        raise DeploymentError("Less than 2 GiB is available on the application filesystem.")
    return {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "application_root": str(root),
        "application_device": root_stat.st_dev,
        "application_metadata": path_metadata(root),
        "maintenance_active": False,
        "static_gate_active": False,
        "dependency_lock_free": True,
        "alpha_repair_lock_free": lock_is_free(DEPLOYMENT_LOCK),
        "scoped_processes": conflicts,
        "active_fpm_connections_observed": active_fpm_connections(),
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "front_controller_sha256": EXPECTED_FRONT_CONTROLLER_SHA256,
        "front_controller_metadata": front_controller_metadata,
        "dependencies": dependencies,
        "live_source": live_source,
        "runtime": runtime,
        "runtime_command": runtime_command,
        "health": health,
    }


def runtime_probe_memory(helper: Path) -> dict[str, Any]:
    completed = run_command(
        ["/usr/bin/php", str(helper), str(APP_ROOT)], cwd=APP_ROOT, timeout=120
    )
    if completed.returncode != 0:
        raise DeploymentError("The read-only runtime probe failed.")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise DeploymentError("The read-only runtime probe returned invalid JSON.") from exception
    if not isinstance(payload, dict):
        raise DeploymentError("The read-only runtime probe returned a non-object payload.")
    return payload


def preflight_guard(helper: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Perform the hard-stop checks without creating a receipt or directory."""
    if os.geteuid() == 0:
        raise DeploymentError("Refusing to run an application deployment artifact as root.")
    root = require_real_directory(APP_ROOT)
    if root.stat().st_dev != EXPECTED_APP_DEVICE:
        raise DeploymentError("Application filesystem device differs from the reviewed value.")
    if LARAVEL_MAINTENANCE_FILE.exists():
        raise DeploymentError("Laravel maintenance is unexpectedly active.")
    require_regular_file(FRONT_CONTROLLER, EXPECTED_FRONT_CONTROLLER_SHA256)
    require_regular_file(helper, EXPECTED_HELPER_SHA256)
    if not lock_is_free(DEPENDENCY_LOCK) or not lock_is_free(DEPLOYMENT_LOCK):
        raise DeploymentError("A production deployment lock is active.")
    if scoped_processes():
        raise DeploymentError("A scoped production process is active.")
    source = live_manifest_snapshot(rows, target=False)
    dependencies = dependency_identity()
    runtime = runtime_probe_memory(helper)
    validate_runtime_snapshot(runtime, require_target_absent=True)
    health = health_snapshot()
    return {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "source": source,
        "dependencies": dependencies,
        "runtime": runtime,
        "health": health,
    }


def validate_archive_members(
    archive: Path, rows: list[dict[str, Any]]
) -> list[tarfile.TarInfo]:
    expected_paths = {row["path"] for row in rows}
    with tarfile.open(archive, mode="r:") as handle:
        members = handle.getmembers()
    regular_members: list[tarfile.TarInfo] = []
    seen: set[str] = set()
    for member in members:
        name = member.name.removeprefix("./")
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            raise DeploymentError(f"Archive contains an unsafe path: {member.name}")
        if member.isdir():
            continue
        if not member.isfile() or member.islnk() or member.issym():
            raise DeploymentError(f"Archive contains a non-regular member: {member.name}")
        if name in seen:
            raise DeploymentError(f"Archive contains a duplicate file: {name}")
        seen.add(name)
        member.name = name
        regular_members.append(member)
    if seen != expected_paths:
        missing = sorted(expected_paths - seen)
        extra = sorted(seen - expected_paths)
        raise DeploymentError(f"Archive path set differs from manifest; missing={missing}, extra={extra}")
    return regular_members


def extract_candidate(
    archive: Path,
    candidate: Path,
    rows: list[dict[str, Any]],
    evidence_directory: Path,
) -> dict[str, Any]:
    candidate.mkdir(mode=0o700, parents=False, exist_ok=False)
    members = validate_archive_members(archive, rows)
    extraction_rows: list[dict[str, Any]] = []
    with tarfile.open(archive, mode="r:") as handle:
        member_by_name = {member.name.removeprefix("./"): member for member in handle.getmembers()}
        for row in rows:
            relative = row["path"]
            member = member_by_name[relative]
            target = candidate / Path(relative)
            resolved_parent = target.parent.resolve(strict=False)
            if not is_relative_to(resolved_parent, candidate.resolve(strict=True)):
                raise DeploymentError(f"Candidate target escapes staging root: {relative}")
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            for parent in [target.parent, *target.parent.parents]:
                if parent == candidate.parent:
                    break
                if parent.is_symlink():
                    raise DeploymentError(f"Candidate parent is symbolic: {parent}")
                if parent == candidate:
                    break
            source = handle.extractfile(member)
            if source is None:
                raise DeploymentError(f"Unable to read archive member: {relative}")
            content = source.read()
            atomic_write(target, content, 0o600)
            digest = sha256_file(target)
            if digest != row["target"]:
                raise DeploymentError(
                    f"Candidate target digest mismatch for {relative}: {digest}"
                )
            if target.stat().st_size != row["target_bytes"]:
                raise DeploymentError(f"Candidate target byte count mismatch for {relative}.")
            extraction_rows.append(
                {
                    "path": relative,
                    "sha256": digest,
                    "bytes": target.stat().st_size,
                    "staged_mode": stat.S_IMODE(target.stat().st_mode),
                }
            )
    log_path = evidence_directory / "candidate-extraction.json"
    atomic_json(log_path, extraction_rows)
    return {
        "files": len(extraction_rows),
        "rows_sha256": sha256_bytes(canonical_bytes(extraction_rows)),
        "log": {
            "path": str(log_path),
            "sha256": sha256_file(log_path),
            "bytes": log_path.stat().st_size,
        },
        "tree": tree_manifest(candidate),
    }


def candidate_verification(
    candidate: Path,
    rows: list[dict[str, Any]],
    evidence_directory: Path,
    *,
    write_evidence: bool = True,
) -> dict[str, Any]:
    expected_paths = {row["path"] for row in rows}
    actual_paths: set[str] = set()
    for path in candidate.rglob("*"):
        if path.is_symlink():
            raise DeploymentError(f"Candidate contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise DeploymentError(f"Candidate contains a special file: {path}")
        actual_paths.add(path.relative_to(candidate).as_posix())
    if actual_paths != expected_paths:
        raise DeploymentError("Candidate file set differs from the reviewed manifest.")
    records: list[dict[str, Any]] = []
    row_map = {row["path"]: row for row in rows}
    for relative in sorted(actual_paths):
        path = candidate / relative
        digest = sha256_file(path)
        if digest != row_map[relative]["target"]:
            raise DeploymentError(f"Candidate verification failed for {relative}.")
        if path.stat().st_size != row_map[relative]["target_bytes"]:
            raise DeploymentError(f"Candidate byte verification failed for {relative}.")
        records.append(
            {
                "path": relative,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "mode": stat.S_IMODE(path.stat().st_mode),
            }
        )
    path = evidence_directory / "candidate-verification.json"
    result = {
        "files": len(records),
        "records_sha256": sha256_bytes(canonical_bytes(records)),
        "tree": tree_manifest(candidate),
    }
    if write_evidence:
        atomic_json(path, records)
        result["evidence"] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    return result


def planned_install_metadata(
    rows: list[dict[str, Any]], evidence_directory: Path
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for row in rows:
        live_path = APP_ROOT / row["path"]
        if row["action"] == "M":
            metadata = path_metadata(live_path)
        else:
            metadata = {
                "kind": "file",
                "mode": 0o664,
                "uid": EXPECTED_APP_UID,
                "gid": EXPECTED_APP_GID,
            }
        records.append({"path": row["path"], "action": row["action"], "metadata": metadata})
    path = evidence_directory / "planned-install-metadata.json"
    atomic_json(path, records)
    return {
        "records": len(records),
        "sha256": sha256_bytes(canonical_bytes(records)),
        "path": str(path),
        "file_sha256": sha256_file(path),
    }


def lint_candidate(
    candidate: Path,
    rows: list[dict[str, Any]],
    evidence_directory: Path,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    php_rows = [row for row in rows if row["path"].endswith(".php")]
    combined_stdout: list[str] = []
    combined_stderr: list[str] = []
    for row in php_rows:
        relative = row["path"]
        completed = run_command(
            ["/usr/bin/php", "-l", str(candidate / relative)],
            cwd=APP_ROOT,
            timeout=30,
        )
        combined_stdout.append(f"[{relative}]\n{completed.stdout}")
        combined_stderr.append(f"[{relative}]\n{completed.stderr}")
        results.append(
            {
                "path": relative,
                "exit_status": completed.returncode,
                "stdout_sha256": sha256_bytes(completed.stdout.encode("utf-8")),
                "stderr_sha256": sha256_bytes(completed.stderr.encode("utf-8")),
            }
        )
        if completed.returncode != 0:
            raise DeploymentError(f"PHP lint failed for candidate {relative}.")
    stdout_path = evidence_directory / "php-lint.stdout.txt"
    stderr_path = evidence_directory / "php-lint.stderr.txt"
    receipt_path = evidence_directory / "php-lint.json"
    atomic_write(stdout_path, "".join(combined_stdout).encode("utf-8"), 0o600)
    atomic_write(stderr_path, "".join(combined_stderr).encode("utf-8"), 0o600)
    atomic_json(receipt_path, results)
    return {
        "status": "pass",
        "files": len(results),
        "results_sha256": sha256_bytes(canonical_bytes(results)),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "receipt_sha256": sha256_file(receipt_path),
        "paths": {
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "receipt": str(receipt_path),
        },
    }


ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def normalize_pretend_output(stdout: str, stderr: str) -> tuple[str, list[str]]:
    normalized = ANSI_ESCAPE.sub("", stdout + ("\n" if stdout and stderr else "") + stderr)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    normalized = "\n".join(lines).strip() + "\n"
    statements = [line.strip() for line in lines if re.search(r"\b(create|alter)\s+table\b", line, re.I)]
    return normalized, statements


def validate_pretend_statements(normalized: str, statements: list[str]) -> None:
    lowered = normalized.lower()
    if TARGET_TABLE not in lowered or TARGET_COLUMN not in lowered:
        raise DeploymentError("Pretend output does not cover savedimages.item_meta.")
    prohibited = re.compile(r"\b(drop|truncate|delete|insert|update|replace|rename)\b", re.I)
    if prohibited.search(normalized):
        raise DeploymentError("Pretend output contains prohibited DDL or DML.")
    if len(statements) != 1:
        raise DeploymentError("Pretend output must contain exactly one DDL statement.")
    for statement in statements:
        statement_lower = re.sub(r"\s+", " ", statement.lower()).strip().rstrip(";")
        position = statement_lower.find("alter table")
        if position < 0 or statement_lower[position:] != EXPECTED_PRETEND_STATEMENT:
            raise DeploymentError("Pretend output differs from the one reviewed ALTER TABLE statement.")


def compare_read_only_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_schema = before["schema"]
    after_schema = after["schema"]
    before_ledger = before["migration_ledger"]
    after_ledger = after["migration_ledger"]
    comparisons = {
        "schema_sha256_equal": before_schema.get("sha256") == after_schema.get("sha256"),
        "schema_section_counts_equal": before_schema.get("section_row_counts")
        == after_schema.get("section_row_counts"),
        "ledger_sha256_equal": before_ledger.get("rows_sha256")
        == after_ledger.get("rows_sha256"),
        "ledger_row_count_equal": before_ledger.get("row_count")
        == after_ledger.get("row_count"),
        "item_meta_absent_before": before_schema.get("savedimages_item_meta", {}).get("exists")
        is False,
        "item_meta_absent_after": after_schema.get("savedimages_item_meta", {}).get("exists")
        is False,
        "savedimages_rows_equal": before_schema.get("savedimages_item_meta", {}).get(
            "savedimages_rows"
        )
        == after_schema.get("savedimages_item_meta", {}).get("savedimages_rows"),
        "savedimages_data_columns_equal": before_schema.get(
            "savedimages_item_meta", {}
        ).get("data_columns_without_item_meta")
        == after_schema.get("savedimages_item_meta", {}).get(
            "data_columns_without_item_meta"
        ),
        "savedimages_data_sha256_equal": before_schema.get(
            "savedimages_item_meta", {}
        ).get("data_sha256_without_item_meta")
        == after_schema.get("savedimages_item_meta", {}).get(
            "data_sha256_without_item_meta"
        ),
        "target_migration_absent_before": before_ledger.get("target_entry_count") == 0,
        "target_migration_absent_after": after_ledger.get("target_entry_count") == 0,
    }
    if not all(comparisons.values()):
        raise DeploymentError("Schema or migration ledger changed during read-only pretend.")
    return comparisons


def artifact_inventory(root: Path, *, exclude: set[Path] | None = None) -> list[dict[str, Any]]:
    exclusions = {path.resolve(strict=False) for path in (exclude or set())}
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise DeploymentError(f"Evidence tree contains a symbolic path: {path}")
        if path.is_dir() or path.resolve(strict=False) in exclusions:
            continue
        if not path.is_file():
            raise DeploymentError(f"Evidence tree contains a special path: {path}")
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "mode": stat.S_IMODE(path.stat().st_mode),
            }
        )
    return records


def stage_release(
    *,
    archive: Path,
    manifest: Path,
    helper: Path,
    approval_token: str,
) -> Path:
    if approval_token != STAGE_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed Phase 1 staging token was not supplied.")
    archive = require_regular_file(archive, EXPECTED_ARCHIVE_SHA256)
    manifest = require_regular_file(manifest, EXPECTED_MANIFEST_SHA256)
    helper = require_regular_file(helper, EXPECTED_HELPER_SHA256)
    runner = require_regular_file(Path(__file__).resolve())
    rows = parse_manifest(manifest)

    # This guard is intentionally before RELEASE_ROOT creation or any copy. A
    # hard-stop mismatch therefore leaves no Phase 1 production artifact.
    preflight_guard(helper, rows)

    RELEASE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(RELEASE_ROOT, 0o700)
    with exclusive_lock(RELEASE_ROOT / ".phase1-stage.lock", create=True):
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        release = RELEASE_ROOT / f"{TARGET_SHORT}-{timestamp}"
        release.mkdir(mode=0o700, exist_ok=False)
        evidence = release / "evidence"
        inputs = release / "inputs"
        evidence.mkdir(mode=0o700)
        inputs.mkdir(mode=0o700)

        copied_archive = inputs / f"production-alpha-transparency-{TARGET_SHORT}.tar"
        copied_manifest = inputs / manifest.name
        copied_helper = inputs / helper.name
        copied_runner = inputs / runner.name
        atomic_copy(archive, copied_archive)
        atomic_copy(manifest, copied_manifest)
        atomic_copy(helper, copied_helper)
        atomic_copy(runner, copied_runner)

        preflight = production_preflight(
            helper=copied_helper,
            manifest_rows=rows,
            evidence_directory=evidence,
            prefix="phase0",
            require_target_absent=True,
        )
        preflight_path = evidence / "phase0-preflight-receipt.json"
        atomic_json(preflight_path, preflight)

        candidate = release / "candidate"
        extraction = extract_candidate(copied_archive, candidate, rows, evidence)
        verification = candidate_verification(candidate, rows, evidence)
        metadata_plan = planned_install_metadata(rows, evidence)
        lint = lint_candidate(candidate, rows, evidence)

        migration = require_regular_file(candidate / MIGRATION_RELATIVE_PATH, EXPECTED_MIGRATION_SHA256)
        before, before_command = runtime_probe(
            copied_helper, evidence, "migration-probe-before-pretend"
        )
        validate_runtime_snapshot(before, require_target_absent=True)

        pretend_command = [
            "/usr/bin/php",
            "artisan",
            "migrate",
            "--database=fuelmysql",
            f"--path={migration}",
            "--realpath",
            "--pretend",
            "--force",
            "--no-interaction",
        ]
        pretend = capture_command(
            pretend_command,
            cwd=APP_ROOT,
            evidence_directory=evidence,
            name="migration-pretend",
            timeout=180,
        )
        require_command_success(pretend, "migration pretend")
        stdout = Path(str(pretend["stdout"]["path"])).read_text("utf-8")
        stderr = Path(str(pretend["stderr"]["path"])).read_text("utf-8")
        normalized, statements = normalize_pretend_output(stdout, stderr)
        validate_pretend_statements(normalized, statements)
        normalized_path = evidence / "migration-pretend.normalized.txt"
        statements_path = evidence / "migration-pretend.statements.json"
        atomic_write(normalized_path, normalized.encode("utf-8"), 0o600)
        atomic_json(statements_path, statements)

        after, after_command = runtime_probe(
            copied_helper, evidence, "migration-probe-after-pretend"
        )
        validate_runtime_snapshot(after, require_target_absent=True)
        comparisons = compare_read_only_snapshots(before, after)

        pretend_receipt = {
            "status": "pass",
            "generated_at_utc": utc_now(),
            "connection_proof": before["connections"],
            "ledger_before": before["migration_ledger"],
            "ledger_after": after["migration_ledger"],
            "schema_before": before["schema"],
            "schema_after": after["schema"],
            "comparisons": comparisons,
            "migration_path": str(migration),
            "migration_sha256": sha256_file(migration),
            "pretend_command": pretend,
            "normalized_output": {
                "path": str(normalized_path),
                "sha256": sha256_file(normalized_path),
                "bytes": normalized_path.stat().st_size,
            },
            "statement_set": {
                "path": str(statements_path),
                "sha256": sha256_file(statements_path),
                "canonical_sha256": sha256_bytes(canonical_bytes(statements)),
                "count": len(statements),
            },
            "before_probe_command": before_command,
            "after_probe_command": after_command,
        }
        pretend_receipt_path = evidence / "migration-pretend-receipt.json"
        atomic_json(pretend_receipt_path, pretend_receipt)

        post_source = live_manifest_snapshot(rows, target=False)
        post_dependencies = dependency_identity()
        post_health = health_snapshot()
        if post_source["sha256"] != preflight["live_source"]["sha256"]:
            raise DeploymentError("Live source identity changed during Phase 1.")
        if post_dependencies != preflight["dependencies"]:
            raise DeploymentError("Live dependency identity changed during Phase 1.")

        stage_receipt = {
            "status": "pass",
            "scope": "alpha-repair-phase0-read-only-and-phase1-restricted-staging-only",
            "generated_at_utc": utc_now(),
            "target_commit": TARGET_COMMIT,
            "release_directory": str(release),
            "inputs": {
                "archive": {"path": str(copied_archive), "sha256": sha256_file(copied_archive)},
                "manifest": {"path": str(copied_manifest), "sha256": sha256_file(copied_manifest)},
                "helper": {"path": str(copied_helper), "sha256": sha256_file(copied_helper)},
                "runner": {"path": str(copied_runner), "sha256": sha256_file(copied_runner)},
            },
            "manifest_counts": {
                "total": len(rows),
                "additions": sum(row["action"] == "A" for row in rows),
                "replacements": sum(row["action"] == "M" for row in rows),
            },
            "preflight_receipt": {
                "path": str(preflight_path),
                "sha256": sha256_file(preflight_path),
            },
            "extraction": extraction,
            "candidate_verification": verification,
            "planned_install_metadata": metadata_plan,
            "php_lint": lint,
            "pretend_receipt": {
                "path": str(pretend_receipt_path),
                "sha256": sha256_file(pretend_receipt_path),
                "normalized_statement_set_sha256": pretend_receipt["statement_set"][
                    "canonical_sha256"
                ],
            },
            "post_phase1": {
                "live_source": post_source,
                "dependencies": post_dependencies,
                "health": post_health,
                "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
                "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
                "dependency_lock_free": lock_is_free(DEPENDENCY_LOCK),
                "alpha_repair_lock_free": lock_is_free(DEPLOYMENT_LOCK),
            },
            "prohibited_actions": {
                "phase2_backup_created": False,
                "maintenance_entered": False,
                "static_gate_installed": False,
                "real_migration_executed": False,
                "live_source_changed": False,
                "live_cache_changed": False,
                "configuration_changed": False,
                "service_restarted": False,
                "capability_enabled": False,
                "shopnltees_changed": False,
                "retention_executed": False,
            },
        }
        stage_receipt_path = release / "release-receipt.json"
        atomic_json(stage_receipt_path, stage_receipt)

        inventory_path = release / "evidence-manifest.json"
        inventory = artifact_inventory(release, exclude={inventory_path})
        atomic_json(inventory_path, inventory)
        complete_path = release / "phase1-complete.json"
        complete = {
            "status": "phase1_complete_no_live_mutation",
            "generated_at_utc": utc_now(),
            "release_directory": str(release),
            "release_receipt": {
                "path": str(stage_receipt_path),
                "sha256": sha256_file(stage_receipt_path),
            },
            "evidence_manifest": {
                "path": str(inventory_path),
                "sha256": sha256_file(inventory_path),
                "entries": len(inventory),
            },
        }
        atomic_json(complete_path, complete)
        return stage_receipt_path


def load_json(path: Path) -> Any:
    require_regular_file(path)
    try:
        return json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exception:
        raise DeploymentError(f"Invalid JSON artifact: {path}") from exception


def validate_release_receipt(
    path: Path, expected_sha256: str
) -> tuple[dict[str, Any], Path, list[dict[str, Any]]]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise DeploymentError("The release-receipt SHA-256 is invalid.")
    path = require_regular_file(path, expected_sha256)
    release = path.parent.resolve(strict=True)
    if not is_relative_to(release, RELEASE_ROOT.resolve(strict=True)):
        raise DeploymentError("Release receipt is outside the approved release root.")
    receipt = load_json(path)
    if not isinstance(receipt, dict) or receipt.get("status") != "pass":
        raise DeploymentError("Release receipt is not a successful Phase 1 receipt.")
    if receipt.get("target_commit") != TARGET_COMMIT or receipt.get("release_directory") != str(release):
        raise DeploymentError("Release receipt identity differs from the reviewed alpha repair.")
    inputs = receipt.get("inputs", {})
    identities = {
        "archive": EXPECTED_ARCHIVE_SHA256,
        "manifest": EXPECTED_MANIFEST_SHA256,
        "helper": EXPECTED_HELPER_SHA256,
    }
    for name, expected in identities.items():
        item = inputs.get(name, {})
        item_path = Path(str(item.get("path", "")))
        if item.get("sha256") != expected:
            raise DeploymentError(f"Release receipt {name} identity differs from baseline.")
        require_regular_file(item_path, expected)
        if not is_relative_to(item_path.resolve(strict=True), release):
            raise DeploymentError(f"Release {name} path escapes the release directory.")
    staged_runner = inputs.get("runner", {})
    staged_runner_path = require_regular_file(Path(str(staged_runner.get("path", ""))))
    staged_runner_sha256 = sha256_file(staged_runner_path)
    if staged_runner.get("sha256") != staged_runner_sha256:
        raise DeploymentError("Staged runner differs from its Phase 1 receipt.")
    if sha256_file(Path(__file__).resolve()) != staged_runner_sha256:
        raise DeploymentError("Executing runner differs from the runner frozen at Phase 1.")
    manifest = Path(str(inputs["manifest"]["path"]))
    rows = parse_manifest(manifest)
    candidate = require_real_directory(release / "candidate", within=release)
    verification = candidate_verification(
        candidate, rows, release / "evidence", write_evidence=False
    )
    recorded = receipt.get("candidate_verification", {})
    if verification.get("records_sha256") != recorded.get("records_sha256"):
        raise DeploymentError("Staged candidate identity differs from its Phase 1 receipt.")
    pretend_receipt = Path(str(receipt.get("pretend_receipt", {}).get("path", "")))
    require_regular_file(pretend_receipt, str(receipt["pretend_receipt"]["sha256"]))
    if not is_relative_to(pretend_receipt.resolve(strict=True), release):
        raise DeploymentError("Pretend receipt escapes the release directory.")
    return receipt, release, rows


def append_event(state_directory: Path, event: str, details: dict[str, Any] | None = None) -> None:
    path = state_directory / "events.jsonl"
    payload = {"at_utc": utc_now(), "event": event, "details": details or {}}
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "ab") as handle:
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.chmod(path, 0o600)


def write_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at_utc"] = utc_now()
    atomic_json(path, state)


def record_front_controller_transition(
    *,
    state: dict[str, Any],
    state_path: Path,
    state_directory: Path,
    operation: str,
    phase: str,
    front_controller: Path,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    history = state.setdefault("front_controller_transitions", [])
    if not isinstance(history, list):
        raise DeploymentError("Front-controller transition history is invalid.")
    transition = {
        "sequence": len(history) + 1,
        "at_utc": utc_now(),
        "operation": operation,
        "phase": phase,
        "front_controller": str(front_controller),
        "details": details or {},
    }
    history.append(transition)
    state["front_controller_transition"] = transition
    write_state(state_path, state)
    append_event(
        state_directory,
        f"front_controller_{phase}",
        {"operation": operation, "sequence": transition["sequence"]},
    )
    return transition


def write_new_json(path: Path, payload: Any) -> str:
    if path.exists() or path.is_symlink():
        raise DeploymentError(f"Refusing to overwrite existing evidence: {path}")
    atomic_json(path, payload)
    return sha256_file(path)


def source_backup(
    rows: list[dict[str, Any]], state_directory: Path
) -> tuple[dict[str, Any], list[str]]:
    backup_root = state_directory / "source-before"
    backup_root.mkdir(mode=0o700)
    records: list[dict[str, Any]] = []
    additions: list[str] = []
    for row in rows:
        live = APP_ROOT / row["path"]
        if row["action"] == "A":
            if live.exists() or live.is_symlink():
                raise DeploymentError(f"Addition is no longer absent before backup: {row['path']}")
            additions.append(row["path"])
            records.append({"path": row["path"], "action": "A", "state": "absent"})
            continue
        require_regular_file(live, row["expected"])
        destination = backup_root / row["path"]
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic_copy(live, destination, 0o600)
        record = {
            "path": row["path"],
            "action": "M",
            "sha256": sha256_file(destination),
            "bytes": destination.stat().st_size,
            "live_metadata": path_metadata(live),
            "backup_path": str(destination),
        }
        if record["sha256"] != row["expected"]:
            raise DeploymentError(f"Source backup differs from expected bytes: {row['path']}")
        if record["bytes"] != row["expected_bytes"]:
            raise DeploymentError(f"Source backup differs from expected byte count: {row['path']}")
        records.append(record)
    receipt = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "records": records,
        "records_sha256": sha256_bytes(canonical_bytes(records)),
        "tree": tree_manifest(backup_root),
    }
    path = state_directory / "source-backup-receipt.json"
    atomic_json(path, receipt)
    return {
        **receipt,
        "path": str(path),
        "receipt_sha256": sha256_file(path),
    }, additions


def verify_gzip(path: Path) -> None:
    import gzip

    with gzip.open(path, "rb") as handle:
        while handle.read(1024 * 1024):
            pass


def database_backups(
    helper: Path,
    before_snapshot: dict[str, Any],
    state_directory: Path,
) -> dict[str, Any]:
    import gzip

    backup_directory = state_directory / "database-before"
    backup_directory.mkdir(mode=0o700)
    client_file = backup_directory / ".mysql-client.cnf"
    helper_result = run_command(
        [
            "/usr/bin/php",
            str(helper),
            str(APP_ROOT),
            "--write-mysql-client",
            str(client_file),
        ],
        cwd=APP_ROOT,
        timeout=60,
    )
    if helper_result.returncode != 0:
        raise DeploymentError("Runtime helper could not create the temporary MySQL client file.")
    try:
        helper_payload = json.loads(helper_result.stdout)
    except json.JSONDecodeError as exception:
        client_file.unlink(missing_ok=True)
        raise DeploymentError("MySQL client helper returned invalid JSON.") from exception
    database_name = helper_payload.get("database_name")
    if not isinstance(database_name, str) or not database_name:
        client_file.unlink(missing_ok=True)
        raise DeploymentError("MySQL client helper did not identify the database.")
    if (
        hashlib.sha256(database_name.encode()).hexdigest()
        != before_snapshot["connections"]["fuel_database_name_sha256"]
    ):
        client_file.unlink(missing_ok=True)
        raise DeploymentError("MySQL backup database identity differs from the audited connection.")
    require_regular_file(client_file)
    os.chmod(client_file, 0o600)

    dumps: dict[str, Any] = {}
    specifications = {
        "schema": [
            "--single-transaction",
            "--skip-lock-tables",
            "--no-tablespaces",
            "--routines",
            "--triggers",
            "--events",
            "--no-data",
            database_name,
        ],
        "migration-ledger": [
            "--single-transaction",
            "--skip-lock-tables",
            "--no-tablespaces",
            database_name,
            str(before_snapshot["migration_ledger"]["table"]),
        ],
        "savedimages-full": [
            "--single-transaction",
            "--skip-lock-tables",
            "--no-tablespaces",
            "--hex-blob",
            database_name,
            TARGET_TABLE,
        ],
    }
    try:
        for name, arguments in specifications.items():
            output = backup_directory / f"{name}.sql.gz"
            stderr_path = backup_directory / f"{name}.stderr.txt"
            command = [
                "/usr/bin/mysqldump",
                f"--defaults-extra-file={client_file}",
                "--set-gtid-purged=OFF",
                *arguments,
            ]
            started = time.monotonic()
            process = subprocess.Popen(
                command,
                cwd=APP_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None
            with gzip.open(output, "wb", compresslevel=9) as compressed:
                shutil.copyfileobj(process.stdout, compressed, length=1024 * 1024)
            _, stderr = process.communicate(timeout=600)
            atomic_write(stderr_path, stderr, 0o600)
            os.chmod(output, 0o600)
            if process.returncode != 0:
                raise DeploymentError(f"{name} database backup failed.")
            verify_gzip(output)
            dumps[name] = {
                "path": str(output),
                "sha256": sha256_file(output),
                "bytes": output.stat().st_size,
                "stderr_sha256": sha256_file(stderr_path),
                "exit_status": process.returncode,
                "duration_seconds": round(time.monotonic() - started, 6),
                "database_name_sha256": hashlib.sha256(database_name.encode()).hexdigest(),
            }
        show_create_path = backup_directory / "savedimages-show-create.txt"
        show_create_stderr = backup_directory / "savedimages-show-create.stderr.txt"
        show_create = run_command(
            [
                "/usr/bin/mysql",
                f"--defaults-extra-file={client_file}",
                "--batch",
                "--raw",
                "--skip-column-names",
                database_name,
                "--execute=SHOW CREATE TABLE `savedimages`",
            ],
            cwd=APP_ROOT,
            timeout=120,
        )
        atomic_write(show_create_path, show_create.stdout.encode("utf-8"), 0o600)
        atomic_write(show_create_stderr, show_create.stderr.encode("utf-8"), 0o600)
        if show_create.returncode != 0 or "CREATE TABLE `savedimages`" not in show_create.stdout:
            raise DeploymentError("SHOW CREATE TABLE savedimages backup failed.")
        dumps["savedimages-show-create"] = {
            "path": str(show_create_path),
            "sha256": sha256_file(show_create_path),
            "bytes": show_create_path.stat().st_size,
            "stderr_sha256": sha256_file(show_create_stderr),
            "exit_status": show_create.returncode,
            "database_name_sha256": hashlib.sha256(database_name.encode()).hexdigest(),
        }
    finally:
        client_file.unlink(missing_ok=True)
        fsync_directory(backup_directory)
    if client_file.exists():
        raise DeploymentError("Temporary MySQL client file was not removed.")
    receipt = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "schema_before": before_snapshot["schema"],
        "migration_ledger_before": before_snapshot["migration_ledger"],
        "savedimages_rows_before": before_snapshot["schema"]["savedimages_item_meta"][
            "savedimages_rows"
        ],
        "dumps": dumps,
        "temporary_client_removed": True,
    }
    path = state_directory / "database-backup-receipt.json"
    atomic_json(path, receipt)
    return {**receipt, "path": str(path), "receipt_sha256": sha256_file(path)}


def atomic_front_controller_replace(
    *,
    replacement_bytes: bytes,
    replacement_sha256: str,
    allowed_current_sha256: set[str],
    metadata: dict[str, Any],
    state: dict[str, Any],
    state_path: Path,
    state_directory: Path,
    operation: str,
    front_controller: Path = FRONT_CONTROLLER,
    application_root: Path = APP_ROOT,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if sha256_bytes(replacement_bytes) != replacement_sha256:
        raise DeploymentError("Front-controller replacement bytes differ from their identity.")
    if metadata != reviewed_front_controller_metadata():
        raise DeploymentError("Front-controller replacement metadata is not the reviewed identity.")

    current = file_identity(front_controller)
    if current["sha256"] not in allowed_current_sha256:
        raise DeploymentError("Front-controller replacement refuses unknown live bytes.")
    parent = require_real_directory(front_controller.parent, within=application_root)
    temporary = parent / (
        f".{front_controller.name}.incoming-{os.getpid()}-{secrets.token_hex(6)}"
    )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(replacement_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.chown(temporary, int(metadata["uid"]), int(metadata["gid"]))
        os.chmod(temporary, int(metadata["mode"]))
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        prepared = file_identity(temporary)
        if (
            prepared["sha256"] != replacement_sha256
            or prepared["metadata"] != metadata
        ):
            raise DeploymentError(
                "Prepared front-controller replacement differs from the reviewed bytes or metadata."
            )

        record_front_controller_transition(
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=operation,
            phase="replacement_pending",
            front_controller=front_controller,
            details={"before": current, "prepared": prepared},
        )
        if fault_injector is not None:
            fault_injector("before_replacement")

        os.replace(temporary, front_controller)
        fsync_directory(parent)
        installed = file_identity(front_controller)
        if (
            installed["sha256"] != replacement_sha256
            or installed["metadata"] != metadata
        ):
            raise DeploymentError(
                "Installed front-controller replacement differs from the reviewed bytes or metadata."
            )
        record_front_controller_transition(
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=operation,
            phase="installed",
            front_controller=front_controller,
            details={"before": current, "installed": installed},
        )
        if fault_injector is not None:
            fault_injector("after_replacement")
        return {"before": current, "prepared": prepared, "installed": installed}
    finally:
        temporary.unlink(missing_ok=True)


def restore_front_controller_exact(
    *,
    backup: Path,
    expected_sha256: str,
    metadata: dict[str, Any],
    allowed_current_sha256: set[str],
    state: dict[str, Any],
    state_path: Path,
    state_directory: Path,
    operation: str,
    receipt_name: str,
    front_controller: Path = FRONT_CONTROLLER,
    application_root: Path = APP_ROOT,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    backup = require_regular_file(backup, expected_sha256)
    if metadata != reviewed_front_controller_metadata():
        raise DeploymentError("Front-controller restoration metadata is not the reviewed identity.")
    before = file_identity(front_controller)
    replacement: dict[str, Any] | None = None
    if before["sha256"] == expected_sha256 and before["metadata"] == metadata:
        record_front_controller_transition(
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=operation,
            phase="original_already_present",
            front_controller=front_controller,
            details={"identity": before},
        )
    else:
        replacement = atomic_front_controller_replace(
            replacement_bytes=backup.read_bytes(),
            replacement_sha256=expected_sha256,
            allowed_current_sha256=allowed_current_sha256,
            metadata=metadata,
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=operation,
            front_controller=front_controller,
            application_root=application_root,
            fault_injector=fault_injector,
        )
    restored = file_identity(front_controller)
    if restored["sha256"] != expected_sha256 or restored["metadata"] != metadata:
        raise DeploymentError("Exact original front-controller restoration failed.")
    record_front_controller_transition(
        state=state,
        state_path=state_path,
        state_directory=state_directory,
        operation=operation,
        phase="exact_original_verified",
        front_controller=front_controller,
        details={"identity": restored},
    )
    state["static_gate_active"] = False
    state["containment_active"] = False
    write_state(state_path, state)
    receipt = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "operation": operation,
        "before": before,
        "replacement": replacement,
        "restored": restored,
        "exact_original_restored": True,
    }
    receipt_path = state_directory / receipt_name
    receipt_sha256 = write_new_json(receipt_path, receipt)
    return {**receipt, "path": str(receipt_path), "receipt_sha256": receipt_sha256}


def mutation_has_started(state: dict[str, Any]) -> bool:
    """Return the durable point after which reopening is never a safe fallback."""
    return bool(
        state.get("migration_execution_started") or state.get("source_install_started")
    )


def gate_probe_passed(result: dict[str, Any], expected_route: str) -> bool:
    return (
        result.get("route") == expected_route
        and result.get("status") == 503
        and result.get("header_verified") is True
        and result.get("sentinel_verified") is True
    )


def capture_health_check(check: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Always return receipt-safe evidence, including when the health check fails."""
    try:
        return {"status": "pass", "result": check()}
    except Exception as exception:
        return {
            "status": "fail",
            "failure_type": type(exception).__name__,
            "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
        }


def retain_static_gate_exact(
    *,
    state_directory: Path,
    name: str,
    state: dict[str, Any],
    state_path: Path,
    original_sha256: str,
    metadata: dict[str, Any],
    front_controller: Path = FRONT_CONTROLLER,
    application_root: Path = APP_ROOT,
) -> dict[str, Any]:
    """Fail closed on the exact reviewed gate without relying on Laravel or HTTP."""
    before = file_identity(front_controller)
    if before["sha256"] not in {original_sha256, EXPECTED_GATE_SHA256}:
        raise DeploymentError(
            "Containment found unknown front-controller bytes and refused overwrite."
        )
    replacement: dict[str, Any] | None = None
    if before["sha256"] != EXPECTED_GATE_SHA256 or before["metadata"] != metadata:
        replacement = atomic_front_controller_replace(
            replacement_bytes=MAINTENANCE_GATE_BYTES,
            replacement_sha256=EXPECTED_GATE_SHA256,
            allowed_current_sha256={original_sha256, EXPECTED_GATE_SHA256},
            metadata=metadata,
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=f"{name}-exact-containment-install",
            front_controller=front_controller,
            application_root=application_root,
        )
    final = file_identity(front_controller)
    if final["sha256"] != EXPECTED_GATE_SHA256 or final["metadata"] != metadata:
        raise DeploymentError("Exact static-gate containment could not be established.")
    record_front_controller_transition(
        state=state,
        state_path=state_path,
        state_directory=state_directory,
        operation=name,
        phase="containment_retained",
        front_controller=front_controller,
        details={"identity": final, "mutation_started": mutation_has_started(state)},
    )
    state["static_gate_active"] = True
    state["containment_active"] = True
    state["status"] = f"{name}_site_gated"
    write_state(state_path, state)
    receipt = {
        "status": "site_gated",
        "generated_at_utc": utc_now(),
        "operation": name,
        "mutation_started": mutation_has_started(state),
        "before": before,
        "replacement": replacement,
        "final": final,
        "exact_gate_retained": True,
        "original_restoration_performed": False,
    }
    receipt_path = state_directory / f"{name}-containment-receipt.json"
    receipt_sha256 = write_new_json(receipt_path, receipt)
    return {**receipt, "path": str(receipt_path), "receipt_sha256": receipt_sha256}


def install_static_gate(
    *,
    state_directory: Path,
    name: str,
    state: dict[str, Any],
    state_path: Path,
    original_backup: Path,
    original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256,
    metadata: dict[str, Any] | None = None,
    front_controller: Path = FRONT_CONTROLLER,
    application_root: Path = APP_ROOT,
    origin_probe: Callable[[], dict[str, Any]] | None = None,
    public_probe: Callable[[], dict[str, Any]] | None = None,
    restored_health_probe: Callable[[], dict[str, Any]] | None = None,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if sha256_bytes(MAINTENANCE_GATE_BYTES) != EXPECTED_GATE_SHA256:
        raise DeploymentError("Embedded static gate differs from the reviewed bytes.")
    reviewed_metadata = metadata or reviewed_front_controller_metadata()
    if reviewed_metadata != reviewed_front_controller_metadata():
        raise DeploymentError("Static-gate metadata is not the reviewed owner and mode.")
    require_regular_file(original_backup, original_sha256)
    initial = file_identity(front_controller)
    replacement: dict[str, Any] | None = None
    reconciled_from_live_identity = False
    origin_result: dict[str, Any] | None = None
    public_result: dict[str, Any] | None = None
    try:
        if initial["sha256"] == original_sha256:
            if initial["metadata"] != reviewed_metadata:
                raise DeploymentError("Original front-controller metadata is not reviewed.")
            replacement = atomic_front_controller_replace(
                replacement_bytes=MAINTENANCE_GATE_BYTES,
                replacement_sha256=EXPECTED_GATE_SHA256,
                allowed_current_sha256={original_sha256},
                metadata=reviewed_metadata,
                state=state,
                state_path=state_path,
                state_directory=state_directory,
                operation=name,
                front_controller=front_controller,
                application_root=application_root,
                fault_injector=fault_injector,
            )
        elif initial["sha256"] == EXPECTED_GATE_SHA256:
            if initial["metadata"] != reviewed_metadata:
                raise DeploymentError("Live static gate has incorrect owner or mode.")
            reconciled_from_live_identity = True
            record_front_controller_transition(
                state=state,
                state_path=state_path,
                state_directory=state_directory,
                operation=name,
                phase="installed_reconciled_from_live_identity",
                front_controller=front_controller,
                details={
                    "identity": initial,
                    "previous_transition": state.get("front_controller_transition"),
                },
            )
        else:
            raise DeploymentError("Static gate refuses unknown front-controller bytes.")

        state["static_gate_active"] = True
        state["containment_active"] = True
        write_state(state_path, state)
        time.sleep(OPCACHE_WAIT_SECONDS)
        origin_result = (
            origin_probe()
            if origin_probe is not None
            else gate_origin_probe(state_directory, name)
        )
        if not gate_probe_passed(origin_result, "origin_loopback"):
            raise DeploymentError(
                "The local/origin static-gate probe did not return the reviewed 503 response."
            )
        public_result = (
            public_probe()
            if public_probe is not None
            else gate_public_probe(state_directory, name)
        )
        if not gate_probe_passed(public_result, "public_cloudflare"):
            raise DeploymentError(
                "The public Cloudflare static-gate probe did not return the reviewed 503 response."
            )
        verified = file_identity(front_controller)
        if (
            verified["sha256"] != EXPECTED_GATE_SHA256
            or verified["metadata"] != reviewed_metadata
        ):
            raise DeploymentError("Verified static-gate identity changed during HTTP verification.")
        record_front_controller_transition(
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=name,
            phase="verified",
            front_controller=front_controller,
            details={
                "identity": verified,
                "origin_probe": origin_result,
                "public_probe": public_result,
            },
        )
        return {
            "sha256": EXPECTED_GATE_SHA256,
            "metadata": reviewed_metadata,
            "initial": initial,
            "replacement": replacement,
            "reconciled_from_live_identity": reconciled_from_live_identity,
            "origin_probe": origin_result,
            "public_probe": public_result,
        }
    except Exception as exception:
        live_after_failure = file_identity(front_controller)
        if live_after_failure["sha256"] not in {original_sha256, EXPECTED_GATE_SHA256}:
            raise DeploymentError(
                "Static-gate failure left unknown front-controller bytes; refusing overwrite."
            ) from exception
        if mutation_has_started(state):
            containment = retain_static_gate_exact(
                state_directory=state_directory,
                name=f"{name}-verification-failure",
                state=state,
                state_path=state_path,
                original_sha256=original_sha256,
                metadata=reviewed_metadata,
                front_controller=front_controller,
                application_root=application_root,
            )
            failure_receipt = {
                "status": "gate_failed_site_gated",
                "generated_at_utc": utc_now(),
                "operation": name,
                "failure_type": type(exception).__name__,
                "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
                "mutation_started": True,
                "initial": initial,
                "live_after_failure": live_after_failure,
                "origin_probe": origin_result,
                "public_probe": public_result,
                "containment_receipt": {
                    "path": containment["path"],
                    "sha256": containment["receipt_sha256"],
                },
                "original_restoration_performed": False,
                "final": file_identity(front_controller),
            }
        else:
            restoration = restore_front_controller_exact(
                backup=original_backup,
                expected_sha256=original_sha256,
                metadata=reviewed_metadata,
                allowed_current_sha256={original_sha256, EXPECTED_GATE_SHA256},
                state=state,
                state_path=state_path,
                state_directory=state_directory,
                operation=f"{name}-automatic-original-restore",
                receipt_name=f"{name}-automatic-original-restore-receipt.json",
                front_controller=front_controller,
                application_root=application_root,
            )
            restored_health = capture_health_check(restored_health_probe or health_snapshot)
            failure_receipt = {
                "status": "gate_failed_original_restored",
                "generated_at_utc": utc_now(),
                "operation": name,
                "failure_type": type(exception).__name__,
                "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
                "mutation_started": False,
                "initial": initial,
                "live_after_failure": live_after_failure,
                "origin_probe": origin_result,
                "public_probe": public_result,
                "restoration_receipt": {
                    "path": restoration["path"],
                    "sha256": restoration["receipt_sha256"],
                },
                "post_restoration_health": restored_health,
                "original_restoration_performed": True,
                "final": file_identity(front_controller),
            }
        failure_path = state_directory / f"{name}-gate-failure-receipt.json"
        failure_sha256 = write_new_json(failure_path, failure_receipt)
        state["gate_failure_receipt"] = str(failure_path)
        if mutation_has_started(state):
            state["static_gate_active"] = True
            state["containment_active"] = True
            state["status"] = f"{name}_failed_site_gated"
        else:
            state["static_gate_active"] = False
            state["containment_active"] = False
            state["status"] = f"{name}_failed_original_restored"
        write_state(state_path, state)
        if mutation_has_started(state):
            raise DeploymentError(
                "Static-gate verification failed after mutation began; the exact 0644 "
                f"gate remains installed (receipt {failure_sha256})."
            ) from exception
        raise DeploymentError(
            "Static-gate installation or verification failed before mutation; the exact "
            f"original front controller was restored and health recorded (receipt {failure_sha256})."
        ) from exception


def gate_http_probe(
    state_directory: Path, name: str, *, origin_loopback: bool
) -> dict[str, Any]:
    route = "origin" if origin_loopback else "public"
    headers = state_directory / f"{name}.{route}.headers.txt"
    body = state_directory / f"{name}.{route}.body.txt"
    routing_arguments = (
        [
            "--noproxy",
            "*",
            "--insecure",
            "--resolve",
            "buy-dtf.com:443:127.0.0.1",
        ]
        if origin_loopback
        else []
    )
    completed = run_command(
        [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--dump-header",
            str(headers),
            "--output",
            str(body),
            "--write-out",
            "%{http_code}",
            "--header",
            "Cache-Control: no-cache, no-store",
            "--connect-timeout",
            "5",
            "--max-time",
            "15",
            *routing_arguments,
            f"https://buy-dtf.com/?ops_gate={secrets.token_hex(12)}",
        ],
        cwd=APP_ROOT,
        timeout=20,
    )
    if completed.returncode != 0 or not completed.stdout.isdigit():
        raise DeploymentError("Static gate HTTP probe failed.")
    header_text = headers.read_text("utf-8", errors="replace").lower()
    body_text = body.read_text("utf-8", errors="replace")
    return {
        "route": "origin_loopback" if origin_loopback else "public_cloudflare",
        "status": int(completed.stdout),
        "header_verified": f"{MAINTENANCE_GATE_HEADER_NAME}: {MAINTENANCE_GATE_HEADER_VALUE}".lower()
        in header_text,
        "sentinel_verified": MAINTENANCE_GATE_SENTINEL in body_text,
        "headers_sha256": sha256_file(headers),
        "body_sha256": sha256_file(body),
    }


def gate_origin_probe(state_directory: Path, name: str) -> dict[str, Any]:
    return gate_http_probe(state_directory, name, origin_loopback=True)


def gate_public_probe(state_directory: Path, name: str) -> dict[str, Any]:
    return gate_http_probe(state_directory, name, origin_loopback=False)


def atomic_install_file(source: Path, destination: Path, metadata: dict[str, Any]) -> None:
    require_regular_file(source)
    if metadata.get("kind") != "file":
        raise DeploymentError("Install metadata does not describe a regular file.")
    parent = require_real_directory(destination.parent, within=APP_ROOT)
    temporary = parent / f".{destination.name}.incoming-{os.getpid()}-{secrets.token_hex(5)}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, int(metadata["mode"]))
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.chown(temporary, int(metadata["uid"]), int(metadata["gid"]))
        os.chmod(temporary, int(metadata["mode"]))
        os.replace(temporary, destination)
        fsync_directory(parent)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_runtime_parents(
    destination: Path, created_directories: list[str]
) -> None:
    missing: list[Path] = []
    current = destination.parent
    while current != APP_ROOT and not current.exists():
        missing.append(current)
        current = current.parent
    require_real_directory(current, within=APP_ROOT)
    for directory in reversed(missing):
        directory.mkdir(mode=0o775)
        os.chown(directory, EXPECTED_APP_UID, EXPECTED_APP_GID)
        os.chmod(directory, 0o775)
        fsync_directory(directory.parent)
        created_directories.append(directory.relative_to(APP_ROOT).as_posix())


def install_runtime_files(
    candidate: Path,
    rows: list[dict[str, Any]],
    state_directory: Path,
    *,
    state: dict[str, Any] | None = None,
    state_path: Path | None = None,
    fault_injector: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    created_directories: list[str] = []
    results: list[dict[str, Any]] = []
    ordered = sorted(
        rows,
        key=lambda row: (
            0 if row["action"] == "A" else 1,
            1 if row["path"].startswith("routes/") else 0,
            row["path"],
        ),
    )
    for row in ordered:
        source = candidate / row["path"]
        require_regular_file(source, row["target"])
        destination = APP_ROOT / row["path"]
        ensure_runtime_parents(destination, created_directories)
        if row["action"] == "M":
            require_regular_file(destination, row["expected"])
            metadata = path_metadata(destination)
        else:
            if destination.exists() or destination.is_symlink():
                raise DeploymentError(f"Addition appeared during cutover: {row['path']}")
            metadata = {
                "kind": "file",
                "mode": 0o664,
                "uid": EXPECTED_APP_UID,
                "gid": EXPECTED_APP_GID,
            }
        transition = {
            "sequence": len(results) + 1,
            "path": row["path"],
            "phase": "replacement_pending",
            "expected_before_sha256": row["expected"],
            "target_sha256": row["target"],
        }
        if state is not None and state_path is not None:
            state["source_file_transition"] = transition
            write_state(state_path, state)
        append_event(state_directory, "source_file_replacement_pending", transition)
        if fault_injector is not None:
            fault_injector("before_replacement", row["path"])
        atomic_install_file(source, destination, metadata)
        require_regular_file(destination, row["target"])
        if destination.stat().st_size != row["target_bytes"]:
            raise DeploymentError(f"Installed byte count differs for {row['path']}.")
        if path_metadata(destination) != metadata:
            raise DeploymentError(f"Installed metadata differs for {row['path']}.")
        result = {
            "path": row["path"],
            "action": row["action"],
            "sha256": row["target"],
            "bytes": destination.stat().st_size,
            "metadata": metadata,
        }
        results.append(result)
        if state is not None and state_path is not None:
            state["source_file_transition"] = {
                **transition,
                "phase": "installed",
                "installed_sha256": row["target"],
                "installed_bytes": destination.stat().st_size,
            }
            write_state(state_path, state)
        append_event(state_directory, "source_file_installed", result)
        if fault_injector is not None:
            fault_injector("after_replacement", row["path"])
    receipt = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "files": results,
        "files_sha256": sha256_bytes(canonical_bytes(results)),
        "created_directories": created_directories,
        "live_target_snapshot": live_manifest_snapshot(rows, target=True),
    }
    path = state_directory / "source-install-receipt.json"
    atomic_json(path, receipt)
    return {**receipt, "path": str(path), "receipt_sha256": sha256_file(path)}


def run_artisan(
    arguments: list[str],
    *,
    state_directory: Path,
    name: str,
    timeout: int = 300,
) -> dict[str, Any]:
    result = capture_command(
        ["/usr/bin/php", "artisan", *arguments],
        cwd=APP_ROOT,
        evidence_directory=state_directory,
        name=name,
        timeout=timeout,
    )
    require_command_success(result, name)
    return result


def enter_laravel_maintenance(state_directory: Path, name: str) -> dict[str, Any]:
    result = run_artisan(
        ["down", "--retry=120", "--no-interaction"],
        state_directory=state_directory,
        name=name,
        timeout=60,
    )
    if not LARAVEL_MAINTENANCE_FILE.is_file():
        raise DeploymentError("Laravel did not create its maintenance marker.")
    return result


def leave_laravel_maintenance(state_directory: Path, name: str) -> dict[str, Any]:
    result = run_artisan(
        ["up", "--no-interaction"],
        state_directory=state_directory,
        name=name,
        timeout=60,
    )
    if LARAVEL_MAINTENANCE_FILE.exists():
        raise DeploymentError("Laravel maintenance marker remains after artisan up.")
    return result


def drain_runtime(state_directory: Path) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    deadline = time.monotonic() + DRAIN_SECONDS
    while True:
        connections = active_fpm_connections()
        conflicts = scoped_processes()
        samples.append(
            {
                "at_utc": utc_now(),
                "active_fpm_connections": connections,
                "scoped_processes": conflicts,
            }
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(5, remaining))
    if samples[-1]["active_fpm_connections"] != 0 or samples[-1]["scoped_processes"]:
        raise DeploymentError("Production runtime did not drain cleanly under the static gate.")
    path = state_directory / "runtime-drain.json"
    atomic_json(path, samples)
    return {"samples": samples, "path": str(path), "sha256": sha256_file(path)}


def staged_pretend(
    *,
    migration: Path,
    state_directory: Path,
    name: str,
    expected_statement_sha256: str,
) -> dict[str, Any]:
    require_regular_file(migration, EXPECTED_MIGRATION_SHA256)
    command = [
        "/usr/bin/php",
        "artisan",
        "migrate",
        "--database=fuelmysql",
        f"--path={migration}",
        "--realpath",
        "--pretend",
        "--force",
        "--no-interaction",
    ]
    result = capture_command(
        command,
        cwd=APP_ROOT,
        evidence_directory=state_directory,
        name=name,
        timeout=180,
    )
    require_command_success(result, name)
    stdout = Path(str(result["stdout"]["path"])).read_text("utf-8")
    stderr = Path(str(result["stderr"]["path"])).read_text("utf-8")
    normalized, statements = normalize_pretend_output(stdout, stderr)
    validate_pretend_statements(normalized, statements)
    statement_sha256 = sha256_bytes(canonical_bytes(statements))
    if statement_sha256 != expected_statement_sha256:
        raise DeploymentError("Cutover pretend statements differ from the reviewed Phase 1 set.")
    normalized_path = state_directory / f"{name}.normalized.txt"
    statements_path = state_directory / f"{name}.statements.json"
    atomic_write(normalized_path, normalized.encode("utf-8"), 0o600)
    atomic_json(statements_path, statements)
    return {
        "command": result,
        "normalized_path": str(normalized_path),
        "normalized_sha256": sha256_file(normalized_path),
        "statements_path": str(statements_path),
        "statement_set_sha256": statement_sha256,
        "statement_count": len(statements),
    }


def execute_single_migration(
    migration: Path, state_directory: Path
) -> dict[str, Any]:
    require_regular_file(migration, EXPECTED_MIGRATION_SHA256)
    result = capture_command(
        [
            "/usr/bin/php",
            "artisan",
            "migrate",
            "--database=fuelmysql",
            f"--path={migration}",
            "--realpath",
            "--force",
            "--no-interaction",
        ],
        cwd=APP_ROOT,
        evidence_directory=state_directory,
        name="single-migration-execution",
        timeout=300,
    )
    require_command_success(result, "single migration execution")
    return result


def verify_post_migration(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    before_verification = validate_runtime_snapshot(before, require_target_absent=True)
    after_verification = validate_runtime_snapshot(
        after,
        require_target_absent=False,
        require_all_item_meta_null=True,
    )
    before_schema = before["schema"]
    after_schema = after["schema"]
    if before_schema["savedimages_item_meta"]["savedimages_rows"] != after_schema[
        "savedimages_item_meta"
    ]["savedimages_rows"]:
        raise DeploymentError("The savedimages row count changed during the additive migration.")
    if (
        before_schema["savedimages_item_meta"]["data_columns_without_item_meta"]
        != after_schema["savedimages_item_meta"]["data_columns_without_item_meta"]
        or before_schema["savedimages_item_meta"]["data_sha256_without_item_meta"]
        != after_schema["savedimages_item_meta"]["data_sha256_without_item_meta"]
    ):
        raise DeploymentError("Existing savedimages row data changed during the additive migration.")
    if before_schema.get("required_table_row_counts") != after_schema.get(
        "required_table_row_counts"
    ):
        raise DeploymentError("A required Fuel table row count changed during the additive migration.")
    if before_schema.get("target_definitions", {}).get("tables") != after_schema.get(
        "target_definitions", {}
    ).get("tables"):
        raise DeploymentError("The savedimages table identity changed beyond the new column.")
    return {
        "status": "pass",
        "before": before_verification,
        "after": after_verification,
        "required_table_row_counts_unchanged": True,
        "savedimages_row_count_unchanged": True,
        "savedimages_existing_row_data_unchanged": True,
        "all_preexisting_item_meta_null": True,
        "only_schema_delta_is_item_meta": True,
        "only_ledger_delta_is_target_migration": True,
    }


def candidate_fpm_probe_source() -> bytes:
    return f'''<?php
declare(strict_types=1);
require {str(APP_ROOT / "vendor/autoload.php")!r};
$app = require {str(APP_ROOT / "bootstrap/app.php")!r};
$kernel = $app->make(Illuminate\\Contracts\\Console\\Kernel::class);
$kernel->bootstrap();
$dtf = new App\\Models\\DtfImage();
$dtf->setRawAttributes(['item_meta' => '{{"alpha_processing":{{"scope":"production_derivative","version":1,"threshold":128}}}}'], true);
$classes = [
    'ImageHelper' => App\\Helpers\\ImageHelper::class,
    'ProductionHelper' => App\\Helpers\\ProductionHelper::class,
    'OrderImageController' => App\\Http\\Controllers\\Admin\\OrderImageController::class,
    'CartController' => App\\Http\\Controllers\\CartController::class,
    'TeamCustomizationController' => App\\Http\\Controllers\\TeamCustomizationController::class,
    'DtfImage' => App\\Models\\DtfImage::class,
    'SavedImage' => App\\Models\\SavedImage::class,
];
$classFiles = [];
foreach ($classes as $name => $class) {{
    $classFiles[$name] = (new ReflectionClass($class))->getFileName();
}}
$payload = [
    'php_version' => PHP_VERSION,
    'laravel_version' => (string) $app->version(),
    'sapi' => PHP_SAPI,
    'alpha_contract' => [
        'image_bounds_method' => method_exists(App\\Helpers\\ImageHelper::class, 'productionAlphaBounds'),
        'dtf_threshold_method' => method_exists(App\\Models\\DtfImage::class, 'productionAlphaThreshold'),
        'saved_metadata_method' => method_exists(App\\Models\\SavedImage::class, 'getItemMetadata'),
        'threshold' => $dtf->productionAlphaThreshold(),
        'identity' => $dtf->productionAlphaPolicyIdentity(),
    ],
    'capabilities' => [
        'receiver_enabled' => (bool) config('incoming_order.receiver_enabled', false),
        'job_label_enabled' => (bool) config('incoming_order.job_label_enabled', false),
        'retention_enabled' => (bool) config('incoming_order.retention.enabled', false),
        'allowed_host_count' => count((array) config('incoming_order.allowed_hosts', [])),
    ],
    'class_files' => $classFiles,
];
header('Content-Type: application/json');
echo json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
'''.encode("utf-8")


def candidate_fpm_probe(state_directory: Path, name: str) -> dict[str, Any]:
    """Boot the candidate through the live FPM pool without exposing a route."""
    if not FPM_SOCKET.is_socket():
        raise DeploymentError("The reviewed PHP-FPM socket is unavailable.")
    probe_parent = require_real_directory(APP_ROOT / "storage/framework", within=APP_ROOT)
    probe_directory = probe_parent / f"alpha-probe-{secrets.token_hex(10)}"
    probe_directory.mkdir(mode=0o755)
    os.chmod(probe_directory, 0o755)
    probe = probe_directory / "probe.php"
    source = candidate_fpm_probe_source()
    atomic_write(probe, source, 0o644)
    environment = dict(os.environ)
    environment.update(
        {
            "SCRIPT_FILENAME": str(probe),
            "SCRIPT_NAME": "/internal-alpha-probe.php",
            "REQUEST_METHOD": "GET",
            "REQUEST_URI": "/internal-alpha-probe.php",
            "REDIRECT_STATUS": "200",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "GATEWAY_INTERFACE": "CGI/1.1",
        }
    )
    stdout_path = state_directory / f"{name}.stdout.txt"
    stderr_path = state_directory / f"{name}.stderr.txt"
    try:
        completed = run_command(
            ["/usr/bin/cgi-fcgi", "-bind", "-connect", str(FPM_SOCKET)],
            cwd=APP_ROOT,
            timeout=60,
            env=environment,
        )
        atomic_write(stdout_path, completed.stdout.encode("utf-8"), 0o600)
        atomic_write(stderr_path, completed.stderr.encode("utf-8"), 0o600)
        if completed.returncode != 0:
            raise DeploymentError("Candidate PHP-FPM probe failed.")
        output = completed.stdout.replace("\r\n", "\n")
        if "\n\n" not in output:
            raise DeploymentError("Candidate PHP-FPM probe returned no CGI body.")
        headers, body = output.split("\n\n", 1)
        if "status: 5" in headers.lower():
            raise DeploymentError("Candidate PHP-FPM probe returned a server error.")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exception:
            raise DeploymentError("Candidate PHP-FPM probe returned invalid JSON.") from exception
        expected_classes = {
            "ImageHelper": "app/Helpers/ImageHelper.php",
            "ProductionHelper": "app/Helpers/ProductionHelper.php",
            "OrderImageController": "app/Http/Controllers/Admin/OrderImageController.php",
            "CartController": "app/Http/Controllers/CartController.php",
            "TeamCustomizationController": "app/Http/Controllers/TeamCustomizationController.php",
            "DtfImage": "app/Models/DtfImage.php",
            "SavedImage": "app/Models/SavedImage.php",
        }
        if (
            payload.get("php_version") != "8.2.30"
            or payload.get("laravel_version") != "12.69.0"
            or payload.get("sapi") != "fpm-fcgi"
            or payload.get("alpha_contract")
            != {
                "image_bounds_method": True,
                "dtf_threshold_method": True,
                "saved_metadata_method": True,
                "threshold": 128,
                "identity": "production_derivative:v1:threshold:128",
            }
            or payload.get("capabilities")
            != {
                "receiver_enabled": False,
                "job_label_enabled": False,
                "retention_enabled": False,
                "allowed_host_count": 0,
            }
        ):
            raise DeploymentError("Candidate PHP-FPM runtime identity differs from review.")
        class_files = payload.get("class_files", {})
        for name_key, relative in expected_classes.items():
            if class_files.get(name_key) != str(APP_ROOT / relative):
                raise DeploymentError(f"Candidate PHP-FPM loaded {name_key} from an unexpected path.")
        return {
            "status": "pass",
            "payload": payload,
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_sha256": sha256_file(stderr_path),
            "probe_source_sha256": sha256_bytes(source),
            "probe_removed": True,
        }
    finally:
        probe.unlink(missing_ok=True)
        try:
            probe_directory.rmdir()
        except OSError as exception:
            raise DeploymentError("Transient candidate PHP-FPM probe directory was not empty.") from exception


def candidate_cli_checks(
    helper: Path,
    rows: list[dict[str, Any]],
    state_directory: Path,
) -> dict[str, Any]:
    live = live_manifest_snapshot(rows, target=True)
    lint_results: list[dict[str, Any]] = []
    for row in rows:
        if not row["path"].endswith(".php"):
            continue
        completed = run_command(
            ["/usr/bin/php", "-l", str(APP_ROOT / row["path"])],
            cwd=APP_ROOT,
            timeout=30,
        )
        if completed.returncode != 0:
            raise DeploymentError(f"Deployed PHP lint failed for {row['path']}.")
        lint_results.append(
            {
                "path": row["path"],
                "stdout_sha256": sha256_bytes(completed.stdout.encode()),
                "stderr_sha256": sha256_bytes(completed.stderr.encode()),
            }
        )
    commands = {
        "about": run_artisan(
            ["about", "--only=environment", "--no-interaction"],
            state_directory=state_directory,
            name="candidate-artisan-about",
            timeout=60,
        ),
        "route": run_artisan(
            ["route:list", "--path=admin/orders", "--no-interaction"],
            state_directory=state_directory,
            name="candidate-route-list",
            timeout=60,
        ),
    }
    route_text = Path(str(commands["route"]["stdout"]["path"])).read_text("utf-8")
    if "admin/orders" not in route_text:
        raise DeploymentError("The reviewed admin order routes were not discovered.")
    runtime, runtime_command = runtime_probe(helper, state_directory, "candidate-runtime-probe")
    runtime_verification = validate_runtime_snapshot(
        runtime,
        require_target_absent=False,
        require_all_item_meta_null=True,
    )
    fpm_first = candidate_fpm_probe(state_directory, "candidate-fpm-probe-1")
    time.sleep(OPCACHE_WAIT_SECONDS)
    fpm_second = candidate_fpm_probe(state_directory, "candidate-fpm-probe-2")
    dependencies = dependency_identity()
    return {
        "status": "pass",
        "live_source": live,
        "lint": lint_results,
        "commands": commands,
        "runtime": runtime,
        "runtime_verification": runtime_verification,
        "runtime_command": runtime_command,
        "fpm_probes": [fpm_first, fpm_second],
        "dependencies": dependencies,
    }


def restore_front_controller(
    backup: Path,
    metadata: dict[str, Any],
    *,
    state: dict[str, Any],
    state_path: Path,
    state_directory: Path,
    name: str,
) -> dict[str, Any]:
    return restore_front_controller_exact(
        backup=backup,
        expected_sha256=EXPECTED_FRONT_CONTROLLER_SHA256,
        metadata=metadata,
        allowed_current_sha256={EXPECTED_FRONT_CONTROLLER_SHA256, EXPECTED_GATE_SHA256},
        state=state,
        state_path=state_path,
        state_directory=state_directory,
        operation=name,
        receipt_name=f"{name}-receipt.json",
    )


def capability_probe(state_directory: Path, name: str) -> dict[str, Any]:
    body = state_directory / f"{name}.body.json"
    headers = state_directory / f"{name}.headers.txt"
    completed = run_command(
        [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--dump-header",
            str(headers),
            "--output",
            str(body),
            "--write-out",
            "%{http_code}",
            "--header",
            "Cache-Control: no-cache, no-store",
            "--connect-timeout",
            "5",
            "--max-time",
            "15",
            f"https://buy-dtf.com/api/incomingorder/capabilities?ops_probe={secrets.token_hex(12)}",
        ],
        cwd=APP_ROOT,
        timeout=20,
    )
    if completed.returncode != 0 or completed.stdout != "200":
        raise DeploymentError("Capability endpoint did not return HTTP 200.")
    payload = load_json(body)
    if not isinstance(payload, dict):
        raise DeploymentError("Capability endpoint did not return a JSON object.")
    capabilities = payload.get("capabilities", {})
    receiver = capabilities.get("receiver_idempotency_v1", {})
    label = capabilities.get("job_label_metadata_v1", {})
    if receiver.get("enabled") is not False:
        raise DeploymentError("Receiver capability is unexpectedly enabled.")
    if label.get("enabled") is not False or label.get("modes") != []:
        raise DeploymentError("Job-label capability is unexpectedly enabled.")
    if label.get("artwork_hosts") != []:
        raise DeploymentError("Artwork allowlist is unexpectedly populated.")
    header_text = headers.read_text("utf-8", errors="replace").lower()
    if "cache-control:" not in header_text or "max-age=60" not in header_text:
        raise DeploymentError("Capability endpoint cache policy differs from the reviewed contract.")
    return {
        "status": 200,
        "payload_sha256": sha256_file(body),
        "headers_sha256": sha256_file(headers),
        "receiver_enabled": False,
        "job_label_enabled": False,
        "job_label_modes": [],
        "artwork_hosts": [],
    }


def post_open_health(
    helper: Path, state_directory: Path, name: str
) -> dict[str, Any]:
    health_first = health_snapshot()
    capability_first = capability_probe(state_directory, f"{name}-capability-1")
    time.sleep(3)
    health_second = health_snapshot()
    capability_second = capability_probe(state_directory, f"{name}-capability-2")
    runtime, runtime_command = runtime_probe(helper, state_directory, f"{name}-runtime")
    runtime_verification = validate_runtime_snapshot(runtime, require_target_absent=False)
    return {
        "health_first": health_first,
        "health_second": health_second,
        "capability_first": capability_first,
        "capability_second": capability_second,
        "runtime": runtime,
        "runtime_verification": runtime_verification,
        "runtime_command": runtime_command,
        "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
        "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
    }


def monitor_production(
    helper: Path,
    rows: list[dict[str, Any]],
    state_directory: Path,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    sample_count = MONITOR_SECONDS // MONITOR_INTERVAL_SECONDS
    for index in range(sample_count):
        runtime, _ = runtime_probe(helper, state_directory, f"monitor-runtime-{index + 1:02d}")
        verification = validate_runtime_snapshot(runtime, require_target_absent=False)
        sample = {
            "number": index + 1,
            "at_utc": utc_now(),
            "health": health_snapshot(),
            "capabilities": runtime["capabilities"],
            "queue": runtime["queue"],
            "schema_verification": verification,
            "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
            "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
            "source_sha256": live_manifest_snapshot(rows, target=True)["sha256"],
            "dependencies": dependency_identity(),
            "deployment_lock_held_by_runner": True,
        }
        samples.append(sample)
        atomic_json(state_directory / "monitoring-samples.json", samples)
        if index + 1 < sample_count:
            time.sleep(MONITOR_INTERVAL_SECONDS)
    path = state_directory / "monitoring-samples.json"
    return {
        "status": "pass",
        "samples": len(samples),
        "path": str(path),
        "sha256": sha256_file(path),
    }


def log_baseline() -> dict[str, Any]:
    path = APP_ROOT / "storage/logs/laravel.log"
    if not path.exists():
        return {"path": str(path), "exists": False, "inode": None, "bytes": 0}
    require_regular_file(path)
    metadata = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "inode": metadata.st_ino,
        "bytes": metadata.st_size,
    }


def log_delta(baseline: dict[str, Any], state_directory: Path) -> dict[str, Any]:
    path = Path(str(baseline["path"]))
    if not path.exists():
        return {"bytes": 0, "sha256": sha256_bytes(b""), "error_markers": []}
    require_regular_file(path)
    metadata = path.stat()
    offset = int(baseline.get("bytes", 0)) if metadata.st_ino == baseline.get("inode") else 0
    if metadata.st_size < offset:
        offset = 0
    if metadata.st_size - offset > 20 * 1024 * 1024:
        raise DeploymentError("Laravel log delta exceeds the reviewed 20 MiB evidence bound.")
    with path.open("rb") as handle:
        handle.seek(offset)
        content = handle.read()
    evidence = state_directory / "laravel-log-delta.txt"
    atomic_write(evidence, content, 0o600)
    text = content.decode("utf-8", errors="replace")
    markers = sorted(
        {
            marker
            for marker in (
                ".ERROR",
                "Fatal error",
                "Uncaught ",
                "SQLSTATE[",
                "Class \"",
                "View [",
            )
            if marker.lower() in text.lower()
        }
    )
    if markers:
        raise DeploymentError(f"Laravel log delta contains error markers: {markers}")
    return {
        "bytes": len(content),
        "sha256": sha256_file(evidence),
        "path": str(evidence),
        "error_markers": markers,
    }


def restore_sources(
    *,
    state: dict[str, Any],
    state_directory: Path,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    backup_receipt_path = Path(str(state["source_backup_receipt"]))
    backup_receipt = load_json(backup_receipt_path)
    records = {record["path"]: record for record in backup_receipt["records"]}
    restored: list[dict[str, Any]] = []
    for row in rows:
        live = APP_ROOT / row["path"]
        if row["action"] == "M":
            if live.is_symlink() or not live.is_file():
                raise DeploymentError(f"Rollback replacement is missing or invalid: {row['path']}")
            current = sha256_file(live)
            if current not in {row["expected"], row["target"]}:
                raise DeploymentError(f"Rollback refuses unknown bytes at {row['path']}.")
            record = records[row["path"]]
            backup = require_regular_file(Path(str(record["backup_path"])), row["expected"])
            atomic_install_file(backup, live, record["live_metadata"])
            require_regular_file(live, row["expected"])
            if live.stat().st_size != row["expected_bytes"]:
                raise DeploymentError(f"Rollback restored the wrong byte count: {row['path']}")
            restored.append({"path": row["path"], "action": "restored", "sha256": row["expected"]})
        else:
            if not live.exists() and not live.is_symlink():
                restored.append({"path": row["path"], "action": "already_absent"})
                continue
            require_regular_file(live, row["target"])
            live.unlink()
            fsync_directory(live.parent)
            restored.append({"path": row["path"], "action": "removed", "sha256": row["target"]})
    for relative in sorted(state.get("created_directories", []), key=lambda value: value.count("/"), reverse=True):
        directory = APP_ROOT / relative
        if directory.exists():
            require_real_directory(directory, within=APP_ROOT)
            try:
                directory.rmdir()
                fsync_directory(directory.parent)
            except OSError as exception:
                raise DeploymentError(f"Rollback-created directory is not empty: {relative}") from exception
    snapshot = live_manifest_snapshot(rows, target=False)
    receipt = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "files": restored,
        "snapshot": snapshot,
    }
    path = state_directory / "source-rollback-receipt.json"
    atomic_json(path, receipt)
    return {**receipt, "path": str(path), "receipt_sha256": sha256_file(path)}


def front_controller_recovery_required(
    state: dict[str, Any],
    *,
    front_controller: Path = FRONT_CONTROLLER,
    original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256,
) -> bool:
    """Decide from live identity and durable mutation state, never a gate boolean."""
    live = file_identity(front_controller)
    if live["sha256"] not in {original_sha256, EXPECTED_GATE_SHA256}:
        raise DeploymentError("Recovery found unknown live front-controller bytes.")
    history = state.get("front_controller_transitions", [])
    latest = state.get("front_controller_transition")
    if not isinstance(history, list):
        raise DeploymentError("Recovery found invalid front-controller transition history.")
    if history:
        if not isinstance(latest, dict) or latest != history[-1]:
            raise DeploymentError("Recovery found inconsistent durable front-controller state.")
        phase = latest.get("phase")
        if not isinstance(phase, str):
            raise DeploymentError("Recovery found an invalid durable transition phase.")
    if live["sha256"] == EXPECTED_GATE_SHA256:
        return True
    if history and latest["phase"] in {
        "installed",
        "installed_reconciled_from_live_identity",
        "verified",
        "containment_retained",
    }:
        raise DeploymentError(
            "Durable state says the gate is installed but live identity is the original."
        )
    return mutation_has_started(state)


def establish_rollback_containment(
    *,
    state_directory: Path,
    name: str,
    state: dict[str, Any],
    state_path: Path,
    original_backup: Path,
    original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256,
    metadata: dict[str, Any] | None = None,
    front_controller: Path = FRONT_CONTROLLER,
    application_root: Path = APP_ROOT,
    origin_probe: Callable[[], dict[str, Any]] | None = None,
    public_probe: Callable[[], dict[str, Any]] | None = None,
    restored_health_probe: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Explicitly contain rollback before any source or runtime recovery work."""
    state["containment_requested"] = True
    state["status"] = f"{name}_establishing_containment"
    write_state(state_path, state)
    append_event(
        state_directory,
        "rollback_containment_requested",
        {"operation": name, "mutation_started": mutation_has_started(state)},
    )
    try:
        gate = install_static_gate(
            state_directory=state_directory,
            name=name,
            state=state,
            state_path=state_path,
            original_backup=original_backup,
            original_sha256=original_sha256,
            metadata=metadata,
            front_controller=front_controller,
            application_root=application_root,
            origin_probe=origin_probe,
            public_probe=public_probe,
            restored_health_probe=restored_health_probe,
        )
    except Exception:
        live = file_identity(front_controller)
        if mutation_has_started(state):
            reviewed_metadata = metadata or reviewed_front_controller_metadata()
            if (
                live["sha256"] != EXPECTED_GATE_SHA256
                or live["metadata"] != reviewed_metadata
                or state.get("static_gate_active") is not True
                or state.get("containment_active") is not True
            ):
                raise DeploymentError(
                    "Rollback containment failed after mutation and did not retain the exact gate."
                )
            state["status"] = f"{name}_verification_failed_site_gated"
            append_event(
                state_directory,
                "rollback_containment_verification_failed_site_gated",
                {"operation": name, "identity": live},
            )
        else:
            state["status"] = f"{name}_failed_before_mutation_original_restored"
            append_event(
                state_directory,
                "rollback_containment_failed_before_mutation_original_restored",
                {"operation": name, "identity": live},
            )
        write_state(state_path, state)
        raise
    state["containment_active"] = True
    state["status"] = f"{name}_containment_verified"
    write_state(state_path, state)
    append_event(
        state_directory,
        "rollback_containment_verified",
        {"operation": name, "identity": file_identity(front_controller)},
    )
    return gate


def rollback_operation(
    *,
    state_path: Path,
    state: dict[str, Any],
    rows: list[dict[str, Any]],
    helper: Path,
    automatic: bool,
) -> dict[str, Any]:
    state_directory = state_path.parent
    append_event(state_directory, "rollback_started", {"automatic": automatic})
    state["rollback_started"] = True
    state["status"] = "rolling_back"
    write_state(state_path, state)

    # Rollback starts with an explicit containment phase. Never trust a
    # persisted boolean: reconcile actual bytes and durable transition state
    # before any recovery write.
    gate = establish_rollback_containment(
        state_directory=state_directory,
        name="rollback-static-gate",
        state=state,
        state_path=state_path,
        original_backup=Path(str(state["front_controller_backup"])),
        metadata=state["front_controller_metadata"],
    )
    try:
        try:
            enter_laravel_maintenance(state_directory, "rollback-artisan-down")
            state["laravel_maintenance_active"] = True
            write_state(state_path, state)
        except Exception as exception:  # old/candidate Laravel may be unbootable
            append_event(
                state_directory,
                "rollback_artisan_down_unavailable",
                {"exception_type": type(exception).__name__},
            )

        source = restore_sources(
            state=state,
            state_directory=state_directory,
            rows=rows,
        )
        state["source_rollback_receipt"] = source["path"]
        write_state(state_path, state)
        dependency_identity()

        runtime, runtime_command = runtime_probe(helper, state_directory, "rollback-runtime-probe")
        rollback_schema = verify_rollback_schema_state(runtime, state)
        rollback_schema_path = state_directory / "rollback-schema-preservation-receipt.json"
        atomic_json(rollback_schema_path, rollback_schema)

        leave_laravel_maintenance(state_directory, "rollback-artisan-up")
        state["laravel_maintenance_active"] = False
        write_state(state_path, state)
        time.sleep(OPCACHE_WAIT_SECONDS)
        front_restore = restore_front_controller(
            Path(str(state["front_controller_backup"])),
            state["front_controller_metadata"],
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            name="rollback-original-front-controller-restore",
        )
        state["front_controller_restore_receipt"] = front_restore["path"]
        health = health_snapshot()
        state["status"] = "rolled_back"
        state["rollback_complete"] = True
        state["rollback_finished_at_utc"] = utc_now()
        write_state(state_path, state)
        append_event(state_directory, "rollback_complete")
        return {
            "status": "rolled_back",
            "gate": gate,
            "source": source,
            "runtime": runtime,
            "runtime_command": runtime_command,
            "schema_preservation": {
                "path": str(rollback_schema_path),
                "sha256": sha256_file(rollback_schema_path),
                **rollback_schema,
            },
            "front_controller_restore": front_restore,
            "health": health,
        }
    except Exception as rollback_exception:
        try:
            containment = establish_rollback_containment(
                state_directory=state_directory,
                name="rollback-failure-static-gate",
                state=state,
                state_path=state_path,
                original_backup=Path(str(state["front_controller_backup"])),
                metadata=state["front_controller_metadata"],
            )
            state["status"] = "rollback_failed_site_gated"
            state["rollback_failure_gate"] = containment
            write_state(state_path, state)
            append_event(state_directory, "rollback_failed_site_gated")
        except Exception as gate_exception:
            live = file_identity(FRONT_CONTROLLER)
            state["rollback_failure_type"] = type(rollback_exception).__name__
            state["rollback_failure_message_sha256"] = sha256_bytes(
                str(rollback_exception).encode("utf-8")
            )
            state["gate_failure_type"] = type(gate_exception).__name__
            state["gate_failure_message_sha256"] = sha256_bytes(
                str(gate_exception).encode("utf-8")
            )
            if mutation_has_started(state):
                if (
                    live["sha256"] != EXPECTED_GATE_SHA256
                    or live["metadata"] != state["front_controller_metadata"]
                ):
                    raise DeploymentError(
                        "Rollback and containment both failed after mutation; exact gate identity is absent."
                    ) from gate_exception
                state["static_gate_active"] = True
                state["containment_active"] = True
                state["status"] = "rollback_failed_containment_unverified_site_gated"
                outcome = "the exact gate remains installed"
            else:
                state["static_gate_active"] = False
                state["containment_active"] = False
                state["status"] = "rollback_failed_before_mutation_original_restored"
                outcome = "the exact original front controller was restored"
            write_state(state_path, state)
            append_event(
                state_directory,
                "rollback_failed_containment_verification",
                {"mutation_started": mutation_has_started(state), "identity": live},
            )
            raise DeploymentError(
                f"Rollback failed and containment verification also failed; {outcome}."
            ) from gate_exception
        raise


def deploy_release(
    *,
    release_receipt_path: Path,
    release_receipt_sha256: str,
    approval_token: str,
) -> Path:
    if approval_token != DEPLOY_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed deployment approval token was not supplied.")
    receipt, release, rows = validate_release_receipt(
        release_receipt_path, release_receipt_sha256
    )
    helper = require_regular_file(
        Path(str(receipt["inputs"]["helper"]["path"])), EXPECTED_HELPER_SHA256
    )
    candidate = require_real_directory(release / "candidate", within=release)
    migration = require_regular_file(candidate / MIGRATION_RELATIVE_PATH, EXPECTED_MIGRATION_SHA256)
    pretend_receipt = load_json(Path(str(receipt["pretend_receipt"]["path"])))
    reviewed_statement_sha256 = str(pretend_receipt["statement_set"]["canonical_sha256"])

    ROLLBACK_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(ROLLBACK_ROOT, 0o700)
    with exclusive_lock(DEPLOYMENT_LOCK, create=True):
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        state_directory = ROLLBACK_ROOT / f"{TARGET_SHORT}-{timestamp}"
        state_directory.mkdir(mode=0o700, exist_ok=False)
        state_path = state_directory / "state.json"
        state: dict[str, Any] = {
            "version": 1,
            "status": "initializing",
            "target_commit": TARGET_COMMIT,
            "release_receipt": str(release_receipt_path),
            "release_receipt_sha256": release_receipt_sha256,
            "state_directory": str(state_directory),
            "static_gate_active": False,
            "containment_active": False,
            "laravel_maintenance_active": False,
            "migration_execution_started": False,
            "migration_executed": False,
            "source_install_started": False,
            "source_install_complete": False,
            "rollback_started": False,
            "rollback_complete": False,
            "created_directories": [],
            "front_controller_transitions": [],
        }
        write_state(state_path, state)
        append_event(state_directory, "deployment_initialized")
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(DeploymentError("SIGTERM")))
        signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(DeploymentError("SIGINT")))
        try:
            preflight = production_preflight(
                helper=helper,
                manifest_rows=rows,
                evidence_directory=state_directory,
                prefix="cutover-preflight",
                require_target_absent=True,
            )
            preflight_path = state_directory / "cutover-preflight-receipt.json"
            atomic_json(preflight_path, preflight)
            state["preflight_receipt"] = str(preflight_path)
            state["status"] = "preflight_complete"
            write_state(state_path, state)

            log_start = log_baseline()
            source, additions = source_backup(rows, state_directory)
            state["source_backup_receipt"] = source["path"]
            state["additions_absent_before"] = additions

            front_backup = state_directory / "front-controller-before.php"
            atomic_copy(FRONT_CONTROLLER, front_backup, 0o600)
            require_regular_file(front_backup, EXPECTED_FRONT_CONTROLLER_SHA256)
            state["front_controller_backup"] = str(front_backup)
            state["front_controller_metadata"] = require_exact_metadata(
                FRONT_CONTROLLER,
                reviewed_front_controller_metadata(),
                label="Front controller",
            )

            before_snapshot = preflight["runtime"]
            database = database_backups(helper, before_snapshot, state_directory)
            state["database_backup_receipt"] = database["path"]
            state["status"] = "phase2_backups_complete"
            write_state(state_path, state)
            append_event(state_directory, "phase2_backups_complete")

            gate = install_static_gate(
                state_directory=state_directory,
                name="cutover-static-gate",
                state=state,
                state_path=state_path,
                original_backup=front_backup,
                metadata=state["front_controller_metadata"],
            )
            state["status"] = "static_gate_active"
            write_state(state_path, state)
            append_event(state_directory, "static_gate_active", gate)

            enter_laravel_maintenance(state_directory, "cutover-artisan-down")
            state["laravel_maintenance_active"] = True
            write_state(state_path, state)
            drain = drain_runtime(state_directory)

            # Repeat every relevant identity under the gate before schema/source mutation.
            live_manifest_snapshot(rows, target=False)
            dependency_identity()
            before_repeat, before_repeat_command = runtime_probe(
                helper, state_directory, "cutover-schema-before-pretend"
            )
            validate_runtime_snapshot(before_repeat, require_target_absent=True)
            if (
                before_repeat["schema"]["sha256"] != before_snapshot["schema"]["sha256"]
                or before_repeat["migration_ledger"]["rows_sha256"]
                != before_snapshot["migration_ledger"]["rows_sha256"]
            ):
                raise DeploymentError("Schema or ledger drifted after the Phase 2 backup.")
            repeat_pretend = staged_pretend(
                migration=migration,
                state_directory=state_directory,
                name="cutover-migration-pretend",
                expected_statement_sha256=reviewed_statement_sha256,
            )
            after_repeat, after_repeat_command = runtime_probe(
                helper, state_directory, "cutover-schema-after-pretend"
            )
            validate_runtime_snapshot(after_repeat, require_target_absent=True)
            repeat_comparisons = compare_read_only_snapshots(before_repeat, after_repeat)
            repeat_receipt = {
                "before": before_repeat,
                "after": after_repeat,
                "before_command": before_repeat_command,
                "after_command": after_repeat_command,
                "pretend": repeat_pretend,
                "comparisons": repeat_comparisons,
            }
            repeat_path = state_directory / "cutover-pretend-receipt.json"
            atomic_json(repeat_path, repeat_receipt)

            state["migration_execution_started"] = True
            state["status"] = "migration_execution_started"
            write_state(state_path, state)
            append_event(state_directory, "single_migration_execution_started")
            migration_result = execute_single_migration(migration, state_directory)
            state["migration_executed"] = True
            state["status"] = "migration_executed"
            write_state(state_path, state)
            append_event(state_directory, "single_migration_executed")
            post_migration, post_migration_command = runtime_probe(
                helper, state_directory, "post-migration-runtime-probe"
            )
            post_migration_verification = verify_post_migration(before_repeat, post_migration)
            post_migration_path = state_directory / "post-migration-verification.json"
            atomic_json(
                post_migration_path,
                {
                    "migration_command": migration_result,
                    "probe_command": post_migration_command,
                    "verification": post_migration_verification,
                },
            )

            absent_directories = sorted(
                {
                    parent.relative_to(APP_ROOT).as_posix()
                    for row in rows
                    for parent in (APP_ROOT / row["path"]).parents
                    if parent != APP_ROOT
                    and is_relative_to(parent, APP_ROOT)
                    and not parent.exists()
                },
                key=lambda value: value.count("/"),
            )
            state["created_directories"] = absent_directories
            state["source_install_started"] = True
            state["status"] = "installing_source"
            write_state(state_path, state)
            source_install = install_runtime_files(
                candidate,
                rows,
                state_directory,
                state=state,
                state_path=state_path,
            )
            state["source_install_complete"] = True
            state["source_install_receipt"] = source_install["path"]
            state["status"] = "source_installed"
            write_state(state_path, state)

            candidate_checks = candidate_cli_checks(helper, rows, state_directory)
            candidate_path = state_directory / "candidate-checks.json"
            atomic_json(candidate_path, candidate_checks)

            leave_laravel_maintenance(state_directory, "candidate-artisan-up")
            state["laravel_maintenance_active"] = False
            state["status"] = "candidate_up_gate_active"
            write_state(state_path, state)
            time.sleep(OPCACHE_WAIT_SECONDS)
            # Any failure after artisan up is caught below; rollback starts by
            # unconditionally re-entering the static gate.
            front_restore = restore_front_controller(
                front_backup,
                state["front_controller_metadata"],
                state=state,
                state_path=state_path,
                state_directory=state_directory,
                name="candidate-original-front-controller-restore",
            )
            state["front_controller_restore_receipt"] = front_restore["path"]
            state["status"] = "candidate_public"
            write_state(state_path, state)

            health = post_open_health(helper, state_directory, "post-open")
            logs = log_delta(log_start, state_directory)
            state["status"] = "monitoring"
            write_state(state_path, state)
            monitoring = monitor_production(helper, rows, state_directory)
            final_logs = log_delta(log_start, state_directory)
            final = {
                "status": "success",
                "generated_at_utc": utc_now(),
                "target_commit": TARGET_COMMIT,
                "release_receipt_sha256": release_receipt_sha256,
                "preflight_receipt_sha256": sha256_file(preflight_path),
                "source_backup_receipt_sha256": source["receipt_sha256"],
                "database_backup_receipt_sha256": database["receipt_sha256"],
                "drain": drain,
                "cutover_pretend_receipt_sha256": sha256_file(repeat_path),
                "post_migration_verification_sha256": sha256_file(post_migration_path),
                "source_install_receipt_sha256": source_install["receipt_sha256"],
                "candidate_checks_sha256": sha256_file(candidate_path),
                "front_controller_restore_receipt_sha256": front_restore[
                    "receipt_sha256"
                ],
                "health": health,
                "initial_log_delta": logs,
                "final_log_delta": final_logs,
                "monitoring": monitoring,
                "dependencies": dependency_identity(),
                "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
                "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
                "static_gate_active": False,
                "rollback_started": False,
                "migration_execution_started": True,
                "migration_executed": True,
                "schema": validate_runtime_snapshot(
                    health["runtime"], require_target_absent=False
                ),
                "source": live_manifest_snapshot(rows, target=True),
            }
            final_path = state_directory / "final-receipt.json"
            atomic_json(final_path, final)
            state["status"] = "success"
            state["final_receipt"] = str(final_path)
            state["finished_at_utc"] = utc_now()
            write_state(state_path, state)
            append_event(state_directory, "deployment_success")
            return final_path
        except Exception as exception:
            state["failure_type"] = type(exception).__name__
            state["failure_message_sha256"] = sha256_bytes(str(exception).encode("utf-8"))
            state["status"] = "failed"
            write_state(state_path, state)
            append_event(
                state_directory,
                "deployment_failed",
                {"exception_type": type(exception).__name__},
            )
            if front_controller_recovery_required(state):
                rollback_operation(
                    state_path=state_path,
                    state=state,
                    rows=rows,
                    helper=helper,
                    automatic=True,
                )
            raise


def recover_state(
    *, state_path: Path, approval_token: str
) -> Path:
    if approval_token != RECOVERY_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed recovery approval token was not supplied.")
    state_path = require_regular_file(state_path)
    state_directory = state_path.parent.resolve(strict=True)
    if not is_relative_to(state_directory, ROLLBACK_ROOT.resolve(strict=True)):
        raise DeploymentError("Recovery state is outside the approved rollback root.")
    state = load_json(state_path)
    if not isinstance(state, dict) or state.get("target_commit") != TARGET_COMMIT:
        raise DeploymentError("Recovery state does not belong to the reviewed alpha repair.")
    receipt_path = Path(str(state.get("release_receipt", "")))
    receipt_sha256 = str(state.get("release_receipt_sha256", ""))
    receipt, _, rows = validate_release_receipt(receipt_path, receipt_sha256)
    helper = require_regular_file(
        Path(str(receipt["inputs"]["helper"]["path"])), EXPECTED_HELPER_SHA256
    )
    with exclusive_lock(DEPLOYMENT_LOCK, create=True):
        result = rollback_operation(
            state_path=state_path,
            state=state,
            rows=rows,
            helper=helper,
            automatic=False,
        )
        receipt_path = state_directory / "manual-recovery-receipt.json"
        atomic_json(receipt_path, result)
        return receipt_path


def describe() -> dict[str, Any]:
    return {
        "artifact": "BuyDTF production-alpha transparency repair deployment runner v1",
        "target_application_commit": TARGET_COMMIT,
        "artifact_base_commit": ARTIFACT_BASE_COMMIT,
        "application_root": str(APP_ROOT),
        "release_root": str(RELEASE_ROOT),
        "rollback_root": str(ROLLBACK_ROOT),
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "helper_sha256": EXPECTED_HELPER_SHA256,
        "migration": {
            "path": MIGRATION_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_MIGRATION_SHA256,
            "connection": "fuelmysql",
            "pretend_statement": EXPECTED_PRETEND_STATEMENT,
            "general_migrate_allowed": False,
            "rollback_command_allowed": False,
        },
        "pre_migration_identity": {
            "schema_sha256": EXPECTED_PRE_SCHEMA_SHA256,
            "ledger_rows": EXPECTED_PRE_LEDGER_ROW_COUNT,
            "ledger_sha256": EXPECTED_PRE_LEDGER_SHA256,
            "target_migration_entries": 0,
            "item_meta": "absent",
            "source_cas_sha256": EXPECTED_PRE_SOURCE_CAS_SHA256,
            "target_source_cas_sha256": EXPECTED_TARGET_SOURCE_CAS_SHA256,
        },
        "runtime_paths": {
            "total": EXPECTED_RUNTIME_PATHS,
            "additions": EXPECTED_ADDITIONS,
            "replacements": EXPECTED_REPLACEMENTS,
        },
        "dependency_identity": {
            "composer_lock_sha256": EXPECTED_COMPOSER_LOCK_SHA256,
            "vendor_manifest_sha256": EXPECTED_VENDOR_MANIFEST_SHA256,
            "cache_manifest_sha256": EXPECTED_CACHE_MANIFEST_SHA256,
            "packages_sha256": EXPECTED_PACKAGES_SHA256,
            "services_sha256": EXPECTED_SERVICES_SHA256,
        },
        "front_controller_sha256": EXPECTED_FRONT_CONTROLLER_SHA256,
        "static_gate_sha256": EXPECTED_GATE_SHA256,
        "front_controller_gate": {
            "uid": EXPECTED_APP_UID,
            "gid": EXPECTED_APP_GID,
            "mode": oct(EXPECTED_FRONT_CONTROLLER_MODE),
            "web_reader_uid": EXPECTED_WEB_UID,
            "web_reader_gid": EXPECTED_WEB_GID,
            "replacement_pending_persisted_before_swap": True,
            "installed_persisted_before_http_verification": True,
            "pre_mutation_verification_failure": (
                "restore_exact_original_front_controller_with_receipt_and_health_check"
            ),
            "post_migration_or_source_mutation_verification_failure": (
                "retain_exact_0644_gate_with_durable_rollback_containment"
            ),
            "recovery_uses_live_identity_and_durable_state": True,
        },
        "approval_tokens": {
            "stage": STAGE_APPROVAL_TOKEN,
            "deploy": DEPLOY_APPROVAL_TOKEN,
            "recover": RECOVERY_APPROVAL_TOKEN,
        },
        "safety": {
            "git_operations": False,
            "composer_operations": False,
            "general_migration": False,
            "migration_rollback": False,
            "service_restart": False,
            "environment_change": False,
            "cache_change": False,
            "capability_enablement": False,
            "retention_execution": False,
            "source_rollback_drops_additive_schema": False,
            "migration_failure_accepts_only_exact_absent_or_exact_installed_state": True,
            "schema_preserved_after_successful_migration": True,
            "pre_mutation_gate_failure_restores_original_with_receipt": True,
            "post_mutation_gate_failure_retains_exact_0644_gate": True,
        },
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--describe", action="store_true")
    action.add_argument("--stage", action="store_true")
    action.add_argument("--deploy", action="store_true")
    action.add_argument("--recover", action="store_true")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--helper", type=Path)
    parser.add_argument("--release-receipt", type=Path)
    parser.add_argument("--release-receipt-sha256")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--approval-token")
    return parser.parse_args()


def main() -> int:
    os.umask(0o077)
    arguments = parse_arguments()
    try:
        if arguments.describe:
            print(json.dumps(describe(), indent=2, sort_keys=True))
            return 0
        if arguments.stage:
            if arguments.archive is None or arguments.manifest is None or arguments.helper is None:
                raise DeploymentError("Stage mode requires --archive, --manifest, and --helper.")
            receipt = stage_release(
                archive=arguments.archive,
                manifest=arguments.manifest,
                helper=arguments.helper,
                approval_token=arguments.approval_token or "",
            )
            print(
                json.dumps(
                    {
                        "status": "phase1_complete",
                        "release_receipt": str(receipt),
                        "release_receipt_sha256": sha256_file(receipt),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if arguments.deploy:
            if arguments.release_receipt is None or not arguments.release_receipt_sha256:
                raise DeploymentError(
                    "Deploy mode requires --release-receipt and --release-receipt-sha256."
                )
            receipt = deploy_release(
                release_receipt_path=arguments.release_receipt,
                release_receipt_sha256=arguments.release_receipt_sha256,
                approval_token=arguments.approval_token or "",
            )
            print(
                json.dumps(
                    {
                        "status": "success",
                        "final_receipt": str(receipt),
                        "final_receipt_sha256": sha256_file(receipt),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if arguments.recover:
            if arguments.state is None:
                raise DeploymentError("Recover mode requires --state.")
            receipt = recover_state(
                state_path=arguments.state,
                approval_token=arguments.approval_token or "",
            )
            print(
                json.dumps(
                    {
                        "status": "rolled_back",
                        "recovery_receipt": str(receipt),
                        "recovery_receipt_sha256": sha256_file(receipt),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        raise DeploymentError("No operation was selected.")
    except DeploymentError as exception:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "reason": str(exception),
                    "reason_sha256": sha256_bytes(str(exception).encode("utf-8")),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
