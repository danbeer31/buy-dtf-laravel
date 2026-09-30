#!/usr/bin/env python3
"""Stage, deploy, verify, and source-roll back BuyDTF incoming-order v1.

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
RELEASE_ROOT = APP_ROOT / "storage/app/private/operations/incoming-order-v1-releases"
ROLLBACK_ROOT = APP_ROOT / "storage/app/private/operations/incoming-order-v1-rollbacks"
DEPLOYMENT_LOCK = APP_ROOT / "storage/framework/incoming-order-v1-deployment.lock"
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

TARGET_COMMIT = "0799440b7cbb0bad364fc2a65b41285f20245658"
TARGET_SHORT = TARGET_COMMIT[:8]
EXPECTED_ARCHIVE_SHA256 = "ed1df143d219fa073efb2707508c3eb81ba17b777597cebc20a72d3c546522c2"
EXPECTED_MANIFEST_SHA256 = "b6efbd5463c82f895ca8d359b665a145d88c0d363ce7f97b247eae9080853bb6"
EXPECTED_HELPER_SHA256 = "1b37d3a38834ef633cee5caa784d909b2f5be41ae6e22766f817f80f9f4a20bd"
EXPECTED_MIGRATION_SHA256 = "79fa911b0b2ad9bb79c33080725446093dffd4df3e01c3cb3888d508087c9f9d"
MIGRATION_RELATIVE_PATH = Path(
    "database/migrations/2026_09_27_120000_create_incoming_order_v1_tables.php"
)
TARGET_MIGRATION = "2026_09_27_120000_create_incoming_order_v1_tables"
TARGET_TABLES = frozenset({"incoming_order_jobs", "api_asset_records"})
EXPECTED_RUNTIME_PATHS = 37
EXPECTED_ADDITIONS = 26
EXPECTED_REPLACEMENTS = 11

EXPECTED_COMPOSER_LOCK_SHA256 = "eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831"
EXPECTED_VENDOR_MANIFEST_SHA256 = "97cd0bb104c42b57fbf90204ee74837ec1359b0ab1cbf8dac7d6929a154922d7"
EXPECTED_CACHE_MANIFEST_SHA256 = "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9"
EXPECTED_PACKAGES_SHA256 = "21da8f9ed19687e708cc7bc5cc59394c6fcdf9b9deadf617ae70526f815a1db0"
EXPECTED_SERVICES_SHA256 = "1f7623b2b4ffd2c4099fb34ad86fc96c1479e27bf81b1b0ba328c988cc4ffcb5"
EXPECTED_FRONT_CONTROLLER_SHA256 = "eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9"
FONT_RELATIVE_PATH = Path("resources/fonts/job-card-v2/DejaVuSans.ttf")
FONT_LICENSE_RELATIVE_PATH = Path("resources/fonts/job-card-v2/LICENSE.txt")
EXPECTED_FONT_PATH = APP_ROOT / FONT_RELATIVE_PATH
EXPECTED_FONT_SHA256 = "ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280"
EXPECTED_FONT_LICENSE_PATH = APP_ROOT / FONT_LICENSE_RELATIVE_PATH
EXPECTED_FONT_LICENSE_SHA256 = "bc88ec457a574842b8f28c20e97a1fe91ecca69db14840484a22c694f2ffb6da"
EXPECTED_RENDERER_VERSION = "separate-job-card-v2"

STAGE_APPROVAL_TOKEN = f"STAGE-BUYDTF-INCOMING-{TARGET_COMMIT[:16]}"
DEPLOY_APPROVAL_TOKEN = f"DEPLOY-BUYDTF-INCOMING-{TARGET_COMMIT[:16]}"
RECOVERY_APPROVAL_TOKEN = f"RECOVER-BUYDTF-INCOMING-{TARGET_COMMIT[:16]}"

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


def require_bundled_font_absent() -> dict[str, Any]:
    """Prove both reviewed application-owned font additions are still absent."""
    records: list[dict[str, Any]] = []
    for path, expected_sha256 in (
        (EXPECTED_FONT_PATH, EXPECTED_FONT_SHA256),
        (EXPECTED_FONT_LICENSE_PATH, EXPECTED_FONT_LICENSE_SHA256),
    ):
        if path.exists() or path.is_symlink():
            raise DeploymentError(f"Reviewed font addition is unexpectedly present: {path}")
        records.append(
            {
                "path": str(path),
                "expected_sha256": expected_sha256,
                "state": "absent",
            }
        )
    return {"state": "reviewed_additions_absent", "files": records}


def bundled_font_identity(root: Path = APP_ROOT) -> dict[str, Any]:
    """Verify and describe the immutable bundled font and its license."""
    font = require_regular_file(root / FONT_RELATIVE_PATH, EXPECTED_FONT_SHA256)
    license_path = require_regular_file(
        root / FONT_LICENSE_RELATIVE_PATH,
        EXPECTED_FONT_LICENSE_SHA256,
    )
    return {
        "renderer_version": EXPECTED_RENDERER_VERSION,
        "font": {
            "path": str(font),
            "sha256": EXPECTED_FONT_SHA256,
            "bytes": font.stat().st_size,
        },
        "license": {
            "path": str(license_path),
            "sha256": EXPECTED_FONT_LICENSE_SHA256,
            "bytes": license_path.stat().st_size,
        },
    }


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


def parse_manifest(path: Path) -> list[dict[str, str]]:
    require_regular_file(path, EXPECTED_MANIFEST_SHA256)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text("utf-8").splitlines(), start=1):
        if not raw_line or raw_line.startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 4 or fields[0] not in {"A", "M"}:
            raise DeploymentError(f"Invalid manifest row at line {line_number}.")
        action, expected, target, relative_text = fields
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
        if not re.fullmatch(r"[0-9a-f]{64}", target):
            raise DeploymentError(f"Invalid target digest for {relative_text}.")
        if action == "A" and expected != "ABSENT":
            raise DeploymentError(f"Addition does not require absence: {relative_text}")
        if action == "M" and not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise DeploymentError(f"Replacement has an invalid expected digest: {relative_text}")
        seen.add(relative_text)
        rows.append(
            {"action": action, "expected": expected, "target": target, "path": relative_text}
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


def live_manifest_snapshot(rows: list[dict[str, str]], *, target: bool = False) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
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
            continue
        require_regular_file(path)
        actual = sha256_file(path)
        if actual != expected:
            raise DeploymentError(
                f"Live source CAS mismatch for {relative}: expected {expected}, got {actual}"
            )
        results.append(
            {
                "path": relative,
                "state": "file",
                "sha256": actual,
                "bytes": path.stat().st_size,
                "metadata": path_metadata(path),
                "matches": True,
            }
        )
    return {
        "expectation": "target" if target else "expected-live",
        "count": len(results),
        "rows": results,
        "sha256": sha256_bytes(canonical_bytes(results)),
    }


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
    require_renderer_ready: bool = False,
) -> None:
    if payload.get("application_environment") != "local":
        raise DeploymentError("APP_ENV differs from the reviewed local value.")
    if payload.get("application_debug") is not False:
        raise DeploymentError("APP_DEBUG is not false.")
    runtime = payload.get("runtime", {})
    if runtime.get("php_version") != "8.2.30" or runtime.get("laravel_version") != "12.61.1":
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
    required = schema.get("required_tables", {})
    if any(required.get(name) is not True for name in ("businesses", "dtforders", "dtfimages")):
        raise DeploymentError("A required Fuel table is missing.")
    if require_target_absent:
        target = schema.get("target_tables", {})
        if any(target.get(name) is not False for name in TARGET_TABLES):
            raise DeploymentError("A target incoming-order table already exists.")
        if ledger.get("target_entry_count") != 0:
            raise DeploymentError("The target incoming-order migration is already in the ledger.")
    capabilities = payload.get("capabilities", {})
    if (
        capabilities.get("receiver_enabled") is not False
        or capabilities.get("job_label_enabled") is not False
        or capabilities.get("retention_enabled") is not False
        or capabilities.get("allowed_host_count") != 0
    ):
        raise DeploymentError("An incoming-order capability or artwork host is unexpectedly enabled.")
    renderer = payload.get("job_card_renderer", {})
    if require_renderer_ready:
        readiness = renderer.get("readiness", {})
        if (
            renderer.get("class_available") is not True
            or not isinstance(readiness, dict)
            or readiness.get("ready") is not True
            or readiness.get("reason") is not None
            or readiness.get("renderer_version") != EXPECTED_RENDERER_VERSION
            or readiness.get("font_sha256") != EXPECTED_FONT_SHA256
            or readiness.get("width_px") != 1500
            or readiness.get("height_px") != 900
            or readiness.get("dpi") != 300
        ):
            raise DeploymentError("The immutable job-card renderer is not exactly ready.")
    queue = payload.get("queue", {})
    if queue.get("connection") != "sync":
        raise DeploymentError("The queue connection is no longer sync.")
    counts = queue.get("counts", {})
    if counts.get("jobs") not in (0, None) or counts.get("failed_jobs") not in (0, None):
        raise DeploymentError("Queued or failed jobs are present.")


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
    manifest_rows: list[dict[str, str]],
    evidence_directory: Path,
    prefix: str,
    require_target_absent: bool = True,
) -> dict[str, Any]:
    if os.geteuid() == 0:
        raise DeploymentError("Refusing to run an application deployment artifact as root.")
    if sys.version_info[:3] != (3, 10, 12):
        raise DeploymentError("Python differs from the reviewed 3.10.12 runtime.")
    for executable in ("/usr/bin/php", "/usr/bin/curl", "/usr/bin/ss"):
        if not Path(executable).is_file() or not os.access(executable, os.X_OK):
            raise DeploymentError(f"Required executable is unavailable: {executable}")
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
    font_asset = (
        require_bundled_font_absent()
        if require_target_absent
        else bundled_font_identity()
    )
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
        "receiver_lock_free": lock_is_free(DEPLOYMENT_LOCK),
        "scoped_processes": conflicts,
        "active_fpm_connections_observed": active_fpm_connections(),
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "front_controller_sha256": EXPECTED_FRONT_CONTROLLER_SHA256,
        "front_controller_metadata": front_controller_metadata,
        "font_asset": font_asset,
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


def preflight_guard(helper: Path, rows: list[dict[str, str]]) -> dict[str, Any]:
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
    font_asset = require_bundled_font_absent()
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
        "font_asset": font_asset,
        "dependencies": dependencies,
        "runtime": runtime,
        "health": health,
    }


def validate_archive_members(
    archive: Path, rows: list[dict[str, str]]
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
    rows: list[dict[str, str]],
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
    rows: list[dict[str, str]],
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
    rows: list[dict[str, str]], evidence_directory: Path
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
    rows: list[dict[str, str]],
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
    if "incoming_order_jobs" not in lowered or "api_asset_records" not in lowered:
        raise DeploymentError("Pretend output does not cover both reviewed target tables.")
    prohibited = re.compile(r"\b(drop|truncate|delete|insert|update|replace|rename)\b", re.I)
    if prohibited.search(normalized):
        raise DeploymentError("Pretend output contains prohibited DDL or DML.")
    creates = 0
    for statement in statements:
        statement_lower = statement.lower()
        mentioned = {name for name in TARGET_TABLES if name in statement_lower}
        if not mentioned:
            raise DeploymentError("Pretend SQL targets an unreviewed table.")
        if re.search(r"\bcreate\s+table\b", statement_lower):
            creates += 1
        elif not re.search(r"\balter\s+table\b", statement_lower):
            raise DeploymentError("Pretend output contains an unreviewed SQL operation.")
    if creates != 2:
        raise DeploymentError(f"Pretend output contains {creates} CREATE TABLE statements, expected 2.")


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
        "target_tables_absent_before": all(
            before_schema.get("target_tables", {}).get(name) is False for name in TARGET_TABLES
        ),
        "target_tables_absent_after": all(
            after_schema.get("target_tables", {}).get(name) is False for name in TARGET_TABLES
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

        copied_archive = inputs / f"incoming-order-v1-{TARGET_SHORT}.tar"
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
        font_asset = bundled_font_identity(candidate)
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
            "scope": "phase0-read-only-and-phase1-restricted-staging-only",
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
            "font_asset": font_asset,
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
) -> tuple[dict[str, Any], Path, list[dict[str, str]]]:
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
        raise DeploymentError("Release receipt identity differs from the reviewed receiver.")
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
    font_asset = bundled_font_identity(candidate)
    recorded_font = receipt.get("font_asset", {})
    if (
        recorded_font.get("renderer_version") != EXPECTED_RENDERER_VERSION
        or recorded_font.get("font", {}).get("sha256") != EXPECTED_FONT_SHA256
        or recorded_font.get("license", {}).get("sha256")
        != EXPECTED_FONT_LICENSE_SHA256
        or font_asset["font"]["sha256"] != EXPECTED_FONT_SHA256
        or font_asset["license"]["sha256"] != EXPECTED_FONT_LICENSE_SHA256
    ):
        raise DeploymentError("Staged immutable font asset differs from its Phase 1 receipt.")
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
    rows: list[dict[str, str]], state_directory: Path
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
    probe: Callable[[], dict[str, Any]] | None = None,
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
        write_state(state_path, state)
        time.sleep(OPCACHE_WAIT_SECONDS)
        result = probe() if probe is not None else gate_http_probe(state_directory, name)
        if (
            result.get("status") != 503
            or result.get("header_verified") is not True
            or result.get("sentinel_verified") is not True
        ):
            raise DeploymentError(
                "Boot-independent static gate did not return its reviewed 503 response."
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
            details={"identity": verified, "probe": result},
        )
        return {
            "sha256": EXPECTED_GATE_SHA256,
            "metadata": reviewed_metadata,
            "initial": initial,
            "replacement": replacement,
            "reconciled_from_live_identity": reconciled_from_live_identity,
            "probe": result,
        }
    except Exception as exception:
        live_after_failure = file_identity(front_controller)
        if live_after_failure["sha256"] not in {original_sha256, EXPECTED_GATE_SHA256}:
            raise DeploymentError(
                "Static-gate failure left unknown front-controller bytes; refusing overwrite."
            ) from exception
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
        failure_receipt = {
            "status": "gate_failed_original_restored",
            "generated_at_utc": utc_now(),
            "operation": name,
            "failure_type": type(exception).__name__,
            "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
            "initial": initial,
            "live_after_failure": live_after_failure,
            "restoration_receipt": {
                "path": restoration["path"],
                "sha256": restoration["receipt_sha256"],
            },
            "final": file_identity(front_controller),
        }
        failure_path = state_directory / f"{name}-gate-failure-receipt.json"
        failure_sha256 = write_new_json(failure_path, failure_receipt)
        state["static_gate_active"] = False
        state["gate_failure_receipt"] = str(failure_path)
        state["status"] = f"{name}_failed_original_restored"
        write_state(state_path, state)
        raise DeploymentError(
            "Static-gate installation or verification failed; the exact original "
            f"front controller was restored (receipt {failure_sha256})."
        ) from exception


def gate_http_probe(state_directory: Path, name: str) -> dict[str, Any]:
    headers = state_directory / f"{name}.headers.txt"
    body = state_directory / f"{name}.body.txt"
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
        "status": int(completed.stdout),
        "header_verified": f"{MAINTENANCE_GATE_HEADER_NAME}: {MAINTENANCE_GATE_HEADER_VALUE}".lower()
        in header_text,
        "sentinel_verified": MAINTENANCE_GATE_SENTINEL in body_text,
        "headers_sha256": sha256_file(headers),
        "body_sha256": sha256_file(body),
    }


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
    rows: list[dict[str, str]],
    state_directory: Path,
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
        atomic_install_file(source, destination, metadata)
        require_regular_file(destination, row["target"])
        if path_metadata(destination) != metadata:
            raise DeploymentError(f"Installed metadata differs for {row['path']}.")
        result = {
            "path": row["path"],
            "action": row["action"],
            "sha256": row["target"],
            "metadata": metadata,
        }
        results.append(result)
        append_event(state_directory, "source_file_installed", result)
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
    ledger = after.get("migration_ledger", {})
    schema = after.get("schema", {})
    target_tables = schema.get("target_tables", {})
    target_counts = schema.get("target_table_row_counts", {})
    if ledger.get("target_entry_count") != 1:
        raise DeploymentError("The exact incoming-order migration ledger entry was not recorded once.")
    if any(target_tables.get(name) is not True for name in TARGET_TABLES):
        raise DeploymentError("The incoming-order migration did not create both reviewed tables.")
    if any(target_counts.get(name) != 0 for name in TARGET_TABLES):
        raise DeploymentError("A newly created incoming-order table is not empty.")
    if schema.get("required_table_row_counts") != before["schema"].get(
        "required_table_row_counts"
    ):
        raise DeploymentError("A required Fuel table row count changed during the additive migration.")

    definitions = schema.get("target_definitions", {})
    table_rows = definitions.get("tables", [])
    if {row.get("TABLE_NAME") for row in table_rows} != TARGET_TABLES:
        raise DeploymentError("Target table definitions are incomplete.")
    if any(str(row.get("ENGINE", "")).lower() != "innodb" for row in table_rows):
        raise DeploymentError("A target table is not InnoDB.")
    columns = definitions.get("columns", [])
    binary_columns = {
        (row.get("TABLE_NAME"), row.get("COLUMN_NAME")): row.get("COLLATION_NAME")
        for row in columns
        if row.get("COLUMN_NAME")
        in {"integration_client", "idempotency_key", "lease_owner", "production_owner"}
    }
    required_binary = {
        ("incoming_order_jobs", "integration_client"),
        ("incoming_order_jobs", "idempotency_key"),
        ("incoming_order_jobs", "lease_owner"),
        ("incoming_order_jobs", "production_owner"),
    }
    if set(binary_columns) != required_binary or any(
        str(collation).lower() != "ascii_bin" for collation in binary_columns.values()
    ):
        raise DeploymentError("Reviewed idempotency/owner columns are not ascii_bin.")
    index_names = {row.get("INDEX_NAME") for row in definitions.get("statistics", [])}
    expected_indexes = {
        "PRIMARY",
        "incoming_order_jobs_dtfimage_id_unique",
        "incoming_jobs_client_key_unique",
        "incoming_jobs_state_lease_index",
        "incoming_jobs_label_status_index",
        "incoming_jobs_production_state_index",
        "incoming_jobs_production_lease_index",
        "api_assets_job_role_path_unique",
        "api_assets_retention_index",
        "api_assets_path_hash_index",
    }
    if not expected_indexes.issubset(index_names):
        missing = sorted(expected_indexes - index_names)
        raise DeploymentError(f"Target schema is missing reviewed indexes: {missing}")
    return {
        "status": "pass",
        "ledger": ledger,
        "schema": schema,
        "required_table_row_counts_unchanged": True,
        "target_tables_empty": True,
        "ascii_bin_columns": binary_columns,
        "reviewed_indexes_present": sorted(expected_indexes),
    }


def candidate_cli_checks(
    helper: Path,
    rows: list[dict[str, str]],
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
            ["route:list", "--path=api/incomingorder", "--no-interaction"],
            state_directory=state_directory,
            name="candidate-route-list",
            timeout=60,
        ),
        "commands": run_artisan(
            ["list", "--raw", "--no-interaction"],
            state_directory=state_directory,
            name="candidate-command-list",
            timeout=60,
        ),
    }
    route_text = Path(str(commands["route"]["stdout"]["path"])).read_text("utf-8")
    if route_text.count("POST") < 1 or route_text.count("GET") < 1:
        raise DeploymentError("Incoming-order legacy/capability routes were not both discovered.")
    command_text = Path(str(commands["commands"]["stdout"]["path"])).read_text("utf-8")
    if "incoming-orders:retention-report" not in command_text:
        raise DeploymentError("The report-only retention command was not discovered.")
    runtime, runtime_command = runtime_probe(helper, state_directory, "candidate-runtime-probe")
    validate_runtime_snapshot(
        runtime,
        require_target_absent=False,
        require_renderer_ready=True,
    )
    font_asset = bundled_font_identity()
    if any(runtime["schema"]["target_tables"].get(name) is not True for name in TARGET_TABLES):
        raise DeploymentError("Candidate runtime does not observe both incoming-order tables.")
    if any(runtime["schema"]["target_table_row_counts"].get(name) != 0 for name in TARGET_TABLES):
        raise DeploymentError("Candidate runtime observes unexpected incoming-order rows.")
    dependencies = dependency_identity()
    return {
        "status": "pass",
        "live_source": live,
        "lint": lint_results,
        "commands": commands,
        "runtime": runtime,
        "runtime_command": runtime_command,
        "font_asset": font_asset,
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
    readiness = label.get("renderer_readiness", {})
    if (
        label.get("renderer_version") != EXPECTED_RENDERER_VERSION
        or label.get("renderer_font_sha256") != EXPECTED_FONT_SHA256
        or not isinstance(readiness, dict)
        or readiness.get("ready") is not True
        or readiness.get("reason") is not None
        or readiness.get("renderer_version") != EXPECTED_RENDERER_VERSION
        or readiness.get("font_sha256") != EXPECTED_FONT_SHA256
        or readiness.get("width_px") != 1500
        or readiness.get("height_px") != 900
        or readiness.get("dpi") != 300
    ):
        raise DeploymentError("Capability endpoint reports an unready job-card renderer.")
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
        "renderer_version": EXPECTED_RENDERER_VERSION,
        "renderer_font_sha256": EXPECTED_FONT_SHA256,
        "renderer_readiness": readiness,
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
    validate_runtime_snapshot(
        runtime,
        require_target_absent=False,
        require_renderer_ready=True,
    )
    if any(runtime["schema"]["target_table_row_counts"].get(table) != 0 for table in TARGET_TABLES):
        raise DeploymentError("Post-open incoming-order tables are not empty.")
    return {
        "health_first": health_first,
        "health_second": health_second,
        "capability_first": capability_first,
        "capability_second": capability_second,
        "runtime": runtime,
        "runtime_command": runtime_command,
        "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
        "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
    }


def monitor_production(
    helper: Path,
    rows: list[dict[str, str]],
    state_directory: Path,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    sample_count = MONITOR_SECONDS // MONITOR_INTERVAL_SECONDS
    for index in range(sample_count):
        runtime, _ = runtime_probe(helper, state_directory, f"monitor-runtime-{index + 1:02d}")
        validate_runtime_snapshot(
            runtime,
            require_target_absent=False,
            require_renderer_ready=True,
        )
        if any(runtime["schema"]["target_table_row_counts"].get(table) != 0 for table in TARGET_TABLES):
            raise DeploymentError("Monitoring observed an unexpected incoming-order row.")
        sample = {
            "number": index + 1,
            "at_utc": utc_now(),
            "health": health_snapshot(),
            "capabilities": runtime["capabilities"],
            "queue": runtime["queue"],
            "target_table_row_counts": runtime["schema"]["target_table_row_counts"],
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
    rows: list[dict[str, str]],
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
    }:
        raise DeploymentError(
            "Durable state says the gate is installed but live identity is the original."
        )
    return bool(state.get("migration_executed") or state.get("source_install_started"))


def rollback_operation(
    *,
    state_path: Path,
    state: dict[str, Any],
    rows: list[dict[str, str]],
    helper: Path,
    automatic: bool,
) -> dict[str, Any]:
    state_directory = state_path.parent
    append_event(state_directory, "rollback_started", {"automatic": automatic})
    state["rollback_started"] = True
    state["status"] = "rolling_back"
    write_state(state_path, state)

    # Never trust a persisted boolean. The corrected primitive reconciles the
    # actual front-controller bytes with durable transition state before any
    # recovery write.
    gate = install_static_gate(
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

        view_clear = run_artisan(
            ["view:clear", "--no-interaction"],
            state_directory=state_directory,
            name="rollback-view-clear",
            timeout=60,
        )
        runtime, runtime_command = runtime_probe(helper, state_directory, "rollback-runtime-probe")
        validate_runtime_snapshot(runtime, require_target_absent=False)

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
            "view_clear": view_clear,
            "runtime": runtime,
            "runtime_command": runtime_command,
            "front_controller_restore": front_restore,
            "health": health,
        }
    except Exception as rollback_exception:
        try:
            containment = install_static_gate(
                state_directory=state_directory,
                name="rollback-failure-static-gate",
                state=state,
                state_path=state_path,
                original_backup=Path(str(state["front_controller_backup"])),
                metadata=state["front_controller_metadata"],
            )
            state["static_gate_active"] = True
            state["status"] = "rollback_failed_site_gated"
            state["rollback_failure_gate"] = containment
            write_state(state_path, state)
            append_event(state_directory, "rollback_failed_site_gated")
        except Exception as gate_exception:
            # The gate primitive restores the exact original front controller
            # whenever its own initial verification fails.
            state["static_gate_active"] = False
            state["status"] = "rollback_failed_gate_unavailable_original_restored"
            state["rollback_failure_type"] = type(rollback_exception).__name__
            state["rollback_failure_message_sha256"] = sha256_bytes(
                str(rollback_exception).encode("utf-8")
            )
            state["gate_failure_type"] = type(gate_exception).__name__
            state["gate_failure_message_sha256"] = sha256_bytes(
                str(gate_exception).encode("utf-8")
            )
            write_state(state_path, state)
            append_event(state_directory, "rollback_failed_gate_unavailable_original_restored")
            raise DeploymentError(
                "Rollback failed and the static gate could not be verified; "
                "the gate primitive restored the exact original front controller."
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
            "laravel_maintenance_active": False,
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
            source_install = install_runtime_files(candidate, rows, state_directory)
            state["source_install_complete"] = True
            state["source_install_receipt"] = source_install["path"]
            state["status"] = "source_installed"
            write_state(state_path, state)

            view_clear = run_artisan(
                ["view:clear", "--no-interaction"],
                state_directory=state_directory,
                name="candidate-view-clear",
                timeout=60,
            )
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
                "view_clear": view_clear,
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
        raise DeploymentError("Recovery state does not belong to the reviewed receiver.")
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
        "artifact": "BuyDTF incoming-order v1 fixed deployment runner",
        "target_commit": TARGET_COMMIT,
        "application_root": str(APP_ROOT),
        "release_root": str(RELEASE_ROOT),
        "rollback_root": str(ROLLBACK_ROOT),
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "helper_sha256": EXPECTED_HELPER_SHA256,
        "migration": {
            "path": MIGRATION_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_MIGRATION_SHA256,
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
            "verification_failure_restores_exact_original": True,
            "recovery_uses_live_identity_and_durable_state": True,
        },
        "font_asset": {
            "renderer_version": EXPECTED_RENDERER_VERSION,
            "path": str(EXPECTED_FONT_PATH),
            "sha256": EXPECTED_FONT_SHA256,
            "license_path": str(EXPECTED_FONT_LICENSE_PATH),
            "license_sha256": EXPECTED_FONT_LICENSE_SHA256,
            "predeployment_state": "absent_reviewed_addition",
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
            "service_restart": False,
            "environment_change": False,
            "capability_enablement": False,
            "retention_execution": False,
            "source_rollback_drops_additive_schema": False,
            "gate_failure_restores_original_with_receipt": True,
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
