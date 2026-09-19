#!/usr/bin/env python3
"""Stage, atomically exchange, verify, and roll back BuyDTF dependencies.

Production modes are intentionally fixed to /var/www/buy-dtf and to reviewed
artifact hashes. There are no Git, migration, dependency-update, source-copy,
configuration-copy, or service-restart operations in this program.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


APP_ROOT = Path("/var/www/buy-dtf")
RELEASE_ROOT = APP_ROOT / "storage/app/private/operations/dependency-releases"
ROLLBACK_ROOT = APP_ROOT / "storage/app/private/operations/dependency-rollbacks"
DEPLOYMENT_LOCK = APP_ROOT / "storage/framework/dependency-deployment.lock"
FPM_SOCKET = Path("/run/php/php8.2-fpm.sock")
LARAVEL_MAINTENANCE_FILE = APP_ROOT / "storage/framework/down"
FRONT_CONTROLLER = APP_ROOT / "public/index.php"
MAINTENANCE_PROBE_URL = "https://buy-dtf.com/"

EXPECTED_APP_UID = 1000
EXPECTED_APP_GID = 1000
EXPECTED_WEB_GID = 33
EXPECTED_LIVE_COMPOSER_JSON_SHA256 = "7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872"
EXPECTED_LIVE_LOCK_SHA256 = "16eef909889a727717fccf52e9c7c23e8a0d2cc661777f6044abde97713d2579"
CANDIDATE_LOCK_SHA256 = "eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831"
EXPECTED_DATABASE_CONFIG_SHA256 = "d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9"
EXPECTED_SOURCE_MANIFEST_SHA256 = "46f6a1ffa03364b550395c89111a0d69a844d1379f3c5aba6ed5c1e17616abca"
EXPECTED_LIVE_VENDOR_MANIFEST_SHA256 = "738c326e7f8e9199d36d0bb754eff031c38c5f69603bb56baa3cd189c98dbdcc"
EXPECTED_FRONT_CONTROLLER_SHA256 = "eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9"
EXPECTED_APP_ENVIRONMENT = "local"
EXPECTED_APP_DEBUG = False
RUNTIME_HELPER_SHA256 = "e664bbff0af18ba07763bfb0fd1f2f4d2f4a5f7f2f2e378caed8daeea3ca31b7"

OLD_LARAVEL_VERSION = "12.46.0"
OLD_GUZZLE_VERSION = "7.10.0"
NEW_LARAVEL_VERSION = "12.61.1"
NEW_GUZZLE_VERSION = "7.15.2"
STAGE_APPROVAL_TOKEN = f"STAGE-BUYDTF-DEPS-{CANDIDATE_LOCK_SHA256[:16]}"
CUTOVER_APPROVAL_TOKEN = f"DEPLOY-BUYDTF-DEPS-{CANDIDATE_LOCK_SHA256[:16]}"
RECOVERY_APPROVAL_TOKEN = f"RECOVER-BUYDTF-DEPS-{EXPECTED_LIVE_LOCK_SHA256[:16]}"

DRAIN_SECONDS = 65
OPCACHE_WAIT_SECONDS = 5
OPCACHE_SECOND_PROBE_DELAY_SECONDS = 3
MONITOR_SECONDS = 30 * 60
MONITOR_INTERVAL_SECONDS = 60

SOURCE_ROOTS = (
    "app",
    "bootstrap",
    "config",
    "database/migrations",
    "resources/views",
    "routes",
    "public/build",
)
SOURCE_TOP_LEVEL_FILES = ("artisan", "composer.json")

NORMAL_HEALTH_CHECKS = (
    ("https://buy-dtf.com/", {200}),
    ("https://buy-dtf.com/up", {200}),
    ("https://buy-dtf.com/login", {200}),
    ("https://buy-dtf.com/admin", {302}),
    ("https://buy-dtf.com/checkout", {302}),
)

AT_FDCWD = -100
RENAME_EXCHANGE = 2

REQUIRED_CANDIDATE_CACHE_FILES = frozenset({"packages.php", "services.php"})
CUTOVER_TRANSITIONS = (
    "after_gate_install",
    "after_vendor_exchange",
    "after_cache_exchange",
    "after_lock_replacement",
    "after_candidate_runtime",
    "after_candidate_fpm_probes",
    "after_candidate_gate_open",
    "after_candidate_health",
)
ROLLBACK_TRANSITIONS = (
    "after_rollback_gate_install",
    "after_rollback_vendor",
    "after_rollback_cache",
    "after_rollback_lock",
    "after_rollback_runtime",
    "after_rollback_fpm_probes",
    "after_rollback_gate_open",
    "after_rollback_health",
)
MAINTENANCE_GATE_HEADER = "X-BuyDTF-Dependency-Maintenance: static-v2"
MAINTENANCE_GATE_SENTINEL = "BUYDTF_DEPENDENCY_MAINTENANCE_STATIC_V2"
MAINTENANCE_GATE_BYTES = f"""<?php
declare(strict_types=1);

http_response_code(503);
header('Content-Type: text/plain; charset=UTF-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Retry-After: 120');
header('{MAINTENANCE_GATE_HEADER}');
echo '{MAINTENANCE_GATE_SENTINEL}';
""".encode("utf-8")
MAINTENANCE_GATE_SHA256 = hashlib.sha256(MAINTENANCE_GATE_BYTES).hexdigest()


class DeploymentError(RuntimeError):
    """Expected fail-closed stop."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def require_real_directory(path: Path, *, within: Path | None = None) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise DeploymentError(f"Required directory is missing, invalid, or symbolic: {path}")
    resolved = path.resolve(strict=True)
    if within is not None and not is_relative_to(resolved, within.resolve(strict=True)):
        raise DeploymentError(f"Directory escapes its approved root: {path}")
    return resolved


def require_regular_file(path: Path, expected_sha256: str | None = None) -> Path:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise DeploymentError(f"Required file is missing, invalid, or symbolic: {path}")
    if expected_sha256 is not None:
        actual = sha256_file(path)
        if actual != expected_sha256:
            raise DeploymentError(
                f"Checksum mismatch for {path.name}: expected {expected_sha256}, got {actual}"
            )
    return path.resolve(strict=True)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def deployment_lock() -> Any:
    DEPLOYMENT_LOCK.parent.mkdir(mode=0o775, parents=True, exist_ok=True)
    with DEPLOYMENT_LOCK.open("a+b") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exception:
            raise DeploymentError("Another dependency operation holds the application lock.") from exception
        yield


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
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


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(
        path,
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )


