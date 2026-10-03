#!/usr/bin/env python3
"""Stage, atomically exchange, verify, and roll back Laravel 12.69.1.

Production modes are intentionally fixed to /var/www/buy-dtf and to reviewed
artifact hashes. There are no Git, migration, dependency-update, live-source
mutation, configuration-copy, or service-restart operations in this program.
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
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


DEPLOYMENT_MODULE_DIRECTORY = Path(__file__).resolve().parent
if str(DEPLOYMENT_MODULE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(DEPLOYMENT_MODULE_DIRECTORY))

import laravel_dependency_database_envelope as database_envelope
import laravel_dependency_gate as dependency_gate
import laravel_log_delta as laravel_log_delta


APP_ROOT = Path("/var/www/buy-dtf")
PRIVATE_OPERATIONS_ROOT = APP_ROOT / "storage/app/private/operations"
RELEASE_ROOT = PRIVATE_OPERATIONS_ROOT / "laravel-remember-cookie-v3-releases"
ROLLBACK_ROOT = PRIVATE_OPERATIONS_ROOT / "laravel-remember-cookie-v3-rollbacks"
DEPLOYMENT_LOCK = APP_ROOT / "storage/framework/dependency-deployment.lock"
FPM_SOCKET = Path("/run/php/php8.2-fpm.sock")
LARAVEL_MAINTENANCE_FILE = APP_ROOT / "storage/framework/down"
FRONT_CONTROLLER = APP_ROOT / "public/index.php"
LARAVEL_LOG_PATH = APP_ROOT / "storage/logs/laravel.log"
MAINTENANCE_PROBE_URL = "https://buy-dtf.com/"

EXPECTED_APP_UID = 1000
EXPECTED_APP_GID = 1000
EXPECTED_WEB_GID = 33
EXPECTED_LIVE_COMPOSER_JSON_SHA256 = "7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872"
EXPECTED_LIVE_LOCK_SHA256 = "22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9"
CANDIDATE_LOCK_SHA256 = "77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d"
EXPECTED_DATABASE_CONFIG_SHA256 = "d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9"
EXPECTED_SOURCE_MANIFEST_SHA256 = "3909bdc2303b5c578135859c847f311cd84b827e62ac4e5dbce3d2297f6da71f"
EXPECTED_LIVE_VENDOR_MANIFEST_SHA256 = "7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed"
EXPECTED_FRONT_CONTROLLER_SHA256 = "eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9"
EXPECTED_APP_ENVIRONMENT = "local"
EXPECTED_APP_DEBUG = False
EXPECTED_PHP_VERSION = "8.2.30"
RUNTIME_HELPER_SHA256 = "7cd804545f9e09d096d348924021047e0a7b1b6ecf3a1b783fd015aef24c48d2"
DATABASE_ENVELOPE_VALIDATOR_SHA256 = "e3aa9109fcc6a6c8725f07665f27fc28a242447861b5b6c2a8d614a5a0a805b3"
GATE_HELPER_SHA256 = "1269a277e931dee346293bed4ea0f6d029cf9ded7810127a0ef547289ce51f80"
LOG_PARSER_SHA256 = "b91ac879b9559e229e18b7613fa4c570cee54016fbadc2e306925c0a71bcf179"
HANDOFF_FILENAME = "HANDOFF.md"
HANDOFF_SHA256 = "305127ee8dc6c578ea8a8a1901a455b2e18378c481c8c726b3b120917e62a984"
ARTIFACT_REVIEW_STATUS = "review-only; not staged or deployed"

EXPECTED_SOURCE_MANIFEST = {
    "files": 326,
    "sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
}
EXPECTED_LIVE_VENDOR_MANIFEST = {
    "bytes": 26453056,
    "directories": 925,
    "files": 6460,
    "sha256": EXPECTED_LIVE_VENDOR_MANIFEST_SHA256,
}

EXPECTED_LIVE_CACHE_IDENTITY = {
    "entries": {
        "packages.php": {
            "bytes": 415,
            "gid": EXPECTED_WEB_GID,
            "kind": "file",
            "mode": 0o664,
            "sha256": "21da8f9ed19687e708cc7bc5cc59394c6fcdf9b9deadf617ae70526f815a1db0",
            "uid": EXPECTED_APP_UID,
        },
        "services.php": {
            "bytes": 21353,
            "gid": EXPECTED_WEB_GID,
            "kind": "file",
            "mode": 0o664,
            "sha256": "1f7623b2b4ffd2c4099fb34ad86fc96c1479e27bf81b1b0ba328c988cc4ffcb5",
            "uid": EXPECTED_APP_UID,
        },
    },
    "manifest": {
        "bytes": 21768,
        "directories": 0,
        "files": 2,
        "sha256": "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9",
    },
    "root_metadata": {
        "gid": EXPECTED_WEB_GID,
        "kind": "directory",
        "mode": 0o2775,
        "uid": EXPECTED_APP_UID,
    },
}
EXPECTED_CANDIDATE_VENDOR_MANIFEST = {
    "bytes": 26481661,
    "directories": 925,
    "files": 6460,
    "sha256": "7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8",
}
EXPECTED_CANDIDATE_VENDOR_FILE_COUNT = 6460
EXPECTED_CANDIDATE_VENDOR_DIRECTORY_COUNT = 925
EXPECTED_CANDIDATE_VENDOR_ORDINARY_FILE_COUNT = 6450
EXPECTED_CANDIDATE_CACHE_IDENTITY = EXPECTED_LIVE_CACHE_IDENTITY

CANDIDATE_VENDOR_EXECUTABLE_PATHS = (
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
)
CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256 = (
    "551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154"
)
EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256 = (
    "db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d"
)
EXPECTED_APPLICATION_AUTOLOAD_ENTRIES = 126
EXPECTED_APPLICATION_AUTOLOAD_SHA256 = (
    "342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91"
)
EXPECTED_ROUTE_COUNT = 178

OLD_PACKAGE_VERSIONS = {
    "guzzlehttp/guzzle": "7.15.2",
    "laravel/framework": "12.69.0",
    "league/commonmark": "2.10.2",
    "league/flysystem": "3.35.3",
    "league/flysystem-local": "3.35.3",
}
NEW_PACKAGE_VERSIONS = {
    "guzzlehttp/guzzle": "7.15.2",
    "laravel/framework": "12.69.1",
    "league/commonmark": "2.10.2",
    "league/flysystem": "3.35.3",
    "league/flysystem-local": "3.35.3",
}
STAGE_APPROVAL_TOKEN = f"STAGE-BUYDTF-LARAVEL-REMEMBER-V3-{CANDIDATE_LOCK_SHA256[:16]}"
CUTOVER_APPROVAL_TOKEN = f"DEPLOY-BUYDTF-LARAVEL-REMEMBER-V3-{CANDIDATE_LOCK_SHA256[:16]}"
RECOVERY_APPROVAL_TOKEN = f"RECOVER-BUYDTF-LARAVEL-REMEMBER-V3-{EXPECTED_LIVE_LOCK_SHA256[:16]}"
FINALIZE_MONITOR_APPROVAL_TOKEN = (
    f"FINALIZE-BUYDTF-LARAVEL-REMEMBER-V3-{CANDIDATE_LOCK_SHA256[:16]}"
)

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
MAINTENANCE_GATE_HEADER = (
    f"{dependency_gate.MAINTENANCE_GATE_HEADER_NAME}: "
    f"{dependency_gate.MAINTENANCE_GATE_HEADER_VALUE}"
)
MAINTENANCE_GATE_SENTINEL = dependency_gate.MAINTENANCE_GATE_SENTINEL
MAINTENANCE_GATE_BYTES = dependency_gate.MAINTENANCE_GATE_BYTES
MAINTENANCE_GATE_SHA256 = dependency_gate.EXPECTED_GATE_SHA256


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


def ensure_private_operations_root(root: Path, *, create: bool) -> Path:
    app_root = require_real_directory(APP_ROOT)
    try:
        relative_operations = PRIVATE_OPERATIONS_ROOT.relative_to(APP_ROOT)
    except ValueError as exception:
        raise DeploymentError("Private operations path escapes the application root.") from exception
    current = app_root
    for part in relative_operations.parts:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            raise DeploymentError(f"Private operations path is missing, invalid, or symbolic: {current}")
    operations_root = current.resolve(strict=True)
    if not is_relative_to(operations_root, app_root):
        raise DeploymentError("Private operations path escapes the application root.")
    if root.parent != PRIVATE_OPERATIONS_ROOT:
        raise DeploymentError("Dependency operations root is outside the fixed private parent.")
    if root.is_symlink():
        raise DeploymentError("Dependency operations root must not be symbolic.")
    if not root.exists():
        if not create:
            raise DeploymentError("Dependency operations root does not exist.")
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
        os.chmod(root, 0o700)
        fsync_directory(operations_root)
    resolved = require_real_directory(root, within=operations_root)
    if resolved.parent != operations_root:
        raise DeploymentError("Dependency operations root resolves outside its fixed parent.")
    metadata = resolved.lstat()
    if (
        stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != EXPECTED_APP_UID
        or metadata.st_gid != EXPECTED_WEB_GID
    ):
        raise DeploymentError("Dependency operations root ownership or mode differs from review.")
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


def tree_metadata_identity(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    records: list[bytes] = []
    root_entry = path_metadata(root)
    records.append(
        (
            f"{root_entry['kind']}\0.\0{root_entry['mode']:o}\0"
            f"{root_entry['uid']}\0{root_entry['gid']}\n"
        ).encode()
    )
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        entry = path_metadata(path)
        records.append(
            (
                f"{entry['kind']}\0{relative}\0{entry['mode']:o}\0"
                f"{entry['uid']}\0{entry['gid']}\n"
            ).encode()
        )
    records.sort()
    return {
        "manifest": tree_manifest(root),
        "metadata_sha256": sha256_bytes(b"".join(records)),
        "root_metadata": root_entry,
    }


def executable_allowlist_sha256() -> str:
    canonical = "".join(f"{path}\n" for path in CANDIDATE_VENDOR_EXECUTABLE_PATHS)
    return sha256_bytes(canonical.encode("utf-8"))


def hash_regular_file_nofollow(path: Path, expected: os.stat_result) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exception:
        raise DeploymentError(f"Candidate vendor file could not be opened safely: {path}") from exception
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_gid",
            "st_size",
            "st_mtime_ns",
        )
        if any(getattr(before, field) != getattr(expected, field) for field in stable_fields):
            raise DeploymentError(f"Candidate vendor file changed before hashing: {path}")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if any(getattr(after, field) != getattr(before, field) for field in stable_fields):
            raise DeploymentError(f"Candidate vendor file changed while hashing: {path}")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def candidate_vendor_identity(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    if executable_allowlist_sha256() != CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256:
        raise DeploymentError("Candidate vendor executable allowlist is not canonical.")

    expected_root = {
        "kind": "directory",
        "mode": 0o775,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
    }
    root_before = root.lstat()
    if (
        not stat.S_ISDIR(root_before.st_mode)
        or stat.S_IMODE(root_before.st_mode) != expected_root["mode"]
        or root_before.st_uid != EXPECTED_APP_UID
        or root_before.st_gid != EXPECTED_APP_GID
    ):
        raise DeploymentError("Candidate vendor root metadata differs from review.")

    metadata_records = [
        (
            f"d\0.\0{expected_root['mode']:o}\0"
            f"{expected_root['uid']}\0{expected_root['gid']}\n"
        ).encode()
    ]
    manifest_records: list[bytes] = []
    executable_paths = set(CANDIDATE_VENDOR_EXECUTABLE_PATHS)
    found_executable_paths: set[str] = set()
    file_count = 0
    directory_count = 0
    ordinary_file_count = 0
    total_bytes = 0

    for current_root, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)
        for name in directory_names:
            path = current / name
            relative = path.relative_to(root).as_posix()
            metadata = path.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o775
                or metadata.st_uid != EXPECTED_APP_UID
                or metadata.st_gid != EXPECTED_APP_GID
            ):
                raise DeploymentError(f"Candidate vendor directory metadata differs: {path}")
            metadata_records.append(
                f"d\0{relative}\0{0o775:o}\0{metadata.st_uid}\0{metadata.st_gid}\n".encode()
            )
            manifest_records.append(f"d\0{relative}\0{0o775:o}\n".encode())
            directory_count += 1
        for name in file_names:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if relative.startswith("bin/") and Path(relative).name.lower().endswith(".bat"):
                raise DeploymentError(f"Candidate vendor contains a Windows proxy: {relative}")
            is_executable = relative in executable_paths
            expected_mode = 0o775 if is_executable else 0o664
            metadata = path.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != expected_mode
                or metadata.st_uid != EXPECTED_APP_UID
                or metadata.st_gid != EXPECTED_APP_GID
            ):
                raise DeploymentError(f"Candidate vendor file metadata differs: {path}")
            digest = hash_regular_file_nofollow(path, metadata)
            metadata_records.append(
                f"f\0{relative}\0{expected_mode:o}\0{metadata.st_uid}\0{metadata.st_gid}\n".encode()
            )
            manifest_records.append(
                f"f\0{relative}\0{expected_mode:o}\0{metadata.st_size}\0{digest}\n".encode()
            )
            file_count += 1
            total_bytes += metadata.st_size
            if is_executable:
                found_executable_paths.add(relative)
            else:
                ordinary_file_count += 1

    if found_executable_paths != executable_paths:
        missing = sorted(executable_paths - found_executable_paths)
        raise DeploymentError(f"Candidate vendor executable allowlist is incomplete: {missing}")
    if (file_count, directory_count, ordinary_file_count) != (
        EXPECTED_CANDIDATE_VENDOR_FILE_COUNT,
        EXPECTED_CANDIDATE_VENDOR_DIRECTORY_COUNT,
        EXPECTED_CANDIDATE_VENDOR_ORDINARY_FILE_COUNT,
    ):
        raise DeploymentError(
            "Candidate vendor structural counts differ from 6,460 files, "
            "925 directories, and 6,450 ordinary files."
        )

    root_after = root.lstat()
    if (
        root_after.st_dev,
        root_after.st_ino,
        root_after.st_mode,
        root_after.st_uid,
        root_after.st_gid,
    ) != (
        root_before.st_dev,
        root_before.st_ino,
        root_before.st_mode,
        root_before.st_uid,
        root_before.st_gid,
    ):
        raise DeploymentError("Candidate vendor root changed while hashing.")
    metadata_records.sort()
    manifest_records.sort()
    manifest = {
        "sha256": sha256_bytes(b"".join(manifest_records)),
        "files": file_count,
        "directories": directory_count,
        "bytes": total_bytes,
    }
    return {
        "manifest": manifest,
        "metadata_sha256": sha256_bytes(b"".join(metadata_records)),
        "root_metadata": expected_root,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
        "directory_mode": 0o775,
        "ordinary_file_mode": 0o664,
        "executable_file_mode": 0o775,
        "ordinary_files": ordinary_file_count,
        "executable_files": len(found_executable_paths),
        "executable_allowlist_sha256": CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256,
        "total_bytes": total_bytes,
    }


def normalize_candidate_vendor(root: Path) -> dict[str, Any]:
    root = require_real_directory(root)
    directories: list[Path] = []
    files: list[tuple[Path, str]] = []
    for current_root, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        directory_names.sort()
        file_names.sort()
        current = Path(current_root)
        for name in directory_names:
            path = current / name
            if path.is_symlink() or not path.is_dir():
                raise DeploymentError(f"Candidate vendor contains an invalid directory: {path}")
            directories.append(path)
        for name in file_names:
            path = current / name
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise DeploymentError(f"Candidate vendor contains an invalid file: {path}")
            relative = path.relative_to(root).as_posix()
            if relative.startswith("bin/") and Path(relative).name.lower().endswith(".bat"):
                raise DeploymentError(f"Candidate vendor contains a Windows proxy: {relative}")
            files.append((path, relative))

    executable_paths = set(CANDIDATE_VENDOR_EXECUTABLE_PATHS)
    actual_paths = {relative for _path, relative in files}
    missing = sorted(executable_paths - actual_paths)
    if missing:
        raise DeploymentError(f"Candidate vendor executable allowlist is incomplete: {missing}")
    if (len(files), len(directories), sum(rel not in executable_paths for _, rel in files)) != (
        EXPECTED_CANDIDATE_VENDOR_FILE_COUNT,
        EXPECTED_CANDIDATE_VENDOR_DIRECTORY_COUNT,
        EXPECTED_CANDIDATE_VENDOR_ORDINARY_FILE_COUNT,
    ):
        raise DeploymentError("Candidate vendor cannot be normalized because its structure differs.")

    os.chown(root, EXPECTED_APP_UID, EXPECTED_APP_GID)
    os.chmod(root, 0o775)
    for path in directories:
        os.chown(path, EXPECTED_APP_UID, EXPECTED_APP_GID)
        os.chmod(path, 0o775)
    for path, relative in files:
        os.chown(path, EXPECTED_APP_UID, EXPECTED_APP_GID)
        os.chmod(path, 0o775 if relative in executable_paths else 0o664)
    fsync_directory(root)
    return candidate_vendor_identity(root)


def require_candidate_vendor(root: Path) -> dict[str, Any]:
    identity = candidate_vendor_identity(root)
    if identity["manifest"] != EXPECTED_CANDIDATE_VENDOR_MANIFEST:
        raise DeploymentError("Candidate vendor differs from the deterministic reviewed manifest.")
    if identity["metadata_sha256"] != EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256:
        raise DeploymentError("Candidate vendor ownership/mode identity differs from review.")
    return identity


def application_autoload_identity(shadow: Path) -> dict[str, Any]:
    shadow = require_real_directory(shadow)
    composer_root = require_real_directory(shadow / "vendor/composer", within=shadow)
    pattern = re.compile(
        r"'(?P<class>App(?:\\\\[^']+)+)'\s*=>[^\n]*'(?P<path>/app/[^']+)'"
    )
    entries_by_file: dict[str, set[tuple[str, str]]] = {}
    application_root = require_real_directory(shadow / "app", within=shadow)
    for name in ("autoload_classmap.php", "autoload_static.php"):
        path = require_regular_file(composer_root / name)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exception:
            raise DeploymentError(f"Composer optimized autoload file is not UTF-8: {name}") from exception
        entries = {
            (match.group("class").replace("\\\\", "\\"), match.group("path"))
            for match in pattern.finditer(content)
        }
        if len(entries) != EXPECTED_APPLICATION_AUTOLOAD_ENTRIES:
            raise DeploymentError(
                f"{name} has {len(entries)} application entries; expected "
                f"{EXPECTED_APPLICATION_AUTOLOAD_ENTRIES}."
            )
        for _class_name, relative_path in entries:
            mapped = require_regular_file(shadow / relative_path.removeprefix("/"))
            if not is_relative_to(mapped, application_root):
                raise DeploymentError(f"Composer application entry escapes app/: {relative_path}")
        entries_by_file[name] = entries

    classmap_entries = entries_by_file["autoload_classmap.php"]
    static_entries = entries_by_file["autoload_static.php"]
    if classmap_entries != static_entries:
        raise DeploymentError("Composer optimized application autoload entries disagree.")
    canonical = b"".join(
        f"{class_name}\0{relative_path}\n".encode("utf-8")
        for class_name, relative_path in sorted(classmap_entries)
    )
    return {
        "entries": len(classmap_entries),
        "sha256": sha256_bytes(canonical),
        "files": {
            name: {
                "entries": len(entries),
                "sha256": sha256_file(composer_root / name),
            }
            for name, entries in sorted(entries_by_file.items())
        },
    }


def require_application_autoload(shadow: Path) -> dict[str, Any]:
    identity = application_autoload_identity(shadow)
    if identity["sha256"] != EXPECTED_APPLICATION_AUTOLOAD_SHA256:
        raise DeploymentError("Composer application autoload identity differs from review.")
    return identity


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


def validate_database_envelope(
    payload: dict[str, Any],
    *,
    pre_source: bool,
) -> dict[str, Any]:
    """Apply the reviewed schema/ledger contract to one runtime snapshot."""

    try:
        if pre_source:
            return database_envelope.validate_pre_source_database_envelope(payload)
        return database_envelope.validate_post_cutover_database_envelope(payload)
    except database_envelope.DatabaseEnvelopeError as exception:
        raise DeploymentError(f"Production database envelope rejected: {exception}") from exception


def require_database_envelope_validator() -> Path:
    module_path = Path(str(database_envelope.__file__)).resolve(strict=True)
    return require_regular_file(module_path, DATABASE_ENVELOPE_VALIDATOR_SHA256)


def database_envelope_stable_identity(summary: dict[str, Any]) -> dict[str, Any]:
    """Remove only the post-cutover item_meta population counter from comparison."""

    stable = json.loads(json.dumps(summary))
    item_meta = stable.get("savedimages_item_meta")
    if not isinstance(item_meta, dict):
        raise DeploymentError("Database-envelope summary has no savedimages.item_meta proof.")
    item_meta.pop("nonnull_rows", None)
    stable.pop("item_meta_row_policy", None)
    return stable


def require_log_parser() -> Path:
    module_path = Path(str(laravel_log_delta.__file__)).resolve(strict=True)
    return require_regular_file(module_path, LOG_PARSER_SHA256)


def normalize_package_version(value: Any) -> str:
    version = str(value or "")
    return version[1:] if version.startswith("v") else version


def validate_package_identity(
    payload: dict[str, Any], expected_versions: dict[str, str]
) -> None:
    versions = payload.get("package_versions")
    paths = payload.get("package_install_paths")
    if versions != expected_versions:
        raise DeploymentError("Runtime package versions do not match the exact approved baseline.")
    if not isinstance(paths, dict) or set(paths) != set(expected_versions):
        raise DeploymentError("Runtime package install paths are incomplete or unexpected.")
    vendor_prefix = str(APP_ROOT / "vendor") + os.sep
    for package_name, package_path in paths.items():
        if not str(package_path).startswith(vendor_prefix):
            raise DeploymentError(
                f"Runtime package path for {package_name} is outside the live vendor directory."
            )


def validate_runtime_baseline(
    payload: dict[str, Any], *, expected_versions: dict[str, str]
) -> None:
    if payload.get("app_environment") != EXPECTED_APP_ENVIRONMENT:
        raise DeploymentError("The live application environment differs from the reported baseline.")
    if payload.get("app_debug") is not EXPECTED_APP_DEBUG:
        raise DeploymentError("The live application debug setting differs from the reported baseline.")
    if payload.get("queue_connection") != "sync":
        raise DeploymentError("The live queue connection is no longer sync.")
    if payload.get("disabled_capabilities") != {
        "incoming_order_receiver_enabled": False,
        "incoming_order_job_label_enabled": False,
        "incoming_order_retention_enabled": False,
        "incoming_order_allowed_host_count": 0,
    }:
        raise DeploymentError("Incoming-order, job-label, or retention capability is enabled.")
    queue_tables = payload.get("queue_tables")
    if not isinstance(queue_tables, dict):
        raise DeploymentError("Queue table state is unavailable.")
    if queue_tables.get("jobs") not in (0, None) or queue_tables.get("failed_jobs") not in (0, None):
        raise DeploymentError("Queued or failed jobs are present.")
    if payload.get("php_version") != EXPECTED_PHP_VERSION:
        raise DeploymentError("Runtime PHP version does not match the reviewed baseline.")
    extensions = payload.get("php_extensions")
    if (
        not isinstance(extensions, list)
        or not extensions
        or extensions != sorted(set(extensions))
        or not all(isinstance(extension, str) and extension for extension in extensions)
    ):
        raise DeploymentError("Runtime PHP extension inventory is invalid.")
    validate_package_identity(payload, expected_versions)
    if payload.get("laravel_version") != expected_versions["laravel/framework"]:
        raise DeploymentError("Runtime Laravel version differs from its package identity.")
    if normalize_package_version(payload.get("guzzle_version")) != expected_versions["guzzlehttp/guzzle"]:
        raise DeploymentError("Runtime Guzzle version differs from its package identity.")
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
    if php.stdout != EXPECTED_PHP_VERSION:
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
    if source != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Production runtime-source CAS manifest differs from the approved baseline.")
    vendor = tree_manifest(APP_ROOT / "vendor")
    if check_old_vendor and vendor != EXPECTED_LIVE_VENDOR_MANIFEST:
        raise DeploymentError("Live vendor manifest differs from the retained rollback baseline.")
    cache = cache_identity(APP_ROOT / "bootstrap/cache")
    if cache != EXPECTED_LIVE_CACHE_IDENTITY:
        raise DeploymentError("Production bootstrap cache differs from the retained rollback baseline.")
    return {
        "source": source,
        "vendor": vendor,
        "cache": cache,
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
        "COMPOSER_BIN_COMPAT": "proxy",
    }


def locked_package_versions(lock_path: Path) -> dict[str, str]:
    lock_path = require_regular_file(lock_path)
    try:
        document = json.loads(lock_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise DeploymentError("Composer lock is not valid UTF-8 JSON.") from exception
    packages = document.get("packages") if isinstance(document, dict) else None
    if not isinstance(packages, list):
        raise DeploymentError("Composer lock has no production package list.")
    available = {
        package.get("name"): normalize_package_version(package.get("version"))
        for package in packages
        if isinstance(package, dict) and isinstance(package.get("name"), str)
    }
    try:
        return {name: available[name] for name in NEW_PACKAGE_VERSIONS}
    except KeyError as exception:
        raise DeploymentError(
            f"Composer lock is missing required package {exception.args[0]}."
        ) from exception


def deployment_lock_snapshot() -> dict[str, Any]:
    if not DEPLOYMENT_LOCK.exists():
        return {"exists": False, "free": True}
    require_regular_file(DEPLOYMENT_LOCK)
    with DEPLOYMENT_LOCK.open("rb") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"exists": True, "free": False}
        try:
            return {"exists": True, "free": True}
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def production_preflight(
    candidate_lock: Path,
    helper: Path,
    *,
    deployment_lock_owned: bool = False,
) -> dict[str, Any]:
    candidate_lock = require_regular_file(candidate_lock, CANDIDATE_LOCK_SHA256)
    if candidate_lock.is_relative_to(APP_ROOT / "vendor"):
        raise DeploymentError("Candidate lock may not be sourced from vendor.")
    candidate_versions = locked_package_versions(candidate_lock)
    if candidate_versions != NEW_PACKAGE_VERSIONS:
        raise DeploymentError("Candidate lock package versions differ from the approved set.")

    lock_state = (
        {"exists": DEPLOYMENT_LOCK.exists(), "free": False, "owned_by_stage_process": True}
        if deployment_lock_owned
        else deployment_lock_snapshot()
    )
    if not deployment_lock_owned and lock_state["free"] is not True:
        raise DeploymentError("Another dependency operation holds the application lock.")

    require_database_envelope_validator()
    require_gate_helper()
    require_log_parser()
    baseline = assert_production_baseline(helper)
    processes = scoped_processes()
    if processes:
        raise DeploymentError("A scoped Artisan/payout process is active; preflight stopped.")
    health = health_snapshot()
    runtime = runtime_probe(helper)
    validate_runtime_baseline(runtime, expected_versions=OLD_PACKAGE_VERSIONS)
    database_summary = validate_database_envelope(runtime, pre_source=True)
    return {
        "artifact": "buy-dtf-laravel-remember-cookie-production-preflight-v3",
        "handoff": {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256},
        "cutover_requires_separate_independent_review": True,
        "status": "pass",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "database_envelope_validator_sha256": DATABASE_ENVELOPE_VALIDATOR_SHA256,
        "gate_helper_sha256": GATE_HELPER_SHA256,
        "log_parser_sha256": LOG_PARSER_SHA256,
        "database_envelope": database_summary,
        "live_composer_json_sha256": sha256_file(APP_ROOT / "composer.json"),
        "live_lock_sha256": sha256_file(APP_ROOT / "composer.lock"),
        "candidate_lock_sha256": sha256_file(candidate_lock),
        "database_config_sha256": sha256_file(APP_ROOT / "config/database.php"),
        "source_manifest": baseline["source"],
        "vendor_manifest": baseline["vendor"],
        "cache_identity": baseline["cache"],
        "front_controller": baseline["front_controller"],
        "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
        "deployment_lock": lock_state,
        "scoped_processes": processes,
        "health": health,
        "runtime": runtime,
        "candidate_package_versions": candidate_versions,
    }


def copy_runtime_shadow(source_root: Path, destination: Path) -> dict[str, Any]:
    source_root = require_real_directory(source_root)
    destination = require_real_directory(destination)
    source_identity = source_manifest(source_root)
    if source_identity != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Runtime source differs from the approved CAS before shadow copy.")

    for relative_name in SOURCE_TOP_LEVEL_FILES:
        source = source_root / relative_name
        target = destination / relative_name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise DeploymentError(f"Runtime shadow target already exists: {target}")
        shutil.copy2(source, target, follow_symlinks=False)
    for relative_root in SOURCE_ROOTS:
        source = source_root / relative_root
        target = destination / relative_root
        if source.is_symlink():
            raise DeploymentError(f"Cannot shadow-copy symbolic runtime root: {source}")
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise DeploymentError(f"Runtime shadow target already exists: {target}")

        def ignore_bootstrap_cache(directory: str, names: list[str]) -> set[str]:
            if Path(directory) == source_root / "bootstrap" and "cache" in names:
                return {"cache"}
            return set()

        shutil.copytree(
            source,
            target,
            symlinks=True,
            ignore=ignore_bootstrap_cache if relative_root == "bootstrap" else None,
        )
    cache = destination / "bootstrap/cache"
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    copied_identity = source_manifest(destination)
    if copied_identity != source_identity:
        raise DeploymentError("Runtime source CAS changed while constructing the shadow.")
    if source_manifest(source_root) != source_identity:
        raise DeploymentError("Runtime source CAS changed during the shadow copy.")
    for relative in (
        "storage/app",
        "storage/framework/cache",
        "storage/framework/sessions",
        "storage/framework/views",
        "storage/logs",
    ):
        (destination / relative).mkdir(mode=0o700, parents=True, exist_ok=True)
    return copied_identity


def stage_release(candidate_lock: Path, approval_token: str, helper: Path) -> Path:
    if approval_token != STAGE_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed staging approval token was not supplied.")
    preflight = production_preflight(candidate_lock, helper, deployment_lock_owned=True)
    baseline = {
        "source": preflight["source_manifest"],
        "vendor": preflight["vendor_manifest"],
        "cache": preflight["cache_identity"],
        "front_controller": preflight["front_controller"],
    }
    before_health = preflight["health"]
    before_runtime = preflight["runtime"]
    candidate_lock = require_regular_file(candidate_lock, CANDIDATE_LOCK_SHA256)

    release_root = ensure_private_operations_root(RELEASE_ROOT, create=True)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    release = release_root / f"{CANDIDATE_LOCK_SHA256[:12]}-{timestamp}"
    release.mkdir(mode=0o700)
    shadow = release / "shadow"
    shadow.mkdir(mode=0o700)
    logs = release / "logs"
    logs.mkdir(mode=0o700)
    composer_home = release / ".composer-home"
    composer_home.mkdir(mode=0o700)
    (release / ".home").mkdir(mode=0o700)
    environment = safe_environment(composer_home)

    shadow_source = copy_runtime_shadow(APP_ROOT, shadow)
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
            "--no-autoloader",
            "--no-interaction",
            "--no-scripts",
            "--no-ansi",
        ],
        cwd=shadow,
        timeout=900,
        env=environment,
    )
    command_receipts["composer_install"] = write_command_result(logs / "composer-install.txt", install)
    dump_autoload = run(
        [
            composer,
            "--no-plugins",
            "dump-autoload",
            "--no-dev",
            "--optimize",
            "--no-scripts",
            "--no-interaction",
            "--no-ansi",
        ],
        cwd=shadow,
        timeout=300,
        env=environment,
    )
    command_receipts["composer_dump_autoload"] = write_command_result(
        logs / "composer-dump-autoload.txt", dump_autoload
    )
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
        ["/usr/bin/php", "artisan", "route:list", "--json", "--no-ansi"],
        cwd=shadow,
        timeout=120,
        env=environment,
    )
    command_receipts["shadow_routes"] = write_command_result(logs / "shadow-routes.txt", routes)
    try:
        route_payload = json.loads(routes.stdout)
    except json.JSONDecodeError as exception:
        raise DeploymentError("Candidate route discovery did not return JSON.") from exception
    if not isinstance(route_payload, list) or len(route_payload) != EXPECTED_ROUTE_COUNT:
        raise DeploymentError("Candidate route discovery did not return the expected 178 routes.")

    vendor_identity = normalize_candidate_vendor(shadow / "vendor")
    vendor = vendor_identity["manifest"]
    autoload_identity = require_application_autoload(shadow)
    candidate_cache = normalize_candidate_cache(shadow / "bootstrap/cache")
    if vendor != EXPECTED_CANDIDATE_VENDOR_MANIFEST:
        raise DeploymentError("Staged vendor differs from the deterministic reviewed candidate.")
    if vendor_identity["metadata_sha256"] != EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256:
        raise DeploymentError("Staged vendor metadata differs from the deterministic reviewed candidate.")
    if candidate_cache != EXPECTED_CANDIDATE_CACHE_IDENTITY:
        raise DeploymentError("Staged bootstrap cache differs from the deterministic reviewed candidate.")
    installed = json.loads((shadow / "vendor/composer/installed.json").read_text(encoding="utf-8"))
    packages = installed.get("packages", installed) if isinstance(installed, dict) else installed
    versions = {
        package.get("name"): normalize_package_version(package.get("version"))
        for package in packages
        if isinstance(package, dict)
    }
    installed_candidate_versions = {
        package_name: versions.get(package_name) for package_name in NEW_PACKAGE_VERSIONS
    }
    if installed_candidate_versions != NEW_PACKAGE_VERSIONS:
        raise DeploymentError("Staged package versions do not match the exact approved candidate.")
    if "laravel/pail" in versions:
        raise DeploymentError("The no-dev candidate unexpectedly contains Laravel Pail.")
    if (shadow / "vendor/laravel/pail").exists():
        raise DeploymentError("The no-dev candidate contains a Laravel Pail directory.")
    shadow_source_after = source_manifest(shadow)
    if shadow_source_after != shadow_source:
        raise DeploymentError("Staged source CAS changed during candidate construction.")

    # Re-read the live system after candidate construction. This proves that
    # source, dependencies, front controller, configuration, schema, queues,
    # and disabled capability flags remained unchanged throughout staging.
    post_candidate_baseline = assert_production_baseline(helper)
    if post_candidate_baseline != baseline:
        raise DeploymentError("Production CAS baseline changed during candidate construction.")
    post_candidate_runtime = runtime_probe(helper)
    validate_runtime_baseline(
        post_candidate_runtime,
        expected_versions=OLD_PACKAGE_VERSIONS,
    )
    post_candidate_database = validate_database_envelope(
        post_candidate_runtime,
        pre_source=True,
    )
    if post_candidate_database != preflight["database_envelope"]:
        raise DeploymentError(
            "Production schema, ledger, queues, capabilities, or guarded row counts "
            "changed during candidate construction."
        )
    post_candidate_health = health_snapshot()
    database_receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-database-envelope-v3",
        "status": "pass",
        "policy": "pre_source_exactly_zero",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "validator_sha256": DATABASE_ENVELOPE_VALIDATOR_SHA256,
        "before_candidate_construction": preflight["database_envelope"],
        "after_candidate_construction": post_candidate_database,
        "stable_identity": database_envelope_stable_identity(post_candidate_database),
        "database_read_only": True,
        "migration_command_invoked": False,
        "migration_executed": False,
    }
    database_receipt_path = release / "database-envelope-receipt.json"
    atomic_json(database_receipt_path, database_receipt)

    receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-release-v3",
        "status": "staged",
        "handoff": {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256},
        "cutover_requires_separate_independent_review": True,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_path": str(release),
        "shadow_path": str(shadow),
        "candidate_lock_sha256": CANDIDATE_LOCK_SHA256,
        "live_composer_json_sha256": EXPECTED_LIVE_COMPOSER_JSON_SHA256,
        "approved_source_manifest": baseline["source"],
        "shadow_source_manifest": shadow_source,
        "shadow_source_manifest_after": shadow_source_after,
        "retained_vendor_manifest": baseline["vendor"],
        "retained_cache_identity": baseline["cache"],
        "candidate_cache_identity": candidate_cache,
        "candidate_vendor_manifest": vendor,
        "candidate_vendor_identity": vendor_identity,
        "application_autoload_identity": autoload_identity,
        "composer_bin_compat": "proxy",
        "route_count": len(route_payload),
        "front_controller": baseline["front_controller"],
        "maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
        "command_receipts": command_receipts,
        "production_preflight": preflight,
        "database_envelope_receipt": {
            "path": str(database_receipt_path),
            "sha256": sha256_file(database_receipt_path),
        },
        "database_envelope": post_candidate_database,
        "post_candidate_baseline": post_candidate_baseline,
        "health_before": before_health,
        "health_after_candidate_construction": post_candidate_health,
        "runtime_before": before_runtime,
        "runtime_after_candidate_construction": post_candidate_runtime,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "database_envelope_validator_sha256": DATABASE_ENVELOPE_VALIDATOR_SHA256,
        "gate_helper_sha256": GATE_HELPER_SHA256,
        "log_parser_sha256": LOG_PARSER_SHA256,
        "versions": NEW_PACKAGE_VERSIONS,
        "no_dev": True,
    }
    receipt_path = release / "release-receipt.json"
    atomic_json(receipt_path, receipt)
    print(f"Staging complete. Independently review and approve receipt: {receipt_path}")
    print(f"release_receipt_sha256={sha256_file(receipt_path)}")
    return receipt_path


def load_approved_release(receipt_path: Path, approved_sha256: str) -> tuple[dict[str, Any], Path]:
    release_root = ensure_private_operations_root(RELEASE_ROOT, create=False)
    receipt_path = require_regular_file(receipt_path, approved_sha256)
    if not is_relative_to(receipt_path, release_root):
        raise DeploymentError("Release receipt is outside the fixed release root.")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise DeploymentError("Release receipt is invalid JSON.") from exception
    if (
        receipt.get("artifact") != "buy-dtf-laravel-remember-cookie-release-v3"
        or receipt.get("status") != "staged"
    ):
        raise DeploymentError("Release receipt is not an approved staged release.")
    if receipt.get("handoff") != {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256}:
        raise DeploymentError("Release receipt references a different review handoff.")
    if receipt.get("cutover_requires_separate_independent_review") is not True:
        raise DeploymentError("Release receipt does not preserve the independent-review boundary.")
    if receipt.get("candidate_lock_sha256") != CANDIDATE_LOCK_SHA256:
        raise DeploymentError("Release receipt references a different candidate lock.")
    if receipt.get("versions") != NEW_PACKAGE_VERSIONS:
        raise DeploymentError("Release receipt references different candidate package versions.")
    if receipt.get("candidate_vendor_manifest") != EXPECTED_CANDIDATE_VENDOR_MANIFEST:
        raise DeploymentError("Release receipt references a different candidate vendor.")
    candidate_identity = receipt.get("candidate_vendor_identity")
    if (
        not isinstance(candidate_identity, dict)
        or candidate_identity.get("manifest") != EXPECTED_CANDIDATE_VENDOR_MANIFEST
        or candidate_identity.get("metadata_sha256")
        != EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256
        or candidate_identity.get("executable_allowlist_sha256")
        != CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256
    ):
        raise DeploymentError("Release receipt has no approved candidate metadata identity.")
    if receipt.get("application_autoload_identity", {}).get("sha256") != (
        EXPECTED_APPLICATION_AUTOLOAD_SHA256
    ):
        raise DeploymentError("Release receipt has no approved application autoload identity.")
    if (
        receipt.get("composer_bin_compat") != "proxy"
        or receipt.get("route_count") != EXPECTED_ROUTE_COUNT
    ):
        raise DeploymentError("Release receipt lacks the reviewed Unix proxy or route proof.")
    if receipt.get("shadow_source_manifest") != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Release receipt has no exact shadow-source CAS proof.")
    if receipt.get("shadow_source_manifest_after") != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Release receipt has no final shadow-source CAS proof.")
    if receipt.get("candidate_cache_identity") != EXPECTED_CANDIDATE_CACHE_IDENTITY:
        raise DeploymentError("Release receipt references a different candidate bootstrap cache.")
    preflight = receipt.get("production_preflight")
    if (
        not isinstance(preflight, dict)
        or preflight.get("status") != "pass"
        or preflight.get("script_sha256") != sha256_file(Path(__file__).resolve())
        or preflight.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256
        or preflight.get("database_envelope_validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or preflight.get("gate_helper_sha256") != GATE_HELPER_SHA256
        or preflight.get("log_parser_sha256") != LOG_PARSER_SHA256
        or receipt.get("database_envelope_validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or receipt.get("gate_helper_sha256") != GATE_HELPER_SHA256
        or receipt.get("log_parser_sha256") != LOG_PARSER_SHA256
    ):
        raise DeploymentError("Release receipt has no matching successful production preflight.")
    before_database = validate_database_envelope(
        preflight.get("runtime", {}),
        pre_source=True,
    )
    after_database = validate_database_envelope(
        receipt.get("runtime_after_candidate_construction", {}),
        pre_source=True,
    )
    if (
        before_database != preflight.get("database_envelope")
        or after_database != receipt.get("database_envelope")
        or before_database != after_database
    ):
        raise DeploymentError("Release receipt database-envelope proof is invalid or drifted.")
    database_item = receipt.get("database_envelope_receipt")
    if not isinstance(database_item, dict):
        raise DeploymentError("Release receipt has no database-envelope receipt.")
    database_receipt_path = require_regular_file(
        Path(str(database_item.get("path", ""))),
        str(database_item.get("sha256", "")),
    )
    if database_receipt_path != receipt_path.parent / "database-envelope-receipt.json":
        raise DeploymentError("Database-envelope receipt is outside its release directory.")
    try:
        database_receipt = json.loads(database_receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise DeploymentError("Database-envelope receipt is invalid JSON.") from exception
    if (
        not isinstance(database_receipt, dict)
        or database_receipt.get("artifact")
        != "buy-dtf-laravel-remember-cookie-database-envelope-v3"
        or database_receipt.get("status") != "pass"
        or database_receipt.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256
        or database_receipt.get("validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or database_receipt.get("before_candidate_construction") != before_database
        or database_receipt.get("after_candidate_construction") != after_database
        or database_receipt.get("database_read_only") is not True
        or database_receipt.get("migration_command_invoked") is not False
        or database_receipt.get("migration_executed") is not False
    ):
        raise DeploymentError("Database-envelope receipt does not prove the reviewed state.")
    shadow = Path(str(receipt.get("shadow_path", "")))
    shadow = require_real_directory(shadow, within=release_root)
    if source_manifest(shadow) != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Staged source differs from the approved CAS manifest.")
    require_regular_file(shadow / "composer.lock", CANDIDATE_LOCK_SHA256)
    vendor_identity = require_candidate_vendor(shadow / "vendor")
    if vendor_identity != receipt.get("candidate_vendor_identity"):
        raise DeploymentError("Staged vendor differs from the approved release receipt.")
    if require_application_autoload(shadow) != receipt.get("application_autoload_identity"):
        raise DeploymentError("Staged optimized autoload differs from its release receipt.")
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


def require_gate_helper() -> Path:
    module_path = Path(str(dependency_gate.__file__)).resolve(strict=True)
    return require_regular_file(module_path, GATE_HELPER_SHA256)


def gate_context(state: dict[str, Any], state_path: Path) -> dependency_gate.GateContext:
    backup_value = state.get("front_controller_backup")
    backup_sha256 = state.get("front_controller_backup_sha256")
    if not isinstance(backup_value, str) or not isinstance(backup_sha256, str):
        raise DeploymentError("Front-controller rollback backup is unavailable.")
    state_directory = state_path.resolve(strict=True).parent
    backup = require_regular_file(Path(backup_value), backup_sha256)
    if backup != state_directory / "public-index.before.php":
        raise DeploymentError("Front-controller backup differs from the durable state path.")
    return dependency_gate.GateContext(
        application_root=APP_ROOT,
        front_controller=FRONT_CONTROLLER,
        state_path=state_path,
        evidence_directory=state_directory,
        original_backup=backup,
        original_sha256=backup_sha256,
    )


def _next_gate_operation(state: dict[str, Any], reason: str) -> str:
    history = state.get("front_controller_transitions", [])
    if not isinstance(history, list):
        raise DeploymentError("Front-controller transition history is invalid.")
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", reason):
        raise DeploymentError("Static-gate operation reason is invalid.")
    return f"{reason}-{len(history) + 1:04d}"


def _gate_origin_probe(state_directory: Path, operation: str) -> dict[str, Any]:
    return dependency_gate.gate_origin_probe(
        evidence_directory=state_directory,
        operation=operation,
        public_url=MAINTENANCE_PROBE_URL,
        cwd=APP_ROOT,
    )


def _gate_public_probe(state_directory: Path, operation: str) -> dict[str, Any]:
    return dependency_gate.gate_public_probe(
        evidence_directory=state_directory,
        operation=operation,
        public_url=MAINTENANCE_PROBE_URL,
        cwd=APP_ROOT,
    )


def install_static_gate(
    state: dict[str, Any],
    state_path: Path,
    reason: str,
    *,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    require_gate_helper()
    context = gate_context(state, state_path)
    operation = _next_gate_operation(state, reason)
    try:
        evidence = dependency_gate.install_static_gate(
            context=context,
            state=state,
            operation=operation,
            origin_probe=lambda: _gate_origin_probe(context.evidence_directory, operation),
            public_probe=lambda: _gate_public_probe(context.evidence_directory, operation),
            restored_health_probe=health_snapshot,
            fault_injector=fault_injector,
        )
    except dependency_gate.GateError as exception:
        raise DeploymentError(str(exception)) from exception
    evidence["method"] = "durable_atomic_static_front_controller"
    evidence["reason"] = reason
    evidence["operation"] = operation
    return evidence


def establish_rollback_gate(
    state: dict[str, Any],
    state_path: Path,
    reason: str,
) -> dict[str, Any]:
    require_gate_helper()
    context = gate_context(state, state_path)
    operation = _next_gate_operation(state, reason)
    try:
        return dependency_gate.establish_rollback_containment(
            context=context,
            state=state,
            operation=operation,
            origin_probe=lambda: _gate_origin_probe(context.evidence_directory, operation),
            public_probe=lambda: _gate_public_probe(context.evidence_directory, operation),
            restored_health_probe=health_snapshot,
        )
    except dependency_gate.GateError as exception:
        raise DeploymentError(str(exception)) from exception


def restore_front_controller(
    state: dict[str, Any],
    state_path: Path,
    *,
    reason: str = "dependency_rollback_reopen",
) -> dict[str, Any]:
    require_gate_helper()
    context = gate_context(state, state_path)
    operation = _next_gate_operation(state, reason)
    receipt_name = f"{operation}-exact-original-restoration-receipt.json"
    try:
        receipt = dependency_gate.restore_front_controller_exact(
            context=context,
            state=state,
            operation=operation,
            receipt_name=receipt_name,
        )
    except dependency_gate.GateError as exception:
        raise DeploymentError(str(exception)) from exception
    time.sleep(OPCACHE_WAIT_SECONDS)
    return receipt


def restore_pre_mutation_failure(
    state: dict[str, Any],
    state_path: Path,
    exception: BaseException,
) -> None:
    """Restore the exact original and prove normal health without dependency rollback."""

    if dependency_gate.dependency_mutation_has_started(state):
        raise DeploymentError("Pre-mutation restoration was requested after mutation began.")
    live = dependency_gate.file_identity(FRONT_CONTROLLER)
    if live["sha256"] == EXPECTED_FRONT_CONTROLLER_SHA256 and (
        live["metadata"] == dependency_gate.reviewed_front_controller_metadata()
    ):
        restoration: dict[str, Any] = {
            "status": "already_restored",
            "restored": live,
        }
    else:
        restoration = restore_front_controller(
            state,
            state_path,
            reason="pre_mutation_failure_restore",
        )
    health = health_snapshot()
    receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-pre-mutation-restoration-v3",
        "status": "pass",
        "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "failure_class": type(exception).__name__,
        "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
        "dependency_mutation_started": False,
        "restoration": restoration,
        "health": health,
        "front_controller": dependency_gate.file_identity(FRONT_CONTROLLER),
    }
    receipt_path = state_path.parent / "pre-mutation-failure-restoration-receipt.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise DeploymentError("Pre-mutation restoration receipt already exists.")
    dependency_gate.write_new_json(receipt_path, receipt)
    state["pre_mutation_failure_restoration_receipt"] = str(receipt_path)
    state["pre_mutation_failure_restoration_receipt_sha256"] = sha256_file(receipt_path)
    state["status"] = "failed_before_dependency_mutation_original_restored"
    state["static_gate_active"] = False
    state["containment_active"] = False
    state["gate_active"] = False
    state["gate_verified"] = False
    write_state(state_path, state)


def reassert_and_record_gate(
    state: dict[str, Any],
    state_path: Path,
    reason: str,
    *,
    status: str | None = None,
    operation: Callable[[dict[str, Any], Path, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Compatibility wrapper used by focused runner tests. Production rollback
    # uses establish_rollback_gate so post-mutation HTTP failure cannot reopen.
    reassertion = operation or install_static_gate
    evidence = reassertion(state, state_path, reason)
    history = state.setdefault("gate_reassertions", [])
    if not isinstance(history, list):
        raise DeploymentError("Static-gate reassertion history is invalid.")
    history.append(evidence)
    state["gate_active"] = True
    state["gate_verified"] = bool(evidence.get("http_verified", True))
    if status is not None:
        state["status"] = status
    write_state(state_path, state)
    return evidence

def contain_cutover_failure(
    state: dict[str, Any],
    state_path: Path,
    exception: BaseException,
) -> bool:
    """Contain a cutover failure and return whether dependency rollback is armed."""

    mutation_started = dependency_gate.dependency_mutation_has_started(state)
    state["failure_class"] = type(exception).__name__
    state["failure_message_sha256"] = sha256_bytes(str(exception).encode("utf-8"))
    if not mutation_started:
        restore_pre_mutation_failure(state, state_path, exception)
        return False

    containment = establish_rollback_gate(
        state,
        state_path,
        "cutover_failure",
    )
    state["cutover_failure_containment"] = containment
    state["status"] = "failed_dependency_rollback_required"
    state["gate_active"] = True
    state["gate_verified"] = bool(containment.get("http_verified"))
    write_state(state_path, state)
    return True


def contain_rollback_failure(
    state: dict[str, Any],
    state_path: Path,
    exception: BaseException,
) -> None:
    """Retain the exact gate locally even when HTTP paths or Laravel are broken."""

    context = gate_context(state, state_path)
    operation = _next_gate_operation(state, "rollback_failure")
    try:
        containment = dependency_gate.retain_static_gate_exact(
            context=context,
            state=state,
            operation=operation,
        )
    except dependency_gate.GateError as gate_exception:
        state["gate_active"] = None
        state["gate_verified"] = False
        state["rollback_failure_class"] = type(exception).__name__
        state["rollback_failure_message_sha256"] = sha256_bytes(
            str(exception).encode("utf-8")
        )
        state["gate_failure_class"] = type(gate_exception).__name__
        state["gate_failure_message_sha256"] = sha256_bytes(
            str(gate_exception).encode("utf-8")
        )
        state["status"] = "rollback_failed_static_gate_identity_unavailable"
        write_state(state_path, state)
        raise DeploymentError(
            "Rollback failed and exact local static-gate containment could not be established."
        ) from gate_exception
    state["rollback_failure_class"] = type(exception).__name__
    state["rollback_failure_message_sha256"] = sha256_bytes(
        str(exception).encode("utf-8")
    )
    state["rollback_failure_containment"] = containment
    state["status"] = "rollback_failed_static_gate_retained"
    state["gate_active"] = True
    state["gate_verified"] = False
    write_state(state_path, state)

def fpm_probe(expected_versions: dict[str, str]) -> dict[str, Any]:
    if not FPM_SOCKET.is_socket():
        raise DeploymentError("The reviewed PHP-FPM socket is unavailable.")
    probe_directory = APP_ROOT / "storage/framework/laravel-remember-cookie-probes"
    probe_directory.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.chown(probe_directory, -1, 33)
    os.chmod(probe_directory, 0o2750)
    probe = probe_directory / f"probe-{secrets.token_hex(12)}.php"
    package_names_php = json.dumps(list(expected_versions))
    source = f'''<?php
declare(strict_types=1);
require {str(APP_ROOT / "vendor/autoload.php")!r};
$packageNames = {package_names_php};
$packageVersions = [];
$packageInstallPaths = [];
foreach ($packageNames as $packageName) {{
    $packageVersions[$packageName] = ltrim(
        (string) Composer\\InstalledVersions::getPrettyVersion($packageName),
        'v'
    );
    $installPath = Composer\\InstalledVersions::getInstallPath($packageName);
    $packageInstallPaths[$packageName] = is_string($installPath) ? realpath($installPath) : false;
}}
$phpExtensions = get_loaded_extensions();
sort($phpExtensions, SORT_STRING);
$payload = [
    'laravel_version' => Illuminate\\Foundation\\Application::VERSION,
    'guzzle_version' => Composer\\InstalledVersions::getPrettyVersion('guzzlehttp/guzzle'),
    'package_versions' => $packageVersions,
    'package_install_paths' => $packageInstallPaths,
    'php_version' => PHP_VERSION,
    'php_extensions' => $phpExtensions,
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
        validate_package_identity(payload, expected_versions)
        if payload.get("php_version") != EXPECTED_PHP_VERSION:
            raise DeploymentError("PHP-FPM loaded an unexpected PHP version.")
        extensions = payload.get("php_extensions")
        if not isinstance(extensions, list) or not extensions or extensions != sorted(set(extensions)):
            raise DeploymentError("PHP-FPM returned an invalid PHP extension inventory.")
        if payload.get("laravel_version") != expected_versions["laravel/framework"]:
            raise DeploymentError("PHP-FPM loaded an unexpected Laravel version.")
        if normalize_package_version(payload.get("guzzle_version")) != expected_versions["guzzlehttp/guzzle"]:
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
    rollback_root = ensure_private_operations_root(ROLLBACK_ROOT, create=False)
    release_root = ensure_private_operations_root(RELEASE_ROOT, create=False)
    state_path = require_regular_file(state_path)
    state_directory = state_path.parent.resolve(strict=True)
    if not is_relative_to(state_directory, rollback_root):
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
    cache_backup = require_real_directory(Path(cache_value), within=rollback_root)
    if cache_backup != state_directory / "bootstrap-cache-before":
        raise DeploymentError("Rollback cache backup is outside the state directory.")

    receipt_value = state.get("release_receipt")
    receipt_sha256 = state.get("release_receipt_sha256")
    if not isinstance(receipt_value, str) or not isinstance(receipt_sha256, str):
        raise DeploymentError("Rollback state has no approved release receipt.")
    receipt_path = require_regular_file(Path(receipt_value), receipt_sha256)
    if not is_relative_to(receipt_path, release_root):
        raise DeploymentError("Rollback release receipt is outside the fixed release root.")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise DeploymentError("Rollback release receipt is invalid JSON.") from exception
    if receipt.get("artifact") != "buy-dtf-laravel-remember-cookie-release-v3":
        raise DeploymentError("Rollback release receipt has an unexpected artifact identity.")
    if receipt.get("status") != "staged":
        raise DeploymentError("Rollback release receipt is not a staged v3 release.")
    if receipt.get("handoff") != {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256}:
        raise DeploymentError("Rollback release receipt references a different review handoff.")
    shadow = require_real_directory(Path(str(receipt.get("shadow_path", ""))), within=release_root)
    if Path(str(state.get("staged_vendor", ""))).resolve(strict=True) != shadow / "vendor":
        raise DeploymentError("Rollback staged-vendor path differs from its release receipt.")
    if Path(str(state.get("staged_cache", ""))).resolve(strict=True) != shadow / "bootstrap/cache":
        raise DeploymentError("Rollback staged-cache path differs from its release receipt.")
    if state.get("script_sha256") != sha256_file(Path(__file__).resolve()):
        raise DeploymentError("Rollback state was created by a different deployment script.")
    if state.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256:
        raise DeploymentError("Rollback state references a different runtime helper.")
    if (
        state.get("database_envelope_validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or state.get("gate_helper_sha256") != GATE_HELPER_SHA256
        or state.get("log_parser_sha256") != LOG_PARSER_SHA256
    ):
        raise DeploymentError("Rollback state references different reviewed control helpers.")
    if (
        receipt.get("database_envelope_validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or receipt.get("gate_helper_sha256") != GATE_HELPER_SHA256
        or receipt.get("log_parser_sha256") != LOG_PARSER_SHA256
    ):
        raise DeploymentError("Rollback receipt references different reviewed control helpers.")
    if receipt.get("candidate_lock_sha256") != CANDIDATE_LOCK_SHA256:
        raise DeploymentError("Rollback receipt references a different candidate lock.")
    if receipt.get("approved_source_manifest") != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Rollback receipt references a different source CAS.")
    if (
        receipt.get("shadow_source_manifest") != EXPECTED_SOURCE_MANIFEST
        or receipt.get("shadow_source_manifest_after") != EXPECTED_SOURCE_MANIFEST
    ):
        raise DeploymentError("Rollback receipt lacks the initial and final shadow-source CAS.")
    if receipt.get("retained_vendor_manifest") != EXPECTED_LIVE_VENDOR_MANIFEST:
        raise DeploymentError("Rollback receipt references a different retained vendor.")
    if receipt.get("candidate_vendor_manifest") != EXPECTED_CANDIDATE_VENDOR_MANIFEST:
        raise DeploymentError("Rollback receipt references a different candidate manifest.")
    if receipt.get("candidate_vendor_identity", {}).get("metadata_sha256") != (
        EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256
    ):
        raise DeploymentError("Rollback receipt references a different vendor metadata identity.")
    if receipt.get("application_autoload_identity", {}).get("sha256") != (
        EXPECTED_APPLICATION_AUTOLOAD_SHA256
    ):
        raise DeploymentError("Rollback receipt references a different autoload identity.")
    if receipt.get("candidate_cache_identity") != EXPECTED_CANDIDATE_CACHE_IDENTITY:
        raise DeploymentError("Rollback receipt references a different candidate cache.")
    if receipt.get("retained_cache_identity") != EXPECTED_LIVE_CACHE_IDENTITY:
        raise DeploymentError("Rollback receipt references a different retained cache.")
    if receipt.get("maintenance_gate_sha256") != MAINTENANCE_GATE_SHA256:
        raise DeploymentError("Rollback receipt references a different maintenance gate.")
    if receipt.get("front_controller") != {
        "sha256": EXPECTED_FRONT_CONTROLLER_SHA256,
        "metadata": {
            "kind": "file",
            "mode": 0o644,
            "uid": EXPECTED_APP_UID,
            "gid": EXPECTED_APP_GID,
        },
    }:
        raise DeploymentError("Rollback receipt references a different front controller.")
    receipt_preflight = receipt.get("production_preflight")
    if not isinstance(receipt_preflight, dict):
        raise DeploymentError("Rollback receipt has no production preflight.")
    receipt_database = validate_database_envelope(
        receipt_preflight.get("runtime", {}),
        pre_source=True,
    )
    if receipt.get("database_envelope") != receipt_database:
        raise DeploymentError("Rollback receipt database envelope is inconsistent.")
    database_receipt_item = receipt.get("database_envelope_receipt")
    if not isinstance(database_receipt_item, dict):
        raise DeploymentError("Rollback receipt has no database-envelope evidence.")
    database_receipt_path = require_regular_file(
        Path(str(database_receipt_item.get("path", ""))),
        str(database_receipt_item.get("sha256", "")),
    )
    if database_receipt_path != receipt_path.parent / "database-envelope-receipt.json":
        raise DeploymentError("Rollback database-envelope receipt path differs.")
    if state.get("database_envelope_receipt") != database_receipt_item:
        raise DeploymentError("Rollback state references different database evidence.")
    if (
        state.get("database_envelope_staged") != receipt_database
        or state.get("database_envelope_before_cutover") != receipt_database
        or state.get("database_envelope_stable_identity")
        != database_envelope_stable_identity(receipt_database)
    ):
        raise DeploymentError("Rollback state database envelope differs from its release receipt.")
    if state.get("candidate_vendor_identity") != receipt.get("candidate_vendor_identity"):
        raise DeploymentError("Rollback state references a different candidate vendor identity.")
    if state.get("application_autoload_identity") != receipt.get("application_autoload_identity"):
        raise DeploymentError("Rollback state references a different application autoload identity.")
    if state.get("candidate_vendor_sha256") != EXPECTED_CANDIDATE_VENDOR_MANIFEST["sha256"]:
        raise DeploymentError("Rollback state references a different candidate vendor manifest.")
    if state.get("candidate_cache_identity") != receipt.get("candidate_cache_identity"):
        raise DeploymentError("Rollback state references a different candidate cache.")
    if state.get("retained_cache_identity") != receipt.get("retained_cache_identity"):
        raise DeploymentError("Rollback state references a different retained cache.")
    if state.get("maintenance_gate_sha256") != MAINTENANCE_GATE_SHA256:
        raise DeploymentError("Rollback state references a different maintenance gate.")
    if state.get("front_controller_backup_sha256") != EXPECTED_FRONT_CONTROLLER_SHA256:
        raise DeploymentError("Rollback state references a different front-controller backup.")


def rollback_from_state(
    state: dict[str, Any],
    state_path: Path,
    helper: Path,
    *,
    failure_injector: Callable[[str], None] | None = None,
) -> None:
    validate_rollback_state_paths(state, state_path)
    state["rollback_started"] = True
    state["status"] = "rollback_starting"
    write_state(state_path, state)

    def inject(stage: str) -> None:
        if failure_injector is not None:
            failure_injector(stage)

    try:
        containment = establish_rollback_gate(
            state,
            state_path,
            "rollback_start",
        )
        state["rollback_containment"] = containment
        state["status"] = "rollback_contained_by_static_gate"
        state["gate_active"] = True
        state["gate_verified"] = bool(containment.get("http_verified"))
        write_state(state_path, state)
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
            if require_candidate_vendor(live_vendor) != state["candidate_vendor_identity"]:
                raise DeploymentError("Rollback found candidate vendor metadata drift.")
            rename_exchange(live_vendor, staged_vendor)
        elif (
            live_manifest == EXPECTED_LIVE_VENDOR_MANIFEST_SHA256
            and staged_manifest == state["candidate_vendor_sha256"]
        ):
            if require_candidate_vendor(staged_vendor) != state["candidate_vendor_identity"]:
                raise DeploymentError("Rollback retained candidate vendor metadata drift.")
        else:
            raise DeploymentError("Rollback cannot identify the retained old vendor safely.")
        inject("after_rollback_vendor")

        live_cache = APP_ROOT / "bootstrap/cache"
        staged_cache = Path(state["staged_cache"])
        live_cache_identity = cache_identity(live_cache)
        staged_cache_identity = cache_identity(staged_cache)
        old_cache_identity = state["retained_cache_identity"]
        candidate_cache_identity = state["candidate_cache_identity"]
        if candidate_cache_identity == old_cache_identity:
            if (
                live_cache_identity != old_cache_identity
                or staged_cache_identity != candidate_cache_identity
            ):
                raise DeploymentError("Rollback found drift in identical bootstrap caches.")
            state["rollback_cache_exchange_skipped_identical"] = True
            write_state(state_path, state)
        elif (
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
            expected_versions=OLD_PACKAGE_VERSIONS,
        )
        rollback_database = validate_database_envelope(
            rollback_runtime,
            pre_source=True,
        )
        if rollback_database != state.get("database_envelope_before_cutover"):
            raise DeploymentError(
                "Database schema, ledger, incoming tables, queues, or capabilities "
                "drifted before rollback gate reopen."
            )
        state["database_envelope_after_rollback_dependencies"] = rollback_database
        write_state(state_path, state)
        inject("after_rollback_runtime")
        time.sleep(OPCACHE_WAIT_SECONDS)
        first = fpm_probe(OLD_PACKAGE_VERSIONS)
        time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
        second = fpm_probe(OLD_PACKAGE_VERSIONS)
        inject("after_rollback_fpm_probes")
        front_controller = restore_front_controller(
            state,
            state_path,
            reason="dependency_rollback_reopen",
        )
        inject("after_rollback_gate_open")
        state["rollback_fpm_probes"] = [first, second]
        state["rollback_runtime"] = rollback_runtime
        state["front_controller_restored"] = front_controller
        state["rollback_health"] = health_snapshot()
        rollback_final_runtime = runtime_probe(helper)
        validate_runtime_baseline(
            rollback_final_runtime,
            expected_versions=OLD_PACKAGE_VERSIONS,
        )
        rollback_final_database = validate_database_envelope(
            rollback_final_runtime,
            pre_source=True,
        )
        if rollback_final_database != state.get("database_envelope_before_cutover"):
            raise DeploymentError(
                "Database envelope drifted during rollback health verification."
            )
        state["database_envelope_after_rollback_health"] = rollback_final_database
        inject("after_rollback_health")
        state["static_gate_active"] = False
        state["containment_active"] = False
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
    require_database_envelope_validator()
    require_gate_helper()
    require_log_parser()
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
    validate_runtime_baseline(before_runtime, expected_versions=OLD_PACKAGE_VERSIONS)
    before_database = validate_database_envelope(before_runtime, pre_source=True)
    if before_database != receipt.get("database_envelope"):
        raise DeploymentError(
            "Cutover database envelope differs from the independently reviewed staged receipt."
        )
    old_fpm_preflight = fpm_probe(OLD_PACKAGE_VERSIONS)

    rollback_root = ensure_private_operations_root(ROLLBACK_ROOT, create=True)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rollback_directory = rollback_root / f"{CANDIDATE_LOCK_SHA256[:12]}-{timestamp}"
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
        "artifact": "buy-dtf-laravel-remember-cookie-cutover-v3",
        "handoff": {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256},
        "status": "preparing",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_receipt": str(receipt_path),
        "release_receipt_sha256": receipt_sha256,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "database_envelope_validator_sha256": DATABASE_ENVELOPE_VALIDATOR_SHA256,
        "gate_helper_sha256": GATE_HELPER_SHA256,
        "log_parser_sha256": LOG_PARSER_SHA256,
        "database_envelope_receipt": receipt["database_envelope_receipt"],
        "database_envelope_staged": receipt["database_envelope"],
        "database_envelope_before_cutover": before_database,
        "database_envelope_stable_identity": database_envelope_stable_identity(
            before_database
        ),
        "staged_vendor": str(shadow / "vendor"),
        "staged_cache": str(shadow / "bootstrap/cache"),
        "candidate_vendor_sha256": receipt["candidate_vendor_manifest"]["sha256"],
        "candidate_vendor_identity": receipt["candidate_vendor_identity"],
        "application_autoload_identity": receipt["application_autoload_identity"],
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
        **dependency_gate.initial_gate_state(),
        "gate_active": False,
        "gate_reassertions": [],
        "dependency_mutation_started": False,
        "vendor_exchange_intent": False,
        "vendor_exchange_complete": False,
        "cache_exchange_intent": False,
        "cache_exchange_complete": False,
        "cache_exchange_required": (
            receipt["candidate_cache_identity"] != receipt["retained_cache_identity"]
        ),
        "lock_replaced": False,
        "rollback_started": False,
        "rollback_complete": False,
    }
    write_state(state_path, state)
    log_collector: laravel_log_delta.RotationSafeLaravelLogCollector | None = None

    def inject(stage: str) -> None:
        if failure_injector is not None:
            failure_injector(stage)

    def capture_laravel_log(phase: str) -> dict[str, Any]:
        if log_collector is None:
            raise DeploymentError("Laravel log collector is not initialized.")
        try:
            capture = log_collector.capture()
        except (
            laravel_log_delta.LogContinuityError,
            laravel_log_delta.LaravelLogDeltaError,
            ValueError,
        ) as exception:
            raise DeploymentError(f"Laravel log delta failed closed: {exception}") from exception
        safe_capture = {"phase": phase, **capture}
        history = state.setdefault("laravel_log_capture_samples", [])
        if not isinstance(history, list):
            raise DeploymentError("Laravel log capture history is invalid.")
        history.append(safe_capture)
        write_state(state_path, state)
        return safe_capture

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
        validate_runtime_baseline(after_drain, expected_versions=OLD_PACKAGE_VERSIONS)
        pre_mutation_database = validate_database_envelope(
            after_drain,
            pre_source=True,
        )
        if pre_mutation_database != before_database:
            raise DeploymentError(
                "Production database envelope drifted under the static gate before mutation."
            )
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
        if require_candidate_vendor(staged_vendor) != receipt["candidate_vendor_identity"]:
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
        # Repeat the read-only helper at the last possible point before the
        # durable mutation boundary. No filesystem or dependency mutation has
        # occurred while this exact database receipt is created.
        final_pre_mutation_runtime = runtime_probe(helper)
        validate_runtime_baseline(
            final_pre_mutation_runtime,
            expected_versions=OLD_PACKAGE_VERSIONS,
        )
        final_pre_mutation_database = validate_database_envelope(
            final_pre_mutation_runtime,
            pre_source=True,
        )
        if final_pre_mutation_database != before_database:
            raise DeploymentError(
                "Production database envelope drifted immediately before dependency mutation."
            )
        database_gate_receipt = {
            "artifact": "buy-dtf-laravel-remember-cookie-gated-database-envelope-v3",
            "status": "pass",
            "phase": "immediately_before_dependency_mutation",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
            "validator_sha256": DATABASE_ENVELOPE_VALIDATOR_SHA256,
            "database_envelope": final_pre_mutation_database,
            "dependency_mutation_started": False,
            "migration_command_invoked": False,
            "migration_executed": False,
        }
        database_gate_receipt_path = (
            rollback_directory / "database-envelope-before-mutation-receipt.json"
        )
        database_gate_receipt_sha256 = dependency_gate.write_new_json(
            database_gate_receipt_path,
            database_gate_receipt,
        )
        state["database_envelope_after_drain"] = pre_mutation_database
        state["database_envelope_before_mutation"] = final_pre_mutation_database
        state["database_envelope_before_mutation_receipt"] = {
            "path": str(database_gate_receipt_path),
            "sha256": database_gate_receipt_sha256,
        }
        write_state(state_path, state)

        log_private_directory = rollback_directory / "laravel-log-private"
        try:
            log_collector = laravel_log_delta.RotationSafeLaravelLogCollector(
                LARAVEL_LOG_PATH,
                log_private_directory,
            )
        except (
            laravel_log_delta.LogContinuityError,
            ValueError,
        ) as exception:
            raise DeploymentError(
                f"Laravel log baseline failed closed before dependency mutation: {exception}"
            ) from exception
        state["laravel_log_monitor"] = {
            "status": "capturing",
            "classification": "private-do-not-commit",
            "private_directory": str(log_private_directory),
            "capture_state_path": str(log_collector.state_path),
            "capture_state_sha256": sha256_file(log_collector.state_path),
            "parser_sha256": LOG_PARSER_SHA256,
            "baseline_before_dependency_mutation": True,
        }
        write_state(state_path, state)

        # This durable boundary is written before the first dependency mutation.
        # Every subsequent failure retains/reasserts the reviewed gate and runs
        # boot-independent rollback instead of reopening a partial dependency set.
        state["dependency_mutation_started"] = True
        state["vendor_exchange_intent"] = True
        state["status"] = "dependency_mutation_armed"
        write_state(state_path, state)
        rename_exchange(live_vendor, staged_vendor)
        state["vendor_exchange_complete"] = True
        state["status"] = "vendor_exchanged"
        write_state(state_path, state)
        inject("after_vendor_exchange")

        if receipt["candidate_cache_identity"] == receipt["retained_cache_identity"]:
            require_cache_identity(live_cache, receipt["retained_cache_identity"])
            require_cache_identity(staged_cache, receipt["candidate_cache_identity"])
            state["cache_exchange_complete"] = True
            state["cache_exchange_skipped_identical"] = True
            state["status"] = "cache_identity_reused"
            write_state(state_path, state)
        else:
            state["cache_exchange_intent"] = True
            write_state(state_path, state)
            rename_exchange(live_cache, staged_cache)
            state["cache_exchange_complete"] = True
            state["status"] = "cache_exchanged"
            write_state(state_path, state)
        inject("after_cache_exchange")

        if require_candidate_vendor(live_vendor) != receipt["candidate_vendor_identity"]:
            raise DeploymentError("Live candidate vendor differs from its approved manifest.")
        if require_application_autoload(APP_ROOT) != receipt["application_autoload_identity"]:
            raise DeploymentError("Live optimized autoload differs from its approved identity.")
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
        validate_runtime_baseline(live_runtime, expected_versions=NEW_PACKAGE_VERSIONS)
        candidate_database = validate_database_envelope(
            live_runtime,
            pre_source=True,
        )
        if candidate_database != state.get("database_envelope_before_cutover"):
            raise DeploymentError(
                "Database envelope drifted after the candidate dependency exchange."
            )
        state["database_envelope_after_candidate_exchange"] = candidate_database
        write_state(state_path, state)
        inject("after_candidate_runtime")
        if sha256_file(APP_ROOT / "composer.lock") != CANDIDATE_LOCK_SHA256:
            raise DeploymentError("Live composer.lock differs from the approved candidate.")

        time.sleep(OPCACHE_WAIT_SECONDS)
        first_probe = fpm_probe(NEW_PACKAGE_VERSIONS)
        time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
        second_probe = fpm_probe(NEW_PACKAGE_VERSIONS)
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
        capture_laravel_log("candidate_health")
        inject("after_candidate_health")

        monitor_deadline = time.monotonic() + MONITOR_SECONDS
        monitor_samples: list[dict[str, Any]] = []
        while time.monotonic() < monitor_deadline:
            sample = {
                "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "health": health_snapshot(),
                "runtime": runtime_probe(helper),
            }
            validate_runtime_baseline(
                sample["runtime"], expected_versions=NEW_PACKAGE_VERSIONS
            )
            sample["database_envelope"] = validate_database_envelope(
                sample["runtime"],
                pre_source=True,
            )
            if sample["database_envelope"] != state.get(
                "database_envelope_before_cutover"
            ):
                raise DeploymentError(
                    "Database envelope drifted during candidate monitoring."
                )
            sample["laravel_log_delta"] = capture_laravel_log("monitor_sample")
            monitor_samples.append(sample)
            state["monitor_samples"] = monitor_samples
            write_state(state_path, state)
            remaining = monitor_deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(MONITOR_INTERVAL_SECONDS, remaining))

        final_monitor_health = health_snapshot()
        final_monitor_runtime = runtime_probe(helper)
        validate_runtime_baseline(
            final_monitor_runtime,
            expected_versions=NEW_PACKAGE_VERSIONS,
        )
        final_monitor_database = validate_database_envelope(
            final_monitor_runtime,
            pre_source=True,
        )
        if final_monitor_database != state.get("database_envelope_before_cutover"):
            raise DeploymentError("Database envelope drifted at monitor completion.")
        final_sample = {
            "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phase": "monitor_completion",
            "health": final_monitor_health,
            "runtime": final_monitor_runtime,
            "database_envelope": final_monitor_database,
        }
        monitor_samples.append(final_sample)
        state["monitor_samples"] = monitor_samples
        write_state(state_path, state)

        if log_collector is None:
            raise DeploymentError("Laravel log collector disappeared during monitoring.")
        finishing_collector = log_collector
        try:
            log_result = finishing_collector.finish()
        except (
            laravel_log_delta.LogContinuityError,
            laravel_log_delta.LaravelLogDeltaError,
            ValueError,
        ) as exception:
            raise DeploymentError(
                f"Laravel monitoring delta failed closed: {exception}"
            ) from exception
        finally:
            finishing_collector.close()
            log_collector = None
        if log_result.get("status") != "pass":
            raise DeploymentError("Laravel monitoring delta did not pass classification.")
        final_sample["laravel_log_delta"] = {
            "status": log_result["status"],
            "raw_manifest_sha256": log_result["raw_manifest_sha256"],
            "analysis_summary_sha256": log_result["analysis_sha256"],
            "capture_state_sha256": log_result["capture_state_sha256"],
        }

        monitor_samples_path = rollback_directory / "monitor-samples-private.json"
        monitor_samples_sha256 = dependency_gate.write_new_json(
            monitor_samples_path,
            {
                "artifact": "buy-dtf-laravel-remember-cookie-monitor-samples-v3",
                "classification": "private-do-not-commit",
                "status": "pass",
                "samples": monitor_samples,
            },
        )
        database_monitor_path = rollback_directory / "database-envelope-monitor-final.json"
        database_monitor_sha256 = dependency_gate.write_new_json(
            database_monitor_path,
            {
                "artifact": "buy-dtf-laravel-remember-cookie-database-monitor-v3",
                "status": "pass",
                "policy": "pre_source_exactly_zero",
                "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
                "validator_sha256": DATABASE_ENVELOPE_VALIDATOR_SHA256,
                "stable_identity": database_envelope_stable_identity(
                    final_monitor_database
                ),
                "database_envelope": final_monitor_database,
            },
        )

        state["runtime_at_monitor_completion"] = final_monitor_runtime
        state["health_at_monitor_completion"] = final_monitor_health
        state["database_envelope_at_monitor_completion"] = final_monitor_database
        state["monitor_samples_receipt"] = {
            "path": str(monitor_samples_path),
            "sha256": monitor_samples_sha256,
        }
        state["database_envelope_monitor_receipt"] = {
            "path": str(database_monitor_path),
            "sha256": database_monitor_sha256,
        }
        state["laravel_log_monitor"] = {
            "status": "analysis_pass_pending_independent_review",
            "classification": "private-do-not-commit",
            "private_directory": str(log_private_directory),
            "raw_manifest_path": log_result["raw_manifest_path"],
            "raw_manifest_sha256": log_result["raw_manifest_sha256"],
            "analysis_path": log_result["analysis_path"],
            "analysis_summary_sha256": log_result["analysis_sha256"],
            "capture_state_path": log_result["capture_state_path"],
            "capture_state_sha256": log_result["capture_state_sha256"],
            "parser_sha256": LOG_PARSER_SHA256,
        }
        state["rollback_retained_vendor_path"] = str(staged_vendor)
        if state.get("cache_exchange_skipped_identical") is True:
            state["rollback_retained_cache_path"] = str(live_cache)
            state["candidate_cache_duplicate_path"] = str(staged_cache)
        else:
            state["rollback_retained_cache_path"] = str(staged_cache)
            state["active_candidate_cache_path"] = str(live_cache)
        state["status"] = "monitor_analysis_pass_pending_independent_review"
        state["monitor_completed_at_utc"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        write_state(state_path, state)

        immutable_state_path = rollback_directory / "deployment-state-monitor-complete.json"
        immutable_state_sha256 = dependency_gate.write_new_json(
            immutable_state_path,
            state,
        )
        review_binding = laravel_log_delta.build_independent_review_binding(
            deployment_state_sha256=immutable_state_sha256,
            release_receipt_sha256=receipt_sha256,
            runner_sha256=sha256_file(Path(__file__).resolve()),
            runtime_helper_sha256=RUNTIME_HELPER_SHA256,
            parser_sha256=LOG_PARSER_SHA256,
            raw_manifest_sha256=log_result["raw_manifest_sha256"],
            analysis_summary_sha256=log_result["analysis_sha256"],
            monitor_samples_sha256=monitor_samples_sha256,
            database_envelope_sha256=database_monitor_sha256,
        )
        review_receipt_path = rollback_directory / "independent-log-review-receipt.json"
        review_request_path = rollback_directory / "independent-log-review-request.json"
        review_request_sha256 = dependency_gate.write_new_json(
            review_request_path,
            {
                "artifact": "buy-dtf-laravel-log-independent-review-request-v1",
                "status": "awaiting_independent_read_only_review",
                "classification": "private-do-not-commit",
                "created_at_utc": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                ),
                "evidence_binding": review_binding,
                "required_checks": laravel_log_delta.INDEPENDENT_REVIEW_CHECKS,
                "private_raw_manifest_path": log_result["raw_manifest_path"],
                "redacted_analysis_path": log_result["analysis_path"],
                "monitor_samples_path": str(monitor_samples_path),
                "database_envelope_path": str(database_monitor_path),
                "immutable_state_path": str(immutable_state_path),
                "expected_receipt_path": str(review_receipt_path),
                "finalization_requires_separate_token": True,
            },
        )
        state["independent_log_review"] = {
            "status": "awaiting",
            "binding": review_binding,
            "immutable_state_path": str(immutable_state_path),
            "immutable_state_sha256": immutable_state_sha256,
            "request_path": str(review_request_path),
            "request_sha256": review_request_sha256,
            "expected_receipt_path": str(review_receipt_path),
        }
        state["status"] = "awaiting_independent_log_review"
        write_state(state_path, state)
        print(
            "Candidate monitor passed automated checks and awaits independent "
            f"read-only log review. State: {state_path}"
        )
        return state_path
    except BaseException as exception:
        if log_collector is not None:
            log_collector.close()
        rollback_required = contain_cutover_failure(state, state_path, exception)
        if rollback_required:
            rollback_from_state(
                state,
                state_path,
                helper,
                failure_injector=failure_injector,
            )
        raise


def validate_private_log_evidence(
    private_directory: Path,
    raw_manifest_path: Path,
    analysis_path: Path,
    capture_state_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Reassemble and attest the private delta used by the parser."""

    directory_metadata = path_metadata(private_directory)
    if (
        directory_metadata.get("kind") != "directory"
        or directory_metadata.get("mode") != 0o700
        or directory_metadata.get("uid") != EXPECTED_APP_UID
    ):
        raise DeploymentError("Private Laravel log evidence directory metadata drifted.")
    evidence_gid = directory_metadata["gid"]

    def private_file(path: Path, expected_name: str) -> Path:
        resolved = require_regular_file(path)
        if resolved != private_directory / expected_name:
            raise DeploymentError("Private Laravel log evidence path differs.")
        if path_metadata(resolved) != {
            "kind": "file",
            "mode": 0o600,
            "uid": EXPECTED_APP_UID,
            "gid": evidence_gid,
        }:
            raise DeploymentError("Private Laravel log evidence metadata drifted.")
        return resolved

    raw_manifest_path = private_file(raw_manifest_path, "raw-manifest.json")
    analysis_path = private_file(analysis_path, "redacted-analysis.json")
    capture_state_path = private_file(capture_state_path, "capture-state.json")
    try:
        raw_manifest = json.loads(raw_manifest_path.read_text(encoding="utf-8"))
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        capture_state = json.loads(capture_state_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise DeploymentError("Private Laravel log evidence contains invalid JSON.") from exception
    if (
        not isinstance(capture_state, dict)
        or capture_state.get("artifact") != "buy-dtf-laravel-log-capture-state-v1"
        or capture_state.get("status") != "analysis_pass"
    ):
        raise DeploymentError("Laravel log capture state is not a complete analysis pass.")
    if (
        not isinstance(raw_manifest, dict)
        or raw_manifest.get("artifact") != "buy-dtf-laravel-log-private-raw-manifest-v1"
        or raw_manifest.get("classification") != "private-do-not-commit"
        or raw_manifest.get("status") != "captured"
        or not isinstance(raw_manifest.get("segments"), list)
    ):
        raise DeploymentError("Private Laravel log manifest is invalid.")
    if (
        not isinstance(analysis, dict)
        or analysis.get("artifact") != "buy-dtf-laravel-log-redacted-analysis-v1"
        or analysis.get("classification") != "message-free-redacted-summary"
        or analysis.get("status") != "pass"
        or not isinstance(analysis.get("analysis"), dict)
        or analysis["analysis"].get("status") != "pass"
        or not isinstance(analysis.get("segments"), list)
        or analysis.get("raw_manifest_sha256") != sha256_file(raw_manifest_path)
    ):
        raise DeploymentError("Redacted Laravel log analysis is not a complete pass.")

    expected_names = {"raw-manifest.json", "redacted-analysis.json", "capture-state.json"}
    framed = hashlib.sha256()
    captured_bytes = 0
    next_chunk_number = 1
    analysis_segments = analysis["segments"]
    if len(analysis_segments) != len(raw_manifest["segments"]):
        raise DeploymentError("Laravel log manifest and analysis segment counts differ.")
    for number, (segment, report) in enumerate(
        zip(raw_manifest["segments"], analysis_segments),
        start=1,
    ):
        if not isinstance(segment, dict) or not isinstance(report, dict):
            raise DeploymentError("Laravel log segment evidence is invalid.")
        segment_id = f"segment-{number:04d}"
        if segment.get("segment_id") != segment_id or report.get("segment_id") != segment_id:
            raise DeploymentError("Laravel log segment identities are not contiguous.")
        chunks = segment.get("chunks")
        if not isinstance(chunks, list):
            raise DeploymentError("Laravel log segment chunk inventory is invalid.")
        delta_parts: list[bytes] = []
        expected_start = segment.get("start_offset")
        if not isinstance(expected_start, int) or expected_start < 0:
            raise DeploymentError("Laravel log segment start offset is invalid.")
        for chunk in chunks:
            if not isinstance(chunk, dict) or set(chunk) != {
                "name",
                "bytes",
                "sha256",
                "start",
                "end",
            }:
                raise DeploymentError("Laravel log chunk receipt shape differs.")
            expected_name = f"{segment_id}-chunk-{next_chunk_number:04d}.bin"
            name = chunk.get("name")
            if name != expected_name:
                raise DeploymentError("Laravel log chunk name is invalid.")
            next_chunk_number += 1
            if name in expected_names:
                raise DeploymentError("Laravel log evidence repeats a private filename.")
            expected_names.add(name)
            chunk_path = private_file(private_directory / name, name)
            value = chunk_path.read_bytes()
            if (
                not isinstance(chunk.get("bytes"), int)
                or chunk["bytes"] < 0
                or len(value) != chunk["bytes"]
                or sha256_bytes(value) != chunk.get("sha256")
                or chunk.get("start") != expected_start
                or not isinstance(chunk.get("end"), int)
                or chunk["end"] != expected_start + len(value)
            ):
                raise DeploymentError("Laravel log chunk content or range differs.")
            expected_start = chunk["end"]
            delta_parts.append(value)
        if expected_start != segment.get("final_offset"):
            raise DeploymentError("Laravel log segment final offset differs.")
        delta = b"".join(delta_parts)
        if (
            len(delta) != segment.get("delta_bytes")
            or sha256_bytes(delta) != segment.get("delta_sha256")
            or report.get("delta_bytes") != len(delta)
            or report.get("delta_sha256") != sha256_bytes(delta)
        ):
            raise DeploymentError("Laravel log segment delta identity differs.")
        captured_bytes += len(delta)

        analysis_offset = segment.get("analysis_delta_offset")
        if not isinstance(analysis_offset, int) or not 0 <= analysis_offset <= len(delta):
            raise DeploymentError("Laravel log analysis offset is invalid.")
        context_receipt = segment.get("analysis_context")
        context = b""
        if context_receipt is not None:
            if not isinstance(context_receipt, dict) or set(context_receipt) != {
                "name",
                "bytes",
                "sha256",
            }:
                raise DeploymentError("Laravel log analysis context receipt is invalid.")
            context_name = context_receipt.get("name")
            if context_name != f"{segment_id}-analysis-context.bin":
                raise DeploymentError("Laravel log analysis context name is invalid.")
            if context_name in expected_names:
                raise DeploymentError("Laravel log evidence repeats a context filename.")
            expected_names.add(context_name)
            context_path = private_file(private_directory / context_name, context_name)
            context = context_path.read_bytes()
            if (
                len(context) != context_receipt.get("bytes")
                or sha256_bytes(context) != context_receipt.get("sha256")
            ):
                raise DeploymentError("Laravel log analysis context identity differs.")
        inspection = context + delta[analysis_offset:]
        if (
            report.get("analysis_bytes") != len(inspection)
            or report.get("analysis_sha256") != sha256_bytes(inspection)
        ):
            raise DeploymentError("Laravel log complete-entry replay differs from analysis.")
        replayed_analysis = laravel_log_delta.analyze_log_bytes(inspection)
        if report.get("analysis") != replayed_analysis or replayed_analysis.get("status") != "pass":
            raise DeploymentError("Laravel log complete-entry classification replay failed.")
        identifier = segment_id.encode("utf-8")
        framed.update(len(identifier).to_bytes(4, "big"))
        framed.update(identifier)
        framed.update(len(delta).to_bytes(8, "big"))
        framed.update(delta)

    actual_names = {item.name for item in private_directory.iterdir()}
    if actual_names != expected_names:
        raise DeploymentError("Private Laravel log evidence contains missing or extra files.")
    if (
        captured_bytes != raw_manifest.get("captured_bytes")
        or captured_bytes != analysis.get("captured_bytes")
        or captured_bytes != capture_state.get("captured_bytes")
        or framed.hexdigest() != raw_manifest.get("framed_delta_sha256")
        or framed.hexdigest() != analysis.get("framed_delta_sha256")
    ):
        raise DeploymentError("Laravel log aggregate framing identity differs.")
    replayed_aggregate = laravel_log_delta.aggregate_reports(analysis_segments)
    if replayed_aggregate != analysis.get("analysis") or replayed_aggregate.get("status") != "pass":
        raise DeploymentError("Laravel log aggregate classification replay failed.")
    return raw_manifest, analysis, capture_state


def load_pending_monitor_state(state_path: Path) -> tuple[dict[str, Any], Path]:
    """Load and revalidate every immutable input to independent finalization."""

    rollback_root = ensure_private_operations_root(ROLLBACK_ROOT, create=False)
    state_path = require_regular_file(state_path)
    if not is_relative_to(state_path, rollback_root):
        raise DeploymentError("Monitor state is outside the fixed rollback root.")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise DeploymentError("Monitor state is invalid JSON.") from exception
    if state.get("artifact") != "buy-dtf-laravel-remember-cookie-cutover-v3":
        raise DeploymentError("Monitor state has an unexpected artifact identity.")
    if state.get("handoff") != {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256}:
        raise DeploymentError("Monitor state references a different review handoff.")
    if state.get("status") != "awaiting_independent_log_review":
        raise DeploymentError("Monitor state is not awaiting independent log review.")
    if state.get("dependency_mutation_started") is not True:
        raise DeploymentError("Monitor state does not record the dependency mutation boundary.")
    if state.get("rollback_complete") is not False:
        raise DeploymentError("Monitor state is already rolled back or invalid.")
    if state.get("script_sha256") != sha256_file(Path(__file__).resolve()):
        raise DeploymentError("Monitor state was created by a different deployment script.")
    if state.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256:
        raise DeploymentError("Monitor state references a different runtime helper.")
    if (
        state.get("database_envelope_validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or state.get("gate_helper_sha256") != GATE_HELPER_SHA256
        or state.get("log_parser_sha256") != LOG_PARSER_SHA256
    ):
        raise DeploymentError("Monitor state references different reviewed control helpers.")
    validate_rollback_state_paths(state, state_path)

    state_directory = state_path.parent.resolve(strict=True)
    review = state.get("independent_log_review")
    log_monitor = state.get("laravel_log_monitor")
    monitor_item = state.get("monitor_samples_receipt")
    database_item = state.get("database_envelope_monitor_receipt")
    if not all(isinstance(item, dict) for item in (review, log_monitor, monitor_item, database_item)):
        raise DeploymentError("Monitor state has incomplete log or database evidence bindings.")
    assert isinstance(review, dict)
    assert isinstance(log_monitor, dict)
    assert isinstance(monitor_item, dict)
    assert isinstance(database_item, dict)

    immutable_state_path = require_regular_file(
        Path(str(review.get("immutable_state_path", ""))),
        str(review.get("immutable_state_sha256", "")),
    )
    request_path = require_regular_file(
        Path(str(review.get("request_path", ""))),
        str(review.get("request_sha256", "")),
    )
    monitor_samples_path = require_regular_file(
        Path(str(monitor_item.get("path", ""))),
        str(monitor_item.get("sha256", "")),
    )
    database_path = require_regular_file(
        Path(str(database_item.get("path", ""))),
        str(database_item.get("sha256", "")),
    )
    expected_fixed_paths = {
        immutable_state_path: state_directory / "deployment-state-monitor-complete.json",
        request_path: state_directory / "independent-log-review-request.json",
        monitor_samples_path: state_directory / "monitor-samples-private.json",
        database_path: state_directory / "database-envelope-monitor-final.json",
    }
    for actual, expected in expected_fixed_paths.items():
        if actual != expected:
            raise DeploymentError("Monitor evidence path is outside its durable state directory.")

    private_directory = require_real_directory(
        Path(str(log_monitor.get("private_directory", ""))),
        within=state_directory,
    )
    if private_directory != state_directory / "laravel-log-private":
        raise DeploymentError("Private Laravel log evidence directory is unexpected.")
    raw_manifest_path = require_regular_file(
        Path(str(log_monitor.get("raw_manifest_path", ""))),
        str(log_monitor.get("raw_manifest_sha256", "")),
    )
    analysis_path = require_regular_file(
        Path(str(log_monitor.get("analysis_path", ""))),
        str(log_monitor.get("analysis_summary_sha256", "")),
    )
    capture_state_path = require_regular_file(
        Path(str(log_monitor.get("capture_state_path", ""))),
        str(log_monitor.get("capture_state_sha256", "")),
    )
    if (
        raw_manifest_path != private_directory / "raw-manifest.json"
        or analysis_path != private_directory / "redacted-analysis.json"
        or capture_state_path != private_directory / "capture-state.json"
    ):
        raise DeploymentError("Laravel log evidence files are outside the private evidence set.")
    if log_monitor.get("status") != "analysis_pass_pending_independent_review":
        raise DeploymentError("Laravel log analysis is not pending a successful review.")
    if log_monitor.get("parser_sha256") != LOG_PARSER_SHA256:
        raise DeploymentError("Laravel log evidence references a different parser.")

    raw_manifest, analysis, capture_state = validate_private_log_evidence(
        private_directory,
        raw_manifest_path,
        analysis_path,
        capture_state_path,
    )
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        immutable_state = json.loads(immutable_state_path.read_text(encoding="utf-8"))
        monitor_receipt = json.loads(monitor_samples_path.read_text(encoding="utf-8"))
        database_receipt = json.loads(database_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise DeploymentError("Monitor evidence contains invalid JSON.") from exception
    if (
        not isinstance(monitor_receipt, dict)
        or monitor_receipt.get("artifact")
        != "buy-dtf-laravel-remember-cookie-monitor-samples-v3"
        or monitor_receipt.get("classification") != "private-do-not-commit"
        or monitor_receipt.get("status") != "pass"
        or monitor_receipt.get("samples") != state.get("monitor_samples")
    ):
        raise DeploymentError("Private monitoring sample receipt is invalid.")
    if (
        not isinstance(database_receipt, dict)
        or database_receipt.get("artifact")
        != "buy-dtf-laravel-remember-cookie-database-monitor-v3"
        or database_receipt.get("status") != "pass"
        or database_receipt.get("policy") != "pre_source_exactly_zero"
        or database_receipt.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256
        or database_receipt.get("validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or database_receipt.get("database_envelope")
        != state.get("database_envelope_at_monitor_completion")
        or database_receipt.get("database_envelope")
        != state.get("database_envelope_before_cutover")
        or database_receipt.get("stable_identity")
        != database_envelope_stable_identity(database_receipt["database_envelope"])
    ):
        raise DeploymentError("Final monitoring database-envelope receipt is invalid.")
    if (
        not isinstance(immutable_state, dict)
        or immutable_state.get("status")
        != "monitor_analysis_pass_pending_independent_review"
        or immutable_state.get("script_sha256") != state.get("script_sha256")
        or immutable_state.get("release_receipt_sha256")
        != state.get("release_receipt_sha256")
    ):
        raise DeploymentError("Immutable monitor-completion state is invalid.")
    expected_live_state = json.loads(json.dumps(immutable_state))
    expected_live_state["status"] = "awaiting_independent_log_review"
    expected_live_state["independent_log_review"] = review
    expected_live_state["updated_at_utc"] = state.get("updated_at_utc")
    if state != expected_live_state:
        raise DeploymentError("Mutable monitor state differs from its immutable snapshot.")
    if (
        capture_state.get("captured_bytes") != raw_manifest.get("captured_bytes")
        or analysis.get("captured_bytes") != raw_manifest.get("captured_bytes")
        or log_monitor.get("capture_state_sha256") != sha256_file(capture_state_path)
    ):
        raise DeploymentError("Laravel log capture receipts differ.")

    try:
        expected_binding = laravel_log_delta.build_independent_review_binding(
            deployment_state_sha256=sha256_file(immutable_state_path),
            release_receipt_sha256=str(state.get("release_receipt_sha256", "")),
            runner_sha256=sha256_file(Path(__file__).resolve()),
            runtime_helper_sha256=RUNTIME_HELPER_SHA256,
            parser_sha256=LOG_PARSER_SHA256,
            raw_manifest_sha256=sha256_file(raw_manifest_path),
            analysis_summary_sha256=sha256_file(analysis_path),
            monitor_samples_sha256=sha256_file(monitor_samples_path),
            database_envelope_sha256=sha256_file(database_path),
        )
    except laravel_log_delta.IndependentReviewError as exception:
        raise DeploymentError(f"Independent review evidence binding is invalid: {exception}") from exception
    if review.get("binding") != expected_binding:
        raise DeploymentError("Monitor state independent-review binding differs.")
    expected_receipt_path = state_directory / "independent-log-review-receipt.json"
    if Path(str(review.get("expected_receipt_path", ""))) != expected_receipt_path:
        raise DeploymentError("Independent-review receipt path is unexpected.")
    if (
        not isinstance(request, dict)
        or request.get("artifact")
        != "buy-dtf-laravel-log-independent-review-request-v1"
        or request.get("status") != "awaiting_independent_read_only_review"
        or request.get("evidence_binding") != expected_binding
        or request.get("required_checks")
        != laravel_log_delta.INDEPENDENT_REVIEW_CHECKS
        or request.get("expected_receipt_path") != str(expected_receipt_path)
    ):
        raise DeploymentError("Independent Laravel log-review request is invalid.")
    return state, expected_receipt_path


def verify_live_candidate_after_monitor(
    state: dict[str, Any],
    state_path: Path,
    helper: Path,
) -> dict[str, Any]:
    """Prove the candidate and exact rollback set before final success."""

    if os.geteuid() == 0:
        raise DeploymentError("Refusing to finalize application deployment as root.")
    validate_toolchain()
    app_root = require_real_directory(APP_ROOT)
    if (app_root.stat().st_uid, app_root.stat().st_gid) != (
        EXPECTED_APP_UID,
        EXPECTED_APP_GID,
    ):
        raise DeploymentError("Application owner/group differs during finalization.")
    require_regular_file(APP_ROOT / "composer.json", EXPECTED_LIVE_COMPOSER_JSON_SHA256)
    require_regular_file(APP_ROOT / "composer.lock", CANDIDATE_LOCK_SHA256)
    require_regular_file(APP_ROOT / "config/database.php", EXPECTED_DATABASE_CONFIG_SHA256)
    require_regular_file(helper, RUNTIME_HELPER_SHA256)
    require_regular_file(FRONT_CONTROLLER, EXPECTED_FRONT_CONTROLLER_SHA256)
    front_controller_identity = dependency_gate.file_identity(FRONT_CONTROLLER)
    if front_controller_identity.get("metadata") != (
        dependency_gate.reviewed_front_controller_metadata()
    ):
        raise DeploymentError("Front-controller metadata differs during finalization.")
    try:
        transition_history, latest_transition = dependency_gate.validate_transition_history(
            gate_context(state, state_path),
            state,
        )
    except dependency_gate.GateError as exception:
        raise DeploymentError(
            f"Front-controller transition history is invalid: {exception}"
        ) from exception
    if LARAVEL_MAINTENANCE_FILE.exists():
        raise DeploymentError("Laravel maintenance mode is unexpectedly active.")
    if source_manifest(APP_ROOT) != EXPECTED_SOURCE_MANIFEST:
        raise DeploymentError("Runtime source CAS differs during finalization.")
    candidate_vendor = require_candidate_vendor(APP_ROOT / "vendor")
    if candidate_vendor != state.get("candidate_vendor_identity"):
        raise DeploymentError("Live candidate vendor differs during finalization.")
    autoload = require_application_autoload(APP_ROOT)
    if autoload != state.get("application_autoload_identity"):
        raise DeploymentError("Live optimized autoload differs during finalization.")
    require_cache_identity(
        APP_ROOT / "bootstrap/cache",
        state["candidate_cache_identity"],
    )
    candidate_cache = cache_identity(APP_ROOT / "bootstrap/cache")
    runtime = runtime_probe(helper)
    validate_runtime_baseline(runtime, expected_versions=NEW_PACKAGE_VERSIONS)
    database = validate_database_envelope(runtime, pre_source=True)
    if database != state.get("database_envelope_before_cutover"):
        raise DeploymentError("Database envelope drifted before finalization.")

    retained_vendor = Path(str(state.get("staged_vendor", "")))
    if tree_manifest(retained_vendor) != EXPECTED_LIVE_VENDOR_MANIFEST:
        raise DeploymentError("Retained Laravel 12.69.0 vendor is not the exact rollback set.")
    require_regular_file(Path(str(state.get("old_lock_backup", ""))), EXPECTED_LIVE_LOCK_SHA256)
    require_regular_file(
        Path(str(state.get("front_controller_backup", ""))),
        EXPECTED_FRONT_CONTROLLER_SHA256,
    )
    retained_cache = Path(str(state.get("staged_cache", "")))
    require_cache_identity(retained_cache, EXPECTED_LIVE_CACHE_IDENTITY)
    health = health_snapshot()
    first_fpm = fpm_probe(NEW_PACKAGE_VERSIONS)
    time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
    second_fpm = fpm_probe(NEW_PACKAGE_VERSIONS)
    return {
        "status": "pass",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lock_sha256": sha256_file(APP_ROOT / "composer.lock"),
        "source_manifest": EXPECTED_SOURCE_MANIFEST,
        "front_controller": front_controller_identity,
        "front_controller_transition_count": len(transition_history),
        "front_controller_latest_transition": latest_transition,
        "candidate_vendor_identity": candidate_vendor,
        "application_autoload_identity": autoload,
        "candidate_cache_identity": candidate_cache,
        "runtime": runtime,
        "database_envelope": database,
        "health": health,
        "fpm_probes": [first_fpm, second_fpm],
        "retained_old_lock_sha256": EXPECTED_LIVE_LOCK_SHA256,
        "retained_old_vendor_manifest": EXPECTED_LIVE_VENDOR_MANIFEST,
        "retained_old_cache_identity": EXPECTED_LIVE_CACHE_IDENTITY,
    }


def finalize_monitor(
    state_path: Path,
    independent_receipt_path: Path,
    independent_receipt_sha256: str,
    approval_token: str,
    helper: Path,
) -> None:
    """Finalize only after an evidence-bound independent read-only log review."""

    if approval_token != FINALIZE_MONITOR_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed monitor-finalization token was not supplied.")
    require_database_envelope_validator()
    require_gate_helper()
    require_log_parser()
    state, expected_receipt_path = load_pending_monitor_state(state_path)
    independent_receipt_path = require_regular_file(
        independent_receipt_path,
        independent_receipt_sha256,
    )
    if independent_receipt_path != expected_receipt_path:
        raise DeploymentError("Independent log-review receipt is outside its fixed path.")
    try:
        independent_receipt = laravel_log_delta.validate_independent_review_receipt(
            independent_receipt_path,
            expected_sha256=independent_receipt_sha256,
            expected_binding=state["independent_log_review"]["binding"],
        )
    except laravel_log_delta.IndependentReviewError as exception:
        raise DeploymentError(f"Independent Laravel log review rejected: {exception}") from exception
    if independent_receipt["reviewed_at_utc"] < str(
        state.get("monitor_completed_at_utc", "")
    ):
        raise DeploymentError("Independent Laravel log review predates monitor completion.")

    # Invalid or missing review evidence above never mutates live state. Once the
    # independent pass is accepted, any candidate drift is a post-mutation
    # deployment failure and must use the reviewed containment and rollback path.
    try:
        final_verification = verify_live_candidate_after_monitor(state, state_path, helper)
    except BaseException as exception:
        rollback_required = contain_cutover_failure(state, state_path, exception)
        if rollback_required:
            rollback_from_state(state, state_path, helper)
        raise
    state["independent_log_review"]["status"] = "accepted"
    state["independent_log_review"]["receipt_path"] = str(independent_receipt_path)
    state["independent_log_review"]["receipt_sha256"] = independent_receipt_sha256
    state["independent_log_review"]["receipt"] = independent_receipt
    state["final_candidate_verification"] = final_verification
    state["status"] = "success"
    state["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_state(state_path, state)
    print(f"Dependency deployment finalized after independent log review: {state_path}")


def verify_recovered_old_live_state(
    state: dict[str, Any],
    helper: Path,
) -> dict[str, Any]:
    """Verify the complete old dependency and database envelope after recovery."""

    baseline = assert_production_baseline(helper)
    runtime = runtime_probe(helper)
    validate_runtime_baseline(runtime, expected_versions=OLD_PACKAGE_VERSIONS)
    database = validate_database_envelope(runtime, pre_source=True)
    if database != state.get("database_envelope_before_cutover"):
        raise DeploymentError("Database envelope drifted during recovery verification.")
    if scoped_processes():
        raise DeploymentError("A scoped Artisan/payout process is active after recovery.")
    first_fpm = fpm_probe(OLD_PACKAGE_VERSIONS)
    time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
    second_fpm = fpm_probe(OLD_PACKAGE_VERSIONS)
    return {
        "status": "pass",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline": baseline,
        "runtime": runtime,
        "database_envelope": database,
        "health": health_snapshot(),
        "fpm_probes": [first_fpm, second_fpm],
    }


def recover(state_path: Path, approval_token: str, helper: Path) -> None:
    if approval_token != RECOVERY_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed recovery approval token was not supplied.")
    require_database_envelope_validator()
    require_gate_helper()
    require_log_parser()
    rollback_root = ensure_private_operations_root(ROLLBACK_ROOT, create=False)
    state_path = require_regular_file(state_path)
    if not is_relative_to(state_path, rollback_root):
        raise DeploymentError("Recovery state is outside the fixed rollback root.")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise DeploymentError("Recovery state is invalid JSON.") from exception
    if state.get("artifact") != "buy-dtf-laravel-remember-cookie-cutover-v3":
        raise DeploymentError("Recovery state has an unexpected artifact identity.")
    if state.get("handoff") != {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256}:
        raise DeploymentError("Recovery state references a different review handoff.")
    if state.get("script_sha256") != sha256_file(Path(__file__).resolve()):
        raise DeploymentError("Recovery state was created by a different deployment script.")
    if state.get("runtime_helper_sha256") != RUNTIME_HELPER_SHA256:
        raise DeploymentError("Recovery state references a different runtime helper.")
    if (
        state.get("database_envelope_validator_sha256")
        != DATABASE_ENVELOPE_VALIDATOR_SHA256
        or state.get("gate_helper_sha256") != GATE_HELPER_SHA256
        or state.get("log_parser_sha256") != LOG_PARSER_SHA256
    ):
        raise DeploymentError("Recovery state references different reviewed control helpers.")
    if state.get("front_controller_metadata") != {
        "kind": "file",
        "mode": 0o644,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
    }:
        raise DeploymentError("Recovery state has invalid front-controller metadata.")
    validate_rollback_state_paths(state, state_path)
    context = gate_context(state, state_path)
    try:
        decision = dependency_gate.recovery_decision(
            context=context,
            state=state,
        )
    except dependency_gate.GateError as exception:
        raise DeploymentError(str(exception)) from exception
    state["front_controller_recovery_decision"] = decision
    write_state(state_path, state)
    if decision["action"] == "rollback_dependencies":
        containment = establish_rollback_gate(
            state,
            state_path,
            "explicit_recovery_entry",
        )
        state["explicit_recovery_containment"] = containment
        write_state(state_path, state)
        rollback_from_state(state, state_path, helper)
        return
    if decision["action"] == "restore_original":
        restoration = restore_front_controller(
            state,
            state_path,
            reason="explicit_pre_mutation_recovery",
        )
        state["explicit_recovery_restoration"] = restoration
        state["explicit_recovery_verification"] = verify_recovered_old_live_state(
            state,
            helper,
        )
        state["status"] = "recovered_before_dependency_mutation"
        state["gate_active"] = False
        state["gate_verified"] = False
        write_state(state_path, state)
        return
    state["explicit_recovery_verification"] = verify_recovered_old_live_state(
        state,
        helper,
    )
    state["status"] = "recovery_not_required_original_verified"
    write_state(state_path, state)


def rehearse(parent: Path) -> dict[str, Any]:
    parent = require_real_directory(parent)
    rehearsal_root = Path(
        tempfile.mkdtemp(prefix="buy-dtf-laravel-remember-cookie-rehearsal-", dir=parent)
    )
    results: dict[str, Any] = {
        "artifact": "buy-dtf-laravel-remember-cookie-atomic-exchange-rehearsal-v3",
        "artifact_review_status": ARTIFACT_REVIEW_STATUS,
        "handoff": {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256},
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "live_lock_sha256": EXPECTED_LIVE_LOCK_SHA256,
        "candidate_lock_sha256": CANDIDATE_LOCK_SHA256,
        "retained_vendor_manifest": EXPECTED_LIVE_VENDOR_MANIFEST,
        "candidate_vendor_manifest": EXPECTED_CANDIDATE_VENDOR_MANIFEST,
        "candidate_vendor_metadata_sha256": EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256,
        "candidate_vendor_executable_allowlist_sha256": (
            CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256
        ),
        "application_autoload_sha256": EXPECTED_APPLICATION_AUTOLOAD_SHA256,
        "retained_cache_identity": EXPECTED_LIVE_CACHE_IDENTITY,
        "candidate_cache_identity": EXPECTED_CANDIDATE_CACHE_IDENTITY,
        "maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
        "filesystem_device": rehearsal_root.stat().st_dev,
        "cutover_transitions": list(CUTOVER_TRANSITIONS),
        "rollback_transitions": list(ROLLBACK_TRANSITIONS),
        "scenarios": {},
    }

    try:
        def fixture(
            name: str,
            *,
            unbootable: bool = False,
            stale_live_cache: bool = False,
        ) -> dict[str, Any]:
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
            live_provider = (
                "Laravel\\\\Pail\\\\PailServiceProvider"
                if stale_live_cache
                else "production-provider"
            )
            (live_cache / "packages.php").write_text(
                f"<?php return ['{live_provider}'];\n",
                encoding="utf-8",
            )
            (live_cache / "services.php").write_text(
                f"<?php return ['providers' => ['{live_provider}']];\n",
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
                "candidate_vendor_identity": tree_metadata_identity(staged_vendor),
                "live_cache": live_cache,
                "staged_cache": staged_cache,
                "old_cache_identity": cache_identity(live_cache),
                "candidate_cache_identity": cache_identity(staged_cache),
                "live_cache_inode": (live_cache.stat().st_dev, live_cache.stat().st_ino),
                "staged_cache_inode": (staged_cache.stat().st_dev, staged_cache.stat().st_ino),
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
                if tree_metadata_identity(item["live_vendor"]) != item["candidate_vendor_identity"]:
                    raise DeploymentError("Rehearsal candidate vendor metadata drifted.")
                rename_exchange(item["live_vendor"], item["staged_vendor"])
            elif (
                live_hash == item["old_vendor_sha256"]
                and staged_hash == item["candidate_vendor_sha256"]
            ):
                if tree_metadata_identity(item["staged_vendor"]) != item["candidate_vendor_identity"]:
                    raise DeploymentError("Rehearsal retained candidate metadata drifted.")
            else:
                raise DeploymentError("Rehearsal recovery found unknown vendor identities.")

        def restore_cache_pair(item: dict[str, Any]) -> None:
            live_identity = cache_identity(item["live_cache"])
            staged_identity = cache_identity(item["staged_cache"])
            if item["candidate_cache_identity"] == item["old_cache_identity"]:
                if (
                    live_identity != item["old_cache_identity"]
                    or staged_identity != item["candidate_cache_identity"]
                ):
                    raise DeploymentError("Rehearsal identical cache identities drifted.")
                item["events"].append("identical_cache_exchange_skipped")
            elif (
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
            if tree_metadata_identity(item["live_vendor"]) != item["candidate_vendor_identity"]:
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
                if item["candidate_cache_identity"] != item["old_cache_identity"]:
                    rename_exchange(item["live_cache"], item["staged_cache"])
                else:
                    item["events"].append("identical_cache_exchange_skipped")
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
            if item["candidate_cache_identity"] != item["old_cache_identity"]:
                rename_exchange(item["live_cache"], item["staged_cache"])
            else:
                item["events"].append("identical_cache_exchange_skipped")
            atomic_copy(item["candidate_lock"], item["live_lock"])

        item = fixture("stale-dev-provider-success", stale_live_cache=True)
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

        item = fixture("identical-cache-idempotence", unbootable=True)
        original_cache_inodes = (
            (item["live_cache"].stat().st_dev, item["live_cache"].stat().st_ino),
            (item["staged_cache"].stat().st_dev, item["staged_cache"].stat().st_ino),
        )
        prepare_unbootable_candidate_state(item)
        recover_fixture(item)
        recover_fixture(item)
        recovered_cache_inodes = (
            (item["live_cache"].stat().st_dev, item["live_cache"].stat().st_ino),
            (item["staged_cache"].stat().st_dev, item["staged_cache"].stat().st_ino),
        )
        if recovered_cache_inodes != original_cache_inodes:
            raise DeploymentError("Repeated recovery moved identical bootstrap caches.")
        verify_restored(item)
        results["scenarios"]["identical_cache_recovery_is_idempotent"] = "pass"

        if os.geteuid() != 0:
            raise DeploymentError("Metadata-drift rehearsal requires root on a safe local tree.")
        item = fixture("candidate-owner-drift", unbootable=True)
        prepare_unbootable_candidate_state(item)
        candidate_tree_before = tree_manifest(item["live_vendor"])
        os.chown(item["live_vendor"] / "identity.txt", 33, 33)
        if tree_manifest(item["live_vendor"]) != candidate_tree_before:
            raise DeploymentError("Ownership-only rehearsal unexpectedly changed legacy manifest.")
        try:
            recover_fixture(item)
        except DeploymentError as exception:
            if "metadata drifted" not in str(exception):
                raise
        else:
            raise DeploymentError("Recovery accepted candidate ownership drift.")
        if sha256_file(item["front_controller"]) != MAINTENANCE_GATE_SHA256:
            raise DeploymentError("Metadata-drift refusal did not retain the static gate.")
        results["scenarios"]["candidate_owner_drift_fails_closed"] = "pass"

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
            "buy-dtf-laravel-remember-cookie-rehearsal-"
        ):
            raise DeploymentError("Refusing to remove an unrecognized rehearsal directory.")
        shutil.rmtree(rehearsal_root)


def describe() -> None:
    print(
        json.dumps(
            {
                "artifact": "buy-dtf-laravel-remember-cookie-dependency-review-v3",
                "artifact_review_status": ARTIFACT_REVIEW_STATUS,
                "handoff": {"filename": HANDOFF_FILENAME, "sha256": HANDOFF_SHA256},
                "application_root": str(APP_ROOT),
                "live_composer_json_sha256": EXPECTED_LIVE_COMPOSER_JSON_SHA256,
                "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
                "source_manifest": EXPECTED_SOURCE_MANIFEST,
                "old_vendor_manifest_sha256": EXPECTED_LIVE_VENDOR_MANIFEST_SHA256,
                "old_vendor_manifest": EXPECTED_LIVE_VENDOR_MANIFEST,
                "old_cache_identity": EXPECTED_LIVE_CACHE_IDENTITY,
                "old_lock_sha256": EXPECTED_LIVE_LOCK_SHA256,
                "candidate_lock_sha256": CANDIDATE_LOCK_SHA256,
                "candidate_vendor_manifest": EXPECTED_CANDIDATE_VENDOR_MANIFEST,
                "candidate_vendor_metadata_sha256": EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256,
                "candidate_vendor_executable_paths": list(
                    CANDIDATE_VENDOR_EXECUTABLE_PATHS
                ),
                "candidate_vendor_executable_allowlist_sha256": (
                    CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256
                ),
                "application_autoload_entries": EXPECTED_APPLICATION_AUTOLOAD_ENTRIES,
                "application_autoload_sha256": EXPECTED_APPLICATION_AUTOLOAD_SHA256,
                "candidate_cache_identity": EXPECTED_CANDIDATE_CACHE_IDENTITY,
                "database_config_sha256": EXPECTED_DATABASE_CONFIG_SHA256,
                "front_controller_sha256": EXPECTED_FRONT_CONTROLLER_SHA256,
                "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
                "database_envelope_validator_sha256": (
                    DATABASE_ENVELOPE_VALIDATOR_SHA256
                ),
                "gate_helper_sha256": GATE_HELPER_SHA256,
                "log_parser_sha256": LOG_PARSER_SHA256,
                "database_envelope": {
                    "schema_sha256": database_envelope.EXPECTED_SCHEMA_SHA256,
                    "migration_ledger_rows": database_envelope.EXPECTED_LEDGER_ROW_COUNT,
                    "migration_ledger_sha256": database_envelope.EXPECTED_LEDGER_SHA256,
                    "target_migration_entry_count": (
                        database_envelope.EXPECTED_TARGET_MIGRATION_ENTRY_COUNT
                    ),
                    "savedimages_item_meta_policy": (
                        "nullable_text_and_zero_nonnull_through_dependency_deployment"
                    ),
                    "incoming_order_tables_zero_rows": True,
                    "read_only": True,
                },
                "old_package_versions": OLD_PACKAGE_VERSIONS,
                "candidate_package_versions": NEW_PACKAGE_VERSIONS,
                "atomic_vendor_operation": "renameat2(RENAME_EXCHANGE)",
                "cache_exchange_required": (
                    EXPECTED_CANDIDATE_CACHE_IDENTITY != EXPECTED_LIVE_CACHE_IDENTITY
                ),
                "atomic_cache_operation": (
                    "renameat2(RENAME_EXCHANGE) when identities differ; "
                    "skipped for the frozen identical identities"
                ),
                "static_maintenance_gate_sha256": MAINTENANCE_GATE_SHA256,
                "static_gate_verification_routes": ["direct_origin", "public_cloudflare"],
                "durable_gate_transition_history": True,
                "laravel_log_delta": {
                    "rotation_safe": True,
                    "complete_entry_parser": True,
                    "raw_evidence": "private-do-not-commit",
                    "invalid_utf8_or_unparsed_data_fails_closed": True,
                    "independent_read_only_review_required": True,
                    "direct_success_before_independent_review": False,
                },
                "monitor_finalization_is_separate_action": True,
                "candidate_install_no_dev": True,
                "composer_bin_compat": "proxy",
                "expected_route_count": EXPECTED_ROUTE_COUNT,
                "release_root": str(RELEASE_ROOT),
                "rollback_root": str(ROLLBACK_ROOT),
                "read_only_preflight_available": True,
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
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--stage", action="store_true")
    action.add_argument("--cutover", action="store_true")
    action.add_argument("--finalize-monitor", action="store_true")
    action.add_argument("--recover", action="store_true")
    action.add_argument("--rehearse", action="store_true")
    parser.add_argument("--candidate-lock", type=Path)
    parser.add_argument("--release-receipt", type=Path)
    parser.add_argument("--release-receipt-sha256")
    parser.add_argument("--independent-review-receipt", type=Path)
    parser.add_argument("--independent-review-receipt-sha256")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--rehearsal-parent", type=Path)
    parser.add_argument("--approval-token")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    helper = Path(__file__).resolve().with_name("laravel_remember_cookie_runtime_probe.php")
    try:
        if arguments.describe:
            describe()
        elif arguments.preflight:
            if arguments.candidate_lock is None:
                raise DeploymentError("--preflight requires --candidate-lock.")
            require_regular_file(helper, RUNTIME_HELPER_SHA256)
            print(
                json.dumps(
                    production_preflight(arguments.candidate_lock, helper),
                    indent=2,
                    sort_keys=True,
                )
            )
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
        elif arguments.finalize_monitor:
            if (
                arguments.state is None
                or arguments.independent_review_receipt is None
                or arguments.independent_review_receipt_sha256 is None
                or arguments.approval_token is None
            ):
                raise DeploymentError(
                    "--finalize-monitor requires --state, --independent-review-receipt, "
                    "--independent-review-receipt-sha256, and --approval-token."
                )
            require_regular_file(helper, RUNTIME_HELPER_SHA256)
            with deployment_lock():
                finalize_monitor(
                    arguments.state,
                    arguments.independent_review_receipt,
                    arguments.independent_review_receipt_sha256,
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
