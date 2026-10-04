#!/usr/bin/env python3
"""Durable static front-controller gate primitives for dependency cutovers.

This module deliberately has no production entry point.  Callers supply every
path, probe, health check, and mutation-state predicate.  The implementation
is derived from the independently reviewed incoming-order gate transition and
keeps its durable transition, owner, group, and mode controls.  V4 gate bytes
add a per-install nonce so every HTTP probe can prove route-specific freshness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
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
MAINTENANCE_GATE_PROBE_HEADER_NAME = "X-BuyDTF-Dependency-Probe"
MAINTENANCE_GATE_SENTINEL = "BUYDTF_DEPENDENCY_MAINTENANCE_STATIC_V2"
MAINTENANCE_GATE_BYTES = fr"""<?php
declare(strict_types=1);

$opsGateProbe = $_GET['ops_gate'] ?? '';
if (!is_string($opsGateProbe) || preg_match('/\A[a-f0-9]{{24}}\z/D', $opsGateProbe) !== 1) {{
    $opsGateProbe = 'invalid';
}}
http_response_code(503);
header('Content-Type: text/plain; charset=UTF-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Retry-After: 120');
header('{MAINTENANCE_GATE_HEADER_NAME}: {MAINTENANCE_GATE_HEADER_VALUE}');
header('{MAINTENANCE_GATE_PROBE_HEADER_NAME}: ' . $opsGateProbe);
echo '{MAINTENANCE_GATE_SENTINEL}' . "\n" . $opsGateProbe;
""".encode("utf-8")
EXPECTED_GATE_SHA256 = "d18fc1520808b10814a6e86ef41ce22f9c6d326318f96fc3db78aed153199ea4"

MINIMUM_REVALIDATION_WAIT_SECONDS = 5
REVALIDATION_SAFETY_MARGIN_SECONDS = 1
OPCACHE_DIRECTIVE_NAMES = (
    "opcache.enable",
    "opcache.validate_timestamps",
    "opcache.revalidate_freq",
    "opcache.file_update_protection",
)

ORIGIN_ROUTE = "origin_loopback"
PUBLIC_ROUTE = "public_cloudflare"
TRANSITION_PHASES = frozenset(
    {
        "replacement_pending",
        "installed",
        "installed_reconciled_from_live_identity",
        "revalidation_wait_complete",
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
        "revalidation_wait_complete",
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
NumberedProbe = Callable[[int], dict[str, Any]]
HealthProbe = Callable[[], dict[str, Any]]
MutationPredicate = Callable[[dict[str, Any]], bool]
FaultInjector = Callable[[str], None]
Sleep = Callable[[float], None]
MonotonicClock = Callable[[], int]
WallClock = Callable[[], float]


@dataclass(frozen=True)
class GateContext:
    application_root: Path
    front_controller: Path
    state_path: Path
    evidence_directory: Path
    original_backup: Path
    original_sha256: str
    opcache_policy: dict[str, Any]
    sleep: Sleep = time.sleep
    monotonic_ns: MonotonicClock = time.monotonic_ns
    wall_clock: WallClock = time.time


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if sha256_bytes(MAINTENANCE_GATE_BYTES) != EXPECTED_GATE_SHA256:
    raise RuntimeError("Embedded static-gate bytes differ from the reviewed identity.")


def _normalized_directive(
    probe: dict[str, Any],
    name: str,
) -> bool | int:
    directives = probe.get("directives")
    if not isinstance(directives, dict) or set(directives) != set(OPCACHE_DIRECTIVE_NAMES):
        raise GateError("PHP-FPM OPcache probe has an incomplete directive set.")
    entry = directives.get(name)
    if not isinstance(entry, dict) or set(entry) != {"normalized", "raw"}:
        raise GateError(f"PHP-FPM OPcache directive is malformed: {name}")
    normalized = entry.get("normalized")
    if name in {"opcache.enable", "opcache.validate_timestamps"}:
        if type(normalized) is not bool:
            raise GateError(f"PHP-FPM OPcache boolean directive is invalid: {name}")
    elif type(normalized) is not int or normalized < 0:
        raise GateError(f"PHP-FPM OPcache interval directive is invalid: {name}")
    return normalized


def derive_opcache_revalidation_policy(probe: dict[str, Any]) -> dict[str, Any]:
    """Validate an FPM-SAPI probe and derive the only reviewed wait policy."""

    if probe.get("artifact") != "buy-dtf-php-fpm-opcache-probe-v1":
        raise GateError("PHP-FPM OPcache probe has an unexpected artifact identity.")
    if probe.get("sapi") != "fpm-fcgi":
        raise GateError("OPcache settings must be read through the PHP-FPM SAPI.")
    php_version = probe.get("php_version")
    if not isinstance(php_version, str) or not php_version:
        raise GateError("PHP-FPM OPcache probe has no PHP version identity.")

    enabled = _normalized_directive(probe, "opcache.enable")
    validate_timestamps = _normalized_directive(
        probe,
        "opcache.validate_timestamps",
    )
    revalidate_frequency = _normalized_directive(probe, "opcache.revalidate_freq")
    file_update_protection = _normalized_directive(
        probe,
        "opcache.file_update_protection",
    )
    configuration = probe.get("opcache_configuration_directives")
    expected_configuration = {
        name: probe["directives"][name]["normalized"] for name in OPCACHE_DIRECTIVE_NAMES
    }
    if configuration != expected_configuration:
        raise GateError("PHP-FPM ini values differ from its OPcache configuration values.")
    if enabled is not True:
        raise GateError("PHP-FPM OPcache must be enabled for this reviewed deployment flow.")
    if validate_timestamps is not True:
        raise GateError(
            "PHP-FPM opcache.validate_timestamps must be enabled; a separately reviewed "
            "PHP-FPM reload plan is required."
        )

    if type(revalidate_frequency) is not int or type(file_update_protection) is not int:
        raise GateError("PHP-FPM OPcache timing directives must be nonnegative integers.")
    complete_interval = revalidate_frequency + file_update_protection
    second_revalidation_window = revalidate_frequency
    configured_wait = max(
        MINIMUM_REVALIDATION_WAIT_SECONDS,
        complete_interval
        + second_revalidation_window
        + REVALIDATION_SAFETY_MARGIN_SECONDS,
    )
    policy = {
        "artifact": "buy-dtf-php-fpm-opcache-revalidation-policy-v1",
        "php_version": php_version,
        "sapi": "fpm-fcgi",
        "opcache_enable": enabled,
        "validate_timestamps": validate_timestamps,
        "revalidate_freq_seconds": revalidate_frequency,
        "file_update_protection_seconds": file_update_protection,
        "complete_revalidation_interval_seconds": complete_interval,
        "second_revalidation_window_seconds": second_revalidation_window,
        "minimum_wait_seconds": configured_wait,
        "minimum_floor_seconds": MINIMUM_REVALIDATION_WAIT_SECONDS,
        "safety_margin_seconds": REVALIDATION_SAFETY_MARGIN_SECONDS,
        "formula": "max(5, 2 * revalidate_freq + file_update_protection + 1)",
    }
    validate_opcache_revalidation_policy(policy)
    return policy


def validate_opcache_revalidation_policy(policy: dict[str, Any]) -> None:
    if policy.get("artifact") != "buy-dtf-php-fpm-opcache-revalidation-policy-v1":
        raise GateError("OPcache revalidation policy has an unexpected artifact identity.")
    if policy.get("sapi") != "fpm-fcgi" or policy.get("opcache_enable") is not True:
        raise GateError("OPcache revalidation policy is not bound to enabled PHP-FPM OPcache.")
    if policy.get("validate_timestamps") is not True:
        raise GateError(
            "OPcache timestamp validation is disabled; a separately reviewed PHP-FPM "
            "reload plan is required."
        )
    numeric_fields = (
        "revalidate_freq_seconds",
        "file_update_protection_seconds",
        "complete_revalidation_interval_seconds",
        "second_revalidation_window_seconds",
        "minimum_wait_seconds",
        "minimum_floor_seconds",
        "safety_margin_seconds",
    )
    if any(type(policy.get(field)) is not int or policy[field] < 0 for field in numeric_fields):
        raise GateError("OPcache revalidation policy contains an invalid interval.")
    complete = policy["revalidate_freq_seconds"] + policy["file_update_protection_seconds"]
    second_window = policy["revalidate_freq_seconds"]
    expected_wait = max(
        MINIMUM_REVALIDATION_WAIT_SECONDS,
        complete + second_window + REVALIDATION_SAFETY_MARGIN_SECONDS,
    )
    if (
        policy["complete_revalidation_interval_seconds"] != complete
        or policy["second_revalidation_window_seconds"] != second_window
        or policy["minimum_wait_seconds"] != expected_wait
        or policy["minimum_wait_seconds"] <= complete
        or policy["minimum_floor_seconds"] != MINIMUM_REVALIDATION_WAIT_SECONDS
        or policy["safety_margin_seconds"] != REVALIDATION_SAFETY_MARGIN_SECONDS
        or policy.get("formula")
        != "max(5, 2 * revalidate_freq + file_update_protection + 1)"
    ):
        raise GateError("OPcache revalidation policy does not safely exceed the interval.")


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
        "front_controller_revalidation_waits": [],
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
    validate_opcache_revalidation_policy(context.opcache_policy)
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


def wait_for_front_controller_revalidation(
    *,
    context: GateContext,
    state: dict[str, Any],
    operation: str,
    target_sha256: str,
    target_metadata: dict[str, Any],
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    """Wait a complete FPM OPcache interval after a durable file transition."""

    _validate_context(context)
    validate_opcache_revalidation_policy(context.opcache_policy)
    before = file_identity(context.front_controller)
    if before["sha256"] != target_sha256 or before["metadata"] != target_metadata:
        raise GateError("Front-controller identity is wrong before OPcache revalidation wait.")

    waits = state.setdefault("front_controller_revalidation_waits", [])
    if not isinstance(waits, list):
        raise GateError("Front-controller OPcache wait history is invalid.")
    configured_wait = int(context.opcache_policy["minimum_wait_seconds"])
    wait_ns = configured_wait * 1_000_000_000
    start_monotonic_ns = context.monotonic_ns()
    if type(start_monotonic_ns) is not int or start_monotonic_ns < 0:
        raise GateError("Monotonic clock returned an invalid start value.")
    start_wall_epoch = context.wall_clock()
    deadline_ns = start_monotonic_ns + wait_ns
    wait_record: dict[str, Any] = {
        "sequence": len(waits) + 1,
        "operation": operation,
        "status": "waiting",
        "target_sha256": target_sha256,
        "target_metadata": target_metadata,
        "configured_wait_seconds": configured_wait,
        "complete_revalidation_interval_seconds": context.opcache_policy[
            "complete_revalidation_interval_seconds"
        ],
        "policy": context.opcache_policy,
        "started_at_utc": utc_from_epoch(start_wall_epoch),
        "start_monotonic_ns": start_monotonic_ns,
        "deadline_monotonic_ns": deadline_ns,
        "earliest_allowed_probe_at_utc": utc_from_epoch(
            start_wall_epoch + configured_wait
        ),
        "identity_before": before,
    }
    waits.append(wait_record)
    state["front_controller_revalidation_wait"] = wait_record
    write_state(context.state_path, state)
    append_event(
        context.evidence_directory,
        "front_controller_revalidation_wait_started",
        {
            "operation": operation,
            "sequence": wait_record["sequence"],
            "configured_wait_seconds": configured_wait,
        },
    )
    _inject(fault_injector, "after_revalidation_wait_started")

    previous_ns = start_monotonic_ns
    while True:
        current_ns = context.monotonic_ns()
        if current_ns >= deadline_ns:
            break
        remaining_seconds = (deadline_ns - current_ns) / 1_000_000_000
        context.sleep(remaining_seconds)
        next_ns = context.monotonic_ns()
        if next_ns <= previous_ns:
            raise GateError("Monotonic clock did not advance during OPcache wait.")
        previous_ns = next_ns
    _inject(fault_injector, "after_revalidation_sleep")

    end_monotonic_ns = context.monotonic_ns()
    if end_monotonic_ns < deadline_ns:
        raise GateError("OPcache revalidation wait ended before its monotonic deadline.")
    after = file_identity(context.front_controller)
    if after["sha256"] != target_sha256 or after["metadata"] != target_metadata:
        raise GateError("Front-controller identity drifted during OPcache revalidation wait.")
    _inject(fault_injector, "after_revalidation_identity_verified")

    end_wall_epoch = context.wall_clock()
    completion = {
        "status": "complete",
        "ended_at_utc": utc_from_epoch(end_wall_epoch),
        "end_monotonic_ns": end_monotonic_ns,
        "elapsed_monotonic_ns": end_monotonic_ns - start_monotonic_ns,
        "elapsed_monotonic_seconds": (
            end_monotonic_ns - start_monotonic_ns
        )
        / 1_000_000_000,
        "identity_after": after,
    }
    _inject(fault_injector, "after_revalidation_elapsed_before_receipt")

    # The sequence keeps an orphaned, already-fsynced receipt from colliding
    # with a fresh full wait that repeats the same operation during recovery.
    receipt_path = (
        context.evidence_directory
        / (
            f"{operation}-opcache-revalidation-wait-"
            f"{wait_record['sequence']:04d}-receipt.json"
        )
    )
    receipt = {
        "artifact": "buy-dtf-front-controller-opcache-revalidation-wait-v1",
        **wait_record,
        **completion,
    }
    receipt_sha256 = write_new_json(receipt_path, receipt)
    _inject(fault_injector, "after_revalidation_receipt_created")

    # A wait is not durably complete until its fsynced receipt can be linked in
    # the same atomic state write.  Until this point recovery sees `waiting` and
    # starts a fresh complete interval, even if this process already slept.
    wait_record.update(completion)
    wait_record["receipt"] = {
        "path": str(receipt_path),
        "sha256": receipt_sha256,
    }
    write_state(context.state_path, state)
    record_front_controller_transition(
        context=context,
        state=state,
        operation=operation,
        phase="revalidation_wait_complete",
        details={
            "identity": after,
            "target_sha256": target_sha256,
            "target_metadata": target_metadata,
            "wait_receipt": wait_record["receipt"],
        },
    )
    append_event(
        context.evidence_directory,
        "front_controller_revalidation_wait_complete",
        {
            "operation": operation,
            "sequence": wait_record["sequence"],
            "elapsed_monotonic_ns": wait_record["elapsed_monotonic_ns"],
            "receipt_sha256": receipt_sha256,
        },
    )
    _inject(fault_injector, "after_revalidation_wait_complete")
    return {**wait_record, "path": str(receipt_path), "receipt_sha256": receipt_sha256}


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
        revalidation_wait = wait_for_front_controller_revalidation(
            context=context,
            state=state,
            operation=operation,
            target_sha256=replacement_sha256,
            target_metadata=metadata,
            fault_injector=fault_injector,
        )
        return {
            "before": current,
            "prepared": prepared,
            "installed": installed,
            "revalidation_wait": revalidation_wait,
        }
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
    revalidation_wait: dict[str, Any]
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
        revalidation_wait = wait_for_front_controller_revalidation(
            context=context,
            state=state,
            operation=operation,
            target_sha256=context.original_sha256,
            target_metadata=metadata,
            fault_injector=fault_injector,
        )
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
        revalidation_wait = replacement["revalidation_wait"]

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
        "revalidation_wait": revalidation_wait,
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
        and result.get("cache_buster_verified") is True
        and result.get("route_identity_verified") is True
        and re_full_sha256(str(result.get("cache_buster_sha256", "")))
        and re_full_sha256(str(result.get("request_url_sha256", "")))
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
    revalidation_wait: dict[str, Any]
    if before["sha256"] != EXPECTED_GATE_SHA256 or before["metadata"] != metadata:
        replacement = atomic_front_controller_replace(
            context=context,
            state=state,
            operation=f"{operation}-exact-containment-install",
            replacement_bytes=MAINTENANCE_GATE_BYTES,
            replacement_sha256=EXPECTED_GATE_SHA256,
            allowed_current_sha256={context.original_sha256, EXPECTED_GATE_SHA256},
            fault_injector=fault_injector,
        )
        revalidation_wait = replacement["revalidation_wait"]
    else:
        record_front_controller_transition(
            context=context,
            state=state,
            operation=operation,
            phase="installed_reconciled_from_live_identity",
            details={
                "identity": before,
                "previous_transition": state.get("front_controller_transition"),
                "target_sha256": EXPECTED_GATE_SHA256,
                "target_metadata": metadata,
            },
        )
        _inject(fault_injector, "after_installed_reconciled")
        revalidation_wait = wait_for_front_controller_revalidation(
            context=context,
            state=state,
            operation=operation,
            target_sha256=EXPECTED_GATE_SHA256,
            target_metadata=metadata,
            fault_injector=fault_injector,
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
        "revalidation_wait": revalidation_wait,
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
    origin_probe: NumberedProbe,
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
    revalidation_wait: dict[str, Any] | None = None
    reconciled_from_live_identity = False
    origin_results: list[dict[str, Any]] = []
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
            revalidation_wait = replacement["revalidation_wait"]
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
            revalidation_wait = wait_for_front_controller_revalidation(
                context=context,
                state=state,
                operation=operation,
                target_sha256=EXPECTED_GATE_SHA256,
                target_metadata=metadata,
                fault_injector=fault_injector,
            )
        else:
            raise GateError("Static gate refuses unknown front-controller bytes.")

        state["static_gate_active"] = True
        state["containment_active"] = True
        state["gate_verified"] = False
        write_state(context.state_path, state)
        _inject(fault_injector, "after_gate_state_persisted")

        pre_origin_identity = file_identity(context.front_controller)
        if (
            pre_origin_identity["sha256"] != EXPECTED_GATE_SHA256
            or pre_origin_identity["metadata"] != metadata
        ):
            raise GateError("Static-gate identity changed before direct-origin verification.")
        for ordinal in (1, 2):
            before_origin = file_identity(context.front_controller)
            if before_origin != pre_origin_identity:
                raise GateError("Static-gate identity changed between direct-origin probes.")
            origin_result = origin_probe(ordinal)
            if not gate_probe_passed(origin_result, ORIGIN_ROUTE):
                raise GateError(
                    "A local/origin static-gate probe did not return the reviewed 503 response."
                )
            origin_results.append(origin_result)
            _inject(fault_injector, f"after_origin_{ordinal}_verified")
        if len({result.get("cache_buster_sha256") for result in origin_results}) != 2:
            raise GateError("Direct-origin static-gate probes reused a cache buster.")
        _inject(fault_injector, "after_origin_verified")

        public_result = public_probe()
        if not gate_probe_passed(public_result, PUBLIC_ROUTE):
            raise GateError(
                "The public Cloudflare static-gate probe did not return the reviewed 503 response."
            )
        _inject(fault_injector, "after_public_verified")
        request_identities = {
            result.get("cache_buster_sha256") for result in [*origin_results, public_result]
        }
        if None in request_identities or len(request_identities) != 3:
            raise GateError("Static-gate routes did not use three unique cache busters.")

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
                "pre_origin_identity": pre_origin_identity,
                "origin_probes": origin_results,
                "public_probe": public_result,
                "target_sha256": EXPECTED_GATE_SHA256,
                "target_metadata": metadata,
            },
        )
        state["gate_verified"] = True
        write_state(context.state_path, state)
        verification_receipt = {
            "artifact": "buy-dtf-static-gate-verification-v4",
            "status": "pass",
            "generated_at_utc": utc_now(),
            "operation": operation,
            "gate_sha256": EXPECTED_GATE_SHA256,
            "gate_metadata": metadata,
            "opcache_revalidation_wait": revalidation_wait,
            "pre_origin_identity": pre_origin_identity,
            "origin_probes": origin_results,
            "public_probe": public_result,
            "verified_identity": verified,
        }
        verification_path = (
            context.evidence_directory / f"{operation}-gate-verification-receipt.json"
        )
        verification_sha256 = write_new_json(verification_path, verification_receipt)
        state["gate_verification_receipt"] = {
            "path": str(verification_path),
            "sha256": verification_sha256,
        }
        write_state(context.state_path, state)
        _inject(fault_injector, "after_verified")
        return {
            "http_verified": True,
            "sha256": EXPECTED_GATE_SHA256,
            "metadata": metadata,
            "initial": initial,
            "replacement": replacement,
            "opcache_revalidation_wait": revalidation_wait,
            "reconciled_from_live_identity": reconciled_from_live_identity,
            "origin_probes": origin_results,
            "public_probe": public_result,
            "verification_receipt": state["gate_verification_receipt"],
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
                "origin_probes": origin_results,
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
                "origin_probes": origin_results,
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
    origin_probe: NumberedProbe,
    public_probe: Probe,
    restored_health_probe: HealthProbe,
    mutation_started: MutationPredicate = dependency_mutation_has_started,
    fault_injector: FaultInjector | None = None,
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
            fault_injector=fault_injector,
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
    waits = state.get("front_controller_revalidation_waits", [])
    latest = state.get("front_controller_transition")
    if not isinstance(history, list):
        raise GateError("Recovery found invalid front-controller transition history.")
    if not isinstance(waits, list):
        raise GateError("Recovery found invalid OPcache revalidation wait history.")
    if not history:
        if latest is not None:
            raise GateError("Recovery found a latest transition without transition history.")
        if waits:
            raise GateError("Recovery found OPcache waits without a file transition.")
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
    for sequence, wait in enumerate(waits, start=1):
        if not isinstance(wait, dict) or wait.get("sequence") != sequence:
            raise GateError("Recovery found a non-contiguous OPcache wait history.")
        if wait.get("status") not in {"waiting", "complete"}:
            raise GateError("Recovery found an invalid OPcache wait status.")
        if wait.get("target_sha256") not in {
            context.original_sha256,
            EXPECTED_GATE_SHA256,
        }:
            raise GateError("Recovery found an unknown OPcache wait target.")
        if wait.get("target_metadata") != reviewed_front_controller_metadata():
            raise GateError("Recovery found unreviewed OPcache wait metadata.")
        if wait.get("policy") != context.opcache_policy:
            raise GateError("Recovery OPcache wait policy differs from the frozen policy.")
        if wait.get("status") == "complete":
            if (
                type(wait.get("elapsed_monotonic_ns")) is not int
                or wait["elapsed_monotonic_ns"]
                < int(context.opcache_policy["minimum_wait_seconds"])
                * 1_000_000_000
            ):
                raise GateError("Recovery found an incomplete recorded OPcache wait.")
            receipt = wait.get("receipt")
            if (
                not isinstance(receipt, dict)
                or not isinstance(receipt.get("path"), str)
                or not re_full_sha256(str(receipt.get("sha256", "")))
            ):
                raise GateError("Recovery found a completed wait without a receipt.")
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


def _probe_url(public_url: str) -> tuple[str, str, str]:
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GateError("Static-gate probe URL must be an absolute HTTPS URL.")
    query = parse_qsl(parsed.query, keep_blank_values=True)
    cache_buster = secrets.token_hex(12)
    query.append(("ops_gate", cache_buster))
    return (
        urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", urlencode(query), "")),
        parsed.hostname,
        cache_buster,
    )


def redact_http_headers(header_text: str) -> tuple[str, list[str], int]:
    """Return review-safe headers with every Cookie value removed."""

    redacted: list[str] = []
    names: list[str] = []
    cookie_count = 0
    sensitive_continuation = False
    for line in header_text.replace("\r\n", "\n").split("\n"):
        if not line:
            redacted.append("")
            sensitive_continuation = False
            continue
        if line.startswith((" ", "\t")):
            if sensitive_continuation:
                redacted.append(" <redacted-cookie-continuation>")
            else:
                redacted.append(line)
            continue
        if ":" not in line:
            redacted.append(line)
            sensitive_continuation = False
            continue
        name, value = line.split(":", 1)
        normalized = name.strip().lower()
        names.append(normalized)
        sensitive_continuation = normalized in {"cookie", "set-cookie"}
        if sensitive_continuation:
            cookie_count += 1
            redacted.append(f"{name}: <redacted-cookie-value>")
        else:
            redacted.append(f"{name}:{value}")
    return "\n".join(redacted), sorted(set(names)), cookie_count


def parse_final_http_header_block(header_text: str) -> dict[str, list[str]]:
    """Return exact values from curl's final response header block."""

    normalized = header_text.replace("\r\n", "\n")
    blocks = [block for block in normalized.split("\n\n") if block.strip()]
    if not blocks:
        raise GateError("Static-gate HTTP evidence has no response header block.")
    final_lines = blocks[-1].split("\n")
    if not final_lines or not final_lines[0].startswith("HTTP/"):
        raise GateError("Static-gate final response header block has no status line.")
    values: dict[str, list[str]] = {}
    for line in final_lines[1:]:
        if not line:
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            raise GateError("Static-gate final response contains an invalid header line.")
        name, value = line.split(":", 1)
        normalized_name = name.strip().lower()
        if not normalized_name:
            raise GateError("Static-gate final response contains an empty header name.")
        values.setdefault(normalized_name, []).append(value.strip())
    return values


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
    redacted_headers = directory / f"{operation}.{suffix}.headers.redacted.txt"
    if any(path.exists() or path.is_symlink() for path in (headers, body, redacted_headers)):
        raise GateError("Refusing to overwrite existing static-gate HTTP evidence.")
    for path in (headers, body):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    fsync_directory(directory)
    url, hostname, cache_buster = _probe_url(public_url)
    routing_arguments = (
        [
            "--insecure",
            "--resolve",
            f"{hostname}:443:{origin_address}",
        ]
        if origin_loopback
        else []
    )
    command = [
        str(curl_path),
        "--disable",
        "--silent",
        "--show-error",
        "--noproxy",
        "*",
        "--dump-header",
        str(headers),
        "--output",
        str(body),
        "--write-out",
        "%{http_code}\n%{remote_ip}\n%{remote_port}\n",
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
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
            env={"LANG": "C", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exception:
        raise GateError("Static-gate HTTP probe execution failed.") from exception
    for path in (headers, body):
        if path.is_symlink() or not path.is_file():
            raise GateError("Static-gate HTTP probe did not create regular evidence files.")
        os.chmod(path, 0o600)
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    fsync_directory(directory)
    connection_fields = completed.stdout.strip().splitlines()
    if (
        completed.returncode != 0
        or len(connection_fields) != 3
        or not connection_fields[0].isdigit()
        or not connection_fields[2].isdigit()
    ):
        raise GateError("Static-gate HTTP probe failed.")
    status_text, remote_ip_text, remote_port_text = connection_fields
    try:
        remote_ip = ipaddress.ip_address(remote_ip_text)
    except ValueError as exception:
        raise GateError("Static-gate HTTP probe returned an invalid peer address.") from exception
    remote_port = int(remote_port_text)
    try:
        raw_header_text = headers.read_text("utf-8")
        body_text = body.read_text("utf-8")
    except UnicodeDecodeError as exception:
        raise GateError("Static-gate HTTP evidence is not valid UTF-8.") from exception
    final_headers = parse_final_http_header_block(raw_header_text)
    redacted_text, header_names, cookie_header_count = redact_http_headers(
        raw_header_text
    )
    atomic_write(redacted_headers, redacted_text.encode("utf-8"), 0o600)
    gate_header_values = final_headers.get(MAINTENANCE_GATE_HEADER_NAME.lower(), [])
    probe_header_values = final_headers.get(
        MAINTENANCE_GATE_PROBE_HEADER_NAME.lower(),
        [],
    )
    cloudflare_ray_values = final_headers.get("cf-ray", [])
    server_values = final_headers.get("server", [])
    cloudflare_route_verified = (
        len(cloudflare_ray_values) == 1
        and re.fullmatch(r"[A-Za-z0-9]+-[A-Za-z0-9]+", cloudflare_ray_values[0])
        is not None
        and len(server_values) == 1
        and server_values[0].strip().lower() == "cloudflare"
    )
    if origin_loopback:
        route_identity_verified = remote_ip == ipaddress.ip_address(origin_address)
    else:
        route_identity_verified = remote_ip.is_global and cloudflare_route_verified
    route_identity_verified = route_identity_verified and remote_port == 443
    expected_body = f"{MAINTENANCE_GATE_SENTINEL}\n{cache_buster}"
    cache_buster_header = probe_header_values == [cache_buster]
    cache_buster_body = body_text == expected_body
    identities = {
        "raw_headers": file_identity(headers),
        "raw_body": file_identity(body),
        "redacted_headers": file_identity(redacted_headers),
    }
    if any(identity["metadata"]["mode"] != 0o600 for identity in identities.values()):
        raise GateError("Static-gate HTTP evidence is not private mode 0600.")
    return {
        "route": route,
        "routing_mode": "direct_origin_resolve" if origin_loopback else "public_dns",
        "remote_ip": str(remote_ip),
        "remote_port": remote_port,
        "route_identity_verified": route_identity_verified,
        "cloudflare_route_verified": cloudflare_route_verified,
        "status": int(status_text),
        "header_verified": (
            gate_header_values == [MAINTENANCE_GATE_HEADER_VALUE]
        ),
        "sentinel_verified": body_text == expected_body,
        "cache_buster_verified": cache_buster_header and cache_buster_body,
        "cache_buster_sha256": sha256_bytes(cache_buster.encode("ascii")),
        "request_url_sha256": sha256_bytes(url.encode("utf-8")),
        "headers_sha256": identities["raw_headers"]["sha256"],
        "body_sha256": identities["raw_body"]["sha256"],
        "redacted_headers_sha256": identities["redacted_headers"]["sha256"],
        "raw_headers_mode": identities["raw_headers"]["metadata"]["mode"],
        "raw_body_mode": identities["raw_body"]["metadata"]["mode"],
        "redacted_headers_mode": identities["redacted_headers"]["metadata"]["mode"],
        "redacted_headers_path": str(redacted_headers),
        "response_header_names": header_names,
        "cookie_header_count": cookie_header_count,
        "raw_http_evidence_classification": "private-mode-0600-do-not-commit",
        "curl_exit_status": completed.returncode,
        "stderr_sha256": sha256_bytes(completed.stderr.encode("utf-8")),
    }


def gate_origin_probe(**kwargs: Any) -> dict[str, Any]:
    return gate_http_probe(origin_loopback=True, **kwargs)


def gate_public_probe(**kwargs: Any) -> dict[str, Any]:
    return gate_http_probe(origin_loopback=False, **kwargs)


def describe() -> dict[str, Any]:
    return {
        "artifact": "buy-dtf-laravel-dependency-static-gate-v4",
        "gate_sha256": EXPECTED_GATE_SHA256,
        "gate_metadata": reviewed_front_controller_metadata(),
        "origin_route": ORIGIN_ROUTE,
        "independent_origin_probe_count": 2,
        "public_route": PUBLIC_ROUTE,
        "unique_cache_buster_per_probe": True,
        "probe_nonce_bound_in_header_and_body": True,
        "raw_http_evidence_mode": "0600",
        "cookie_values_redacted_from_review_derivative": True,
        "transition_phases": sorted(TRANSITION_PHASES),
        "dependency_mutation_fields": list(DEPENDENCY_MUTATION_FIELDS),
        "initial_state": initial_gate_state(),
        "opcache_directives": list(OPCACHE_DIRECTIVE_NAMES),
        "opcache_revalidation_formula": (
            "max(5, 2 * revalidate_freq + file_update_protection + 1)"
        ),
        "opcache_wait_uses_monotonic_clock": True,
        "opcache_wait_after_durable_installed_transition": True,
        "timestamp_validation_required": True,
        "cli_opcache_invalidation_used": False,
        "recovery_uses_actual_identity_and_history": True,
        "pre_mutation_failure": "restore_original_receipt_and_health",
        "post_mutation_failure": "retain_exact_gate_and_continue_bootless_rollback",
    }
