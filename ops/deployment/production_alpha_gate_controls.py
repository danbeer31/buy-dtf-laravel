#!/usr/bin/env python3
"""Source-only adapter for the accepted v4 FPM and gate controls.

No dependency installer, migration, service command or sudo grant is exposed.
The gate itself is the byte-identical accepted v4 shared primitive. Emergency
fallback is permitted only after source mutation and with a private, receipt-
bound envelope rechecked immediately before that mutation.
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import laravel_dependency_gate as dependency_gate
import laravel_nginx_identity as environment_controls

APP_ROOT = Path('/var/www/buy-dtf')
FRONT_CONTROLLER = APP_ROOT / 'public/index.php'
FPM_SOCKET = Path('/run/php/php8.2-fpm.sock')
EXPECTED_PHP_VERSION = '8.2.30'
EXPECTED_FRONT_CONTROLLER_SHA256 = 'eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9'
MAINTENANCE_GATE_SHA256 = dependency_gate.EXPECTED_GATE_SHA256
FPM_OPCACHE_PROBE_SHA256 = 'b8b34f87d45a0c000cc0df7917496631320cfbdcca1ff44bc41741ce0d569262'
NGINX_IDENTITY_HELPER_SHA256 = '1243fea2757aca89f586ec4b322b0d23ee1e19b2d027c21bd6523e71e6e6e8e0'
GATE_HELPER_SHA256 = 'b93c08f58a08333120369c1cc75c60631d621c3a8099ca3967065721c45679f5'
ENVELOPE_SHA256 = '04850fe3aef14981c92f5b2af373bd136cfb6fead456d86fcab7233acb009fd1'

class DeploymentError(RuntimeError):
    pass
class FpmProbeUnavailable(DeploymentError):
    pass

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())
def require_regular_file(path: Path, expected_sha256: str | None = None) -> Path:
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise DeploymentError('Control file is not regular: '+str(path))
    if expected_sha256 is not None and sha256_file(path)!=expected_sha256:
        raise DeploymentError('Control file identity differs: '+str(path))
    return path
def path_metadata(path: Path) -> dict:
    value=path.lstat()
    return {'mode':stat.S_IMODE(value.st_mode),'uid':value.st_uid,'gid':value.st_gid}
def write_state(path: Path, state: dict) -> None:
    dependency_gate.write_state(path,state)
def mutation_has_started(state: dict) -> bool:
    return state.get('source_install_started') is True or state.get('source_install_complete') is True

def frozen_envelope() -> dict:
    path=require_regular_file(Path(__file__).with_name('production_alpha_dependency_envelope.json'),ENVELOPE_SHA256)
    try: envelope=json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError,json.JSONDecodeError) as error:raise DeploymentError('Invalid frozen envelope') from error
    if envelope.get('artifact')!='buy-dtf-transparency-frozen-post-laravel-envelope-v3' or envelope.get('php_version')!='8.2.30' or envelope.get('laravel_version')!='12.69.1':raise DeploymentError('Frozen dependency baseline differs')
    require_regular_file(Path(dependency_gate.__file__),GATE_HELPER_SHA256)
    require_regular_file(Path(environment_controls.__file__),NGINX_IDENTITY_HELPER_SHA256)
    return envelope

def require_fpm_opcache_probe() -> Path:
    return require_regular_file(Path(frozen_envelope()['fpm_probe_path']),FPM_OPCACHE_PROBE_SHA256)
def require_nginx_identity_helper() -> Path:
    return require_regular_file(Path(environment_controls.__file__),NGINX_IDENTITY_HELPER_SHA256)
def run(argv: list[str], *, cwd: Path, timeout: int, env: dict) -> subprocess.CompletedProcess:
    try: result=subprocess.run(argv,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as error:raise DeploymentError('Reviewed FPM probe unavailable') from error
    if result.returncode:raise DeploymentError('Reviewed FPM probe failed')
    return result

def fpm_fastcgi_environment(script_filename: Path, script_name: str) -> dict[str, str]:
    """Build a closed FastCGI parameter set with no inherited ini overrides."""

    script_filename = script_filename.resolve(strict=True)
    if not script_name.startswith("/") or "\x00" in script_name:
        raise DeploymentError("PHP-FPM probe script name is invalid.")
    return {
        "DOCUMENT_ROOT": str(APP_ROOT / "public"),
        "GATEWAY_INTERFACE": "CGI/1.1",
        "HTTPS": "on",
        "QUERY_STRING": "",
        "REDIRECT_STATUS": "200",
        "REMOTE_ADDR": "127.0.0.1",
        "REQUEST_METHOD": "GET",
        "REQUEST_URI": script_name,
        "SCRIPT_FILENAME": str(script_filename),
        "SCRIPT_NAME": script_name,
        "SERVER_NAME": "buy-dtf.com",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
    }

def probe_fpm_opcache() -> dict[str, Any]:
    probe = require_fpm_opcache_probe()
    require_nginx_identity_helper()
    if not FPM_SOCKET.is_socket():
        raise FpmProbeUnavailable("The reviewed PHP-FPM socket is unavailable.")
    environment = fpm_fastcgi_environment(
        probe,
        "/internal-opcache-probe.php",
    )
    try:
        completed = run(
            ["/usr/bin/cgi-fcgi", "-bind", "-connect", str(FPM_SOCKET)],
            cwd=APP_ROOT,
            timeout=30,
            env=environment,
        )
    except DeploymentError as exception:
        raise FpmProbeUnavailable(
            "The reviewed PHP-FPM OPcache probe is unavailable."
        ) from exception
    output = completed.stdout.replace("\r\n", "\n")
    if "\n\n" not in output:
        raise DeploymentError("PHP-FPM OPcache probe returned no CGI body.")
    headers, body = output.split("\n\n", 1)
    if "status: 5" in headers.lower():
        raise DeploymentError("PHP-FPM OPcache probe returned a server error.")
    try:
        payload = json.loads(body)
        validated = environment_controls.validate_fpm_opcache_payload(payload)
        policy = dependency_gate.derive_opcache_revalidation_policy(validated)
    except (
        json.JSONDecodeError,
        environment_controls.EnvironmentControlError,
        dependency_gate.GateError,
    ) as exception:
        raise DeploymentError(f"PHP-FPM OPcache envelope is invalid: {exception}") from exception
    if validated.get("php_version") != EXPECTED_PHP_VERSION:
        raise DeploymentError("PHP-FPM OPcache probe loaded an unexpected PHP version.")
    return {
        "artifact": "buy-dtf-php-fpm-opcache-envelope-v4",
        "status": "pass",
        "probe_helper_sha256": FPM_OPCACHE_PROBE_SHA256,
        "environment_helper_sha256": NGINX_IDENTITY_HELPER_SHA256,
        "probe": validated,
        "policy": policy,
    }

def validate_frozen_fpm_opcache_record(expected: Any) -> dict[str, Any]:
    """Validate a receipt-bound FPM envelope without requiring FPM to be reachable."""

    if not isinstance(expected, dict):
        raise DeploymentError("Durable state has no frozen PHP-FPM OPcache envelope.")
    if set(expected) != {
        "artifact",
        "status",
        "probe_helper_sha256",
        "environment_helper_sha256",
        "probe",
        "policy",
    }:
        raise DeploymentError("Frozen PHP-FPM OPcache envelope has an unexpected shape.")
    if (
        expected.get("artifact") != "buy-dtf-php-fpm-opcache-envelope-v4"
        or expected.get("status") != "pass"
        or expected.get("probe_helper_sha256") != FPM_OPCACHE_PROBE_SHA256
        or expected.get("environment_helper_sha256") != NGINX_IDENTITY_HELPER_SHA256
    ):
        raise DeploymentError("Frozen PHP-FPM OPcache envelope identity differs.")
    try:
        validated_probe = environment_controls.validate_fpm_opcache_payload(
            expected.get("probe")
        )
        derived_policy = dependency_gate.derive_opcache_revalidation_policy(validated_probe)
    except (
        environment_controls.EnvironmentControlError,
        dependency_gate.GateError,
    ) as exception:
        raise DeploymentError(
            f"Frozen PHP-FPM OPcache envelope is invalid: {exception}"
        ) from exception
    if validated_probe.get("php_version") != EXPECTED_PHP_VERSION:
        raise DeploymentError("Frozen PHP-FPM OPcache envelope has an unexpected PHP version.")
    if expected.get("policy") != derived_policy:
        raise DeploymentError("Frozen PHP-FPM OPcache policy differs from its probe values.")
    if expected != frozen_envelope()["fpm_opcache"]:
        raise DeploymentError("Frozen PHP-FPM state differs from the reviewed source envelope.")
    return expected

def require_frozen_fpm_opcache(expected: Any) -> dict[str, Any]:
    """Re-read PHP-FPM and require the exact staged/cutover OPcache envelope."""

    frozen = validate_frozen_fpm_opcache_record(expected)
    current = probe_fpm_opcache()
    if current != frozen:
        raise DeploymentError(
            "PHP-FPM OPcache settings differ from the frozen reviewed envelope; "
            "front-controller mutation is prohibited."
        )
    return current

def record_fpm_opcache_before_mutation(
    state: dict[str, Any],
    state_path: Path,
) -> dict[str, Any]:
    """Recheck and durably bind the staged FPM envelope before mutation."""

    if mutation_has_started(state):
        raise DeploymentError(
            "PHP-FPM OPcache cannot be frozen after source mutation begins."
        )
    frozen = validate_frozen_fpm_opcache_record(state.get("fpm_opcache"))
    current = require_frozen_fpm_opcache(frozen)
    envelope_sha256 = sha256_bytes(dependency_gate.canonical_bytes(frozen))
    receipt = {
        "artifact": "buy-dtf-php-fpm-opcache-before-source-mutation-v3",
        "status": "pass",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "release_receipt_sha256": state.get("release_receipt_sha256"),
        "probe_helper_sha256": FPM_OPCACHE_PROBE_SHA256,
        "staged_frozen_envelope_sha256": envelope_sha256,
        "current_live_envelope_sha256": sha256_bytes(
            dependency_gate.canonical_bytes(current)
        ),
        "exact_match": current == frozen,
        "source_mutation_started": False,
        "fpm_opcache": current,
    }
    if (
        not isinstance(receipt["release_receipt_sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", receipt["release_receipt_sha256"])
        or receipt["exact_match"] is not True
    ):
        raise DeploymentError(
            "The pre-mutation PHP-FPM OPcache receipt cannot bind the staged release."
        )
    receipt_path = state_path.parent / "fpm-opcache-before-source-mutation-receipt.json"
    receipt_sha256 = dependency_gate.write_new_json(receipt_path, receipt)
    state["fpm_opcache_before_mutation"] = receipt
    state["fpm_opcache_before_mutation_receipt"] = {
        "path": str(receipt_path),
        "sha256": receipt_sha256,
    }
    write_state(state_path, state)
    return receipt

def validate_post_mutation_frozen_fpm_opcache(
    state: dict[str, Any],
    state_path: Path,
) -> dict[str, Any]:
    """Validate the staged and immediately-pre-mutation envelope offline."""

    if not mutation_has_started(state):
        raise DeploymentError(
            "Emergency frozen PHP-FPM policy is prohibited before source mutation."
        )
    frozen = validate_frozen_fpm_opcache_record(state.get("fpm_opcache"))
    checkpoint = state.get("fpm_opcache_before_mutation")
    if not isinstance(checkpoint, dict) or set(checkpoint) != {
        "artifact",
        "status",
        "checked_at_utc",
        "release_receipt_sha256",
        "probe_helper_sha256",
        "staged_frozen_envelope_sha256",
        "current_live_envelope_sha256",
        "exact_match",
        "source_mutation_started",
        "fpm_opcache",
    }:
        raise DeploymentError(
            "Durable state has no valid immediately-pre-mutation PHP-FPM envelope."
        )
    envelope_sha256 = sha256_bytes(dependency_gate.canonical_bytes(frozen))
    if (
        checkpoint.get("artifact")
        != "buy-dtf-php-fpm-opcache-before-source-mutation-v3"
        or checkpoint.get("status") != "pass"
        or not isinstance(checkpoint.get("checked_at_utc"), str)
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            checkpoint["checked_at_utc"],
        )
        is None
        or checkpoint.get("release_receipt_sha256")
        != state.get("release_receipt_sha256")
        or checkpoint.get("probe_helper_sha256") != FPM_OPCACHE_PROBE_SHA256
        or checkpoint.get("staged_frozen_envelope_sha256") != envelope_sha256
        or checkpoint.get("current_live_envelope_sha256") != envelope_sha256
        or checkpoint.get("exact_match") is not True
        or checkpoint.get("source_mutation_started") is not False
        or checkpoint.get("fpm_opcache") != frozen
    ):
        raise DeploymentError(
            "Immediately-pre-mutation PHP-FPM envelope differs from the staged envelope."
        )
    receipt_item = state.get("fpm_opcache_before_mutation_receipt")
    if not isinstance(receipt_item, dict) or set(receipt_item) != {"path", "sha256"}:
        raise DeploymentError(
            "Durable state has no pre-mutation PHP-FPM envelope receipt binding."
        )
    receipt_path = require_regular_file(
        Path(str(receipt_item.get("path", ""))),
        str(receipt_item.get("sha256", "")),
    )
    expected_path = (
        state_path.resolve(strict=True).parent
        / "fpm-opcache-before-source-mutation-receipt.json"
    )
    if receipt_path != expected_path or path_metadata(receipt_path).get("mode") != 0o600:
        raise DeploymentError(
            "Pre-mutation PHP-FPM envelope receipt is outside private durable state."
        )
    try:
        persisted = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise DeploymentError(
            "Pre-mutation PHP-FPM envelope receipt is invalid UTF-8 JSON."
        ) from exception
    if persisted != checkpoint:
        raise DeploymentError(
            "Pre-mutation PHP-FPM envelope receipt differs from durable state."
        )
    return frozen

def _gate_context_from_frozen_envelope(
    state: dict[str, Any],
    state_path: Path,
    frozen_opcache: dict[str, Any],
) -> dependency_gate.GateContext:
    backup_value = state.get("front_controller_backup")
    backup_sha256 = state.get("front_controller_backup_sha256")
    if not isinstance(backup_value, str) or backup_sha256 != EXPECTED_FRONT_CONTROLLER_SHA256:
        raise DeploymentError("Front-controller rollback backup is unavailable.")
    state_directory = state_path.resolve(strict=True).parent
    backup = require_regular_file(Path(backup_value), backup_sha256)
    if backup != state_directory / "front-controller-before.php":
        raise DeploymentError("Front-controller backup differs from the durable state path.")
    policy = frozen_opcache.get("policy")
    if not isinstance(policy, dict):
        raise DeploymentError("Durable state has no frozen OPcache revalidation policy.")
    return dependency_gate.GateContext(
        application_root=APP_ROOT,
        front_controller=FRONT_CONTROLLER,
        state_path=state_path,
        evidence_directory=state_directory,
        original_backup=backup,
        original_sha256=backup_sha256,
        opcache_policy=policy,
    )

def gate_context(
    state: dict[str, Any],
    state_path: Path,
    *,
    allow_frozen_policy_for_exact_existing_gate: bool = False,
) -> dependency_gate.GateContext:
    """Build a normal context only after reading the current live FPM SAPI."""

    frozen_opcache = validate_frozen_fpm_opcache_record(state.get("fpm_opcache"))
    policy = frozen_opcache["policy"]
    try:
        require_frozen_fpm_opcache(frozen_opcache)
    except FpmProbeUnavailable as exception:
        live = dependency_gate.file_identity(FRONT_CONTROLLER)
        if (
            not allow_frozen_policy_for_exact_existing_gate
            or live.get("sha256") != MAINTENANCE_GATE_SHA256
            or live.get("metadata")
            != dependency_gate.reviewed_front_controller_metadata()
        ):
            raise
        if mutation_has_started(state):
            frozen_opcache = validate_post_mutation_frozen_fpm_opcache(
                state,
                state_path,
            )
            policy = frozen_opcache["policy"]
        try:
            dependency_gate.validate_opcache_revalidation_policy(policy)
        except dependency_gate.GateError as policy_exception:
            raise DeploymentError(
                "Frozen OPcache policy is invalid during emergency restoration."
            ) from policy_exception
        history = state.setdefault("emergency_existing_gate_opcache_fallbacks", [])
        if not isinstance(history, list):
            raise DeploymentError("Emergency OPcache fallback history is invalid.")
        history.append(
            {
                "status": "exact_existing_gate_retained_with_frozen_policy",
                "failure_class": type(exception).__name__,
                "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
                "front_controller": live,
                "policy": policy,
            }
        )
        write_state(state_path, state)
    return _gate_context_from_frozen_envelope(state, state_path, frozen_opcache)

def post_mutation_emergency_gate_context(
    state: dict[str, Any],
    state_path: Path,
) -> dependency_gate.GateContext:
    """Build post-mutation containment, falling back only when FPM is unavailable."""

    frozen_opcache = validate_post_mutation_frozen_fpm_opcache(state, state_path)
    live = dependency_gate.file_identity(FRONT_CONTROLLER)
    if (
        live.get("sha256")
        not in {EXPECTED_FRONT_CONTROLLER_SHA256, MAINTENANCE_GATE_SHA256}
        or live.get("metadata") != dependency_gate.reviewed_front_controller_metadata()
    ):
        raise DeploymentError(
            "Post-mutation emergency containment found an unknown front controller."
        )
    try:
        current = require_frozen_fpm_opcache(frozen_opcache)
    except FpmProbeUnavailable as exception:
        history = state.setdefault("post_mutation_emergency_fpm_fallbacks", [])
        if not isinstance(history, list):
            raise DeploymentError("Emergency PHP-FPM fallback history is invalid.")
        history.append(
            {
                "status": (
                    "exact_gate_reassertion_with_frozen_policy"
                    if live.get("sha256") == MAINTENANCE_GATE_SHA256
                    else "exact_original_gate_install_with_frozen_policy"
                ),
                "failure_class": type(exception).__name__,
                "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
                "front_controller": live,
                "frozen_envelope_sha256": sha256_bytes(
                    dependency_gate.canonical_bytes(frozen_opcache)
                ),
                "policy": frozen_opcache["policy"],
                "immediately_before_mutation_receipt": state.get(
                    "fpm_opcache_before_mutation_receipt"
                ),
            }
        )
        write_state(state_path, state)
        current = frozen_opcache
    return _gate_context_from_frozen_envelope(state, state_path, current)

EXPECTED_APP_UID = 1000
EXPECTED_APP_GID = 1000
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


EXPECTED_CANDIDATE_VENDOR_FILE_COUNT = 6460


EXPECTED_CANDIDATE_VENDOR_DIRECTORY_COUNT = 925


EXPECTED_CANDIDATE_VENDOR_ORDINARY_FILE_COUNT = 6450


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


EXPECTED_CANDIDATE_VENDOR_MANIFEST = {
    "bytes": 26481661,
    "directories": 925,
    "files": 6460,
    "sha256": "7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8",
}


EXPECTED_APPLICATION_AUTOLOAD_ENTRIES = 126


EXPECTED_APPLICATION_AUTOLOAD_SHA256 = (
    "342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91"
)


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




def verify_read_only_nginx() -> dict[str, Any]:
    """Reconstruct the accepted effective dump without granting nginx privileges.

    Every included raw byte and expanded include set must match. Services must
    still have their accepted PIDs/start times. Drift requires administrator
    re-verification; this function never calls sudo, nginx -T or a reload.
    """
    envelope = frozen_envelope()
    expected = envelope['nginx']['accepted_stable_identity']
    capture = require_regular_file(Path(envelope['accepted_nginx_dump_path']), expected['effective_config_sha256'])
    if path_metadata(capture)['mode'] != 0o600:
        raise DeploymentError('Accepted nginx evidence is not private mode 0600')
    raw = capture.read_bytes()
    markers = list(re.finditer(rb'(?m)^# configuration file ([^\r\n]+):\n', raw))
    names, includes, rebuilt, files = set(), set(), b'', []
    for marker in markers:
        name = marker.group(1).decode('utf-8'); path = Path(name)
        if not path.is_absolute() or not str(path).startswith('/etc/nginx/'):
            raise DeploymentError('Unexpected nginx include path')
        resolved = path.resolve(strict=True)
        for protected in [path, resolved, *path.parents, *resolved.parents]:
            metadata = protected.stat()
            if metadata.st_uid != 0 or metadata.st_gid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022 or os.access(protected, os.W_OK):
                raise DeploymentError('Nginx path is no longer administrator-controlled')
        data = resolved.read_bytes()
        files.append({'path':name,'sha256':sha256_bytes(data),'resolved_path':str(resolved)})
        rebuilt += b'# configuration file ' + marker.group(1) + b':\n' + data + b'\n'; names.add(name)
        for directive in re.finditer(r'(?m)^\s*include\s+([^;\r\n]+);',data.decode('utf-8')):
            pattern = directive.group(1).strip().strip(chr(34)+chr(39))
            if not pattern.startswith('/'): pattern='/etc/nginx/'+pattern
            includes.update(glob.glob(pattern))
    if len(markers) != 18 or rebuilt != raw or includes != names - {'/etc/nginx/nginx.conf'}:
        raise DeploymentError('Current nginx include bytes/set differ; administrator re-verification required')
    try: route=environment_controls.identify_nginx_document_root(raw.decode('utf-8'))
    except environment_controls.EnvironmentControlError as error: raise DeploymentError(str(error)) from error
    if route != expected['document_root_identity']:
        raise DeploymentError('Nginx root/socket/SCRIPT_FILENAME identity differs')
    services = subprocess.run(['/usr/bin/systemctl','show','nginx.service','php8.2-fpm.service','supervisor.service','cron.service','--no-pager','--property=MainPID,NRestarts,ExecMainStartTimestamp,ExecMainStartTimestampMonotonic,Id,LoadState,ActiveState,SubState,ActiveEnterTimestampMonotonic'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
    if services.returncode or sha256_bytes(services.stdout) != envelope['services_sha256']:
        raise DeploymentError('Effective service identity changed; administrator re-verification required')
    return {'status':'pass','method':'accepted_dump_exact_current_bytes_and_includes_unchanged_services','effective_config_sha256':sha256_bytes(raw),'document_root_identity':route,'services_sha256':sha256_bytes(services.stdout),'files':files,'new_administrator_access_required':False}


def require_configuration_identity() -> dict[str, str]:
    expected=frozen_envelope()['configuration_sha256']
    current={name:sha256_file(require_regular_file(APP_ROOT/name)) for name in expected}
    if current != expected:raise DeploymentError('Frozen live configuration bytes differ')
    return current


def require_source_identity(app_root: Path, *, target: bool) -> dict[str, Any]:
    expected=frozen_envelope()['target_source' if target else 'source']
    current=source_manifest(app_root)
    if current != expected:raise DeploymentError('Complete runtime source CAS differs')
    return current


def require_cache_identity(app_root: Path) -> dict[str, Any]:
    expected=frozen_envelope()['cache'];root=app_root/'bootstrap/cache'
    if root.is_symlink() or set(path.name for path in root.iterdir()) != set(expected['entries']):raise DeploymentError('Bootstrap cache path set differs')
    root_metadata={'kind':'directory',**path_metadata(root)}
    if root_metadata != expected['root_metadata']:raise DeploymentError('Bootstrap cache owner/group/mode differs')
    for name,record in expected['entries'].items():
        path=require_regular_file(root/name,record['sha256'])
        if {'kind':'file',**path_metadata(path)} != {key:record[key] for key in ['kind','uid','gid','mode']} or path.stat().st_size != record['bytes']:raise DeploymentError('Bootstrap cache entry owner/group/mode differs')
    return expected
