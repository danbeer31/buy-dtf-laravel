#!/usr/bin/env python3
"""Stage, deploy, verify, and source-roll back the BuyDTF alpha repair.

The nullable Saved Image metadata schema is already installed and is immutable
input to this replacement artifact.  Every mode requires its exact reviewed
schema and migration-ledger identity.  No mode invokes a migration command,
including a pretend or reverse operation.  Staging and cutover remain separate
modes with separate exact approval tokens.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
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


sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_alpha_gate_controls as source_controls
import production_alpha_scheduler_guard as scheduler_controls

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

TARGET_COMMIT = "b02fce3213fc632891036f1b5c98b9cddb94e499"
ARTIFACT_BASE_COMMIT = "307b99e9429ca4623c72cc121e12997bdb4dfcad"
TARGET_SHORT = TARGET_COMMIT[:8]
HANDOFF_SHA256 = "ba9fd4dcf5fa5854b2e23418e0cd6ed8799874494a0341c726302b92a5acc127"
RETIRED_ARTIFACT_COMMIT = "c43f39f556d057c99bb01e95ee7ca68658c05232"
EXPECTED_ARCHIVE_SHA256 = "3067bca578201a39254d8544b633a04ff6a9e43fc0de2a2783a95ccde9a1bfcd"
EXPECTED_MANIFEST_SHA256 = "1821ba8099fafb2ddd48dd75f0a6ee8abbb43d83d5fafda2de9319022750b9a2"
EXPECTED_HELPER_SHA256 = "839588fe2930e1e673c507b05f7ccf15d7166329d66c1563775154cd7030d200"
EXPECTED_MIGRATION_SHA256 = "992fbfe8086732e9bde10be89c3f52ddb4fef49edfdec12b744377c2e4181bbf"
MIGRATION_RELATIVE_PATH = Path(
    "database/migrations/2026_10_01_120000_add_item_meta_to_savedimages_table.php"
)
TARGET_MIGRATION = "2026_10_01_120000_add_item_meta_to_savedimages_table"
TARGET_TABLE = "savedimages"
TARGET_COLUMN = "item_meta"
EXPECTED_RUNTIME_PATHS = 11
EXPECTED_ADDITIONS = 1
EXPECTED_REPLACEMENTS = 10

SCHEMA_STATE = "installed_schema_source_only_v1"
EXPECTED_SCHEMA_SHA256 = "5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da"
EXPECTED_LEDGER_ROW_COUNT = 21
EXPECTED_LEDGER_SHA256 = "f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53"
EXPECTED_TARGET_MIGRATION_ENTRIES = 1
EXPECTED_SCHEMA_WITHOUT_ITEM_META_SHA256 = (
    "4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed"
)
EXPECTED_LEDGER_WITHOUT_TARGET_ROW_COUNT = 20
EXPECTED_LEDGER_WITHOUT_TARGET_SHA256 = (
    "3168a7da9ca4aad0a81e673ec61c1647242916d054768f4dd48ff4b9d7eb28d4"
)
EXPECTED_PRE_SOURCE_CAS_SHA256 = "0ceca182384a8e68560ec542c0c2c0c695971b8488321ca0899ea7a880d6fd17"
EXPECTED_TARGET_SOURCE_CAS_SHA256 = "b3379cd90676d8b3214371e17ffd3278cd43ba1885a6223b12998a8b40e5ea27"

EXPECTED_LOG_GUARD_SHA256 = "75921c4a9f1b9a21d710c7792900014eb517f2e936a97c82ff542dd3c208dd28"

RETIRED_RUNNER_SHA256S = frozenset(
    {
        "59bbd90cafa8d1b5efd56a6c40667924193e37539f4340e4b6163c6274425cab",
        "76cfff204e86ee1119251b1d79931b1219cd19704b099f75d4e3db202ffe5b17",
        "25da4ddef0b4eb088cdedadf4848b1286a389760942493717e52d00f02c014df",
        "880d6ec6cb1ca5cee95964cf48843384afbaaeb73e835d03850e32de92aa21ab",
        "d3c1a26bb1081bb47149eb2b34787d747e56a4db4ef0eb4668f62e3baf231a3d",
    }
)
RETIRED_RELEASE_RECEIPT_SHA256S = frozenset(
    {"15271bdf4a33a85f247bbcaba45cb115b1beed429dd6bc48349fbe4a84bc7eee",
     "5621e1aad4c25bbffa5fad0f858358458595491b6a83c28ec8fc543aa6dd3f2d",
     "6734f82816d511623e54d68718ae10ff55376ecfdf56b03782e6d6caab87642e"}
)
RETIRED_RELEASE_RECEIPT_PATHS = frozenset(
    {
        "/var/www/buy-dtf/storage/app/private/operations/"
        "production-alpha-transparency-releases/"
        "5b2d06cd-20261002T021532Z/release-receipt.json"
        ,"/var/www/buy-dtf/storage/app/private/operations/"
        "production-alpha-transparency-releases/"
        "b02fce32-20261004T234125Z/release-receipt.json"
        ,"/var/www/buy-dtf/storage/app/private/operations/"
        "production-alpha-transparency-releases/"
        "b02fce32-20261005T024550Z/release-receipt.json"
    }
)

EXPECTED_COMPOSER_LOCK_SHA256 = "77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d"
EXPECTED_VENDOR_MANIFEST_SHA256 = "7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8"
EXPECTED_CACHE_MANIFEST_SHA256 = "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9"
EXPECTED_PACKAGES_SHA256 = "21da8f9ed19687e708cc7bc5cc59394c6fcdf9b9deadf617ae70526f815a1db0"
EXPECTED_SERVICES_SHA256 = "1f7623b2b4ffd2c4099fb34ad86fc96c1479e27bf81b1b0ba328c988cc4ffcb5"
EXPECTED_FRONT_CONTROLLER_SHA256 = "eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9"

# Laravel 12.69.1 closeout is accepted. This read-only freeze replaces the
# historical dependency envelope. Staging and cutover need separate authority.
DEPENDENCY_ENVELOPE_FROZEN = True
DEPENDENCY_ENVELOPE_STATUS = "post_laravel_12_69_1_frozen_review_required"
LOCAL_CORRECTION_REVIEW_ONLY = True

STAGE_APPROVAL_TOKEN = f"STAGE-BUYDTF-ALPHA-V5-{TARGET_COMMIT[:16]}"
DEPLOY_APPROVAL_TOKEN = f"DEPLOY-BUYDTF-ALPHA-V5-{TARGET_COMMIT[:16]}"
RECOVERY_APPROVAL_TOKEN = f"RECOVER-BUYDTF-ALPHA-V5-{TARGET_COMMIT[:16]}"

CONTROL_FILES = {'production_alpha_scheduler_guard.py': 'd4334e0181ececbd76d140711998f1d143f648dc9a4de85f413f2083354b6489', 'production_alpha_process_scope_probe.php': '1dca015bffdaf4433ff00ecb0569faad0928c28a726b827f773d4cae4b4737c6', 'production_alpha_scheduler_probe.php': '91e81065a4add34e916674c2a7fcc3ebe5f867324ec350dc9220214102cf0d80', 'production_alpha_gate_controls.py': '2719da67c6d425e5fa4bef70aade0789aba1deccfaf09f8992c8674883c65c00', 'production_alpha_dependency_envelope.json': '04850fe3aef14981c92f5b2af373bd136cfb6fead456d86fcab7233acb009fd1', 'laravel_dependency_gate.py': 'b93c08f58a08333120369c1cc75c60631d621c3a8099ca3967065721c45679f5', 'laravel_nginx_identity.py': '1243fea2757aca89f586ec4b322b0d23ee1e19b2d027c21bd6523e71e6e6e8e0', 'laravel_fpm_opcache_probe.php': 'b8b34f87d45a0c000cc0df7917496631320cfbdcca1ff44bc41741ce0d569262'}

DRAIN_SECONDS = 65
OPCACHE_WAIT_SECONDS = 7
MONITOR_SECONDS = 30 * 60
MONITOR_INTERVAL_SECONDS = 60
LOG_CONTINUITY_ANCHOR_BYTES = 64 * 1024
LOG_ENTRY_CONTEXT_BYTES = 1024 * 1024
LOG_ENTRY_HEADER_BYTES = re.compile(
    br"(?m)^\[[^\]\r\n]+\]\s+[A-Za-z0-9_.-]+\."
    br"(?:DEBUG|INFO|NOTICE|WARNING|ERROR|CRITICAL|ALERT|EMERGENCY):"
)
LOG_HEADER_LIKE_BYTES = re.compile(
    br"^\[[^\]\r\n]+\]\s+[A-Za-z0-9_.-]+\.[A-Za-z]+:"
)

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
MAINTENANCE_GATE_BYTES = source_controls.dependency_gate.MAINTENANCE_GATE_BYTES
EXPECTED_GATE_SHA256 = source_controls.dependency_gate.EXPECTED_GATE_SHA256


def source_gate_context(state, state_path, *, restoration=False, front_controller=None, application_root=None):
    source_controls.APP_ROOT=application_root or APP_ROOT
    source_controls.FRONT_CONTROLLER=front_controller or FRONT_CONTROLLER
    try:
        if mutation_has_started(state):
            return source_controls.post_mutation_emergency_gate_context(state,state_path)
        return source_controls.gate_context(state,state_path,allow_frozen_policy_for_exact_existing_gate=restoration)
    except source_controls.DeploymentError as error: raise DeploymentError(str(error)) from error


def full_source_identity(*, target):
    try:return source_controls.require_source_identity(APP_ROOT,target=target)
    except source_controls.DeploymentError as error:raise DeploymentError(str(error)) from error


def environment_identity():
    source_controls.APP_ROOT=APP_ROOT; source_controls.FRONT_CONTROLLER=FRONT_CONTROLLER
    try:
        fpm=source_controls.require_frozen_fpm_opcache(source_controls.frozen_envelope()['fpm_opcache'])
        nginx=source_controls.verify_read_only_nginx()
        configuration=source_controls.require_configuration_identity()
    except source_controls.DeploymentError as error:raise DeploymentError(str(error)) from error
    return {'fpm_opcache':fpm,'nginx':nginx,'configuration_sha256':configuration,'frozen_envelope_sha256':source_controls.ENVELOPE_SHA256}



class DeploymentError(source_controls.DeploymentError):
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
    if document.get("application_target_commit") != TARGET_COMMIT:
        raise DeploymentError("The manifest application target differs from the runner.")
    if document.get("artifact_status") != "frozen_review_only_non_stageable":
        raise DeploymentError("The manifest pre-freeze status differs from the runner.")
    handoff = document.get("current_handoff", {})
    if (
        handoff.get("name") != "buy-dtf-codie-handoff-2026-10-02.md"
        or handoff.get("sha256") != HANDOFF_SHA256
    ):
        raise DeploymentError("The manifest handoff identity differs from the runner.")
    if document.get("frozen_dependency_envelope_sha256") != source_controls.ENVELOPE_SHA256 or document.get("complete_runtime_source") != {"before":source_controls.frozen_envelope()["source"],"after":source_controls.frozen_envelope()["target_source"]}:
        raise DeploymentError("Manifest complete runtime/dependency envelope differs")
    envelope = document.get("dependency_envelope", {})
    if (
        envelope.get("status") != DEPENDENCY_ENVELOPE_STATUS
        or envelope.get("stageable") is not False
        or envelope.get("deployable") is not False
        or document.get("retired_artifact_commit") != RETIRED_ARTIFACT_COMMIT
        or document.get("retired_runner_sha256s")
        != sorted(RETIRED_RUNNER_SHA256S)
    ):
        raise DeploymentError("The manifest pre-freeze gate differs from the runner.")
    if document.get("hash_algorithm") != "sha256 over exact raw file bytes":
        raise DeploymentError("The manifest does not declare raw-byte hashing.")
    if document.get("scheduler_policy") != scheduler_controls.POLICY or document.get("scheduler_policy_sha256") != scheduler_controls.POLICY_SHA256:
        raise DeploymentError("Manifest scheduler policy differs from the frozen control.")
    if document.get("expected_schema_sha256") != EXPECTED_SCHEMA_SHA256:
        raise DeploymentError("The manifest schema baseline differs from the runner.")
    ledger = document.get("expected_ledger", {})
    if (
        ledger.get("row_count") != EXPECTED_LEDGER_ROW_COUNT
        or ledger.get("sha256") != EXPECTED_LEDGER_SHA256
        or ledger.get("target_entry_count") != EXPECTED_TARGET_MIGRATION_ENTRIES
    ):
        raise DeploymentError("The manifest ledger baseline differs from the runner.")
    migration = document.get("migration", {})
    if (
        migration.get("name") != TARGET_MIGRATION
        or migration.get("expected_live_state") != "absent"
        or migration.get("installed_schema_required") is not True
        or migration.get("source_install_only") is not True
        or migration.get("migration_command_allowed") is not False
        or migration.get("migration_pretend_allowed") is not False
        or migration.get("migration_reverse_allowed") is not False
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
        raise DeploymentError(
            f"The {EXPECTED_RUNTIME_PATHS}-path {label} source CAS differs from baseline."
        )
    return snapshot


def scoped_processes(*, scope_receipts: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    patterns = (
        "artisan migrate",
        "artisan stripe:sync-payouts",
        "artisan accounting:reconcile-stripe-holding",
        "artisan qbo:refresh-admin-cache",
        "artisan queue:",
        "artisan schedule:",
        "composer install",
        "composer update",
        "atomic_dependency_deploy.py --cutover",
        "incoming_order_v1_deploy.py --deploy",
        "production_alpha_transparency_deploy.py --deploy",
    )
    matches: list[dict[str, str]] = []
    scope_reader = scheduler_controls.FpmProcessScopeReader(
        Path(__file__).with_name("production_alpha_process_scope_probe.php"), FPM_SOCKET)
    scope_probes = 0
    def bounded_reader(identity):
        nonlocal scope_probes
        scope_probes += 1
        if scope_probes > scheduler_controls.POLICY["maximum_process_scope_probes_per_observation"]:
            raise scheduler_controls.SchedulerError("Pre-mutation process scope exceeds bounded probe count.")
        return scope_reader(identity)
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in {os.getpid(), os.getppid()}:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
            command = raw.replace(b"\0", b" ").decode(
                "utf-8", errors="strict"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        except UnicodeError as error:
            raise DeploymentError("Malformed process command evidence before source mutation.") from error
        lowered = command.lower()
        if not any(pattern.lower() in lowered for pattern in patterns) and not any(value == b"artisan" or value.endswith(b"/artisan") for value in raw.split(b"\0")):
            continue
        scoped = str(APP_ROOT).lower() in lowered
        try:
            identity, working_directory, executable, source = scheduler_controls.resolve_process_scope(entry, raw, bounded_reader)
            scoped = scoped or working_directory == APP_ROOT or is_relative_to(
                working_directory, APP_ROOT
            )
        except scheduler_controls.ConfirmedProcessExit as exit_proof:
            if scope_receipts is not None:
                scope_receipts.append({**exit_proof.receipt, "pid": exit_proof.receipt["identity"]["pid"],
                    "scoped_conflict": False})
            continue
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (scheduler_controls.SchedulerError, PermissionError, ValueError, IndexError, UnicodeError) as error:
            raise DeploymentError("Pre-mutation process scope is unavailable or ambiguous.") from error
        try:
            cgroup = (entry / "cgroup").read_text("utf-8", errors="replace").lower()
            scoped = scoped or "buy-dtf" in cgroup or "buy_dtf" in cgroup
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            if not entry.exists():
                continue
            raise DeploymentError("Pre-mutation process cgroup scope is unavailable.")
        try:
            if scheduler_controls._process_identity(entry) != identity:
                raise DeploymentError("Pre-mutation process identity changed during scope checks.")
        except (FileNotFoundError, ProcessLookupError):
            continue
        if scope_receipts is not None:
            scope_receipts.append({**identity, "scope_source": source, "scoped_conflict": scoped,
                "working_directory_sha256": sha256_bytes(str(working_directory).encode()),
                "executable_sha256": sha256_bytes(executable.encode()), "read_only": True})
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


class SchedulerGuard:
    """Persist every bounded observation and lock transition in private evidence."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / "scheduler-activity-state.json"

    def observe(self, payload: dict[str, Any], phase: str) -> dict[str, Any]:
        previous = None
        if self.path.exists():
            require_regular_file(self.path)
            if stat.S_IMODE(self.path.stat().st_mode) != 0o600:
                raise DeploymentError("Scheduler activity state is not private.")
            try:
                previous = json.loads(self.path.read_text(encoding="utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise DeploymentError("Malformed durable scheduler activity state.") from error
        try:
            deployment_path = self.directory / "state.json"
            if deployment_path.exists():
                deployment = load_json(deployment_path)
                if not isinstance(deployment, dict) or deployment.get("scheduler_policy_sha256") != scheduler_controls.POLICY_SHA256 or deployment.get("scheduler_identity_sha256") != scheduler_controls.identity_sha256(payload):
                    raise scheduler_controls.SchedulerError("Scheduler identity is not bound to the durable deployment/staging envelope.")
            process_receipt = scheduler_controls.process_envelope(payload, APP_ROOT,
                scope_reader=scheduler_controls.FpmProcessScopeReader(
                    Path(__file__).with_name("production_alpha_process_scope_probe.php"), FPM_SOCKET))
            current, receipt = scheduler_controls.observe(payload, previous, phase=phase)
        except scheduler_controls.SchedulerError as error:
            failure = self.directory / f"scheduler-rejection-{time.monotonic_ns()}.json"
            atomic_json(failure, {"status": "rejected", "phase": phase,
                "policy_sha256": scheduler_controls.POLICY_SHA256,
                "snapshot_sha256": scheduler_controls.digest(payload.get("scheduler")),
                "reason": str(error), "at_utc": utc_now()})
            raise DeploymentError(str(error)) from error
        receipt["process_envelope"] = process_receipt
        atomic_json(self.path, current)
        path = self.directory / f"scheduler-observation-{current['sequence']:04d}.json"
        atomic_json(path, receipt)
        return {**receipt, "path": str(path), "sha256": sha256_file(path),
                "state_path": str(self.path), "state_sha256": sha256_file(self.path)}


def validate_runtime_snapshot(payload: dict[str, Any], *,
                              scheduler_guard: SchedulerGuard | None = None,
                              scheduler_phase: str = "idle") -> dict[str, Any]:
    if (
        payload.get("probe_version") != 4
        or payload.get("artifact")
        != "buy-dtf-production-alpha-transparency-runtime-probe-v1"
    ):
        raise DeploymentError("The runtime probe identity differs from the reviewed helper.")
    if payload.get("application_environment") != "local":
        raise DeploymentError("APP_ENV differs from the reviewed local value.")
    if payload.get("application_debug") is not False:
        raise DeploymentError("APP_DEBUG is not false.")
    runtime = payload.get("runtime", {})
    if runtime.get("php_version") != "8.2.30" or runtime.get("laravel_version") != "12.69.1":
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
        ledger.get("table") != "migrations"
        or ledger.get("row_count") != EXPECTED_LEDGER_ROW_COUNT
        or ledger.get("rows_sha256") != EXPECTED_LEDGER_SHA256
        or ledger.get("target_entry_count") != EXPECTED_TARGET_MIGRATION_ENTRIES
        or ledger.get("without_target_row_count")
        != EXPECTED_LEDGER_WITHOUT_TARGET_ROW_COUNT
        or ledger.get("without_target_rows_sha256")
        != EXPECTED_LEDGER_WITHOUT_TARGET_SHA256
    ):
        raise DeploymentError("Fuel migration ledger differs from the installed-schema baseline.")
    if (
        schema.get("sha256") != EXPECTED_SCHEMA_SHA256
        or schema.get("without_item_meta_sha256")
        != EXPECTED_SCHEMA_WITHOUT_ITEM_META_SHA256
    ):
        raise DeploymentError("Fuel schema differs from the installed-schema baseline.")
    required = schema.get("required_tables", {})
    if any(
        required.get(name) is not True
        for name in ("businesses", "dtforders", "dtfimages", TARGET_TABLE, "incoming_order_jobs", "api_asset_records")
    ):
        raise DeploymentError("A required Fuel table is missing.")
    if any(schema.get("required_table_row_counts",{}).get(name) != 0 for name in ("incoming_order_jobs","api_asset_records")) or ledger.get("incoming_order_entry_count") != 1:
        raise DeploymentError("Incoming-order installed tables/ledger/counts differ")
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
    definition = item_meta.get("definition")
    if (
        item_meta.get("exists") is not True
        or not isinstance(definition, list)
        or len(definition) != 1
        or not isinstance(item_meta.get("nonnull_rows"), int)
        or item_meta.get("nonnull_rows", -1) < 0
    ):
        raise DeploymentError("The guarded item_meta schema is not exactly installed.")
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
    if counts.get("jobs") != 0 or counts.get("failed_jobs") != 0:
        raise DeploymentError("Queued or failed jobs are present.")
    try:
        if scheduler_phase == "idle":
            scheduler_verification = scheduler_controls.require_idle(payload)
        elif scheduler_guard is not None:
            scheduler_verification = scheduler_guard.observe(payload, scheduler_phase)
        else:
            raise DeploymentError("Bounded scheduler verification needs durable activity evidence.")
    except scheduler_controls.SchedulerError as error:
        raise DeploymentError(str(error)) from error
    return {
        "status": "pass",
        "schema_state": SCHEMA_STATE,
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
        "scheduler_verification": scheduler_verification,
        "scheduler_identity_sha256": scheduler_controls.identity_sha256(payload),
        "migration_command_invoked": False,
        "migration_pretend_invoked": False,
        "migration_executed_this_attempt": False,
    }


def validate_pre_source_runtime_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Require the installed schema plus an unused item_meta column.

    This stricter check is limited to staging and the final under-gate check
    immediately before source installation. Post-cutover monitoring and source
    rollback use ``validate_runtime_snapshot`` so legitimate new uploads may
    populate the column after the candidate becomes active.
    """

    verification = validate_runtime_snapshot(payload)
    if verification["item_meta_nonnull_rows"] != 0:
        raise DeploymentError(
            "savedimages.item_meta must be null for every existing row before source installation."
        )
    return {**verification, "pre_source_item_meta_empty": True}


def compare_installed_schema_snapshots(
    before: dict[str, Any], after: dict[str, Any], *,
    scheduler_guard: SchedulerGuard | None = None, scheduler_phase: str = "idle",
) -> dict[str, Any]:
    before_verification = validate_runtime_snapshot(before)
    after_verification = validate_runtime_snapshot(after, scheduler_guard=scheduler_guard,
                                                   scheduler_phase=scheduler_phase)
    stable_keys = (
        "schema_state",
        "schema_sha256",
        "schema_without_item_meta_sha256",
        "ledger_row_count",
        "ledger_sha256",
        "ledger_without_target_sha256",
        "target_migration_entries",
        "savedimages_data_columns",
        "scheduler_identity_sha256",
    )
    if any(before_verification[key] != after_verification[key] for key in stable_keys):
        raise DeploymentError("Installed schema or migration ledger changed during the operation.")
    return {
        "status": "pass",
        "state": SCHEMA_STATE,
        "before": before_verification,
        "after": after_verification,
        "schema_and_ledger_unchanged": True,
        "customer_row_counts_compared": False,
        "customer_row_data_compared": False,
    }


def verify_rollback_schema_state(
    payload: dict[str, Any], state: dict[str, Any], *, scheduler_guard: SchedulerGuard | None = None,
) -> dict[str, Any]:
    """Require the exact installed schema before and after source rollback."""
    if any(
        state.get(name) is True
        for name in (
            "migration_command_invoked",
            "migration_pretend_invoked",
            "migration_executed_this_attempt",
        )
    ):
        raise DeploymentError("Source-only rollback state records a prohibited migration action.")
    verification = validate_runtime_snapshot(payload, scheduler_guard=scheduler_guard,
        scheduler_phase="rollback" if scheduler_guard is not None else "idle")
    return {
        "status": "pass",
        "observed_schema_state": SCHEMA_STATE,
        "migration_command_invoked": False,
        "migration_pretend_invoked": False,
        "migration_executed_this_attempt": False,
        "additive_schema_preserved": True,
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
    vendor_policy = source_controls.require_candidate_vendor(APP_ROOT / "vendor")
    source_controls.require_application_autoload(APP_ROOT)
    vendor = tree_manifest(APP_ROOT / "vendor")
    source_controls.require_cache_identity(APP_ROOT)
    cache = tree_manifest(APP_ROOT / "bootstrap/cache")
    if vendor["sha256"] != EXPECTED_VENDOR_MANIFEST_SHA256:
        raise DeploymentError("The live vendor tree differs from the successful v2 receipt.")
    if cache["sha256"] != EXPECTED_CACHE_MANIFEST_SHA256:
        raise DeploymentError("The live bootstrap cache differs from the successful v2 receipt.")
    return {
        "composer_lock_sha256": EXPECTED_COMPOSER_LOCK_SHA256,
        "vendor": vendor,
        "vendor_policy": vendor_policy,
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
    require_target_source: bool = False,
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
    process_scope_receipts: list[dict[str, Any]] = []
    conflicts = scoped_processes(scope_receipts=process_scope_receipts)
    if conflicts:
        raise DeploymentError("A scoped production process is active.")
    controls=environment_identity()
    full_source=full_source_identity(target=require_target_source)
    live_source = live_manifest_snapshot(manifest_rows, target=require_target_source)
    dependencies = dependency_identity()
    runtime, runtime_command = runtime_probe(helper, evidence_directory, f"{prefix}-runtime-probe")
    runtime_verification = validate_pre_source_runtime_snapshot(runtime)
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
        "process_scope_observations": sorted(process_scope_receipts, key=lambda item: item["pid"]),
        "active_fpm_connections_observed": active_fpm_connections(),
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "front_controller_sha256": EXPECTED_FRONT_CONTROLLER_SHA256,
        "front_controller_metadata": front_controller_metadata,
        "dependencies": dependencies,
        "full_source": full_source,
        "live_source": live_source,
        "controls": controls,
        "runtime": runtime,
        "runtime_command": runtime_command,
        "runtime_verification": runtime_verification,
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
    controls=environment_identity()
    full_source_identity(target=False)
    source = live_manifest_snapshot(rows, target=False)
    dependencies = dependency_identity()
    runtime = runtime_probe_memory(helper)
    runtime_verification = validate_pre_source_runtime_snapshot(runtime)
    health = health_snapshot()
    return {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "source": source,
        "controls": controls,
        "dependencies": dependencies,
        "runtime": runtime,
        "runtime_verification": runtime_verification,
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


def require_local_correction_scope() -> None:
    if LOCAL_CORRECTION_REVIEW_ONLY and APP_ROOT.resolve(strict=False) == Path("/var/www/buy-dtf"):
        raise DeploymentError("Local correction is non-stageable: production actions require a separately reviewed activation package.")


def stage_release(
    *,
    archive: Path,
    manifest: Path,
    helper: Path,
    log_guard: Path,
    approval_token: str,
) -> Path:
    require_local_correction_scope()
    if not DEPENDENCY_ENVELOPE_FROZEN:
        raise DeploymentError(
            "Transparency staging is disabled until the post-Laravel-12.69.1 "
            "production dependency envelope is frozen and reviewed."
        )
    if approval_token != STAGE_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed Phase 1 staging token was not supplied.")
    archive = require_regular_file(archive, EXPECTED_ARCHIVE_SHA256)
    manifest = require_regular_file(manifest, EXPECTED_MANIFEST_SHA256)
    helper = require_regular_file(helper, EXPECTED_HELPER_SHA256)
    log_guard = require_regular_file(log_guard, EXPECTED_LOG_GUARD_SHA256)
    runner = require_regular_file(Path(__file__).resolve())
    if sha256_file(runner) in RETIRED_RUNNER_SHA256S:
        raise DeploymentError("The executing runner is permanently retired.")
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
        copied_log_guard = inputs / log_guard.name
        copied_runner = inputs / runner.name
        atomic_copy(archive, copied_archive)
        atomic_copy(manifest, copied_manifest)
        atomic_copy(helper, copied_helper)
        atomic_copy(log_guard, copied_log_guard)
        atomic_copy(runner, copied_runner)
        control_inputs = {}
        for control_name, control_hash in CONTROL_FILES.items():
            original_control=require_regular_file(Path(__file__).with_name(control_name),control_hash)
            destination=inputs/control_name
            atomic_copy(original_control,destination)
            control_inputs[control_name]={"path":str(destination),"sha256":control_hash}

        preflight = production_preflight(
            helper=copied_helper,
            manifest_rows=rows,
            evidence_directory=evidence,
            prefix="phase0",
            require_target_source=False,
        )
        preflight_path = evidence / "phase0-preflight-receipt.json"
        atomic_json(preflight_path, preflight)

        candidate = release / "candidate"
        extraction = extract_candidate(copied_archive, candidate, rows, evidence)
        verification = candidate_verification(candidate, rows, evidence)
        metadata_plan = planned_install_metadata(rows, evidence)
        lint = lint_candidate(candidate, rows, evidence)

        migration = require_regular_file(
            candidate / MIGRATION_RELATIVE_PATH, EXPECTED_MIGRATION_SHA256
        )
        load_laravel_log_guard(copied_log_guard)
        before = preflight["runtime"]
        before_command = preflight["runtime_command"]
        before_verification = validate_pre_source_runtime_snapshot(before)
        after, after_command = runtime_probe(
            copied_helper, evidence, "installed-schema-after-staging"
        )
        after_verification = validate_pre_source_runtime_snapshot(after)
        comparisons = compare_installed_schema_snapshots(before, after)

        installed_schema_receipt = {
            "status": "pass",
            "state": SCHEMA_STATE,
            "generated_at_utc": utc_now(),
            "before": before,
            "after": after,
            "before_verification": before_verification,
            "after_verification": after_verification,
            "comparisons": comparisons,
            "migration_path": str(migration),
            "migration_sha256": sha256_file(migration),
            "migration_source_live_state": "absent",
            "migration_command_invoked": False,
            "migration_pretend_invoked": False,
            "migration_executed_this_attempt": False,
            "before_probe_command": before_command,
            "after_probe_command": after_command,
        }
        installed_schema_receipt_path = evidence / "installed-schema-state-receipt.json"
        atomic_json(installed_schema_receipt_path, installed_schema_receipt)

        full_source_identity(target=False)
        post_source = live_manifest_snapshot(rows, target=False)
        post_dependencies = dependency_identity()
        post_health = health_snapshot()
        if environment_identity() != preflight["controls"]:
            raise DeploymentError("FPM/nginx envelope changed during staging")
        if post_source["sha256"] != preflight["live_source"]["sha256"]:
            raise DeploymentError("Live source identity changed during Phase 1.")
        if post_dependencies != preflight["dependencies"]:
            raise DeploymentError("Live dependency identity changed during Phase 1.")

        stage_receipt = {
            "status": "pass",
            "scope": "alpha-repair-schema-present-source-only-staging",
            "generated_at_utc": utc_now(),
            "target_commit": TARGET_COMMIT,
            "release_directory": str(release),
            "control_inputs": control_inputs,
            "controls": preflight["controls"],
            "scheduler_policy": scheduler_controls.POLICY,
            "scheduler_policy_sha256": scheduler_controls.POLICY_SHA256,
            "scheduler_identity_sha256": before_verification["scheduler_identity_sha256"],
            "inputs": {
                "archive": {"path": str(copied_archive), "sha256": sha256_file(copied_archive)},
                "manifest": {"path": str(copied_manifest), "sha256": sha256_file(copied_manifest)},
                "helper": {"path": str(copied_helper), "sha256": sha256_file(copied_helper)},
                "log_guard": {
                    "path": str(copied_log_guard),
                    "sha256": sha256_file(copied_log_guard),
                },
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
            "installed_schema_receipt": {
                "path": str(installed_schema_receipt_path),
                "sha256": sha256_file(installed_schema_receipt_path),
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
                "migration_command_invoked": False,
                "migration_pretend_invoked": False,
                "migration_executed_this_attempt": False,
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
    if expected_sha256 in RETIRED_RELEASE_RECEIPT_SHA256S:
        raise DeploymentError("The release receipt belongs to a permanently retired runner.")
    if path.as_posix() in RETIRED_RELEASE_RECEIPT_PATHS:
        raise DeploymentError("The release receipt path is permanently retired.")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise DeploymentError("The release-receipt SHA-256 is invalid.")
    path = require_regular_file(path, expected_sha256)
    release = path.parent.resolve(strict=True)
    if not is_relative_to(release, RELEASE_ROOT.resolve(strict=True)):
        raise DeploymentError("Release receipt is outside the approved release root.")
    receipt = load_json(path)
    if not isinstance(receipt, dict) or receipt.get("scheduler_policy") != scheduler_controls.POLICY or receipt.get("scheduler_policy_sha256") != scheduler_controls.POLICY_SHA256:
        raise DeploymentError("Release receipt scheduler policy differs from the frozen control.")
    if not isinstance(receipt.get("scheduler_identity_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", receipt["scheduler_identity_sha256"]):
        raise DeploymentError("Release receipt lacks its exact scheduler identity.")
    if (
        not isinstance(receipt, dict)
        or receipt.get("status") != "pass"
        or receipt.get("scope") != "alpha-repair-schema-present-source-only-staging"
    ):
        raise DeploymentError("Release receipt is not a successful Phase 1 receipt.")
    if receipt.get("target_commit") != TARGET_COMMIT or receipt.get("release_directory") != str(release):
        raise DeploymentError("Release receipt identity differs from the reviewed alpha repair.")
    for name, digest in CONTROL_FILES.items():
        item=receipt.get("control_inputs",{}).get(name,{})
        if item.get("sha256") != digest or Path(item.get("path","")) != release/"inputs"/name:
            raise DeploymentError("Staged control binding differs")
        require_regular_file(release/"inputs"/name,digest)
        require_regular_file(Path(__file__).with_name(name),digest)
    controls=receipt.get("controls",{})
    source_controls.validate_frozen_fpm_opcache_record(controls.get("fpm_opcache"))
    if controls.get("frozen_envelope_sha256") != source_controls.ENVELOPE_SHA256:
        raise DeploymentError("Staged dependency envelope differs")
    inputs = receipt.get("inputs", {})
    identities = {
        "archive": EXPECTED_ARCHIVE_SHA256,
        "manifest": EXPECTED_MANIFEST_SHA256,
        "helper": EXPECTED_HELPER_SHA256,
        "log_guard": EXPECTED_LOG_GUARD_SHA256,
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
    if staged_runner_sha256 in RETIRED_RUNNER_SHA256S:
        raise DeploymentError("The staged runner is permanently retired.")
    if staged_runner.get("sha256") != staged_runner_sha256:
        raise DeploymentError("Staged runner differs from its Phase 1 receipt.")
    executing_runner_sha256 = sha256_file(Path(__file__).resolve())
    if executing_runner_sha256 in RETIRED_RUNNER_SHA256S:
        raise DeploymentError("The executing runner is permanently retired.")
    if executing_runner_sha256 != staged_runner_sha256:
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
    migration = require_regular_file(
        candidate / MIGRATION_RELATIVE_PATH, EXPECTED_MIGRATION_SHA256
    )
    if migration.stat().st_size < 1:
        raise DeploymentError("Staged migration source is empty.")
    load_laravel_log_guard(Path(str(inputs["log_guard"]["path"])))
    schema_item = receipt.get("installed_schema_receipt", {})
    schema_receipt = Path(str(schema_item.get("path", "")))
    require_regular_file(schema_receipt, str(schema_item.get("sha256", "")))
    if not is_relative_to(schema_receipt.resolve(strict=True), release):
        raise DeploymentError("Installed-schema receipt escapes the release directory.")
    schema_payload = load_json(schema_receipt)
    if (
        not isinstance(schema_payload, dict)
        or schema_payload.get("status") != "pass"
        or schema_payload.get("state") != SCHEMA_STATE
        or schema_payload.get("migration_command_invoked") is not False
        or schema_payload.get("migration_pretend_invoked") is not False
        or schema_payload.get("migration_executed_this_attempt") is not False
    ):
        raise DeploymentError("Installed-schema receipt does not prove source-only staging.")
    for name in ("before_verification", "after_verification"):
        verified = schema_payload.get(name, {})
        if (
            verified.get("schema_state") != SCHEMA_STATE
            or verified.get("schema_sha256") != EXPECTED_SCHEMA_SHA256
            or verified.get("ledger_row_count") != EXPECTED_LEDGER_ROW_COUNT
            or verified.get("ledger_sha256") != EXPECTED_LEDGER_SHA256
            or verified.get("target_migration_entries")
            != EXPECTED_TARGET_MIGRATION_ENTRIES
        ):
            raise DeploymentError("Installed-schema receipt differs from baseline.")
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




def restore_front_controller_exact(*, backup: Path, expected_sha256: str, metadata: dict[str, Any], allowed_current_sha256: set[str], state: dict[str, Any], state_path: Path, state_directory: Path, operation: str, receipt_name: str, front_controller: Path | None = None, application_root: Path | None = None, fault_injector=None) -> dict[str, Any]:
    if expected_sha256 != EXPECTED_FRONT_CONTROLLER_SHA256 or metadata != reviewed_front_controller_metadata():
        raise DeploymentError('Original front-controller identity differs')
    context = source_gate_context(state,state_path,restoration=True,front_controller=front_controller,application_root=application_root)
    try: return source_controls.dependency_gate.restore_front_controller_exact(context=context,state=state,operation=operation,receipt_name=receipt_name,fault_injector=fault_injector)
    except source_controls.dependency_gate.GateError as error: raise DeploymentError(str(error)) from error


def mutation_has_started(state: dict[str, Any]) -> bool:
    """Return the durable point after which reopening is never a safe fallback."""
    return bool(state.get("source_install_started"))


def gate_probe_passed(result: dict[str, Any], expected_route: str) -> bool:
    return source_controls.dependency_gate.gate_probe_passed(result,expected_route)


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


def retain_static_gate_exact(*, state_directory: Path, name: str, state: dict[str, Any], state_path: Path, original_backup: Path, original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256, metadata: dict[str, Any] | None = None, front_controller: Path | None = None, application_root: Path | None = None, fault_injector=None) -> dict[str, Any]:
    context=source_gate_context(state,state_path,front_controller=front_controller,application_root=application_root)
    try: return source_controls.dependency_gate.retain_static_gate_exact(context=context,state=state,operation=name,mutation_started=mutation_has_started,fault_injector=fault_injector)
    except source_controls.dependency_gate.GateError as error:raise DeploymentError(str(error)) from error


def install_static_gate(*, state_directory: Path, name: str, state: dict[str, Any], state_path: Path, original_backup: Path, original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256, metadata: dict[str, Any] | None = None, front_controller: Path | None = None, application_root: Path | None = None, origin_probe=None, public_probe=None, restored_health_probe=None, fault_injector=None) -> dict[str, Any]:
    context=source_gate_context(state,state_path,front_controller=front_controller,application_root=application_root)
    try:
        return source_controls.dependency_gate.install_static_gate(context=context,state=state,operation=name,origin_probe=lambda number: (origin_probe() if origin_probe else gate_origin_probe(state_directory,f'{name}-{number}')),public_probe=public_probe or (lambda:gate_public_probe(state_directory,name)),restored_health_probe=restored_health_probe or health_snapshot,mutation_started=mutation_has_started,fault_injector=fault_injector)
    except source_controls.dependency_gate.GateError as error: raise DeploymentError(str(error)) from error


def gate_http_probe(state_directory: Path, name: str, *, origin_loopback: bool) -> dict[str, Any]:
    return source_controls.dependency_gate.gate_http_probe(evidence_directory=state_directory,operation=name,public_url='https://buy-dtf.com/',origin_loopback=origin_loopback,cwd=APP_ROOT)


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
    source_controls.APP_ROOT=APP_ROOT
    environment=source_controls.fpm_fastcgi_environment(probe,"/internal-alpha-probe.php")
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
            or payload.get("laravel_version") != "12.69.1"
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
    full_source_identity(target=True)
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
    runtime_verification = validate_runtime_snapshot(runtime)
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


def settle_scheduler_activity(
    helper: Path, state_directory: Path, runtime: dict[str, Any], *,
    scheduler_guard: SchedulerGuard, phase: str, target: bool,
    log_checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observe normal work to completion; never manipulate its mutex or task.

    Every active follow-up repeats runtime, source, configuration, dependency,
    front-controller, and (when open) health checks. Expiry/monotonic policy
    bounds the loop even across interruption and recovery.
    """
    followups = []
    verification = validate_runtime_snapshot(runtime, scheduler_guard=scheduler_guard,
                                             scheduler_phase=phase)
    while verification["scheduler_verification"]["active"]:
        pending = verification["scheduler_verification"]["pending"]
        delay = scheduler_controls.STARTUP_POLL_SECONDS if pending["stage"] == "startup" else scheduler_controls.POLL_SECONDS
        time.sleep(delay)
        if log_checkpoint is not None:
            log_checkpoint = verify_log_continuity(log_checkpoint)
        runtime, command = runtime_probe(helper, state_directory,
            f"scheduler-{phase}-followup-{scheduler_guard.path.stat().st_mtime_ns}")
        verification = validate_runtime_snapshot(runtime, scheduler_guard=scheduler_guard,
                                                 scheduler_phase=phase)
        expected_front = EXPECTED_GATE_SHA256 if phase in {"rollback", "recovery"} else EXPECTED_FRONT_CONTROLLER_SHA256
        require_regular_file(FRONT_CONTROLLER, expected_front)
        if phase in {"post_open", "monitor"} and LARAVEL_MAINTENANCE_FILE.exists():
            raise DeploymentError("Maintenance unexpectedly active after reopening.")
        followups.append({"runtime_verification": verification, "runtime_command": command,
            "source": full_source_identity(target=target),
            "configuration_sha256": source_controls.require_configuration_identity(),
            "dependencies": dependency_identity(),
            "health": health_snapshot() if phase in {"post_open", "monitor"} else {"exact_gate_retained": True}})
    return {"status": "pass", "runtime": runtime, "runtime_verification": verification,
            "followups": followups, "log_checkpoint": log_checkpoint}


def post_open_health(
    helper: Path, state_directory: Path, name: str
) -> dict[str, Any]:
    health_first = health_snapshot()
    capability_first = capability_probe(state_directory, f"{name}-capability-1")
    time.sleep(3)
    health_second = health_snapshot()
    capability_second = capability_probe(state_directory, f"{name}-capability-2")
    runtime, runtime_command = runtime_probe(helper, state_directory, f"{name}-runtime")
    guard = SchedulerGuard(state_directory)
    phase = "post_open"
    settled = settle_scheduler_activity(helper, state_directory, runtime,
        scheduler_guard=guard, phase=phase, target=not name.startswith("rollback"))
    runtime = settled["runtime"]
    runtime_verification = settled["runtime_verification"]
    return {
        "health_first": health_first,
        "health_second": health_second,
        "capability_first": capability_first,
        "capability_second": capability_second,
        "runtime": runtime,
        "runtime_verification": runtime_verification,
        "runtime_command": runtime_command,
        "scheduler_completion": settled,
        "maintenance_active": LARAVEL_MAINTENANCE_FILE.exists(),
        "front_controller_sha256": sha256_file(FRONT_CONTROLLER),
    }


def monitor_production(
    helper: Path,
    rows: list[dict[str, Any]],
    state_directory: Path,
    log_checkpoint: dict[str, Any],
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    guard = SchedulerGuard(state_directory)
    sample_count = MONITOR_SECONDS // MONITOR_INTERVAL_SECONDS
    for index in range(sample_count):
        log_checkpoint = verify_log_continuity(log_checkpoint)
        runtime, _ = runtime_probe(helper, state_directory, f"monitor-runtime-{index + 1:02d}")
        verification = validate_runtime_snapshot(runtime, scheduler_guard=guard,
                                                  scheduler_phase="monitor")
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
            "full_source": full_source_identity(target=True),
            "configuration_sha256": source_controls.require_configuration_identity(),
            "dependencies": dependency_identity(),
            "deployment_lock_held_by_runner": True,
            "laravel_log_continuity": {
                "inode": log_checkpoint["inode"],
                "bytes": log_checkpoint["bytes"],
                "anchor_sha256": log_checkpoint["anchor"]["sha256"],
            },
        }
        samples.append(sample)
        atomic_json(state_directory / "monitoring-samples.json", samples)
        settled = settle_scheduler_activity(helper, state_directory, runtime,
            scheduler_guard=guard, phase="monitor", target=True, log_checkpoint=log_checkpoint)
        log_checkpoint = settled["log_checkpoint"]
        sample["scheduler_completion"] = settled
        atomic_json(state_directory / "monitoring-samples.json", samples)
        time.sleep(MONITOR_INTERVAL_SECONDS)
    log_checkpoint = verify_log_continuity(log_checkpoint)
    final_runtime, final_command = runtime_probe(helper, state_directory, "monitor-final-runtime")
    final_settled = settle_scheduler_activity(helper, state_directory, final_runtime,
        scheduler_guard=guard, phase="monitor", target=True, log_checkpoint=log_checkpoint)
    log_checkpoint = final_settled["log_checkpoint"]
    final_verification = final_settled["runtime_verification"]
    require_regular_file(FRONT_CONTROLLER, EXPECTED_FRONT_CONTROLLER_SHA256)
    if LARAVEL_MAINTENANCE_FILE.exists():
        raise DeploymentError("Maintenance unexpectedly active at monitor close.")
    final_checks = {"health": health_snapshot(), "source": live_manifest_snapshot(rows, target=True),
        "full_source": full_source_identity(target=True), "dependencies": dependency_identity(),
        "configuration_sha256": source_controls.require_configuration_identity()}
    path = state_directory / "monitoring-samples.json"
    return {
        "status": "pass",
        "samples": len(samples),
        "completed_intervals": sample_count,
        "minimum_elapsed_seconds": MONITOR_SECONDS,
        "path": str(path),
        "sha256": sha256_file(path),
        "final_log_checkpoint": log_checkpoint,
        "final_runtime_verification": final_verification,
        "final_runtime_command": final_command,
        "final_scheduler_completion": final_settled,
        "final_checks": final_checks,
        "scheduler_state_sha256": sha256_file(guard.path),
    }


def load_laravel_log_guard(path: Path) -> Any:
    path = require_regular_file(path, EXPECTED_LOG_GUARD_SHA256)
    specification = importlib.util.spec_from_file_location(
        "buy_dtf_production_laravel_log_guard", path
    )
    if specification is None or specification.loader is None:
        raise DeploymentError("The reviewed Laravel log guard cannot be imported.")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    if not callable(getattr(module, "inspect_log_bytes", None)):
        raise DeploymentError("The reviewed Laravel log guard has no inspect_log_bytes API.")
    return module


def _log_entry_start(handle: Any, end: int) -> int:
    """Retain the latest Laravel entry as context for a later delta.

    A trailing LF proves only a line boundary. Laravel exceptions and context
    payloads are multiline, so another line may still continue the latest
    entry. Retaining its header lets the later delta distinguish a new header
    from continuation data without treating a partial entry as an orphan.
    """

    read_start = max(0, end - LOG_ENTRY_CONTEXT_BYTES - 1)
    handle.seek(read_start)
    window = handle.read(end - read_start)
    if len(window) != end - read_start:
        raise DeploymentError("Laravel log changed while entry context was read.")
    search_start = 0
    if read_start:
        first_newline = window.find(b"\n")
        if first_newline < 0:
            raise DeploymentError(
                "Laravel log partial entry exceeds the reviewed context bound."
            )
        search_start = first_newline + 1
    matches = list(LOG_ENTRY_HEADER_BYTES.finditer(window, search_start))
    if not matches:
        raise DeploymentError(
            "Laravel log does not have a parseable boundary for its partial entry."
        )
    entry_start = read_start + matches[-1].start()
    if end - entry_start > LOG_ENTRY_CONTEXT_BYTES:
        raise DeploymentError(
            "Laravel log partial entry exceeds the reviewed context bound."
        )
    return entry_start


def _log_checkpoint(path: Path, handle: Any, metadata: os.stat_result) -> dict[str, Any]:
    end = metadata.st_size
    entry_start = _log_entry_start(handle, end)
    handle.seek(end - 1)
    ends_at_line_boundary = handle.read(1) == b"\n"
    context_bytes = end - entry_start
    handle.seek(entry_start)
    entry_context = handle.read(context_bytes)
    if len(entry_context) != context_bytes:
        raise DeploymentError("Laravel log changed while entry context was hashed.")
    anchor_bytes = min(end, LOG_CONTINUITY_ANCHOR_BYTES)
    anchor_start = end - anchor_bytes
    handle.seek(anchor_start)
    anchor = handle.read(anchor_bytes)
    if len(anchor) != anchor_bytes:
        raise DeploymentError("Laravel log changed while its continuity anchor was read.")
    return {
        "path": str(path),
        "exists": True,
        "inode": metadata.st_ino,
        "bytes": end,
        "entry_start": entry_start,
        "boundary_context_bytes": context_bytes,
        "ends_at_line_boundary": ends_at_line_boundary,
        "entry_context": {
            "start": entry_start,
            "bytes": context_bytes,
            "sha256": sha256_bytes(entry_context),
        },
        "anchor": {
            "start": anchor_start,
            "bytes": anchor_bytes,
            "sha256": sha256_bytes(anchor),
        },
    }


def _validate_log_checkpoint(
    checkpoint: dict[str, Any],
) -> tuple[Path, int, dict[str, Any], int]:
    if checkpoint.get("exists") is not True:
        raise DeploymentError("Laravel log continuity baseline is not an existing file.")
    path = Path(str(checkpoint.get("path", "")))
    inode = checkpoint.get("inode")
    offset = checkpoint.get("bytes")
    entry_start = checkpoint.get("entry_start")
    context_bytes = checkpoint.get("boundary_context_bytes")
    entry_context = checkpoint.get("entry_context")
    anchor = checkpoint.get("anchor")
    anchor_start = anchor.get("start") if isinstance(anchor, dict) else None
    anchor_bytes = anchor.get("bytes") if isinstance(anchor, dict) else None
    if (
        not isinstance(inode, int)
        or not isinstance(offset, int)
        or offset < 0
        or not isinstance(entry_start, int)
        or not 0 <= entry_start <= offset
        or not isinstance(context_bytes, int)
        or context_bytes != offset - entry_start
        or context_bytes > LOG_ENTRY_CONTEXT_BYTES
        or not isinstance(checkpoint.get("ends_at_line_boundary"), bool)
        or not isinstance(entry_context, dict)
        or entry_context.get("start") != entry_start
        or entry_context.get("bytes") != context_bytes
        or not re.fullmatch(r"[0-9a-f]{64}", str(entry_context.get("sha256", "")))
        or not isinstance(anchor, dict)
        or not isinstance(anchor_start, int)
        or not isinstance(anchor_bytes, int)
        or not 0 <= anchor_bytes <= LOG_CONTINUITY_ANCHOR_BYTES
        or anchor_start != offset - anchor_bytes
        or not re.fullmatch(r"[0-9a-f]{64}", str(anchor.get("sha256", "")))
    ):
        raise DeploymentError("Laravel log continuity baseline is invalid.")
    return path, offset, anchor, entry_start


@contextmanager
def verified_log_handle(
    checkpoint: dict[str, Any],
) -> Iterator[tuple[Path, Any, os.stat_result]]:
    path, offset, anchor, _ = _validate_log_checkpoint(checkpoint)
    if path.is_symlink() or not path.is_file():
        raise DeploymentError("Laravel log disappeared or became invalid during monitoring.")
    with path.open("rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise DeploymentError("Laravel log is not a regular file.")
        if metadata.st_ino != checkpoint["inode"]:
            raise DeploymentError("Laravel log rotated during monitoring.")
        if metadata.st_size < offset:
            raise DeploymentError("Laravel log was truncated during monitoring.")
        entry_context = checkpoint["entry_context"]
        handle.seek(entry_context["start"])
        observed_context = handle.read(entry_context["bytes"])
        if (
            len(observed_context) != entry_context["bytes"]
            or sha256_bytes(observed_context) != entry_context["sha256"]
        ):
            raise DeploymentError(
                "Laravel log retained entry context changed during monitoring."
            )
        handle.seek(anchor["start"])
        observed_anchor = handle.read(anchor["bytes"])
        if (
            len(observed_anchor) != anchor["bytes"]
            or sha256_bytes(observed_anchor) != anchor["sha256"]
        ):
            raise DeploymentError(
                "Laravel log continuity anchor changed during monitoring."
            )
        yield path, handle, metadata


def log_baseline() -> dict[str, Any]:
    path = APP_ROOT / "storage/logs/laravel.log"
    if path.is_symlink() or not path.is_file():
        raise DeploymentError(
            "Laravel log must exist as a regular file before source cutover."
        )
    with path.open("rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise DeploymentError("Laravel log is not a regular file.")
        if metadata.st_size == 0:
            raise DeploymentError(
                "Laravel log must be nonempty before source cutover so continuity can be anchored."
            )
        return _log_checkpoint(path, handle, metadata)


def verify_log_continuity(checkpoint: dict[str, Any]) -> dict[str, Any]:
    with verified_log_handle(checkpoint) as (path, handle, _):
        metadata = os.fstat(handle.fileno())
        return _log_checkpoint(path, handle, metadata)


def _first_fresh_log_header(content: bytes) -> int | None:
    """Return the first nonblank line offset when it is header-shaped."""

    offset = 0
    for line in content.splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        if not body.strip():
            offset += len(line)
            continue
        return offset if LOG_HEADER_LIKE_BYTES.match(body) else None
    return len(content)


def log_delta(
    baseline: dict[str, Any],
    state_directory: Path,
    log_guard_path: Path,
    *,
    evidence_label: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", evidence_label):
        raise DeploymentError("Laravel log evidence label is invalid.")
    _, offset, _, entry_start = _validate_log_checkpoint(baseline)
    with verified_log_handle(baseline) as (path, handle, metadata):
        if metadata.st_size - offset > 20 * 1024 * 1024:
            raise DeploymentError("Laravel log delta exceeds the reviewed 20 MiB evidence bound.")
        handle.seek(entry_start)
        content = handle.read()
        continuity = _log_checkpoint(path, handle, os.fstat(handle.fileno()))
    evidence = state_directory / f"laravel-log-{evidence_label}-delta.txt"
    atomic_write(evidence, content, 0o600)
    guard = load_laravel_log_guard(log_guard_path)
    context_bytes = offset - entry_start
    new_content = content[context_bytes:]
    if not new_content:
        inspection_content = b""
    elif baseline["ends_at_line_boundary"] and (
        fresh_header := _first_fresh_log_header(new_content)
    ) is not None:
        # A fresh valid header after a complete line cannot continue the
        # retained pre-baseline entry, so classify only newly appended bytes.
        inspection_content = new_content[fresh_header:]
    else:
        # Reparse the retained entry with appended bytes so multiline
        # continuations cannot become an orphan or evade classification.
        inspection_content = content
    report_path = state_directory / f"laravel-log-{evidence_label}-analysis.json"
    try:
        report = guard.inspect_log_bytes(inspection_content)
    except Exception as exception:
        report = getattr(exception, "report", None)
        if not isinstance(report, dict):
            raise DeploymentError("The reviewed Laravel log guard failed unexpectedly.") from exception
        atomic_json(report_path, report)
        signals = sorted(str(name) for name in report.get("signal_counts", {}))
        raise DeploymentError(
            "Laravel log delta contains rollback-worthy entries "
            f"(signals: {signals})."
        ) from exception
    atomic_json(report_path, report)
    return {
        "bytes": len(content),
        "new_bytes": len(new_content),
        "baseline_context_bytes": context_bytes,
        "analysis_bytes": len(inspection_content),
        "sha256": sha256_file(evidence),
        "path": str(evidence),
        "analysis": report,
        "analysis_path": str(report_path),
        "analysis_sha256": sha256_file(report_path),
        "continuity": continuity,
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


def front_controller_recovery_required(state: dict[str, Any], *, front_controller: Path | None = None, original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256) -> bool:
    # Decision validation is offline: a failed live FPM must not block rollback.
    if not state.get('front_controller_backup'):
        return mutation_has_started(state)
    path=Path(state['state_directory'])/'state.json'
    frozen=source_controls.validate_frozen_fpm_opcache_record(state.get('fpm_opcache'))
    context=source_controls._gate_context_from_frozen_envelope(state,path,frozen)
    try: return source_controls.dependency_gate.front_controller_recovery_required(context=context,state=state,mutation_started=mutation_has_started)
    except source_controls.dependency_gate.GateError as error:raise DeploymentError(str(error)) from error


def establish_rollback_containment(*, state_directory: Path, name: str, state: dict[str, Any], state_path: Path, original_backup: Path, original_sha256: str = EXPECTED_FRONT_CONTROLLER_SHA256, metadata: dict[str, Any] | None = None, front_controller: Path | None = None, application_root: Path | None = None, origin_probe=None, public_probe=None, restored_health_probe=None) -> dict[str, Any]:
    context=source_gate_context(state,state_path,front_controller=front_controller,application_root=application_root)
    try:
        return source_controls.dependency_gate.establish_rollback_containment(context=context,state=state,operation=name,origin_probe=lambda number:(origin_probe() if origin_probe else gate_origin_probe(state_directory,f'{name}-{number}')),public_probe=public_probe or (lambda:gate_public_probe(state_directory,name)),restored_health_probe=restored_health_probe or health_snapshot,mutation_started=mutation_has_started)
    except source_controls.dependency_gate.GateError as error:raise DeploymentError(str(error)) from error


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
        full_source_identity(target=False)
        state["source_rollback_receipt"] = source["path"]
        write_state(state_path, state)
        dependency_identity()

        runtime, runtime_command = runtime_probe(helper, state_directory, "rollback-runtime-probe")
        scheduler_guard = SchedulerGuard(state_directory)
        rollback_schema = verify_rollback_schema_state(runtime, state, scheduler_guard=scheduler_guard)
        schema_baseline = state.get("installed_schema_baseline")
        if not isinstance(schema_baseline, dict):
            raise DeploymentError("Rollback state is missing the installed-schema baseline.")
        rollback_schema["comparisons"] = compare_installed_schema_snapshots(
            schema_baseline, runtime, scheduler_guard=scheduler_guard, scheduler_phase="rollback"
        )
        rollback_schema["scheduler_completion"] = settle_scheduler_activity(
            helper, state_directory, runtime, scheduler_guard=scheduler_guard,
            phase="rollback", target=False)
        rollback_schema_path = state_directory / "rollback-schema-preservation-receipt.json"
        atomic_json(rollback_schema_path, rollback_schema)

        leave_laravel_maintenance(state_directory, "rollback-artisan-up")
        state["laravel_maintenance_active"] = False
        write_state(state_path, state)
        front_restore = restore_front_controller(
            Path(str(state["front_controller_backup"])),
            state["front_controller_metadata"],
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            name="rollback-original-front-controller-restore",
        )
        state["front_controller_restore_receipt"] = front_restore["path"]
        health = post_open_health(helper, state_directory, "rollback-post-open")
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
            "migration_command_invoked": False,
            "migration_pretend_invoked": False,
            "migration_executed_this_attempt": False,
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
    require_local_correction_scope()
    if not DEPENDENCY_ENVELOPE_FROZEN:
        raise DeploymentError(
            "Transparency deployment is disabled until the post-Laravel-12.69.1 "
            "production dependency envelope is frozen and reviewed."
        )
    if approval_token != DEPLOY_APPROVAL_TOKEN:
        raise DeploymentError("The exact reviewed deployment approval token was not supplied.")
    receipt, release, rows = validate_release_receipt(
        release_receipt_path, release_receipt_sha256
    )
    helper = require_regular_file(
        Path(str(receipt["inputs"]["helper"]["path"])), EXPECTED_HELPER_SHA256
    )
    log_guard_path = require_regular_file(
        Path(str(receipt["inputs"]["log_guard"]["path"])),
        EXPECTED_LOG_GUARD_SHA256,
    )
    load_laravel_log_guard(log_guard_path)
    candidate = require_real_directory(release / "candidate", within=release)
    require_regular_file(candidate / MIGRATION_RELATIVE_PATH, EXPECTED_MIGRATION_SHA256)

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
            "schema_state": SCHEMA_STATE,
            "schema_present_before_attempt": True,
            "migration_command_invoked": False,
            "migration_pretend_invoked": False,
            "migration_executed_this_attempt": False,
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
                require_target_source=False,
            )
            preflight_path = state_directory / "cutover-preflight-receipt.json"
            atomic_json(preflight_path, preflight)
            if preflight["controls"] != receipt["controls"]:
                raise DeploymentError("FPM/nginx differs from staged envelope")
            if preflight["runtime_verification"]["scheduler_identity_sha256"] != receipt["scheduler_identity_sha256"]:
                raise DeploymentError("Scheduler identity differs from the staged envelope")
            state["scheduler_policy_sha256"] = scheduler_controls.POLICY_SHA256
            state["scheduler_identity_sha256"] = receipt["scheduler_identity_sha256"]
            state["fpm_opcache"]=preflight["controls"]["fpm_opcache"]
            state["nginx"]=preflight["controls"]["nginx"]
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
            state["front_controller_backup_sha256"] = EXPECTED_FRONT_CONTROLLER_SHA256
            state["front_controller_metadata"] = require_exact_metadata(
                FRONT_CONTROLLER,
                reviewed_front_controller_metadata(),
                label="Front controller",
            )

            before_snapshot = preflight["runtime"]
            state["installed_schema_baseline"] = before_snapshot
            state["status"] = "source_backups_complete"
            write_state(state_path, state)
            append_event(state_directory, "source_backups_complete")

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

            # Repeat every relevant identity under the gate before source mutation.
            # The installed schema is immutable input: no migration command is allowed.
            full_source_identity(target=False)
            live_manifest_snapshot(rows, target=False)
            dependency_identity()
            before_repeat, before_repeat_command = runtime_probe(
                helper, state_directory, "cutover-installed-schema-probe"
            )
            installed_verification = validate_pre_source_runtime_snapshot(before_repeat)
            installed_comparisons = compare_installed_schema_snapshots(
                before_snapshot, before_repeat
            )
            installed_receipt = {
                "status": "pass",
                "state": SCHEMA_STATE,
                "generated_at_utc": utc_now(),
                "preflight": before_snapshot,
                "under_gate": before_repeat,
                "under_gate_probe_command": before_repeat_command,
                "verification": installed_verification,
                "comparisons": installed_comparisons,
                "migration_command_invoked": False,
                "migration_pretend_invoked": False,
                "migration_executed_this_attempt": False,
            }
            installed_path = state_directory / "cutover-installed-schema-receipt.json"
            atomic_json(installed_path, installed_receipt)

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
            if environment_identity() != receipt["controls"]:
                raise DeploymentError("Under-gate FPM/nginx envelope differs")
            source_controls.record_fpm_opcache_before_mutation(state,state_path)
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
            logs = log_delta(
                log_start,
                state_directory,
                log_guard_path,
                evidence_label="post-open",
            )
            state["status"] = "monitoring"
            write_state(state_path, state)
            monitoring = monitor_production(
                helper,
                rows,
                state_directory,
                logs["continuity"],
            )
            final_logs = log_delta(
                log_start,
                state_directory,
                log_guard_path,
                evidence_label="final",
            )
            final = {
                "status": "awaiting_independent_log_review",
                "generated_at_utc": utc_now(),
                "target_commit": TARGET_COMMIT,
                "release_receipt_sha256": release_receipt_sha256,
                "preflight_receipt_sha256": sha256_file(preflight_path),
                "source_backup_receipt_sha256": source["receipt_sha256"],
                "drain": drain,
                "installed_schema_receipt_sha256": sha256_file(installed_path),
                "migration_command_invoked": False,
                "migration_pretend_invoked": False,
                "migration_executed_this_attempt": False,
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
                "schema": monitoring["final_runtime_verification"],
                "source": live_manifest_snapshot(rows, target=True),
            }
            final_path = state_directory / "final-receipt.json"
            atomic_json(final_path, final)
            state["status"] = "awaiting_independent_log_review"
            state["final_receipt"] = str(final_path)
            state["finished_at_utc"] = utc_now()
            write_state(state_path, state)
            append_event(state_directory, "awaiting_independent_log_review")
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
    require_local_correction_scope()
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
        "artifact": "BuyDTF local process-scope rollback correction; review only",
        "local_correction_review_only": LOCAL_CORRECTION_REVIEW_ONLY,
        "scheduler_policy": scheduler_controls.POLICY,
        "scheduler_policy_sha256": scheduler_controls.POLICY_SHA256,
        "target_application_commit": TARGET_COMMIT,
        "artifact_base_commit": ARTIFACT_BASE_COMMIT,
        "review_provenance": {
            "handoff": "buy-dtf-codie-handoff-2026-10-02.md",
            "handoff_sha256": HANDOFF_SHA256,
            "status": "frozen_review_only_non_stageable",
        },
        "application_root": str(APP_ROOT),
        "release_root": str(RELEASE_ROOT),
        "rollback_root": str(ROLLBACK_ROOT),
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "helper_sha256": EXPECTED_HELPER_SHA256,
        "log_guard_sha256": EXPECTED_LOG_GUARD_SHA256,
        "migration": {
            "path": MIGRATION_RELATIVE_PATH.as_posix(),
            "sha256": EXPECTED_MIGRATION_SHA256,
            "connection": "fuelmysql",
            "source_predeployment_state": "absent_reviewed_addition",
            "schema_state": SCHEMA_STATE,
            "command_invoked": False,
            "pretend_invoked": False,
            "executed_this_attempt": False,
        },
        "installed_schema_identity": {
            "state": SCHEMA_STATE,
            "schema_sha256": EXPECTED_SCHEMA_SHA256,
            "schema_without_item_meta_sha256": EXPECTED_SCHEMA_WITHOUT_ITEM_META_SHA256,
            "ledger_rows": EXPECTED_LEDGER_ROW_COUNT,
            "ledger_sha256": EXPECTED_LEDGER_SHA256,
            "ledger_without_target_rows": EXPECTED_LEDGER_WITHOUT_TARGET_ROW_COUNT,
            "ledger_without_target_sha256": EXPECTED_LEDGER_WITHOUT_TARGET_SHA256,
            "target_migration_entries": EXPECTED_TARGET_MIGRATION_ENTRIES,
            "item_meta": "nullable_text_installed",
            "source_cas_sha256": EXPECTED_PRE_SOURCE_CAS_SHA256,
            "target_source_cas_sha256": EXPECTED_TARGET_SOURCE_CAS_SHA256,
        },
        "runtime_paths": {
            "total": EXPECTED_RUNTIME_PATHS,
            "additions": EXPECTED_ADDITIONS,
            "replacements": EXPECTED_REPLACEMENTS,
        },
        "dependency_identity": {
            "freeze_status": DEPENDENCY_ENVELOPE_STATUS,
            "frozen_for_stage_or_deploy": DEPENDENCY_ENVELOPE_FROZEN,
            "historical_pre_upgrade_values": {
                "composer_lock_sha256": EXPECTED_COMPOSER_LOCK_SHA256,
                "vendor_manifest_sha256": EXPECTED_VENDOR_MANIFEST_SHA256,
                "cache_manifest_sha256": EXPECTED_CACHE_MANIFEST_SHA256,
                "packages_sha256": EXPECTED_PACKAGES_SHA256,
                "services_sha256": EXPECTED_SERVICES_SHA256,
            },
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
            "post_source_mutation_verification_failure": (
                "retain_exact_0644_gate_with_durable_rollback_containment"
            ),
            "recovery_uses_live_identity_and_durable_state": True,
        },
        "approval_tokens": {
            "status": (
                "blocked_local_correction_requires_new_review_and_authorization"
                if DEPENDENCY_ENVELOPE_FROZEN
                else "withheld_pending_post_laravel_12_69_1_freeze"
            ),
            "stage": None,
            "deploy": None,
            "recover": None,
        },
        "retired_artifacts": {
            "artifact_commit": [RETIRED_ARTIFACT_COMMIT],
            "runner_sha256": sorted(RETIRED_RUNNER_SHA256S),
            "release_receipt_sha256": sorted(RETIRED_RELEASE_RECEIPT_SHA256S),
            "release_receipt_paths": sorted(RETIRED_RELEASE_RECEIPT_PATHS),
        },
        "safety": {
            "git_operations": False,
            "composer_operations": False,
            "general_migration": False,
            "migration_command_invoked": False,
            "migration_pretend_invoked": False,
            "migration_executed_this_attempt": False,
            "service_restart": False,
            "environment_change": False,
            "cache_change": False,
            "capability_enablement": False,
            "retention_execution": False,
            "source_rollback_drops_additive_schema": False,
            "schema_preserved_during_source_deploy_and_rollback": True,
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
    parser.add_argument("--log-guard", type=Path)
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
        if LOCAL_CORRECTION_REVIEW_ONLY:
            raise DeploymentError("Local correction is non-stageable: no deployment, recovery, or retry authorization exists.")
        if arguments.stage:
            if (
                arguments.archive is None
                or arguments.manifest is None
                or arguments.helper is None
                or arguments.log_guard is None
            ):
                raise DeploymentError(
                    "Stage mode requires --archive, --manifest, --helper, and --log-guard."
                )
            receipt = stage_release(
                archive=arguments.archive,
                manifest=arguments.manifest,
                helper=arguments.helper,
                log_guard=arguments.log_guard,
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
                        "status": "awaiting_independent_log_review",
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
