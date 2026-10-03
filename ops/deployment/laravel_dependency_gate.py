#!/usr/bin/env python3
"""Durable static front-controller gate primitives for dependency cutovers.

This module deliberately has no production entry point.  Callers supply every
path, probe, health check, and mutation-state predicate.  The implementation
is derived from the independently reviewed incoming-order gate transition and
keeps the same gate bytes, owner, group, and mode.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


EXPECTED_APP_UID = 1000
EXPECTED_APP_GID = 1000
EXPECTED_WEB_UID = 33
EXPECTED_WEB_GID = 33
EXPECTED_FRONT_CONTROLLER_MODE = 0o644

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

ORIGIN_ROUTE = "origin_loopback"
PUBLIC_ROUTE = "public_cloudflare"
TRANSITION_PHASES = frozenset(
    {
        "replacement_pending",
        "installed",
        "installed_reconciled_from_live_identity",
        "verified",
        "original_already_present",
        "exact_original_verified",
        "containment_retained",
    }
)
GATE_PRESENT_PHASES = frozenset(
    {
        "installed",
        "installed_reconciled_from_live_identity",
        "verified",
        "containment_retained",
    }
)
DEPENDENCY_MUTATION_FIELDS = (
    "dependency_mutation_started",
    "vendor_exchange_intent",
    "vendor_exchange_complete",
    "cache_exchange_intent",
    "cache_exchange_complete",
    "lock_replace_intent",
    "lock_replaced",
)


class GateError(RuntimeError):
    """A gate invariant failed and the deployment must stop closed."""


class GateInterruption(BaseException):
    """Rehearsal-only abrupt interruption that bypasses ordinary recovery."""


Probe = Callable[[], dict[str, Any]]
HealthProbe = Callable[[], dict[str, Any]]
MutationPredicate = Callable[[dict[str, Any]], bool]
FaultInjector = Callable[[str], None]


@dataclass(frozen=True)
class GateContext:
    application_root: Path
    front_controller: Path
    state_path: Path
    evidence_directory: Path
    original_backup: Path
    original_sha256: str


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if sha256_bytes(MAINTENANCE_GATE_BYTES) != EXPECTED_GATE_SHA256:
    raise RuntimeError("Embedded static-gate bytes differ from the reviewed identity.")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def require_real_directory(path: Path, *, within: Path | None = None) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise GateError(f"Required directory is missing, invalid, or symbolic: {path}")
    resolved = path.resolve(strict=True)
    if within is not None:
        root = within.resolve(strict=True)
        if not _is_relative_to(resolved, root):
            raise GateError(f"Directory escapes its approved root: {path}")
    return resolved


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def reviewed_front_controller_metadata() -> dict[str, int | str]:
    return {
        "kind": "file",
        "mode": EXPECTED_FRONT_CONTROLLER_MODE,
        "uid": EXPECTED_APP_UID,
        "gid": EXPECTED_APP_GID,
    }


def initial_gate_state() -> dict[str, Any]:
    """Return the durable fields a new dependency rollback state must bind."""
    return {
        "front_controller_transitions": [],
        "static_gate_active": False,
        "containment_active": False,
        "containment_requested": False,
        "containment_http_verified": False,
        "gate_verified": False,
    }


def _descriptor_identity(descriptor: int) -> tuple[int, int, int, int, int, int, int]:
    metadata = os.fstat(descriptor)
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_mtime_ns,
    )


def file_identity(path: Path) -> dict[str, Any]:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError as exception:
        raise GateError(f"Required front-controller file is missing: {path}") from exception
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise GateError(f"Front-controller path is symbolic or not a regular file: {path}")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        before = _descriptor_identity(descriptor)
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = _descriptor_identity(descriptor)
        if before != after or size != after[2]:
            raise GateError("Front-controller identity changed while it was being read.")
        mode = after[3]
        if not stat.S_ISREG(mode):
            raise GateError("Front controller ceased to be a regular file while read.")
        return {
            "path": str(path.resolve(strict=True)),
            "sha256": digest.hexdigest(),
            "bytes": size,
            "metadata": {
                "kind": "file",
                "mode": stat.S_IMODE(mode),
                "uid": after[4],
                "gid": after[5],
            },
        }
    finally:
        os.close(descriptor)


def require_regular_file(path: Path, expected_sha256: str | None = None) -> Path:
    identity = file_identity(path)
    if expected_sha256 is not None and identity["sha256"] != expected_sha256:
        raise GateError(
            f"Checksum mismatch for {path.name}: expected {expected_sha256}, "
            f"got {identity['sha256']}"
        )
    return path.resolve(strict=True)


def _validate_context(context: GateContext, *, require_backup: bool = True) -> None:
    application_root = require_real_directory(context.application_root)
    front_parent = require_real_directory(context.front_controller.parent, within=application_root)
    if front_parent != context.front_controller.parent.resolve(strict=True):
        raise GateError("Front-controller parent did not resolve to its approved path.")
    evidence = require_real_directory(context.evidence_directory)
    if context.state_path.parent.resolve(strict=True) != evidence:
        raise GateError("Gate state path is outside the evidence directory.")
    backup_parent = context.original_backup.parent.resolve(strict=True)
    if backup_parent != evidence:
        raise GateError("Original front-controller backup is outside the evidence directory.")
    if require_backup:
        require_regular_file(context.original_backup, context.original_sha256)
    if not re_full_sha256(context.original_sha256):
        raise GateError("Original front-controller SHA-256 is invalid.")


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    parent = require_real_directory(path.parent)
    temporary = parent / f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(6)}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, payload: Any) -> None:
    atomic_write(path, canonical_bytes(payload), 0o600)


def write_new_json(path: Path, payload: Any) -> str:
    parent = require_real_directory(path.parent)
    temporary = parent / f".{path.name}.new-{os.getpid()}-{secrets.token_hex(6)}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exception:
            raise GateError(f"Refusing to overwrite existing gate evidence: {path}") from exception
        fsync_directory(parent)
    finally:
        temporary.unlink(missing_ok=True)
    return file_identity(path)["sha256"]


def write_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at_utc"] = utc_now()
    atomic_json(path, state)


def load_state(path: Path) -> dict[str, Any]:
    require_regular_file(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise GateError("Gate state is not valid UTF-8 JSON.") from exception
    if not isinstance(payload, dict):
        raise GateError("Gate state is not a JSON object.")
    return payload


def append_event(
    evidence_directory: Path,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    directory = require_real_directory(evidence_directory)
    path = directory / "gate-events.jsonl"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise GateError("Gate event log is symbolic or not a regular file.")
    payload = {"at_utc": utc_now(), "event": event, "details": details or {}}
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    created = not path.exists()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "ab") as handle:
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if created:
            fsync_directory(directory)


def record_front_controller_transition(
    *,
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    phase: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if phase not in TRANSITION_PHASES:
        raise GateError(f"Unrecognized front-controller transition phase: {phase}")
    history = state.setdefault("front_controller_transitions", [])
    if not isinstance(history, list):
        raise GateError("Front-controller transition history is invalid.")
    transition = {
        "sequence": len(history) + 1,
        "at_utc": utc_now(),
        "operation": operation,
        "phase": phase,
        "front_controller": str(context.front_controller),
        "details": details or {},
    }
    history.append(transition)
    state["front_controller_transition"] = transition
    write_state(context.state_path, state)
    append_event(
        context.evidence_directory,
        f"front_controller_{phase}",
        {"operation": operation, "sequence": transition["sequence"]},
    )
    return transition


def _inject(fault_injector: FaultInjector | None, stage: str) -> None:
    if fault_injector is not None:
        fault_injector(stage)


def atomic_front_controller_replace(
    *,
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    replacement_bytes: bytes,
    replacement_sha256: str,
    allowed_current_sha256: set[str],
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    _validate_context(context)
    if sha256_bytes(replacement_bytes) != replacement_sha256:
        raise GateError("Front-controller replacement bytes differ from their identity.")
    metadata = reviewed_front_controller_metadata()
    current = file_identity(context.front_controller)
    if current["sha256"] not in allowed_current_sha256:
        raise GateError("Front-controller replacement refuses unknown live bytes.")

    parent = require_real_directory(
        context.front_controller.parent,
        within=context.application_root,
    )
    temporary = parent / (
        f".{context.front_controller.name}.dependency-gate-{os.getpid()}-"
        f"{secrets.token_hex(6)}"
    )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchown(descriptor, EXPECTED_APP_UID, EXPECTED_APP_GID)
        os.fchmod(descriptor, EXPECTED_FRONT_CONTROLLER_MODE)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(replacement_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        prepared = file_identity(temporary)
        if prepared["sha256"] != replacement_sha256 or prepared["metadata"] != metadata:
            raise GateError(
                "Prepared front-controller replacement differs from reviewed bytes or metadata."
            )
        _inject(fault_injector, "after_prepared_verified")

        record_front_controller_transition(
            context=context,
            state=state,
            operation=operation,
            phase="replacement_pending",
            details={
                "before": current,
                "prepared": prepared,
                "target_sha256": replacement_sha256,
                "target_metadata": metadata,
            },
        )
        _inject(fault_injector, "after_replacement_pending")

        os.replace(temporary, context.front_controller)
        fsync_directory(parent)
        _inject(fault_injector, "after_replace_before_installed")
        installed = file_identity(context.front_controller)
        if installed["sha256"] != replacement_sha256 or installed["metadata"] != metadata:
            raise GateError(
                "Installed front-controller replacement differs from reviewed bytes or metadata."
            )
        record_front_controller_transition(
            context=context,
            state=state,
            operation=operation,
            phase="installed",
            details={
                "before": current,
                "installed": installed,
                "target_sha256": replacement_sha256,
                "target_metadata": metadata,
            },
        )
        _inject(fault_injector, "after_installed")
        return {"before": current, "prepared": prepared, "installed": installed}
    finally:
        temporary.unlink(missing_ok=True)


def restore_front_controller_exact(
    *,
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    receipt_name: str,
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    _validate_context(context)
    backup = require_regular_file(context.original_backup, context.original_sha256)
    metadata = reviewed_front_controller_metadata()
    before = file_identity(context.front_controller)
    replacement: dict[str, Any] | None = None
    if before["sha256"] == context.original_sha256 and before["metadata"] == metadata:
        record_front_controller_transition(
            context=context,
            state=state,
            operation=operation,
            phase="original_already_present",
            details={
                "identity": before,
                "target_sha256": context.original_sha256,
                "target_metadata": metadata,
            },
        )
        _inject(fault_injector, "after_original_already_present")
    else:
        replacement = atomic_front_controller_replace(
            context=context,
            state=state,
            operation=operation,
            replacement_bytes=backup.read_bytes(),
            replacement_sha256=context.original_sha256,
            allowed_current_sha256={context.original_sha256, EXPECTED_GATE_SHA256},
            fault_injector=fault_injector,
        )

    restored = file_identity(context.front_controller)
    if restored["sha256"] != context.original_sha256 or restored["metadata"] != metadata:
        raise GateError("Exact original front-controller restoration failed.")
    record_front_controller_transition(
        context=context,
        state=state,
        operation=operation,
        phase="exact_original_verified",
        details={
            "identity": restored,
            "target_sha256": context.original_sha256,
            "target_metadata": metadata,
        },
    )
    _inject(fault_injector, "after_exact_original_verified")
    state["static_gate_active"] = False
    state["containment_active"] = False
    state["gate_verified"] = False
    write_state(context.state_path, state)
    _inject(fault_injector, "after_original_state_persisted")

    receipt = {
        "status": "pass",
        "generated_at_utc": utc_now(),
        "operation": operation,
        "before": before,
        "replacement": replacement,
        "restored": restored,
        "exact_original_restored": True,
    }
    receipt_path = context.evidence_directory / receipt_name
    receipt_sha256 = write_new_json(receipt_path, receipt)
    return {**receipt, "path": str(receipt_path), "receipt_sha256": receipt_sha256}


def dependency_mutation_has_started(state: dict[str, Any]) -> bool:
    return any(state.get(field) is True for field in DEPENDENCY_MUTATION_FIELDS)


def gate_probe_passed(result: dict[str, Any], expected_route: str) -> bool:
    return (
        result.get("route") == expected_route
        and result.get("status") == 503
        and result.get("header_verified") is True
        and result.get("sentinel_verified") is True
    )


def capture_health_check(check: HealthProbe) -> dict[str, Any]:
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
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    mutation_started: MutationPredicate = dependency_mutation_has_started,
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    _validate_context(context)
    metadata = reviewed_front_controller_metadata()
    before = file_identity(context.front_controller)
    if before["sha256"] not in {context.original_sha256, EXPECTED_GATE_SHA256}:
        raise GateError("Containment found unknown front-controller bytes and refused overwrite.")
    replacement: dict[str, Any] | None = None
    if before["sha256"] != EXPECTED_GATE_SHA256 or before["metadata"] != metadata:
        replacement = atomic_front_controller_replace(
            context=context,
            state=state,
            operation=f"{operation}-exact-containment-install",
            replacement_bytes=MAINTENANCE_GATE_BYTES,
            replacement_sha256=EXPECTED_GATE_SHA256,
            allowed_current_sha256={context.original_sha256, EXPECTED_GATE_SHA256},
        )
    final = file_identity(context.front_controller)
    if final["sha256"] != EXPECTED_GATE_SHA256 or final["metadata"] != metadata:
        raise GateError("Exact static-gate containment could not be established.")
    record_front_controller_transition(
        context=context,
        state=state,
        operation=operation,
        phase="containment_retained",
        details={
            "identity": final,
            "mutation_started": mutation_started(state),
            "target_sha256": EXPECTED_GATE_SHA256,
            "target_metadata": metadata,
        },
    )
    _inject(fault_injector, "after_containment_retained")
    state["static_gate_active"] = True
    state["containment_active"] = True
    state["gate_verified"] = False
    state["status"] = f"{operation}_site_gated"
    write_state(context.state_path, state)
    _inject(fault_injector, "after_containment_state_persisted")
    receipt = {
        "status": "site_gated",
        "generated_at_utc": utc_now(),
        "operation": operation,
        "mutation_started": mutation_started(state),
        "before": before,
        "replacement": replacement,
        "final": final,
        "exact_gate_retained": True,
        "original_restoration_performed": False,
    }
    receipt_path = context.evidence_directory / f"{operation}-containment-receipt.json"
    receipt_sha256 = write_new_json(receipt_path, receipt)
    return {**receipt, "path": str(receipt_path), "receipt_sha256": receipt_sha256}


def install_static_gate(
    *,
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    origin_probe: Probe,
    public_probe: Probe,
    restored_health_probe: HealthProbe,
    mutation_started: MutationPredicate = dependency_mutation_has_started,
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    _validate_context(context)
    require_regular_file(context.original_backup, context.original_sha256)
    metadata = reviewed_front_controller_metadata()
    initial = file_identity(context.front_controller)
    replacement: dict[str, Any] | None = None
    reconciled_from_live_identity = False
    origin_result: dict[str, Any] | None = None
    public_result: dict[str, Any] | None = None
    try:
        if initial["sha256"] == context.original_sha256:
            if initial["metadata"] != metadata:
                raise GateError("Original front-controller metadata is not reviewed.")
            replacement = atomic_front_controller_replace(
                context=context,
                state=state,
                operation=operation,
                replacement_bytes=MAINTENANCE_GATE_BYTES,
                replacement_sha256=EXPECTED_GATE_SHA256,
                allowed_current_sha256={context.original_sha256},
                fault_injector=fault_injector,
            )
        elif initial["sha256"] == EXPECTED_GATE_SHA256:
            if initial["metadata"] != metadata:
                raise GateError("Live static gate has incorrect owner or mode.")
            reconciled_from_live_identity = True
            record_front_controller_transition(
                context=context,
                state=state,
                operation=operation,
                phase="installed_reconciled_from_live_identity",
                details={
                    "identity": initial,
                    "previous_transition": state.get("front_controller_transition"),
                    "target_sha256": EXPECTED_GATE_SHA256,
                    "target_metadata": metadata,
                },
            )
            _inject(fault_injector, "after_installed_reconciled")
        else:
            raise GateError("Static gate refuses unknown front-controller bytes.")

        state["static_gate_active"] = True
        state["containment_active"] = True
        state["gate_verified"] = False
        write_state(context.state_path, state)
        _inject(fault_injector, "after_gate_state_persisted")

        origin_result = origin_probe()
        if not gate_probe_passed(origin_result, ORIGIN_ROUTE):
            raise GateError(
                "The local/origin static-gate probe did not return the reviewed 503 response."
            )
        _inject(fault_injector, "after_origin_verified")

        public_result = public_probe()
        if not gate_probe_passed(public_result, PUBLIC_ROUTE):
            raise GateError(
                "The public Cloudflare static-gate probe did not return the reviewed 503 response."
            )
        _inject(fault_injector, "after_public_verified")

        verified = file_identity(context.front_controller)
        if verified["sha256"] != EXPECTED_GATE_SHA256 or verified["metadata"] != metadata:
            raise GateError("Verified static-gate identity changed during HTTP verification.")
        record_front_controller_transition(
            context=context,
            state=state,
            operation=operation,
            phase="verified",
            details={
                "identity": verified,
                "origin_probe": origin_result,
                "public_probe": public_result,
                "target_sha256": EXPECTED_GATE_SHA256,
                "target_metadata": metadata,
            },
        )
        state["gate_verified"] = True
        write_state(context.state_path, state)
        _inject(fault_injector, "after_verified")
        return {
            "sha256": EXPECTED_GATE_SHA256,
            "metadata": metadata,
            "initial": initial,
            "replacement": replacement,
            "reconciled_from_live_identity": reconciled_from_live_identity,
            "origin_probe": origin_result,
            "public_probe": public_result,
        }
    except Exception as exception:
        live_after_failure = file_identity(context.front_controller)
        if live_after_failure["sha256"] not in {
            context.original_sha256,
            EXPECTED_GATE_SHA256,
        }:
            raise GateError(
                "Static-gate failure left unknown front-controller bytes; refusing overwrite."
            ) from exception

        if mutation_started(state):
            containment = retain_static_gate_exact(
                context=context,
                state=state,
                operation=f"{operation}-verification-failure",
                mutation_started=mutation_started,
            )
            failure_receipt = {
                "status": "gate_failed_site_gated",
                "generated_at_utc": utc_now(),
                "operation": operation,
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
                "final": file_identity(context.front_controller),
            }
        else:
            restoration = restore_front_controller_exact(
                context=context,
                state=state,
                operation=f"{operation}-automatic-original-restore",
                receipt_name=f"{operation}-automatic-original-restore-receipt.json",
            )
            restored_health = capture_health_check(restored_health_probe)
            failure_receipt = {
                "status": "gate_failed_original_restored",
                "generated_at_utc": utc_now(),
                "operation": operation,
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
                "final": file_identity(context.front_controller),
            }

        failure_path = context.evidence_directory / f"{operation}-gate-failure-receipt.json"
        failure_sha256 = write_new_json(failure_path, failure_receipt)
        state["gate_failure_receipt"] = str(failure_path)
        state["gate_failure_receipt_sha256"] = failure_sha256
        if mutation_started(state):
            state["static_gate_active"] = True
            state["containment_active"] = True
            state["gate_verified"] = False
            state["status"] = f"{operation}_failed_site_gated"
        else:
            state["static_gate_active"] = False
            state["containment_active"] = False
            state["gate_verified"] = False
            if failure_receipt["post_restoration_health"]["status"] == "pass":
                state["status"] = f"{operation}_failed_original_restored"
            else:
                state["status"] = f"{operation}_failed_original_restored_health_failed"
        write_state(context.state_path, state)

        if mutation_started(state):
            raise GateError(
                "Static-gate verification failed after dependency mutation began; the exact "
                f"0644 gate remains installed (receipt {failure_sha256})."
            ) from exception
        if failure_receipt["post_restoration_health"]["status"] != "pass":
            raise GateError(
                "Static-gate installation failed before dependency mutation; the exact original "
                "front controller was restored, but normal health verification failed "
                f"(receipt {failure_sha256})."
            ) from exception
        raise GateError(
            "Static-gate installation failed before dependency mutation; the exact original "
            f"front controller was restored and normal health passed (receipt {failure_sha256})."
        ) from exception


def establish_rollback_containment(
    *,
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    origin_probe: Probe,
    public_probe: Probe,
    restored_health_probe: HealthProbe,
    mutation_started: MutationPredicate = dependency_mutation_has_started,
) -> dict[str, Any]:
    """Contain rollback and permit it under an exact gate if HTTP checks fail.

    Once dependency mutation has begun, origin or public verification failure
    is evidence of an unhealthy edge path, not permission to reopen.  If the
    exact reviewed local gate identity is durable, the caller may continue its
    boot-independent rollback and must keep the gate closed until rollback
    verification succeeds.
    """

    state["containment_requested"] = True
    state["status"] = f"{operation}_establishing_containment"
    write_state(context.state_path, state)
    append_event(
        context.evidence_directory,
        "rollback_containment_requested",
        {"operation": operation, "mutation_started": mutation_started(state)},
    )
    try:
        gate = install_static_gate(
            context=context,
            state=state,
            operation=operation,
            origin_probe=origin_probe,
            public_probe=public_probe,
            restored_health_probe=restored_health_probe,
            mutation_started=mutation_started,
        )
    except GateError as exception:
        live = file_identity(context.front_controller)
        if not mutation_started(state):
            raise
        if (
            live["sha256"] != EXPECTED_GATE_SHA256
            or live["metadata"] != reviewed_front_controller_metadata()
            or state.get("static_gate_active") is not True
            or state.get("containment_active") is not True
        ):
            raise GateError(
                "Rollback containment failed after dependency mutation and did not retain "
                "the exact reviewed gate."
            ) from exception
        state["status"] = f"{operation}_http_unverified_site_gated"
        state["containment_http_verified"] = False
        write_state(context.state_path, state)
        append_event(
            context.evidence_directory,
            "rollback_containment_http_unverified_site_gated",
            {
                "operation": operation,
                "identity": live,
                "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
            },
        )
        return {
            "status": "site_gated_http_unverified",
            "http_verified": False,
            "identity": live,
            "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
            "gate_failure_receipt": state.get("gate_failure_receipt"),
            "rollback_may_continue_boot_independently": True,
        }

    state["containment_active"] = True
    state["containment_http_verified"] = True
    state["status"] = f"{operation}_containment_verified"
    write_state(context.state_path, state)
    append_event(
        context.evidence_directory,
        "rollback_containment_verified",
        {"operation": operation, "identity": file_identity(context.front_controller)},
    )
    return {"status": "verified", "http_verified": True, "gate": gate}


def validate_transition_history(
    context: GateContext,
    state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    history = state.get("front_controller_transitions", [])
    latest = state.get("front_controller_transition")
    if not isinstance(history, list):
        raise GateError("Recovery found invalid front-controller transition history.")
    if not history:
        if latest is not None:
            raise GateError("Recovery found a latest transition without transition history.")
        return history, None
    if not isinstance(latest, dict) or latest != history[-1]:
        raise GateError("Recovery found inconsistent durable front-controller state.")
    for sequence, transition in enumerate(history, start=1):
        if not isinstance(transition, dict):
            raise GateError("Recovery found a non-object front-controller transition.")
        if transition.get("sequence") != sequence:
            raise GateError("Recovery found a non-contiguous front-controller transition sequence.")
        if transition.get("phase") not in TRANSITION_PHASES:
            raise GateError("Recovery found an invalid durable transition phase.")
        if transition.get("front_controller") != str(context.front_controller):
            raise GateError("Recovery transition references a different front controller.")
        if not isinstance(transition.get("operation"), str) or not transition["operation"]:
            raise GateError("Recovery transition has no operation identity.")
        if not isinstance(transition.get("at_utc"), str) or not transition["at_utc"]:
            raise GateError("Recovery transition has no timestamp identity.")
        if not isinstance(transition.get("details"), dict):
            raise GateError("Recovery transition details are invalid.")
        target_sha256 = transition["details"].get("target_sha256")
        if target_sha256 not in {context.original_sha256, EXPECTED_GATE_SHA256}:
            raise GateError("Recovery transition has an unknown target identity.")
        target_metadata = transition["details"].get("target_metadata")
        if target_metadata != reviewed_front_controller_metadata():
            raise GateError("Recovery transition has unreviewed target metadata.")
    return history, latest


def recovery_decision(
    *,
    context: GateContext,
    state: dict[str, Any],
    mutation_started: MutationPredicate = dependency_mutation_has_started,
) -> dict[str, Any]:
    """Return the required recovery action from actual identity and history."""

    _validate_context(context)
    history, latest = validate_transition_history(context, state)
    live = file_identity(context.front_controller)
    if live["sha256"] not in {context.original_sha256, EXPECTED_GATE_SHA256}:
        raise GateError("Recovery found unknown live front-controller bytes.")
    mutation = mutation_started(state)
    latest_phase = latest.get("phase") if latest is not None else None
    latest_target = (
        latest.get("details", {}).get("target_sha256") if latest is not None else None
    )

    if live["sha256"] == EXPECTED_GATE_SHA256:
        action = "rollback_dependencies" if mutation else "restore_original"
    else:
        if live["metadata"] != reviewed_front_controller_metadata():
            raise GateError("Recovery found original bytes with unreviewed metadata.")
        if mutation:
            action = "rollback_dependencies"
        elif latest_phase == "replacement_pending":
            # The swap may or may not have happened.  Re-running exact
            # restoration is idempotent and closes the durable transition.
            action = "restore_original"
        elif latest_phase == "installed" and latest_target == context.original_sha256:
            action = "restore_original"
        elif latest_phase in GATE_PRESENT_PHASES and latest_target != context.original_sha256:
            raise GateError(
                "Durable state says the gate is installed but live identity is the original."
            )
        else:
            action = "none"

    return {
        "action": action,
        "recovery_required": action != "none",
        "mutation_started": mutation,
        "live": live,
        "transition_count": len(history),
        "latest_phase": latest_phase,
        "latest_target_sha256": latest_target,
        "persisted_gate_boolean_ignored": True,
    }


def front_controller_recovery_required(
    *,
    context: GateContext,
    state: dict[str, Any],
    mutation_started: MutationPredicate = dependency_mutation_has_started,
) -> bool:
    return recovery_decision(
        context=context,
        state=state,
        mutation_started=mutation_started,
    )["recovery_required"]


def _probe_url(public_url: str) -> tuple[str, str]:
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GateError("Static-gate probe URL must be an absolute HTTPS URL.")
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("ops_gate", secrets.token_hex(12)))
    return (
        urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(query), "")),
        parsed.hostname,
    )


def gate_http_probe(
    *,
    evidence_directory: Path,
    operation: str,
    public_url: str,
    origin_loopback: bool,
    cwd: Path,
    curl_path: Path = Path("/usr/bin/curl"),
    origin_address: str = "127.0.0.1",
) -> dict[str, Any]:
    """Probe the reviewed gate through exactly one identified network route."""

    directory = require_real_directory(evidence_directory)
    require_real_directory(cwd)
    require_regular_file(curl_path)
    route = ORIGIN_ROUTE if origin_loopback else PUBLIC_ROUTE
    suffix = "origin" if origin_loopback else "public"
    headers = directory / f"{operation}.{suffix}.headers.txt"
    body = directory / f"{operation}.{suffix}.body.txt"
    if any(path.exists() or path.is_symlink() for path in (headers, body)):
        raise GateError("Refusing to overwrite existing static-gate HTTP evidence.")
    url, hostname = _probe_url(public_url)
    routing_arguments = (
        [
            "--noproxy",
            "*",
            "--insecure",
            "--resolve",
            f"{hostname}:443:{origin_address}",
        ]
        if origin_loopback
        else []
    )
    command = [
        str(curl_path),
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
        "--header",
        "Pragma: no-cache",
        "--connect-timeout",
        "5",
        "--max-time",
        "15",
        "--max-redirs",
        "0",
        *routing_arguments,
        url,
    ]
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    for path in (headers, body):
        if path.is_symlink() or not path.is_file():
            raise GateError("Static-gate HTTP probe did not create regular evidence files.")
        os.chmod(path, 0o600)
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    fsync_directory(directory)
    status_text = completed.stdout.strip()
    if completed.returncode != 0 or not status_text.isdigit():
        raise GateError("Static-gate HTTP probe failed.")
    try:
        header_text = headers.read_text("utf-8").lower()
        body_text = body.read_text("utf-8")
    except UnicodeDecodeError as exception:
        raise GateError("Static-gate HTTP evidence is not valid UTF-8.") from exception
    return {
        "route": route,
        "status": int(status_text),
        "header_verified": (
            f"{MAINTENANCE_GATE_HEADER_NAME}: {MAINTENANCE_GATE_HEADER_VALUE}".lower()
            in header_text
        ),
        "sentinel_verified": MAINTENANCE_GATE_SENTINEL in body_text,
        "headers_sha256": file_identity(headers)["sha256"],
        "body_sha256": file_identity(body)["sha256"],
        "curl_exit_status": completed.returncode,
        "stderr_sha256": sha256_bytes(completed.stderr.encode("utf-8")),
    }


def gate_origin_probe(**kwargs: Any) -> dict[str, Any]:
    return gate_http_probe(origin_loopback=True, **kwargs)


def gate_public_probe(**kwargs: Any) -> dict[str, Any]:
    return gate_http_probe(origin_loopback=False, **kwargs)


def describe() -> dict[str, Any]:
    return {
        "artifact": "buy-dtf-laravel-dependency-static-gate-v3",
        "gate_sha256": EXPECTED_GATE_SHA256,
        "gate_metadata": reviewed_front_controller_metadata(),
        "origin_route": ORIGIN_ROUTE,
        "public_route": PUBLIC_ROUTE,
        "transition_phases": sorted(TRANSITION_PHASES),
        "dependency_mutation_fields": list(DEPENDENCY_MUTATION_FIELDS),
        "initial_state": initial_gate_state(),
        "recovery_uses_actual_identity_and_history": True,
        "pre_mutation_failure": "restore_original_receipt_and_health",
        "post_mutation_failure": "retain_exact_gate_and_continue_bootless_rollback",
    }