def atomic_copy(source: Path, destination: Path, mode: int | None = None) -> None:
    require_regular_file(source)
    target_mode = mode if mode is not None else stat.S_IMODE(source.stat().st_mode)
    temporary = destination.with_name(
        f".{destination.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
    )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, target_mode)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, target_mode)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def path_metadata(path: Path) -> dict[str, int | str]:
    if path.is_symlink():
        raise DeploymentError(f"Symbolic path metadata is not allowed: {path}")
    metadata = path.stat()
    if stat.S_ISREG(metadata.st_mode):
        kind = "file"
    elif stat.S_ISDIR(metadata.st_mode):
        kind = "directory"
    else:
        raise DeploymentError(f"Special path metadata is not allowed: {path}")
    return {
        "kind": kind,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def require_path_metadata(path: Path, expected: dict[str, Any]) -> None:
    actual = path_metadata(path)
    if actual != expected:
        raise DeploymentError(f"Path metadata differs from the approved identity: {path}")


def atomic_install_bytes(path: Path, content: bytes, metadata: dict[str, Any]) -> None:
    parent = require_real_directory(path.parent)
    if metadata.get("kind") != "file":
        raise DeploymentError("Atomic file installation requires regular-file metadata.")
    mode = metadata.get("mode")
    uid = metadata.get("uid")
    gid = metadata.get("gid")
    if not all(isinstance(value, int) for value in (mode, uid, gid)):
        raise DeploymentError("Atomic file installation metadata is invalid.")
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(parent)
        require_path_metadata(path, metadata)
    finally:
        temporary.unlink(missing_ok=True)


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise DeploymentError(
            f"Command failed at {Path(command[0]).name} (exit {completed.returncode})."
        )
    return completed


def write_command_result(path: Path, completed: subprocess.CompletedProcess[str]) -> str:
    content = (completed.stdout + completed.stderr).encode("utf-8")
    atomic_write(path, content)
    return sha256_file(path)


def tree_manifest(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    records: list[bytes] = []
    file_count = 0
    directory_count = 0
    total_bytes = 0
    for current_root, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)
        for name in directory_names:
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise DeploymentError(f"Tree contains an invalid directory: {path}")
            relative = path.relative_to(root).as_posix()
            mode = stat.S_IMODE(path.stat().st_mode)
            records.append(f"d\0{relative}\0{mode:o}\n".encode())
            directory_count += 1
        for name in file_names:
            path = current / name
            if path.is_symlink() or not path.is_file():
                raise DeploymentError(f"Tree contains an invalid file: {path}")
            relative = path.relative_to(root).as_posix()
            metadata = path.stat()
            digest = sha256_file(path)
            records.append(
                f"f\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0{metadata.st_size}\0{digest}\n".encode()
            )
            file_count += 1
            total_bytes += metadata.st_size
    records.sort()
    return {
        "sha256": sha256_bytes(b"".join(records)),
        "files": file_count,
        "directories": directory_count,
        "bytes": total_bytes,
    }


def cache_identity(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise DeploymentError(f"Bootstrap cache contains a symbolic path: {path}")
        relative = path.relative_to(root).as_posix()
        metadata = path_metadata(path)
        if metadata["kind"] == "file":
            metadata = {
                **metadata,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        entries[relative] = metadata
    return {
        "manifest": tree_manifest(root),
        "root_metadata": path_metadata(root),
        "entries": entries,
    }


def require_cache_identity(root: Path, expected: dict[str, Any]) -> None:
    if cache_identity(root) != expected:
        raise DeploymentError(f"Bootstrap cache differs from its approved identity: {root}")


def normalize_candidate_cache(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    entries = list(root.iterdir())
    names = {entry.name for entry in entries}
    if names != REQUIRED_CANDIDATE_CACHE_FILES:
        raise DeploymentError("Candidate bootstrap cache has an unexpected file set.")
    os.chown(root, EXPECTED_APP_UID, EXPECTED_WEB_GID)
    os.chmod(root, 0o2775)
    for entry in entries:
        require_regular_file(entry)
        if b"Pail" in entry.read_bytes():
            raise DeploymentError("Candidate bootstrap cache references the dev-only Pail provider.")
        os.chown(entry, EXPECTED_APP_UID, EXPECTED_WEB_GID)
        os.chmod(entry, 0o664)
    fsync_directory(root)
    identity = cache_identity(root)
    if identity["root_metadata"] != {
        "kind": "directory",
        "mode": 0o2775,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_WEB_GID,
    }:
        raise DeploymentError("Candidate bootstrap cache metadata could not be normalized.")
    return identity


def require_candidate_cache(root: Path, expected: dict[str, Any]) -> None:
    root = require_real_directory(root)
    entries = list(root.iterdir())
    if {entry.name for entry in entries} != REQUIRED_CANDIDATE_CACHE_FILES:
        raise DeploymentError("Staged candidate bootstrap cache file set changed.")
    for entry in entries:
        require_regular_file(entry)
        if b"Pail" in entry.read_bytes():
            raise DeploymentError("Staged candidate bootstrap cache references Pail.")
    require_cache_identity(root, expected)


def source_manifest(app_root: Path) -> dict[str, Any]:
    records: list[bytes] = []
    count = 0
    for relative_name in SOURCE_TOP_LEVEL_FILES:
        path = app_root / relative_name
        require_regular_file(path)
        records.append(f"{relative_name}\0{sha256_file(path)}\n".encode())
        count += 1
    for relative_root in SOURCE_ROOTS:
        root = require_real_directory(app_root / relative_root, within=app_root)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(app_root).as_posix()
            if relative.startswith("bootstrap/cache/"):
                continue
            if path.is_symlink():
                raise DeploymentError(f"Runtime source contains a symbolic link: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise DeploymentError(f"Runtime source contains a special file: {path}")
            records.append(f"{relative}\0{sha256_file(path)}\n".encode())
            count += 1
    records.sort()
    return {"sha256": sha256_bytes(b"".join(records)), "files": count}


def rename_exchange(first: Path, second: Path) -> None:
    first = require_real_directory(first)
    second = require_real_directory(second)
    if first == second:
        raise DeploymentError("Atomic exchange paths must be distinct.")
    if first.stat().st_dev != second.stat().st_dev:
        raise DeploymentError("Atomic exchange paths are not on the same filesystem.")

    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exception:
        raise DeploymentError("libc does not expose renameat2; atomic exchange is unavailable.") from exception
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        AT_FDCWD,
        os.fsencode(first),
        AT_FDCWD,
        os.fsencode(second),
        RENAME_EXCHANGE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise DeploymentError(
            f"renameat2(RENAME_EXCHANGE) failed: [{error_number}] {os.strerror(error_number)}"
        )
    fsync_directory(first.parent)
    if second.parent != first.parent:
        fsync_directory(second.parent)


def http_status(url: str, *, cache_buster: bool = False) -> int:
    target = url
    if cache_buster:
        separator = "&" if "?" in target else "?"
        target = f"{target}{separator}ops_probe={secrets.token_hex(12)}"
    completed = run(
        [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--output",
            "/dev/null",
            "--write-out",
            "%{http_code}",
            "--header",
            "Cache-Control: no-cache, no-store",
            "--header",
            "Pragma: no-cache",
            "--connect-timeout",
            "5",
            "--max-time",
            "10",
            "--max-redirs",
            "0",
            target,
        ],
        cwd=APP_ROOT,
        timeout=15,
    )
    try:
        return int(completed.stdout)
    except ValueError as exception:
        raise DeploymentError(f"Invalid HTTP status returned for {url}.") from exception


def health_snapshot() -> dict[str, int]:
    statuses: dict[str, int] = {}
    for url, allowed in NORMAL_HEALTH_CHECKS:
        status = http_status(url, cache_buster=True)
        if status not in allowed:
            raise DeploymentError(f"Health probe failed for {url} with HTTP {status}.")
        statuses[url] = status
    return statuses


def scoped_processes() -> list[str]:
    matches: list[str] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in {os.getpid(), os.getppid()}:
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if "/var/www/buy-dtf/artisan" in command or "artisan stripe:sync-payouts" in command:
            matches.append(f"pid={entry.name}")
    return sorted(matches)


def active_fpm_connections() -> int:
    completed = run(
        ["/usr/bin/ss", "-H", "-x", "state", "connected"],
        cwd=APP_ROOT,
        timeout=15,
    )
    return sum(1 for line in completed.stdout.splitlines() if str(FPM_SOCKET) in line)


def runtime_probe(helper: Path) -> dict[str, Any]:
    completed = run(
        ["/usr/bin/php", str(helper), str(APP_ROOT)],
        cwd=APP_ROOT,
        timeout=60,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise DeploymentError("The dependency runtime helper returned invalid JSON.") from exception
    if not isinstance(payload, dict):
        raise DeploymentError("The dependency runtime helper returned an invalid payload.")
    return payload


def validate_runtime_baseline(payload: dict[str, Any], *, laravel: str, guzzle: str) -> None:
    if payload.get("app_environment") != EXPECTED_APP_ENVIRONMENT:
        raise DeploymentError("The live application environment differs from the reported baseline.")
    if payload.get("app_debug") is not EXPECTED_APP_DEBUG:
        raise DeploymentError("The live application debug setting differs from the reported baseline.")
    if payload.get("queue_connection") != "sync":
        raise DeploymentError("The live queue connection is no longer sync.")
    queue_tables = payload.get("queue_tables")
    if not isinstance(queue_tables, dict):
        raise DeploymentError("Queue table state is unavailable.")
    if queue_tables.get("jobs") not in (0, None) or queue_tables.get("failed_jobs") not in (0, None):
        raise DeploymentError("Queued or failed jobs are present.")
    if payload.get("laravel_version") != laravel or payload.get("guzzle_version") != guzzle:
        raise DeploymentError("Runtime dependency versions do not match the expected baseline.")
    vendor_prefix = str(APP_ROOT / "vendor") + os.sep
    for field in ("laravel_class_path", "guzzle_class_path"):
        if not str(payload.get(field, "")).startswith(vendor_prefix):
            raise DeploymentError(f"{field} does not resolve beneath the live vendor directory.")


def validate_toolchain() -> None:
    for executable in (
        "/usr/bin/cgi-fcgi",
        "/usr/bin/curl",
        "/usr/bin/php",
        "/usr/bin/ss",
        "/usr/local/bin/composer",
    ):
        if not Path(executable).is_file() or not os.access(executable, os.X_OK):
            raise DeploymentError(f"Required reviewed executable is unavailable: {executable}")
    if sys.version_info[:3] != (3, 10, 12):
        raise DeploymentError("Python runtime differs from the reviewed 3.10.12 baseline.")
    php = run(
        ["/usr/bin/php", "-r", "echo PHP_VERSION;"],
        cwd=APP_ROOT,
        timeout=15,
    )
    if php.stdout != "8.2.30":
        raise DeploymentError("PHP CLI differs from the reviewed 8.2.30 baseline.")
    composer = run(
        ["/usr/local/bin/composer", "--version", "--no-ansi"],
        cwd=APP_ROOT,
        timeout=30,
    )
    if not composer.stdout.startswith("Composer version 2.9.3 "):
        raise DeploymentError("Composer differs from the reviewed 2.9.3 baseline.")


def assert_production_baseline(
    helper: Path,
    *,
    check_old_vendor: bool = True,
    expected_front_controller_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256,
) -> dict[str, Any]:
    if os.geteuid() == 0:
        raise DeploymentError("Refusing to run application deployment as root.")
    validate_toolchain()
    app_root = require_real_directory(APP_ROOT)
    metadata = app_root.stat()
    if metadata.st_uid != EXPECTED_APP_UID or metadata.st_gid != EXPECTED_APP_GID:
        raise DeploymentError("Application owner/group differs from the approved baseline.")
    require_regular_file(APP_ROOT / "composer.json", EXPECTED_LIVE_COMPOSER_JSON_SHA256)
    require_regular_file(APP_ROOT / "composer.lock", EXPECTED_LIVE_LOCK_SHA256)
    require_regular_file(APP_ROOT / "config/database.php", EXPECTED_DATABASE_CONFIG_SHA256)
    require_regular_file(helper, RUNTIME_HELPER_SHA256)
    require_regular_file(FRONT_CONTROLLER, expected_front_controller_sha256)
    front_controller_metadata = path_metadata(FRONT_CONTROLLER)
    if front_controller_metadata != {
        "kind": "file",
        "mode": 0o644,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
    }:
        raise DeploymentError("The production front-controller metadata differs from baseline.")
    if LARAVEL_MAINTENANCE_FILE.exists():
        raise DeploymentError("Laravel maintenance mode is unexpectedly active.")
    source = source_manifest(APP_ROOT)
    if source["sha256"] != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise DeploymentError("Production runtime-source CAS manifest differs from the approved baseline.")
    vendor = tree_manifest(APP_ROOT / "vendor")
    if check_old_vendor and vendor["sha256"] != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
        raise DeploymentError("Live vendor manifest differs from the retained rollback baseline.")
    return {
        "source": source,
        "vendor": vendor,
        "cache": cache_identity(APP_ROOT / "bootstrap/cache"),
        "front_controller": {
            "sha256": expected_front_controller_sha256,
            "metadata": front_controller_metadata,
        },
    }


def safe_environment(composer_home: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(composer_home.parent / ".home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "APP_ENV": "testing",
        "APP_DEBUG": "false",
        "APP_KEY": "base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "BROADCAST_CONNECTION": "log",
        "CACHE_STORE": "array",
        "DB_CONNECTION": "sqlite",
        "DB_DATABASE": ":memory:",
        "FILESYSTEM_DISK": "local",
        "FUEL_DB_CONNECTION": "sqlite",
        "LOG_CHANNEL": "stderr",
        "MAIL_MAILER": "array",
        "QUEUE_CONNECTION": "sync",
        "SESSION_DRIVER": "array",
        "COMPOSER_HOME": str(composer_home),
        "COMPOSER_CACHE_DIR": str(composer_home / "cache"),
    }


def copy_runtime_shadow(destination: Path) -> None:
    for relative_name in SOURCE_TOP_LEVEL_FILES:
        if relative_name == "composer.json":
            continue
        source = APP_ROOT / relative_name
        target = destination / relative_name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
    for relative_root in ("app", "bootstrap", "config", "database", "resources", "routes"):
        source = APP_ROOT / relative_root
        target = destination / relative_root
        if source.is_symlink():
            raise DeploymentError(f"Cannot shadow-copy symbolic runtime root: {source}")
        shutil.copytree(
            source,
            target,
            symlinks=False,
            ignore=shutil.ignore_patterns("cache") if relative_root == "bootstrap" else None,
        )
    cache = destination / "bootstrap/cache"
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    for relative in (
        "storage/app",
        "storage/framework/cache",
        "storage/framework/sessions",
        "storage/framework/views",
        "storage/logs",
    ):
        (destination / relative).mkdir(mode=0o700, parents=True, exist_ok=True)


def stage_release(candidate_lock: Path, approval_token: str, helper: Path) -> Path:
    if approval_token != STAGE_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed staging approval token was not supplied.")
    baseline = assert_production_baseline(helper)
    candidate_lock = require_regular_file(candidate_lock, CANDIDATE_LOCK_SHA256)
    if candidate_lock.is_relative_to(APP_ROOT / "vendor"):
        raise DeploymentError("Candidate lock may not be sourced from vendor.")
    if scoped_processes():
        raise DeploymentError("A scoped Artisan/payout process is active; staging stopped.")
    before_health = health_snapshot()
    before_runtime = runtime_probe(helper)
    validate_runtime_baseline(before_runtime, laravel=OLD_LARAVEL_VERSION, guzzle=OLD_GUZZLE_VERSION)

    RELEASE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(RELEASE_ROOT, 0o700)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    release = RELEASE_ROOT / f"{CANDIDATE_LOCK_SHA256[:12]}-{timestamp}"
    release.mkdir(mode=0o700)
    shadow = release / "shadow"
    shadow.mkdir(mode=0o700)
    logs = release / "logs"
    logs.mkdir(mode=0o700)
    composer_home = release / ".composer-home"
    composer_home.mkdir(mode=0o700)
    (release / ".home").mkdir(mode=0o700)
    environment = safe_environment(composer_home)

    atomic_copy(APP_ROOT / "composer.json", shadow / "composer.json", 0o600)
    atomic_copy(candidate_lock, shadow / "composer.lock", 0o600)
    command_receipts: dict[str, str] = {}
    composer = "/usr/local/bin/composer"

    validate = run(
        [
            composer,
            "--no-plugins",
            "validate",
            "--strict",
            "--no-check-publish",
            "--no-interaction",
            "--no-ansi",
        ],
        cwd=shadow,
        timeout=120,
        env=environment,
    )
    command_receipts["composer_validate"] = write_command_result(logs / "composer-validate.txt", validate)
    audit = run(
        [
            composer,
            "--no-plugins",
            "audit",
            "--locked",
            "--no-dev",
            "--no-interaction",
            "--no-ansi",
        ],
        cwd=shadow,
        timeout=120,
        env=environment,
    )
    command_receipts["composer_audit"] = write_command_result(logs / "composer-audit.txt", audit)
    install = run(
        [
            composer,
            "--no-plugins",
            "install",
            "--no-dev",
            "--prefer-dist",
            "--optimize-autoloader",
            "--no-interaction",
            "--no-scripts",
            "--no-ansi",
        ],
        cwd=shadow,
        timeout=900,
        env=environment,
    )
    command_receipts["composer_install"] = write_command_result(logs / "composer-install.txt", install)
    platform = run(
        [
            composer,
            "--no-plugins",
            "check-platform-reqs",
            "--no-dev",
            "--no-interaction",
            "--no-ansi",
        ],
        cwd=shadow,
        timeout=120,
        env=environment,
    )
    command_receipts["platform"] = write_command_result(logs / "platform.txt", platform)

    copy_runtime_shadow(shadow)
    package_discovery = run(
        ["/usr/bin/php", "artisan", "package:discover", "--no-interaction", "--no-ansi"],
        cwd=shadow,
        timeout=120,
        env=environment,
    )
    command_receipts["shadow_package_discovery"] = write_command_result(
        logs / "shadow-package-discovery.txt", package_discovery
    )
    routes = run(
        ["/usr/bin/php", "artisan", "route:list", "--no-ansi"],
        cwd=shadow,
        timeout=120,
        env=environment,
    )
    command_receipts["shadow_routes"] = write_command_result(logs / "shadow-routes.txt", routes)

    vendor = tree_manifest(shadow / "vendor")
    candidate_cache = normalize_candidate_cache(shadow / "bootstrap/cache")
    installed = json.loads((shadow / "vendor/composer/installed.json").read_text(encoding="utf-8"))
    packages = installed.get("packages", installed) if isinstance(installed, dict) else installed
    versions = {
        package.get("name"): package.get("version_normalized", package.get("version"))
        for package in packages
        if isinstance(package, dict)
    }
    if not str(versions.get("laravel/framework", "")).startswith(NEW_LARAVEL_VERSION):
        raise DeploymentError("Staged Laravel version is not the approved candidate.")
    if not str(versions.get("guzzlehttp/guzzle", "")).startswith(NEW_GUZZLE_VERSION):
        raise DeploymentError("Staged Guzzle version is not the approved candidate.")
    if "laravel/pail" in versions:
        raise DeploymentError("The no-dev candidate unexpectedly contains Laravel Pail.")
    if (shadow / "vendor/laravel/pail").exists():
        raise DeploymentError("The no-dev candidate contains a Laravel Pail directory.")

    receipt = {
        "artifact": "buy-dtf-dependency-release-v2",
        "status": "staged",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_path": str(release),
        "shadow_path": str(shadow),
        "candidate_lock_sha256": CANDIDATE_LOCK_SHA256,
        "live_composer_json_sha256": EXPECTED_LIVE_COMPOSER_JSON_SHA256,
        "approved_source_manifest": baseline["source"],
        "retained_vendor_manifest": baseline["vendor"],
        "retained_cache_identity": baseline["cache"],
        "candidate_cache_identity": candidate_cache,
        "candidate_vendor_manifest": vendor,
        "front_controller": baseline["front_controller"],
        "maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
        "command_receipts": command_receipts,
        "health_before": before_health,
        "runtime_before": before_runtime,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "versions": {
            "laravel/framework": NEW_LARAVEL_VERSION,
            "guzzlehttp/guzzle": NEW_GUZZLE_VERSION,
        },
        "no_dev": True,
    }
    receipt_path = release / "release-receipt.json"
    atomic_json(receipt_path, receipt)
    print(f"Staging complete. Independently review and approve receipt: {receipt_path}")
    print(f"release_receipt_sha256={sha256_file(receipt_path)}")
    return receipt_path


def load_approved_release(receipt_path: Path, approved_sha256: str) -> tuple[dict[str, Any], Path]:
    receipt_path = require_regular_file(receipt_path, approved_sha256)
    if not is_relative_to(receipt_path, RELEASE_ROOT.resolve(strict=True)):
        raise DeploymentError("Release receipt is outside the fixed release root.")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise DeploymentError("Release receipt is invalid JSON.") from exception
    if receipt.get("artifact") != "buy-dtf-dependency-release-v2" or receipt.get("status") != "staged":
        raise DeploymentError("Release receipt is not an approved staged release.")
    if receipt.get("candidate_lock_sha256") != CANDIDATE_LOCK_SHA256:
        raise DeploymentError("Release receipt references a different candidate lock.")
    shadow = Path(str(receipt.get("shadow_path", "")))
    shadow = require_real_directory(shadow, within=RELEASE_ROOT)
    require_regular_file(shadow / "composer.lock", CANDIDATE_LOCK_SHA256)
    vendor = tree_manifest(shadow / "vendor")
    if vendor != receipt.get("candidate_vendor_manifest"):
        raise DeploymentError("Staged vendor differs from the approved release receipt.")
    candidate_cache = receipt.get("candidate_cache_identity")
    if not isinstance(candidate_cache, dict):
        raise DeploymentError("Release receipt has no candidate bootstrap-cache identity.")
    require_candidate_cache(shadow / "bootstrap/cache", candidate_cache)
    if receipt.get("maintenance_gate_sha256") != MAINTENANCE_GATE_SHA256:
        raise DeploymentError("Release receipt references a different static maintenance gate.")
    if receipt.get("no_dev") is not True:
        raise DeploymentError("Release receipt does not prove a no-dev dependency install.")
    return receipt, shadow


def copy_cache_snapshot(source: Path, destination: Path) -> dict[str, Any]:
    source = require_real_directory(source, within=APP_ROOT)
    if destination.exists():
        raise DeploymentError("Cache backup destination already exists.")
    source_identity = cache_identity(source)
    shutil.copytree(source, destination, symlinks=False)
    for source_path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
        relative = source_path.relative_to(source)
        destination_path = destination / relative
        metadata = path_metadata(source_path)
        os.chmod(destination_path, int(metadata["mode"]))
    # The deploy user cannot and must not impersonate www-data ownership on a
    # copied directory. The exact old cache (including ownership) is retained
    # by directory exchange; this restricted copy is independent evidence and
    # a content/mode backup only.
    os.chmod(destination, 0o700)
    fsync_directory(destination)
    copy_identity = cache_identity(destination)
    if copy_identity["manifest"] != source_identity["manifest"]:
        raise DeploymentError("Bootstrap-cache evidence copy differs in content or mode.")
    return {
        "source_identity": source_identity,
        "copy_identity": copy_identity,
    }


def probe_static_gate() -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for target in (
        MAINTENANCE_PROBE_URL,
        f"https://buy-dtf.com/__dependency_gate_{secrets.token_hex(12)}",
    ):
        completed = run(
            [
                "/usr/bin/curl",
                "--silent",
                "--show-error",
                "--dump-header",
                "-",
                "--output",
                "-",
                "--header",
                "Cache-Control: no-cache, no-store",
                "--header",
                "Pragma: no-cache",
                "--connect-timeout",
                "5",
                "--max-time",
                "10",
                "--max-redirs",
                "0",
                target,
            ],
            cwd=APP_ROOT,
            timeout=15,
        )
        output = completed.stdout.replace("\r\n", "\n")
        first_line = output.splitlines()[0] if output.splitlines() else ""
        if " 503 " not in first_line:
            raise DeploymentError("Static maintenance gate did not return HTTP 503.")
        if MAINTENANCE_GATE_HEADER.lower() not in output.lower():
            raise DeploymentError("Static maintenance gate response header is missing.")
        if MAINTENANCE_GATE_SENTINEL not in output:
            raise DeploymentError("Static maintenance gate response body is missing.")
        statuses[target] = 503
    return {
        "verified_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate_sha256": sha256_file(FRONT_CONTROLLER),
        "public_statuses": statuses,
    }


def install_static_gate(
    state: dict[str, Any], _state_path: Path, reason: str
) -> dict[str, Any]:
    metadata = state.get("front_controller_metadata")
    if not isinstance(metadata, dict):
        raise DeploymentError("Front-controller metadata is unavailable for the static gate.")
    atomic_install_bytes(FRONT_CONTROLLER, MAINTENANCE_GATE_BYTES, metadata)
    require_regular_file(FRONT_CONTROLLER, MAINTENANCE_GATE_SHA256)
    time.sleep(OPCACHE_WAIT_SECONDS)
    evidence = probe_static_gate()
    evidence["method"] = "atomic_static_front_controller"
    evidence["reason"] = reason
    return evidence


def restore_front_controller(state: dict[str, Any], state_path: Path) -> dict[str, Any]:
    backup_value = state.get("front_controller_backup")
    backup_sha256 = state.get("front_controller_backup_sha256")
    metadata = state.get("front_controller_metadata")
    if not isinstance(backup_value, str) or not isinstance(backup_sha256, str):
        raise DeploymentError("Front-controller rollback backup is unavailable.")
    if not isinstance(metadata, dict):
        raise DeploymentError("Front-controller rollback metadata is unavailable.")
    backup = require_regular_file(Path(backup_value), backup_sha256)
    state_directory = state_path.resolve(strict=True).parent
    expected_backup = state_directory / "public-index.before.php"
    if (
        not is_relative_to(state_directory, ROLLBACK_ROOT.resolve(strict=True))
        or backup != expected_backup
    ):
        raise DeploymentError("Front-controller rollback backup is outside the state directory.")
    atomic_install_bytes(FRONT_CONTROLLER, backup.read_bytes(), metadata)
    require_regular_file(FRONT_CONTROLLER, EXPECTED_FRONT_CONTROLLER_SHA256)
    time.sleep(OPCACHE_WAIT_SECONDS)
    return {
        "restored_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
    }


def reassert_and_record_gate(
    state: dict[str, Any],
    state_path: Path,
    reason: str,
    *,
    status: str | None = None,
    operation: Callable[[dict[str, Any], Path, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Never trust persisted gate state. Reinstall and verify the boot-independent
    # front controller before every rollback or recovery mutation.
    reassertion = operation or install_static_gate
    evidence = reassertion(state, state_path, reason)
    history = state.setdefault("gate_reassertions", [])
    if not isinstance(history, list):
        raise DeploymentError("Static-gate reassertion history is invalid.")
    history.append(evidence)
    state["gate_active"] = True
    state["gate_verified"] = True
    if status is not None:
        state["status"] = status
    write_state(state_path, state)
    return evidence


def contain_cutover_failure(
    state: dict[str, Any],
    state_path: Path,
    exception: BaseException,
    *,
    operation: Callable[[dict[str, Any], Path, str], dict[str, Any]] | None = None,
) -> None:
    try:
        reassert_and_record_gate(
            state,
            state_path,
            "cutover_failure",
            status="failure_contained_by_static_gate",
            operation=operation,
        )
    except BaseException as gate_exception:
        state["gate_active"] = None
        state["gate_verified"] = False
        state["failure_class"] = type(exception).__name__
        state["failure_message"] = str(exception)
        state["gate_failure_class"] = type(gate_exception).__name__
        state["gate_failure_message"] = str(gate_exception)
        state["status"] = "failed_static_gate_unverified"
        write_state(state_path, state)
        raise DeploymentError(
            "Cutover failed and the boot-independent 503 gate could not be re-verified; "
            "automatic rollback was not started."
        ) from gate_exception
    state["failure_class"] = type(exception).__name__
    state["failure_message"] = str(exception)
    state["status"] = "failed_rolling_back"
    write_state(state_path, state)


def contain_rollback_failure(
    state: dict[str, Any],
    state_path: Path,
    exception: BaseException,
    *,
    operation: Callable[[dict[str, Any], Path, str], dict[str, Any]] | None = None,
) -> None:
    try:
        reassert_and_record_gate(
            state,
            state_path,
            "rollback_failure",
            status="rollback_failure_contained_by_static_gate",
            operation=operation,
        )
    except BaseException as gate_exception:
        state["gate_active"] = None
        state["gate_verified"] = False
        state["rollback_failure_class"] = type(exception).__name__
        state["rollback_failure_message"] = str(exception)
        state["gate_failure_class"] = type(gate_exception).__name__
        state["gate_failure_message"] = str(gate_exception)
        state["status"] = "rollback_failed_static_gate_unverified"
        write_state(state_path, state)
        raise DeploymentError(
            "Rollback failed and the boot-independent 503 gate could not be re-verified; "
            "no subsequent rollback step will run."
        ) from gate_exception
    state["rollback_failure_class"] = type(exception).__name__
    state["rollback_failure_message"] = str(exception)
    state["status"] = "rollback_failed_static_gate_verified"
    write_state(state_path, state)


def fpm_probe(expected_laravel: str, expected_guzzle: str) -> dict[str, Any]:
    if not FPM_SOCKET.is_socket():
        raise DeploymentError("The reviewed PHP-FPM socket is unavailable.")
    probe_directory = APP_ROOT / "storage/framework/dependency-probes"
    probe_directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(probe_directory, -1, 33)
    os.chmod(probe_directory, 0o2750)
    probe = probe_directory / f"probe-{secrets.token_hex(12)}.php"
    source = f'''<?php
declare(strict_types=1);
require {str(APP_ROOT / "vendor/autoload.php")!r};
$payload = [
    'laravel_version' => Illuminate\\Foundation\\Application::VERSION,
    'guzzle_version' => Composer\\InstalledVersions::getPrettyVersion('guzzlehttp/guzzle'),
    'laravel_path' => (new ReflectionClass(Illuminate\\Foundation\\Application::class))->getFileName(),
    'guzzle_path' => (new ReflectionClass(GuzzleHttp\\Client::class))->getFileName(),
];
header('Content-Type: application/json');
echo json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
'''.encode("utf-8")
    atomic_write(probe, source, 0o640)
    os.chown(probe, -1, 33)
    environment = dict(os.environ)
    environment.update(
        {
            "SCRIPT_FILENAME": str(probe),
            "SCRIPT_NAME": "/internal-dependency-probe.php",
            "REQUEST_METHOD": "GET",
            "REQUEST_URI": "/internal-dependency-probe.php",
            "REDIRECT_STATUS": "200",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "GATEWAY_INTERFACE": "CGI/1.1",
        }
    )
    try:
        completed = run(
            ["/usr/bin/cgi-fcgi", "-bind", "-connect", str(FPM_SOCKET)],
            cwd=APP_ROOT,
            timeout=30,
            env=environment,
        )
        output = completed.stdout.replace("\r\n", "\n")
        if "\n\n" not in output:
            raise DeploymentError("PHP-FPM probe did not return CGI headers and a body.")
        headers, body = output.split("\n\n", 1)
        if "status: 5" in headers.lower():
            raise DeploymentError("PHP-FPM dependency probe returned a server error.")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exception:
            raise DeploymentError("PHP-FPM dependency probe returned invalid JSON.") from exception
        if payload.get("laravel_version") != expected_laravel:
            raise DeploymentError("PHP-FPM loaded an unexpected Laravel version.")
        if payload.get("guzzle_version") != expected_guzzle:
            raise DeploymentError("PHP-FPM loaded an unexpected Guzzle version.")
        vendor_prefix = str(APP_ROOT / "vendor") + os.sep
        if not str(payload.get("laravel_path", "")).startswith(vendor_prefix):
            raise DeploymentError("PHP-FPM Laravel reflection path is outside live vendor.")
        if not str(payload.get("guzzle_path", "")).startswith(vendor_prefix):
            raise DeploymentError("PHP-FPM Guzzle reflection path is outside live vendor.")
        return payload
    finally:
        probe.unlink(missing_ok=True)
        try:
            probe_directory.rmdir()
        except OSError:
            pass


def write_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    atomic_json(path, state)


def validate_rollback_state_paths(state: dict[str, Any], state_path: Path) -> None:
    state_path = require_regular_file(state_path)
    state_directory = state_path.parent.resolve(strict=True)
    if not is_relative_to(state_directory, ROLLBACK_ROOT.resolve(strict=True)):
        raise DeploymentError("Rollback state directory is outside the fixed rollback root.")
    expected_files = {
        "old_lock_backup": state_directory / "composer.lock.before",
        "front_controller_backup": state_directory / "public-index.before.php",
    }
    for field, expected in expected_files.items():
        value = state.get(field)
        if not isinstance(value, str) or Path(value).resolve(strict=True) != expected:
            raise DeploymentError(f"Rollback state has an invalid {field} path.")
    cache_value = state.get("cache_backup")
    if not isinstance(cache_value, str):
        raise DeploymentError("Rollback state has no cache-backup path.")
    cache_backup = require_real_directory(Path(cache_value), within=ROLLBACK_ROOT)
    if cache_backup != state_directory / "bootstrap-cache-before":
        raise DeploymentError("Rollback cache backup is outside the state directory.")

    receipt_value = state.get("release_receipt")
    receipt_sha256 = state.get("release_receipt_sha256")
    if not isinstance(receipt_value, str) or not isinstance(receipt_sha256, str):
        raise DeploymentError("Rollback state has no approved release receipt.")
    receipt_path = require_regular_file(Path(receipt_value), receipt_sha256)
    if not is_relative_to(receipt_path, RELEASE_ROOT.resolve(strict=True)):
        raise DeploymentError("Rollback release receipt is outside the fixed release root.")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise DeploymentError("Rollback release receipt is invalid JSON.") from exception
    if receipt.get("artifact") != "buy-dtf-dependency-release-v2":
        raise DeploymentError("Rollback release receipt has an unexpected artifact identity.")
    shadow = require_real_directory(Path(str(receipt.get("shadow_path", ""))), within=RELEASE_ROOT)
    if Path(str(state.get("staged_vendor", ""))).resolve(strict=True) != shadow / "vendor":
        raise DeploymentError("Rollback staged-vendor path differs from its release receipt.")
    if Path(str(state.get("staged_cache", ""))).resolve(strict=True) != shadow / "bootstrap/cache":
        raise DeploymentError("Rollback staged-cache path differs from its release receipt.")
    if state.get("script_sha256") != sha256_file(Path(__file__).resolve()):
        raise DeploymentError("Rollback state was created by a different deployment script.")
    if state.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256:
        raise DeploymentError("Rollback state references a different runtime helper.")


def rollback_from_state(
    state: dict[str, Any],
    state_path: Path,
    helper: Path,
    *,
    failure_injector: Callable[[str], None] | None = None,
) -> None:
    validate_rollback_state_paths(state, state_path)
    state["rollback_started"] = True

    def inject(stage: str) -> None:
        if failure_injector is not None:
            failure_injector(stage)

    try:
        reassert_and_record_gate(
            state,
            state_path,
            "rollback_start",
            status="rollback_contained_by_static_gate",
        )
        inject("after_rollback_gate_install")
        require_regular_file(Path(state["old_lock_backup"]), EXPECTED_LIVE_LOCK_SHA256)
        cache_backup = state["cache_backup_evidence"]
        if cache_identity(Path(state["cache_backup"])) != cache_backup["copy_identity"]:
            raise DeploymentError("Rollback bootstrap cache backup differs from its recorded manifest.")
        if cache_backup["source_identity"] != state["retained_cache_identity"]:
            raise DeploymentError("Rollback cache evidence references a different retained cache.")
        require_regular_file(
            Path(state["front_controller_backup"]),
            state["front_controller_backup_sha256"],
        )

        live_vendor = APP_ROOT / "vendor"
        staged_vendor = Path(state["staged_vendor"])
        live_manifest = tree_manifest(live_vendor)["sha256"]
        staged_manifest = tree_manifest(staged_vendor)["sha256"]
        if (
            live_manifest == state["candidate_vendor_sha256"]
            and staged_manifest == EXPECTED_LIVE_VENDOR_MANIFEST_SHA256
        ):
            rename_exchange(live_vendor, staged_vendor)
        elif not (
            live_manifest == EXPECTED_LIVE_VENDOR_MANIFEST_SHA256
            and staged_manifest == state["candidate_vendor_sha256"]
        ):
            raise DeploymentError("Rollback cannot identify the retained old vendor safely.")
        inject("after_rollback_vendor")

        live_cache = APP_ROOT / "bootstrap/cache"
        staged_cache = Path(state["staged_cache"])
        live_cache_identity = cache_identity(live_cache)
        staged_cache_identity = cache_identity(staged_cache)
        old_cache_identity = state["retained_cache_identity"]
        candidate_cache_identity = state["candidate_cache_identity"]
        if (
            live_cache_identity == candidate_cache_identity
            and staged_cache_identity == old_cache_identity
        ):
            rename_exchange(live_cache, staged_cache)
        elif not (
            live_cache_identity == old_cache_identity
            and staged_cache_identity == candidate_cache_identity
        ):
            raise DeploymentError("Rollback cannot identify the retained bootstrap caches safely.")
        inject("after_rollback_cache")

        live_lock = APP_ROOT / "composer.lock"
        live_lock_hash = sha256_file(live_lock)
        if live_lock_hash == CANDIDATE_LOCK_SHA256:
            atomic_copy(Path(state["old_lock_backup"]), live_lock, 0o664)
        elif live_lock_hash != EXPECTED_LIVE_LOCK_SHA256:
            raise DeploymentError("Rollback found an unrecognized live composer.lock.")
        inject("after_rollback_lock")

        require_cache_identity(live_cache, old_cache_identity)
        if tree_manifest(live_vendor)["sha256"] != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
            raise DeploymentError("Retained vendor did not return to the live path.")
        if sha256_file(live_lock) != EXPECTED_LIVE_LOCK_SHA256:
            raise DeploymentError("Retained Composer lock did not return to the live path.")
        rollback_runtime = runtime_probe(helper)
        validate_runtime_baseline(
            rollback_runtime,
            laravel=OLD_LARAVEL_VERSION,
            guzzle=OLD_GUZZLE_VERSION,
        )
        inject("after_rollback_runtime")
        time.sleep(OPCACHE_WAIT_SECONDS)
        first = fpm_probe(OLD_LARAVEL_VERSION, OLD_GUZZLE_VERSION)
        time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
        second = fpm_probe(OLD_LARAVEL_VERSION, OLD_GUZZLE_VERSION)
        inject("after_rollback_fpm_probes")
        front_controller = restore_front_controller(state, state_path)
        inject("after_rollback_gate_open")
        state["rollback_fpm_probes"] = [first, second]
        state["rollback_runtime"] = rollback_runtime
        state["front_controller_restored"] = front_controller
        state["rollback_health"] = health_snapshot()
        inject("after_rollback_health")
        state["gate_active"] = False
        state["gate_verified"] = False
        state["rollback_complete"] = True
        state["status"] = "rolled_back"
        write_state(state_path, state)
    except BaseException as exception:
        contain_rollback_failure(state, state_path, exception)
        raise


def cutover(
    receipt_path: Path,
    receipt_sha256: str,
    approval_token: str,
    helper: Path,
    *,
    failure_injector: Callable[[str], None] | None = None,
) -> Path:
    if approval_token != CUTOVER_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed cutover approval token was not supplied.")
    baseline = assert_production_baseline(helper)
    receipt, shadow = load_approved_release(receipt_path, receipt_sha256)
    if receipt.get("script_sha256") != sha256_file(Path(__file__).resolve()):
        raise DeploymentError("Release receipt was created by a different deployment script.")
    if receipt.get("approved_source_manifest") != baseline["source"]:
        raise DeploymentError("Release receipt source baseline differs from current production.")
    if receipt.get("retained_vendor_manifest") != baseline["vendor"]:
        raise DeploymentError("Release receipt rollback vendor differs from current production.")
    if receipt.get("retained_cache_identity") != baseline["cache"]:
        raise DeploymentError("Release receipt rollback cache differs from current production.")
    if receipt.get("front_controller") != baseline["front_controller"]:
        raise DeploymentError("Release receipt front controller differs from current production.")
    if scoped_processes():
        raise DeploymentError("A scoped Artisan/payout process is active.")
    before_health = health_snapshot()
    before_runtime = runtime_probe(helper)
    validate_runtime_baseline(before_runtime, laravel=OLD_LARAVEL_VERSION, guzzle=OLD_GUZZLE_VERSION)
    old_fpm_preflight = fpm_probe(OLD_LARAVEL_VERSION, OLD_GUZZLE_VERSION)

    ROLLBACK_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(ROLLBACK_ROOT, 0o700)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rollback_directory = ROLLBACK_ROOT / f"{CANDIDATE_LOCK_SHA256[:12]}-{timestamp}"
    rollback_directory.mkdir(mode=0o700)
    state_path = rollback_directory / "deployment-state.json"
    old_lock_backup = rollback_directory / "composer.lock.before"
    atomic_copy(APP_ROOT / "composer.lock", old_lock_backup, 0o600)
    cache_backup = rollback_directory / "bootstrap-cache-before"
    cache_backup_evidence = copy_cache_snapshot(APP_ROOT / "bootstrap/cache", cache_backup)
    if cache_backup_evidence["source_identity"] != baseline["cache"]:
        raise DeploymentError("Bootstrap-cache rollback copy differs from production.")
    front_controller_backup = rollback_directory / "public-index.before.php"
    atomic_copy(FRONT_CONTROLLER, front_controller_backup, 0o600)
    require_regular_file(front_controller_backup, EXPECTED_FRONT_CONTROLLER_SHA256)

    state: dict[str, Any] = {
        "artifact": "buy-dtf-atomic-dependency-cutover-v2",
        "status": "preparing",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_receipt": str(receipt_path),
        "release_receipt_sha256": receipt_sha256,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "staged_vendor": str(shadow / "vendor"),
        "staged_cache": str(shadow / "bootstrap/cache"),
        "candidate_vendor_sha256": receipt["candidate_vendor_manifest"]["sha256"],
        "candidate_cache_identity": receipt["candidate_cache_identity"],
        "retained_cache_identity": receipt["retained_cache_identity"],
        "old_lock_backup": str(old_lock_backup),
        "cache_backup": str(cache_backup),
        "cache_backup_evidence": cache_backup_evidence,
        "front_controller_backup": str(front_controller_backup),
        "front_controller_backup_sha256": sha256_file(front_controller_backup),
        "front_controller_metadata": baseline["front_controller"]["metadata"],
        "maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
        "health_before": before_health,
        "runtime_before": before_runtime,
        "old_fpm_preflight": old_fpm_preflight,
        "gate_active": False,
        "gate_verified": False,
        "gate_reassertions": [],
        "vendor_exchange_intent": False,
        "vendor_exchange_complete": False,
        "cache_exchange_intent": False,
        "cache_exchange_complete": False,
        "lock_replaced": False,
        "rollback_started": False,
        "rollback_complete": False,
    }
    write_state(state_path, state)

    def inject(stage: str) -> None:
        if failure_injector is not None:
            failure_injector(stage)

    try:
        reassert_and_record_gate(
            state,
            state_path,
            "initial_cutover",
            status="static_gate_active",
        )
        inject("after_gate_install")
        time.sleep(DRAIN_SECONDS)
        after_drain = runtime_probe(helper)
        if after_drain.get("business_activity") != before_runtime.get("business_activity"):
            raise DeploymentError("Business activity changed during the maintenance drain window.")
        if scoped_processes():
            raise DeploymentError("A scoped Artisan/payout process appeared during maintenance.")
        connected_fpm_requests = active_fpm_connections()
        if connected_fpm_requests != 0:
            raise DeploymentError(
                f"{connected_fpm_requests} FastCGI connection(s) remain after the drain window."
            )
        repeated_baseline = assert_production_baseline(
            helper,
            expected_front_controller_sha256=MAINTENANCE_GATE_SHA256,
        )
        expected_gated_baseline = dict(baseline)
        expected_gated_baseline["front_controller"] = {
            "sha256": MAINTENANCE_GATE_SHA256,
            "metadata": baseline["front_controller"]["metadata"],
        }
        if repeated_baseline != expected_gated_baseline:
            raise DeploymentError("Production CAS baseline changed during the maintenance drain.")

        live_vendor = APP_ROOT / "vendor"
        staged_vendor = shadow / "vendor"
        live_cache = APP_ROOT / "bootstrap/cache"
        staged_cache = shadow / "bootstrap/cache"
        if tree_manifest(staged_vendor) != receipt["candidate_vendor_manifest"]:
            raise DeploymentError("Staged vendor changed during the maintenance drain.")
        require_candidate_cache(staged_cache, receipt["candidate_cache_identity"])
        devices = {
            live_vendor.stat().st_dev,
            staged_vendor.stat().st_dev,
            live_cache.stat().st_dev,
            staged_cache.stat().st_dev,
        }
        if len(devices) != 1:
            raise DeploymentError("Live and staged vendor/cache paths are not on one filesystem.")
        state["vendor_exchange_intent"] = True
        write_state(state_path, state)
        rename_exchange(live_vendor, staged_vendor)
        state["vendor_exchange_complete"] = True
        state["status"] = "vendor_exchanged"
        write_state(state_path, state)
        inject("after_vendor_exchange")

        state["cache_exchange_intent"] = True
        write_state(state_path, state)
        rename_exchange(live_cache, staged_cache)
        state["cache_exchange_complete"] = True
        state["status"] = "cache_exchanged"
        write_state(state_path, state)
        inject("after_cache_exchange")

        if tree_manifest(live_vendor) != receipt["candidate_vendor_manifest"]:
            raise DeploymentError("Live candidate vendor differs from its approved manifest.")
        if tree_manifest(staged_vendor)["sha256"] != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
            raise DeploymentError("Retained old vendor differs after atomic exchange.")
        require_cache_identity(live_cache, receipt["candidate_cache_identity"])
        require_cache_identity(staged_cache, receipt["retained_cache_identity"])

        atomic_copy(shadow / "composer.lock", APP_ROOT / "composer.lock", 0o664)
        state["lock_replaced"] = True
        state["status"] = "lock_replaced"
        write_state(state_path, state)
        inject("after_lock_replacement")

        # The candidate-compatible cache is live before this first candidate
        # Laravel boot. No candidate command is needed to construct the cache.
        live_runtime = runtime_probe(helper)
        validate_runtime_baseline(live_runtime, laravel=NEW_LARAVEL_VERSION, guzzle=NEW_GUZZLE_VERSION)
        inject("after_candidate_runtime")
        if sha256_file(APP_ROOT / "composer.lock") != CANDIDATE_LOCK_SHA256:
            raise DeploymentError("Live composer.lock differs from the approved candidate.")

        time.sleep(OPCACHE_WAIT_SECONDS)
        first_probe = fpm_probe(NEW_LARAVEL_VERSION, NEW_GUZZLE_VERSION)
        time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
        second_probe = fpm_probe(NEW_LARAVEL_VERSION, NEW_GUZZLE_VERSION)
        state["candidate_fpm_probes"] = [first_probe, second_probe]
        state["candidate_runtime"] = live_runtime
        write_state(state_path, state)
        inject("after_candidate_fpm_probes")

        state["front_controller_restored"] = restore_front_controller(state, state_path)
        inject("after_candidate_gate_open")
        state["health_after"] = health_snapshot()
        state["gate_active"] = False
        state["gate_verified"] = False
        state["status"] = "monitoring"
        write_state(state_path, state)
        inject("after_candidate_health")

        monitor_deadline = time.monotonic() + MONITOR_SECONDS
        monitor_samples: list[dict[str, Any]] = []
        while time.monotonic() < monitor_deadline:
            sample = {
                "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "health": health_snapshot(),
                "runtime": runtime_probe(helper),
            }
            validate_runtime_baseline(sample["runtime"], laravel=NEW_LARAVEL_VERSION, guzzle=NEW_GUZZLE_VERSION)
            monitor_samples.append(sample)
            state["monitor_samples"] = monitor_samples
            write_state(state_path, state)
            remaining = monitor_deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(MONITOR_INTERVAL_SECONDS, remaining))

        state["status"] = "success"
        state["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state["rollback_retained_vendor_path"] = str(staged_vendor)
        state["rollback_retained_cache_path"] = str(staged_cache)
        write_state(state_path, state)
        print(f"Dependency cutover complete. State/receipt: {state_path}")
        return state_path
    except BaseException as exception:
        contain_cutover_failure(state, state_path, exception)
        rollback_from_state(
            state,
            state_path,
            helper,
            failure_injector=failure_injector,
        )
        raise


def recover(state_path: Path, approval_token: str, helper: Path) -> None:
    if approval_token != RECOVERY_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed recovery approval token was not supplied.")
    state_path = require_regular_file(state_path)
    if not is_relative_to(state_path, ROLLBACK_ROOT.resolve(strict=True)):
        raise DeploymentError("Recovery state is outside the fixed rollback root.")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise DeploymentError("Recovery state is invalid JSON.") from exception
    if state.get("artifact") != "buy-dtf-atomic-dependency-cutover-v2":
        raise DeploymentError("Recovery state has an unexpected artifact identity.")
    if state.get("script_sha256") != sha256_file(Path(__file__).resolve()):
        raise DeploymentError("Recovery state was created by a different deployment script.")
    if state.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256:
        raise DeploymentError("Recovery state references a different runtime helper.")
    if state.get("front_controller_metadata") != {
        "kind": "file",
        "mode": 0o644,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
    }:
        raise DeploymentError("Recovery state has invalid front-controller metadata.")
    reassert_and_record_gate(
        state,
        state_path,
        "explicit_recovery_entry",
        status="explicit_recovery_contained_by_static_gate",
    )
    rollback_from_state(state, state_path, helper)


def rehearse(parent: Path) -> dict[str, Any]:
    parent = require_real_directory(parent)
    rehearsal_root = Path(tempfile.mkdtemp(prefix="buy-dtf-dependency-rehearsal-", dir=parent))
    results: dict[str, Any] = {
        "artifact": "buy-dtf-atomic-exchange-rehearsal-v2",
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
        "filesystem_device": rehearsal_root.stat().st_dev,
        "cutover_transitions": list(CUTOVER_TRANSITIONS),
        "rollback_transitions": list(ROLLBACK_TRANSITIONS),
        "scenarios": {},
    }

    try:
        def fixture(name: str, *, unbootable: bool = False) -> dict[str, Any]:
            root = rehearsal_root / name
            application = root / "application"
            release = root / "release"
            rollback = root / "rollback"
            live_vendor = application / "vendor"
            staged_vendor = release / "vendor"
            live_cache = application / "bootstrap/cache"
            staged_cache = release / "bootstrap/cache"
            public = application / "public"
            for directory in (
                live_vendor,
                staged_vendor,
                live_cache,
                staged_cache,
                public,
                rollback,
            ):
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)

            (live_vendor / "identity.txt").write_text("retained-old-vendor\n", encoding="utf-8")
            (staged_vendor / "identity.txt").write_text("approved-new-vendor\n", encoding="utf-8")
            (live_cache / "packages.php").write_text(
                "<?php return ['Laravel\\\\Pail\\\\PailServiceProvider'];\n",
                encoding="utf-8",
            )
            (live_cache / "services.php").write_text(
                "<?php return ['providers' => ['Laravel\\\\Pail\\\\PailServiceProvider']];\n",
                encoding="utf-8",
            )
            (staged_cache / "packages.php").write_text(
                "<?php return ['production-provider'];\n",
                encoding="utf-8",
            )
            (staged_cache / "services.php").write_text(
                "<?php return ['providers' => ['production-provider']];\n",
                encoding="utf-8",
            )

            live_lock = application / "composer.lock"
            candidate_lock = release / "composer.lock"
            old_lock_backup = rollback / "composer.lock.before"
            live_lock.write_text("old-lock\n", encoding="utf-8")
            candidate_lock.write_text("candidate-lock\n", encoding="utf-8")
            atomic_copy(live_lock, old_lock_backup, 0o600)

            front_controller = public / "index.php"
            front_controller.write_text("<?php echo 'application';\n", encoding="utf-8")
            os.chmod(front_controller, 0o644)
            front_controller_backup = rollback / "public-index.before.php"
            atomic_copy(front_controller, front_controller_backup, 0o600)

            return {
                "root": root,
                "live_vendor": live_vendor,
                "staged_vendor": staged_vendor,
                "old_vendor_sha256": tree_manifest(live_vendor)["sha256"],
                "candidate_vendor_sha256": tree_manifest(staged_vendor)["sha256"],
                "live_cache": live_cache,
                "staged_cache": staged_cache,
                "old_cache_identity": cache_identity(live_cache),
                "candidate_cache_identity": cache_identity(staged_cache),
                "live_lock": live_lock,
                "candidate_lock": candidate_lock,
                "old_lock_backup": old_lock_backup,
                "old_lock_sha256": sha256_file(live_lock),
                "candidate_lock_sha256": sha256_file(candidate_lock),
                "front_controller": front_controller,
                "front_controller_metadata": path_metadata(front_controller),
                "front_controller_backup": front_controller_backup,
                "front_controller_sha256": sha256_file(front_controller),
                "events": [],
                "candidate_boot_attempts": 0,
                "unbootable": unbootable,
            }

        def checkpoint(
            item: dict[str, Any],
            stage: str,
            failure_at: str | None,
            *,
            interruption: bool,
        ) -> None:
            item["events"].append(stage)
            if failure_at != stage:
                return
            if interruption:
                raise InterruptedError(f"injected-interruption:{stage}")
            raise DeploymentError(f"injected-failure:{stage}")

        def install_modeled_gate(item: dict[str, Any], event: str) -> None:
            atomic_install_bytes(
                item["front_controller"],
                MAINTENANCE_GATE_BYTES,
                item["front_controller_metadata"],
            )
            if sha256_file(item["front_controller"]) != MAINTENANCE_GATE_SHA256:
                raise DeploymentError("Rehearsal static gate installation failed.")
            item["events"].append(event)

        def restore_modeled_front_controller(item: dict[str, Any]) -> None:
            atomic_install_bytes(
                item["front_controller"],
                item["front_controller_backup"].read_bytes(),
                item["front_controller_metadata"],
            )
            if sha256_file(item["front_controller"]) != item["front_controller_sha256"]:
                raise DeploymentError("Rehearsal front-controller restoration failed.")

        def restore_vendor_pair(item: dict[str, Any]) -> None:
            live_hash = tree_manifest(item["live_vendor"])["sha256"]
            staged_hash = tree_manifest(item["staged_vendor"])["sha256"]
            if (
                live_hash == item["candidate_vendor_sha256"]
                and staged_hash == item["old_vendor_sha256"]
            ):
                rename_exchange(item["live_vendor"], item["staged_vendor"])
            elif not (
                live_hash == item["old_vendor_sha256"]
                and staged_hash == item["candidate_vendor_sha256"]
            ):
                raise DeploymentError("Rehearsal recovery found unknown vendor identities.")

        def restore_cache_pair(item: dict[str, Any]) -> None:
            live_identity = cache_identity(item["live_cache"])
            staged_identity = cache_identity(item["staged_cache"])
            if (
                live_identity == item["candidate_cache_identity"]
                and staged_identity == item["old_cache_identity"]
            ):
                rename_exchange(item["live_cache"], item["staged_cache"])
            elif not (
                live_identity == item["old_cache_identity"]
                and staged_identity == item["candidate_cache_identity"]
            ):
                raise DeploymentError("Rehearsal recovery found unknown cache identities.")

        def restore_lock(item: dict[str, Any]) -> None:
            live_hash = sha256_file(item["live_lock"])
            if live_hash == item["candidate_lock_sha256"]:
                atomic_copy(item["old_lock_backup"], item["live_lock"])
            elif live_hash != item["old_lock_sha256"]:
                raise DeploymentError("Rehearsal recovery found an unknown lock identity.")

        def verify_restored(item: dict[str, Any], *, require_front: bool = True) -> None:
            if tree_manifest(item["live_vendor"])["sha256"] != item["old_vendor_sha256"]:
                raise DeploymentError("Rehearsal did not restore the retained vendor.")
            require_cache_identity(item["live_cache"], item["old_cache_identity"])
            if sha256_file(item["live_lock"]) != item["old_lock_sha256"]:
                raise DeploymentError("Rehearsal did not restore the retained lock.")
            if require_front and sha256_file(item["front_controller"]) != item["front_controller_sha256"]:
                raise DeploymentError("Rehearsal did not restore the front controller.")

        def candidate_boot(item: dict[str, Any]) -> None:
            item["candidate_boot_attempts"] += 1
            if item["unbootable"]:
                raise DeploymentError("modeled candidate Laravel runtime is completely unbootable")
            if tree_manifest(item["live_vendor"])["sha256"] != item["candidate_vendor_sha256"]:
                raise DeploymentError("Modeled candidate boot found the wrong vendor.")
            require_cache_identity(item["live_cache"], item["candidate_cache_identity"])
            for name in REQUIRED_CANDIDATE_CACHE_FILES:
                if b"Pail" in (item["live_cache"] / name).read_bytes():
                    raise DeploymentError("Modeled candidate cache retained a dev provider.")
            if sha256_file(item["live_lock"]) != item["candidate_lock_sha256"]:
                raise DeploymentError("Modeled candidate boot found the wrong lock.")

        def recover_fixture(
            item: dict[str, Any],
            *,
            interrupt_at: str | None = None,
        ) -> None:
            # This deliberately performs no candidate boot. The static gate is
            # always reinstalled before inspecting or mutating dependency state.
            install_modeled_gate(item, "rollback_gate_reasserted")
            checkpoint(
                item,
                "after_rollback_gate_install",
                interrupt_at,
                interruption=True,
            )
            restore_vendor_pair(item)
            checkpoint(item, "after_rollback_vendor", interrupt_at, interruption=True)
            restore_cache_pair(item)
            checkpoint(item, "after_rollback_cache", interrupt_at, interruption=True)
            restore_lock(item)
            checkpoint(item, "after_rollback_lock", interrupt_at, interruption=True)
            verify_restored(item, require_front=False)
            checkpoint(item, "after_rollback_runtime", interrupt_at, interruption=True)
            checkpoint(item, "after_rollback_fpm_probes", interrupt_at, interruption=True)
            restore_modeled_front_controller(item)
            checkpoint(
                item,
                "after_rollback_gate_open",
                interrupt_at,
                interruption=True,
            )
            verify_restored(item)
            checkpoint(item, "after_rollback_health", interrupt_at, interruption=True)

        def execute_cutover(
            item: dict[str, Any],
            *,
            failure_at: str | None = None,
            interruption: bool = False,
        ) -> BaseException | None:
            try:
                install_modeled_gate(item, "gate_installed")
                checkpoint(item, "after_gate_install", failure_at, interruption=interruption)
                rename_exchange(item["live_vendor"], item["staged_vendor"])
                checkpoint(item, "after_vendor_exchange", failure_at, interruption=interruption)
                rename_exchange(item["live_cache"], item["staged_cache"])
                checkpoint(item, "after_cache_exchange", failure_at, interruption=interruption)
                atomic_copy(item["candidate_lock"], item["live_lock"])
                checkpoint(item, "after_lock_replacement", failure_at, interruption=interruption)
                candidate_boot(item)
                checkpoint(item, "after_candidate_runtime", failure_at, interruption=interruption)
                checkpoint(
                    item,
                    "after_candidate_fpm_probes",
                    failure_at,
                    interruption=interruption,
                )
                restore_modeled_front_controller(item)
                checkpoint(
                    item,
                    "after_candidate_gate_open",
                    failure_at,
                    interruption=interruption,
                )
                checkpoint(item, "after_candidate_health", failure_at, interruption=interruption)
                return None
            except BaseException as exception:
                recover_fixture(item)
                return exception

        def prepare_unbootable_candidate_state(item: dict[str, Any]) -> None:
            install_modeled_gate(item, "gate_installed")
            rename_exchange(item["live_vendor"], item["staged_vendor"])
            rename_exchange(item["live_cache"], item["staged_cache"])
            atomic_copy(item["candidate_lock"], item["live_lock"])

        item = fixture("stale-dev-provider-success")
        if b"Pail" not in (item["live_cache"] / "packages.php").read_bytes():
            raise DeploymentError("Stale-provider rehearsal fixture is invalid.")
        if execute_cutover(item) is not None:
            raise DeploymentError("Stale dev-provider cache blocked the candidate-compatible cache.")
        if item["candidate_boot_attempts"] != 1:
            raise DeploymentError("Successful rehearsal did not boot the candidate exactly once.")
        results["scenarios"]["stale_dev_provider_cache_replaced_before_boot"] = "pass"

        item = fixture("between-vendor-cache")
        failure = execute_cutover(item, failure_at="after_vendor_exchange")
        if not isinstance(failure, DeploymentError):
            raise DeploymentError("Vendor/cache transition failure was not injected.")
        verify_restored(item)
        results["scenarios"]["failure_between_vendor_and_cache_exchange"] = "pass"

        item = fixture("between-cache-lock")
        failure = execute_cutover(item, failure_at="after_cache_exchange")
        if not isinstance(failure, DeploymentError):
            raise DeploymentError("Cache/lock transition failure was not injected.")
        verify_restored(item)
        results["scenarios"]["failure_between_cache_and_lock_replacement"] = "pass"

        item = fixture("unbootable-candidate", unbootable=True)
        failure = execute_cutover(item)
        if not isinstance(failure, DeploymentError) or item["candidate_boot_attempts"] != 1:
            raise DeploymentError("Completely unbootable candidate scenario was not exercised.")
        verify_restored(item)
        results["scenarios"]["completely_unbootable_candidate_auto_rollback"] = "pass"

        for transition in CUTOVER_TRANSITIONS:
            item = fixture(f"cutover-interruption-{transition}")
            failure = execute_cutover(
                item,
                failure_at=transition,
                interruption=True,
            )
            if not isinstance(failure, InterruptedError):
                raise DeploymentError(f"Cutover interruption was not injected at {transition}.")
            verify_restored(item)
            results["scenarios"][f"interruption_{transition}"] = "pass"

        item = fixture("bootless-explicit-recovery", unbootable=True)
        prepare_unbootable_candidate_state(item)
        recover_fixture(item)
        if item["candidate_boot_attempts"] != 0:
            raise DeploymentError("Explicit recovery invoked the unbootable candidate runtime.")
        verify_restored(item)
        results["scenarios"]["automatic_recovery_while_laravel_cannot_boot"] = "pass"

        for transition in ROLLBACK_TRANSITIONS:
            item = fixture(f"rollback-interruption-{transition}", unbootable=True)
            prepare_unbootable_candidate_state(item)
            try:
                recover_fixture(item, interrupt_at=transition)
            except InterruptedError:
                pass
            else:
                raise DeploymentError(f"Rollback interruption was not injected at {transition}.")
            recover_fixture(item)
            if item["candidate_boot_attempts"] != 0:
                raise DeploymentError("Interrupted recovery invoked the candidate runtime.")
            verify_restored(item)
            results["scenarios"][f"recovery_interruption_{transition}"] = "pass"

        item = fixture("stale-gate-state")
        item["events"].append("persisted_gate_active_but_public")
        recover_fixture(item)
        if "rollback_gate_reasserted" not in item["events"]:
            raise DeploymentError("Recovery trusted stale persisted gate state.")
        verify_restored(item)
        results["scenarios"]["stale_gate_state_is_reasserted"] = "pass"

        item = fixture("rollback-health-failure", unbootable=True)
        prepare_unbootable_candidate_state(item)
        recover_fixture(item)
        install_modeled_gate(item, "rollback_health_failure_gate_reasserted")
        if sha256_file(item["front_controller"]) != MAINTENANCE_GATE_SHA256:
            raise DeploymentError("Rollback health failure did not leave the static gate active.")
        results["scenarios"]["rollback_health_failure_reinstalls_static_gate"] = "pass"

        results["scenario_count"] = len(results["scenarios"])
        results["status"] = "pass"
        return results
    finally:
        if not is_relative_to(rehearsal_root, parent) or not rehearsal_root.name.startswith(
            "buy-dtf-dependency-rehearsal-"
        ):
            raise DeploymentError("Refusing to remove an unrecognized rehearsal directory.")
        shutil.rmtree(rehearsal_root)


def describe() -> None:
    print(
        json.dumps(
            {
                "application_root": str(APP_ROOT),
                "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
                "old_vendor_manifest_sha256": EXPECTED_LIVE_VENDOR_MANIFEST_SHA256,
                "old_lock_sha256": EXPECTED_LIVE_LOCK_SHA256,
                "candidate_lock_sha256": CANDIDATE_LOCK_SHA256,
                "atomic_vendor_operation": "renameat2(RENAME_EXCHANGE)",
                "atomic_cache_operation": "renameat2(RENAME_EXCHANGE)",
                "static_maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
                "candidate_install_no_dev": True,
                "reported_app_environment": EXPECTED_APP_ENVIRONMENT,
                "reported_app_debug": EXPECTED_APP_DEBUG,
                "git_operations": False,
                "migration_operations": False,
                "dependency_update_operations": False,
                "service_restart_operations": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--describe", action="store_true")
    action.add_argument("--stage", action="store_true")
    action.add_argument("--cutover", action="store_true")
    action.add_argument("--recover", action="store_true")
    action.add_argument("--rehearse", action="store_true")
    parser.add_argument("--candidate-lock", type=Path)
    parser.add_argument("--release-receipt", type=Path)
    parser.add_argument("--release-receipt-sha256")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--rehearsal-parent", type=Path)
    parser.add_argument("--approval-token")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    helper = Path(__file__).resolve().with_name("dependency_runtime_probe.php")
    try:
        if arguments.describe:
            describe()
        elif arguments.rehearse:
            if arguments.rehearsal_parent is None:
                raise DeploymentError("--rehearse requires --rehearsal-parent.")
            print(json.dumps(rehearse(arguments.rehearsal_parent), indent=2, sort_keys=True))
        elif arguments.stage:
            if arguments.candidate_lock is None or arguments.approval_token is None:
                raise DeploymentError("--stage requires --candidate-lock and --approval-token.")
            require_regular_file(helper, RUNTIME_HELPER_SHA256)
            with deployment_lock():
                stage_release(arguments.candidate_lock, arguments.approval_token, helper)
        elif arguments.cutover:
            if (
                arguments.release_receipt is None
                or arguments.release_receipt_sha256 is None
                or arguments.approval_token is None
            ):
                raise DeploymentError(
                    "--cutover requires --release-receipt, --release-receipt-sha256, and --approval-token."
                )
            require_regular_file(helper, RUNTIME_HELPER_SHA256)
            with deployment_lock():
                cutover(
                    arguments.release_receipt,
                    arguments.release_receipt_sha256,
                    arguments.approval_token,
                    helper,
                )
        else:
            if arguments.state is None or arguments.approval_token is None:
                raise DeploymentError("--recover requires --state and --approval-token.")
            require_regular_file(helper, RUNTIME_HELPER_SHA256)
            with deployment_lock():
                recover(arguments.state, arguments.approval_token, helper)
    except (DeploymentError, BlockingIOError, subprocess.TimeoutExpired) as exception:
        print(f"STOP: {exception}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    def interrupted(signum: int, _frame: object) -> None:
        raise DeploymentError(f"Interrupted by signal {signum}; automatic rollback will run if armed.")

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
