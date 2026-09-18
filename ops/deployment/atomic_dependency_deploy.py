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

EXPECTED_APP_UID = 1000
EXPECTED_APP_GID = 1000
EXPECTED_LIVE_COMPOSER_JSON_SHA256 = "7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872"
EXPECTED_LIVE_LOCK_SHA256 = "16eef909889a727717fccf52e9c7c23e8a0d2cc661777f6044abde97713d2579"
CANDIDATE_LOCK_SHA256 = "eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831"
EXPECTED_DATABASE_CONFIG_SHA256 = "d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9"
EXPECTED_SOURCE_MANIFEST_SHA256 = "46f6a1ffa03364b550395c89111a0d69a844d1379f3c5aba6ed5c1e17616abca"
EXPECTED_LIVE_VENDOR_MANIFEST_SHA256 = "738c326e7f8e9199d36d0bb754eff031c38c5f69603bb56baa3cd189c98dbdcc"
RUNTIME_HELPER_SHA256 = "deb44c9c1bccc24ec91ee4ea504184000f30525763aa497b415611509d711dae"

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


def health_snapshot() -> dict[str, int]:
    statuses: dict[str, int] = {}
    for url, allowed in NORMAL_HEALTH_CHECKS:
        completed = run(
            [
                "/usr/bin/curl",
                "--silent",
                "--show-error",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                "--connect-timeout",
                "5",
                "--max-time",
                "10",
                "--max-redirs",
                "0",
                url,
            ],
            cwd=APP_ROOT,
            timeout=15,
        )
        try:
            status = int(completed.stdout)
        except ValueError as exception:
            raise DeploymentError(f"Invalid HTTP status returned for {url}.") from exception
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


def assert_production_baseline(helper: Path, *, check_old_vendor: bool = True) -> dict[str, Any]:
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
    source = source_manifest(APP_ROOT)
    if source["sha256"] != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise DeploymentError("Production runtime-source CAS manifest differs from the approved baseline.")
    vendor = tree_manifest(APP_ROOT / "vendor")
    if check_old_vendor and vendor["sha256"] != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
        raise DeploymentError("Live vendor manifest differs from the retained rollback baseline.")
    return {"source": source, "vendor": vendor}


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

    receipt = {
        "artifact": "buy-dtf-dependency-release-v1",
        "status": "staged",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_path": str(release),
        "shadow_path": str(shadow),
        "candidate_lock_sha256": CANDIDATE_LOCK_SHA256,
        "live_composer_json_sha256": EXPECTED_LIVE_COMPOSER_JSON_SHA256,
        "approved_source_manifest": baseline["source"],
        "retained_vendor_manifest": baseline["vendor"],
        "candidate_vendor_manifest": vendor,
        "command_receipts": command_receipts,
        "health_before": before_health,
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "versions": {
            "laravel/framework": NEW_LARAVEL_VERSION,
            "guzzlehttp/guzzle": NEW_GUZZLE_VERSION,
        },
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
    if receipt.get("artifact") != "buy-dtf-dependency-release-v1" or receipt.get("status") != "staged":
        raise DeploymentError("Release receipt is not an approved staged release.")
    if receipt.get("candidate_lock_sha256") != CANDIDATE_LOCK_SHA256:
        raise DeploymentError("Release receipt references a different candidate lock.")
    shadow = Path(str(receipt.get("shadow_path", "")))
    shadow = require_real_directory(shadow, within=RELEASE_ROOT)
    require_regular_file(shadow / "composer.lock", CANDIDATE_LOCK_SHA256)
    vendor = tree_manifest(shadow / "vendor")
    if vendor != receipt.get("candidate_vendor_manifest"):
        raise DeploymentError("Staged vendor differs from the approved release receipt.")
    return receipt, shadow


def copy_cache_snapshot(source: Path, destination: Path) -> dict[str, Any]:
    source = require_real_directory(source, within=APP_ROOT)
    if destination.exists():
        raise DeploymentError("Cache backup destination already exists.")
    shutil.copytree(source, destination, symlinks=False)
    os.chmod(destination, 0o700)
    return tree_manifest(destination)


def restore_cache_snapshot(snapshot: Path, destination: Path) -> None:
    snapshot = require_real_directory(snapshot, within=ROLLBACK_ROOT)
    destination = require_real_directory(destination, within=APP_ROOT)
    for child in destination.iterdir():
        if child.is_symlink():
            raise DeploymentError(f"Refusing to remove symbolic cache entry: {child}")
        if child.is_dir():
            shutil.rmtree(child)
        elif child.is_file():
            child.unlink()
        else:
            raise DeploymentError(f"Refusing to remove special cache entry: {child}")
    for child in snapshot.iterdir():
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, symlinks=False)
        else:
            shutil.copy2(child, target, follow_symlinks=False)
    fsync_directory(destination)


