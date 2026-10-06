"""V6 activation prerequisites; accepted scheduler/gate controls stay unchanged."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

import production_alpha_scheduler_guard as scheduler

ACCEPTED_CORRECTION_COMMIT = "2c14d6e401c9d24a7153c12f6ee4b74bd96f8582"
ACCEPTED_SCHEDULER_SHA256 = "d4334e0181ececbd76d140711998f1d143f648dc9a4de85f413f2083354b6489"
ACCEPTED_PROCESS_PROBE_SHA256 = "1dca015bffdaf4433ff00ecb0569faad0928c28a726b827f773d4cae4b4737c6"
WITNESS_SHA256 = "d3f9ac27e72f009156aedd3afca57b4f9586ec64a860d2cfd9fe3a5143b2c759"
EXPECTED_PHP_VERSION = "8.2.30"
EXPECTED_SOCKET = Path("/run/php/php8.2-fpm.sock")
GENERATION = "source-only-v6-activation"


class ActivationError(RuntimeError):
    pass


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_control(path: Path, expected: str) -> bytes:
    metadata = path.lstat()
    data = path.read_bytes()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 1000 or metadata.st_gid != 1000 or stat.S_IMODE(metadata.st_mode) & 0o022 or sha(data) != expected:
        raise ActivationError("Activation control bytes or protection differ from review.")
    return data


def socket_identity(path: Path) -> dict[str, Any]:
    item = path.lstat()
    if path != EXPECTED_SOCKET or not stat.S_ISSOCK(item.st_mode):
        raise ActivationError("Activation requires the exact production PHP 8.2 FPM socket.")
    return {"path": str(path), "device": item.st_dev, "inode": item.st_ino,
        "uid": item.st_uid, "gid": item.st_gid, "mode": stat.S_IMODE(item.st_mode)}


def validate_witness(value: Any, nonce: str) -> dict[str, Any]:
    keys = {"artifact", "status", "nonce", "sapi", "php_version", "observer_uid", "observer_gid",
        "identity", "working_directory", "executable", "read_only", "environments_read", "process_or_permission_actions"}
    if not isinstance(value, dict) or set(value) != keys or value.get("artifact") != "buy-dtf-process-scope-v1" or value.get("status") != "pass" or value.get("nonce") != nonce or value.get("sapi") != "fpm-fcgi" or value.get("php_version") != EXPECTED_PHP_VERSION or type(value.get("observer_uid")) is not int or value["observer_uid"] != 33 or type(value.get("observer_gid")) is not int or value["observer_gid"] != 33 or value.get("read_only") is not True or value.get("environments_read") is not False or value.get("process_or_permission_actions") is not False:
        raise ActivationError("Exact PHP 8.2.30 FPM UID/GID 33 witness did not pass.")
    identity = value["identity"]
    if not isinstance(identity, dict) or set(identity) != {"pid", "uid", "start_ticks", "argv_sha256"} or any(type(identity.get(k)) is not int for k in ("pid", "uid", "start_ticks")) or identity["pid"] <= 1 or identity["uid"] != 33 or identity["start_ticks"] <= 0 or not isinstance(identity.get("argv_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", identity["argv_sha256"]):
        raise ActivationError("FPM witness kernel identity is malformed.")
    try:
        scheduler._scope_path(value["working_directory"])
        scheduler._scope_path(value["executable"])
    except scheduler.SchedulerError as error:
        raise ActivationError("FPM witness scope is malformed.") from error
    return identity


def verify_production_fpm_scope() -> dict[str, Any]:
    """One real FastCGI request executes the witness and accepted scope probe.

    No version override exists. Local PHP 8.3.6, CLI PHP 8.2.30, recorded local
    evidence and a target-unavailable rejection cannot qualify this prerequisite.
    """
    if os.geteuid() != 1000:
        raise ActivationError("Activation FPM verification requires UID 1000.")
    root = Path(__file__).resolve().parent
    directory = script = scope_copy = None
    try:
        require_control(root / "production_alpha_scheduler_guard.py", ACCEPTED_SCHEDULER_SHA256)
        scope_probe = root / "production_alpha_process_scope_probe.php"
        scope_code = require_control(scope_probe, ACCEPTED_PROCESS_PROBE_SHA256)
        code = require_control(root / "production_alpha_fpm_activation_probe.php", WITNESS_SHA256)
        socket_before = socket_identity(EXPECTED_SOCKET)
        nonce = secrets.token_hex(24)
        directory = Path(tempfile.mkdtemp(prefix="buy-dtf-readonly-fpm-activation-"))
        script = directory / "witness.php"
        scope_copy = directory / "scope.php"
        script.write_bytes(code)
        scope_copy.write_bytes(scope_code)
        os.chmod(script, 0o644)
        os.chmod(scope_copy, 0o644)
        os.chmod(directory, 0o711)
        scheduler.FpmProcessScopeReader._verify_execution_copy(directory, script, code)
        scheduler.FpmProcessScopeReader._verify_execution_copy(directory, scope_copy, scope_code)
        environment = {"GATEWAY_INTERFACE": "CGI/1.1", "SERVER_PROTOCOL": "HTTP/1.1",
            "REQUEST_METHOD": "GET", "CONTENT_LENGTH": "0", "SCRIPT_FILENAME": str(script),
            "SCRIPT_NAME": "/internal-fpm-activation.php", "DOCUMENT_ROOT": str(directory),
            "REQUEST_URI": "/internal-fpm-activation.php", "QUERY_STRING": "",
            "REMOTE_ADDR": "127.0.0.1", "SERVER_NAME": "buy-dtf.com", "SERVER_PORT": "443",
            "HTTPS": "on", "REDIRECT_STATUS": "200", "BUYDTF_FPM_ACTIVATION_NONCE": nonce}
        result = subprocess.run(["/usr/bin/cgi-fcgi", "-bind", "-connect", str(EXPECTED_SOCKET)],
            env=environment, capture_output=True, timeout=5, check=False)
        scheduler.FpmProcessScopeReader._verify_execution_copy(directory, script, code)
        scheduler.FpmProcessScopeReader._verify_execution_copy(directory, scope_copy, scope_code)
        if result.returncode or len(result.stdout) > 4096 or len(result.stderr) > 4096:
            raise ActivationError("Activation FPM witness transport failed.")
        headers, body = result.stdout.replace(b"\r\n", b"\n").split(b"\n\n", 1)
        statuses = re.findall(br"(?im)^Status:\s*([^\n]+)$", headers)
        if statuses and (len(statuses) != 1 or re.fullmatch(br"200(?:\s+OK)?", statuses[0]) is None):
            raise ActivationError("Production PHP 8.2.30 FPM witness rejected the request.")
        witness = json.loads(body.decode("utf-8", errors="strict"), object_pairs_hook=scheduler._unique_scope_object)
        identity = validate_witness(witness, nonce)
        entry = Path("/proc") / str(identity["pid"])
        if scheduler._process_identity(entry) != identity:
            raise ActivationError("FPM witness kernel identity changed after the accepted probe.")
        if scheduler._process_identity(entry) != identity or socket_identity(EXPECTED_SOCKET) != socket_before:
            raise ActivationError("Production FPM target or socket changed during activation verification.")
        return {"artifact": "buy-dtf-production-fpm-scope-prerequisite-v1", "status": "pass",
            "generation": GENERATION, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(), "php_version": EXPECTED_PHP_VERSION, "sapi": "fpm-fcgi",
            "actor_uid": 1000, "observer_uid": 33, "observer_gid": 33, "identity": identity,
            "socket": socket_before, "witness_sha256": WITNESS_SHA256,
            "accepted_scope_probe_sha256": ACCEPTED_PROCESS_PROBE_SHA256,
            "accepted_scheduler_sha256": ACCEPTED_SCHEDULER_SHA256,
            "witness_response_sha256": sha(result.stdout), "scope_response_sha256": scheduler.digest(witness),
            "working_directory_sha256": sha(witness["working_directory"].encode()),
            "executable_sha256": sha(witness["executable"].encode()), "nonce_sha256": sha(nonce.encode()),
            "read_only": True, "environments_read": False, "process_or_permission_actions": False}
    except ActivationError:
        raise
    except (OSError, ValueError, IndexError, UnicodeError, subprocess.SubprocessError, scheduler.SchedulerError) as error:
        raise ActivationError("Exact production FPM process-scope prerequisite is unavailable or invalid.") from error
    finally:
        if scope_copy is not None and scope_copy.exists():
            scheduler.FpmProcessScopeReader._verify_execution_copy(directory, scope_copy, scope_code)
            scope_copy.unlink()
        if script is not None and script.exists():
            scheduler.FpmProcessScopeReader._verify_execution_copy(directory, script, code)
            script.unlink()
        if directory is not None:
            directory.rmdir()


def validate_proof(proof: Any) -> dict[str, Any]:
    keys = {"artifact", "status", "generation", "checked_at_utc", "monotonic_ns", "php_version", "sapi",
        "actor_uid", "observer_uid", "observer_gid", "identity", "socket", "witness_sha256",
        "accepted_scope_probe_sha256", "accepted_scheduler_sha256", "witness_response_sha256",
        "scope_response_sha256", "working_directory_sha256", "executable_sha256", "nonce_sha256",
        "read_only", "environments_read", "process_or_permission_actions"}
    if not isinstance(proof, dict) or set(proof) != keys or proof.get("artifact") != "buy-dtf-production-fpm-scope-prerequisite-v1" or proof.get("status") != "pass" or proof.get("generation") != GENERATION or proof.get("php_version") != EXPECTED_PHP_VERSION or proof.get("sapi") != "fpm-fcgi" or proof.get("actor_uid") != 1000 or proof.get("observer_uid") != 33 or proof.get("observer_gid") != 33 or proof.get("witness_sha256") != WITNESS_SHA256 or proof.get("accepted_scope_probe_sha256") != ACCEPTED_PROCESS_PROBE_SHA256 or proof.get("accepted_scheduler_sha256") != ACCEPTED_SCHEDULER_SHA256 or proof.get("read_only") is not True or proof.get("environments_read") is not False or proof.get("process_or_permission_actions") is not False:
        raise ActivationError("Staged production PHP 8.2.30 FPM prerequisite is missing or mismatched.")
    try:
        stamp = datetime.fromisoformat(proof["checked_at_utc"])
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0 or type(proof["monotonic_ns"]) is not int or proof["monotonic_ns"] <= 0:
            raise ValueError("Missing observation clock")
        validate_witness({"artifact": "buy-dtf-process-scope-v1", "status": "pass",
            "nonce": "proof-validation", "sapi": proof["sapi"], "php_version": proof["php_version"],
            "observer_uid": proof["observer_uid"], "observer_gid": proof["observer_gid"],
            "identity": proof["identity"], "working_directory": "/", "executable": "/usr/sbin/php-fpm8.2", "read_only": True, "environments_read": False,
            "process_or_permission_actions": False}, "proof-validation")
        socket = proof["socket"]
        if not isinstance(socket, dict) or set(socket) != {"path", "device", "inode", "uid", "gid", "mode"} or socket["path"] != str(EXPECTED_SOCKET) or any(type(socket[k]) is not int or socket[k] < 0 for k in ("device", "inode", "uid", "gid", "mode")) or socket["inode"] == 0 or socket["mode"] > 0o777:
            raise ValueError("Malformed socket")
        for key in ("witness_response_sha256", "scope_response_sha256", "working_directory_sha256", "executable_sha256", "nonce_sha256"):
            if not isinstance(proof[key], str) or not re.fullmatch(r"[0-9a-f]{64}", proof[key]):
                raise ValueError("Malformed proof digest")
    except (ValueError, TypeError, KeyError) as error:
        raise ActivationError("Production FPM proof has malformed clock, kernel or socket evidence.") from error
    return proof