def artisan(command: str, *arguments: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    allowed = {"down", "up", "package:discover"}
    if command not in allowed:
        raise DeploymentError(f"Refusing non-allowlisted Artisan command: {command}")
    return run(
        ["/usr/bin/php", "artisan", command, *arguments, "--no-ansi"],
        cwd=APP_ROOT,
        timeout=timeout,
    )


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


def rollback_from_state(state: dict[str, Any], state_path: Path, helper: Path) -> None:
    state["rollback_started"] = True
    write_state(state_path, state)
    try:
        require_regular_file(Path(state["old_lock_backup"]), EXPECTED_LIVE_LOCK_SHA256)
        if tree_manifest(Path(state["cache_backup"])) != state["cache_backup_manifest"]:
            raise DeploymentError("Rollback bootstrap cache backup differs from its recorded manifest.")
        if not state.get("maintenance_active"):
            secret = secrets.token_urlsafe(24)
            artisan("down", f"--secret={secret}")
            state["maintenance_active"] = True
            write_state(state_path, state)

        live_vendor = APP_ROOT / "vendor"
        staged_vendor = Path(state["staged_vendor"])
        live_manifest = tree_manifest(live_vendor)["sha256"]
        staged_manifest = tree_manifest(staged_vendor)["sha256"]
        if (
            live_manifest == state["candidate_vendor_sha256"]
            and staged_manifest == EXPECTED_LIVE_VENDOR_MANIFEST_SHA256
        ):
            rename_exchange(live_vendor, staged_vendor)
        elif live_manifest != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
            raise DeploymentError("Rollback cannot identify the retained old vendor safely.")

        live_lock = APP_ROOT / "composer.lock"
        live_lock_hash = sha256_file(live_lock)
        if live_lock_hash == CANDIDATE_LOCK_SHA256:
            atomic_copy(Path(state["old_lock_backup"]), live_lock, 0o664)
        elif live_lock_hash != EXPECTED_LIVE_LOCK_SHA256:
            raise DeploymentError("Rollback found an unrecognized live composer.lock.")

        restore_cache_snapshot(Path(state["cache_backup"]), APP_ROOT / "bootstrap/cache")
        artisan("package:discover", "--no-interaction")
        restore_cache_snapshot(Path(state["cache_backup"]), APP_ROOT / "bootstrap/cache")
        if tree_manifest(APP_ROOT / "bootstrap/cache") != state["cache_backup_manifest"]:
            raise DeploymentError("Exact bootstrap cache snapshot was not restored.")
        if tree_manifest(live_vendor)["sha256"] != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
            raise DeploymentError("Retained vendor did not return to the live path.")
        time.sleep(OPCACHE_WAIT_SECONDS)
        first = fpm_probe(OLD_LARAVEL_VERSION, OLD_GUZZLE_VERSION)
        time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
        second = fpm_probe(OLD_LARAVEL_VERSION, OLD_GUZZLE_VERSION)
        artisan("up")
        state["maintenance_active"] = False
        state["rollback_fpm_probes"] = [first, second]
        state["rollback_health"] = health_snapshot()
        state["rollback_complete"] = True
        state["status"] = "rolled_back"
        write_state(state_path, state)
    except BaseException:
        state["status"] = "rollback_failed_maintenance_retained"
        write_state(state_path, state)
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
    if scoped_processes():
        raise DeploymentError("A scoped Artisan/payout process is active.")
    before_health = health_snapshot()
    before_runtime = runtime_probe(helper)
    validate_runtime_baseline(before_runtime, laravel=OLD_LARAVEL_VERSION, guzzle=OLD_GUZZLE_VERSION)

    ROLLBACK_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(ROLLBACK_ROOT, 0o700)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rollback_directory = ROLLBACK_ROOT / f"{CANDIDATE_LOCK_SHA256[:12]}-{timestamp}"
    rollback_directory.mkdir(mode=0o700)
    state_path = rollback_directory / "deployment-state.json"
    old_lock_backup = rollback_directory / "composer.lock.before"
    atomic_copy(APP_ROOT / "composer.lock", old_lock_backup, 0o600)
    cache_backup = rollback_directory / "bootstrap-cache-before"
    cache_manifest = copy_cache_snapshot(APP_ROOT / "bootstrap/cache", cache_backup)

    state: dict[str, Any] = {
        "artifact": "buy-dtf-atomic-dependency-cutover-v1",
        "status": "preparing",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_receipt": str(receipt_path),
        "release_receipt_sha256": receipt_sha256,
        "staged_vendor": str(shadow / "vendor"),
        "candidate_vendor_sha256": receipt["candidate_vendor_manifest"]["sha256"],
        "old_lock_backup": str(old_lock_backup),
        "cache_backup": str(cache_backup),
        "cache_backup_manifest": cache_manifest,
        "health_before": before_health,
        "runtime_before": before_runtime,
        "maintenance_active": False,
        "exchange_intent": False,
        "exchange_complete": False,
        "lock_replaced": False,
        "rollback_started": False,
        "rollback_complete": False,
    }
    write_state(state_path, state)

    def inject(stage: str) -> None:
        if failure_injector is not None:
            failure_injector(stage)

    try:
        secret = secrets.token_urlsafe(24)
        artisan("down", f"--secret={secret}")
        state["maintenance_active"] = True
        state["status"] = "maintenance"
        write_state(state_path, state)
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
        repeated_baseline = assert_production_baseline(helper)
        if repeated_baseline != baseline:
            raise DeploymentError("Production CAS baseline changed during the maintenance drain.")

        live_vendor = APP_ROOT / "vendor"
        staged_vendor = shadow / "vendor"
        if tree_manifest(staged_vendor) != receipt["candidate_vendor_manifest"]:
            raise DeploymentError("Staged vendor changed during the maintenance drain.")
        if live_vendor.stat().st_dev != staged_vendor.stat().st_dev:
            raise DeploymentError("Live and staged vendor are not on the same filesystem.")
        state["exchange_intent"] = True
        write_state(state_path, state)
        rename_exchange(live_vendor, staged_vendor)
        state["exchange_complete"] = True
        state["status"] = "vendor_exchanged"
        write_state(state_path, state)
        inject("after_exchange")

        if tree_manifest(live_vendor) != receipt["candidate_vendor_manifest"]:
            raise DeploymentError("Live candidate vendor differs from its approved manifest.")
        if tree_manifest(staged_vendor)["sha256"] != EXPECTED_LIVE_VENDOR_MANIFEST_SHA256:
            raise DeploymentError("Retained old vendor differs after atomic exchange.")

        atomic_copy(shadow / "composer.lock", APP_ROOT / "composer.lock", 0o664)
        state["lock_replaced"] = True
        state["status"] = "lock_replaced"
        write_state(state_path, state)
        inject("after_lock")

        artisan("package:discover", "--no-interaction")
        inject("after_package_discovery")
        live_runtime = runtime_probe(helper)
        validate_runtime_baseline(live_runtime, laravel=NEW_LARAVEL_VERSION, guzzle=NEW_GUZZLE_VERSION)
        if sha256_file(APP_ROOT / "composer.lock") != CANDIDATE_LOCK_SHA256:
            raise DeploymentError("Live composer.lock differs from the approved candidate.")

        time.sleep(OPCACHE_WAIT_SECONDS)
        first_probe = fpm_probe(NEW_LARAVEL_VERSION, NEW_GUZZLE_VERSION)
        time.sleep(OPCACHE_SECOND_PROBE_DELAY_SECONDS)
        second_probe = fpm_probe(NEW_LARAVEL_VERSION, NEW_GUZZLE_VERSION)
        state["candidate_fpm_probes"] = [first_probe, second_probe]
        write_state(state_path, state)

        artisan("up")
        state["maintenance_active"] = False
        state["status"] = "monitoring"
        state["health_after"] = health_snapshot()
        write_state(state_path, state)

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
        write_state(state_path, state)
        print(f"Dependency cutover complete. State/receipt: {state_path}")
        return state_path
    except BaseException as exception:
        state["failure_class"] = type(exception).__name__
        state["failure_message"] = str(exception)
        state["status"] = "failed_rolling_back"
        write_state(state_path, state)
        rollback_from_state(state, state_path, helper)
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
    if state.get("artifact") != "buy-dtf-atomic-dependency-cutover-v1":
        raise DeploymentError("Recovery state has an unexpected artifact identity.")
    rollback_from_state(state, state_path, helper)


def rehearse(parent: Path) -> dict[str, Any]:
    parent = require_real_directory(parent)
    rehearsal_root = Path(tempfile.mkdtemp(prefix="buy-dtf-dependency-rehearsal-", dir=parent))
    results: dict[str, Any] = {
        "artifact": "buy-dtf-atomic-exchange-rehearsal-v1",
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "filesystem_device": rehearsal_root.stat().st_dev,
        "scenarios": {},
    }
    try:
        def fixture(name: str) -> tuple[Path, Path, Path, Path, str, str]:
            root = rehearsal_root / name
            live = root / "application/vendor"
            staged = root / "release/vendor"
            live.mkdir(mode=0o700, parents=True)
            staged.mkdir(mode=0o700, parents=True)
            (live / "identity.txt").write_text("retained-old-vendor\n", encoding="utf-8")
            (staged / "identity.txt").write_text("approved-new-vendor\n", encoding="utf-8")
            live_lock = root / "application/composer.lock"
            candidate_lock = root / "release/composer.lock"
            live_lock.write_text("old-lock\n", encoding="utf-8")
            candidate_lock.write_text("candidate-lock\n", encoding="utf-8")
            return (
                live,
                staged,
                live_lock,
                candidate_lock,
                tree_manifest(live)["sha256"],
                tree_manifest(staged)["sha256"],
            )

        live, staged, live_lock, candidate_lock, old_hash, candidate_hash = fixture("success")
        rename_exchange(live, staged)
        atomic_copy(candidate_lock, live_lock)
        if tree_manifest(live)["sha256"] != candidate_hash or tree_manifest(staged)["sha256"] != old_hash:
            raise DeploymentError("Successful rehearsal did not atomically exchange vendor identities.")
        if live_lock.read_text(encoding="utf-8") != "candidate-lock\n":
            raise DeploymentError("Successful rehearsal did not atomically replace the lock.")
        results["scenarios"]["success"] = "pass"

        live, staged, live_lock, _candidate_lock, old_hash, candidate_hash = fixture("exchange-failure")
        try:
            rename_exchange(live, staged)
            raise DeploymentError("injected-post-exchange-failure")
        except DeploymentError as exception:
            if str(exception) != "injected-post-exchange-failure":
                raise
            if tree_manifest(live)["sha256"] == candidate_hash:
                rename_exchange(live, staged)
        if tree_manifest(live)["sha256"] != old_hash or tree_manifest(staged)["sha256"] != candidate_hash:
            raise DeploymentError("Post-exchange failure rehearsal did not restore both vendors.")
        if live_lock.read_text(encoding="utf-8") != "old-lock\n":
            raise DeploymentError("Post-exchange failure rehearsal unexpectedly changed the lock.")
        results["scenarios"]["post_exchange_failure_rollback"] = "pass"

        live, staged, live_lock, candidate_lock, old_hash, candidate_hash = fixture("failure")
        old_lock_copy = live_lock.read_bytes()
        try:
            rename_exchange(live, staged)
            atomic_copy(candidate_lock, live_lock)
            raise DeploymentError("injected-post-lock-failure")
        except DeploymentError as exception:
            if str(exception) != "injected-post-lock-failure":
                raise
            if tree_manifest(live)["sha256"] == candidate_hash:
                rename_exchange(live, staged)
            atomic_write(live_lock, old_lock_copy)
        if tree_manifest(live)["sha256"] != old_hash or tree_manifest(staged)["sha256"] != candidate_hash:
            raise DeploymentError("Failure rehearsal did not restore the old vendor.")
        if live_lock.read_text(encoding="utf-8") != "old-lock\n":
            raise DeploymentError("Failure rehearsal did not restore the old lock.")
        results["scenarios"]["post_lock_failure_rollback"] = "pass"

        live, staged, live_lock, candidate_lock, old_hash, candidate_hash = fixture(
            "package-discovery-failure"
        )
        cache = live.parent / "bootstrap/cache"
        cache.mkdir(mode=0o700, parents=True)
        (cache / "packages.php").write_text("retained-old-cache\n", encoding="utf-8")
        cache_backup = (cache / "packages.php").read_bytes()
        old_lock_copy = live_lock.read_bytes()
        try:
            rename_exchange(live, staged)
            atomic_copy(candidate_lock, live_lock)
            (cache / "packages.php").write_text("candidate-cache\n", encoding="utf-8")
            raise DeploymentError("injected-package-discovery-failure")
        except DeploymentError as exception:
            if str(exception) != "injected-package-discovery-failure":
                raise
            if tree_manifest(live)["sha256"] == candidate_hash:
                rename_exchange(live, staged)
            atomic_write(live_lock, old_lock_copy)
            atomic_write(cache / "packages.php", cache_backup)
        if tree_manifest(live)["sha256"] != old_hash or tree_manifest(staged)["sha256"] != candidate_hash:
            raise DeploymentError("Package-discovery failure rehearsal did not restore both vendors.")
        if live_lock.read_text(encoding="utf-8") != "old-lock\n":
            raise DeploymentError("Package-discovery failure rehearsal did not restore the lock.")
        if (cache / "packages.php").read_text(encoding="utf-8") != "retained-old-cache\n":
            raise DeploymentError("Package-discovery failure rehearsal did not restore the cache.")
        results["scenarios"]["package_discovery_failure_rollback"] = "pass"

        live, staged, live_lock, _candidate_lock, old_hash, candidate_hash = fixture("interruption")
        try:
            rename_exchange(live, staged)
            raise InterruptedError("injected-interruption-after-exchange")
        except InterruptedError:
            if tree_manifest(live)["sha256"] == candidate_hash:
                rename_exchange(live, staged)
        if tree_manifest(live)["sha256"] != old_hash or tree_manifest(staged)["sha256"] != candidate_hash:
            raise DeploymentError("Interruption rehearsal did not restore both vendors.")
        if live_lock.read_text(encoding="utf-8") != "old-lock\n":
            raise DeploymentError("Interruption rehearsal unexpectedly changed the lock.")
        results["scenarios"]["interruption_after_exchange_rollback"] = "pass"

        live, staged, _live_lock, _candidate_lock, old_hash, candidate_hash = fixture("double-exchange")
        rename_exchange(live, staged)
        rename_exchange(live, staged)
        if tree_manifest(live)["sha256"] != old_hash or tree_manifest(staged)["sha256"] != candidate_hash:
            raise DeploymentError("Double-exchange rehearsal did not restore both directories.")
        results["scenarios"]["double_exchange_recovery"] = "pass"
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
