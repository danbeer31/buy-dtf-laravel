#!/usr/bin/env python3
"""Rehearse the incoming-order front-controller gate on disposable Linux paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable

import incoming_order_v1_deploy as deploy


ORIGINAL_BYTES = b"<?php echo 'BUYDTF_REHEARSAL_ORIGINAL';\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise deploy.DeploymentError(message)


def command_identity(command: list[str], completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "argv_sha256": deploy.sha256_bytes("\0".join(command).encode("utf-8")),
        "executable_chain": [Path(command[0]).name, Path(command[4]).name],
        "exit_status": completed.returncode,
        "stdout_sha256": deploy.sha256_bytes(completed.stdout.encode("utf-8")),
        "stderr_sha256": deploy.sha256_bytes(completed.stderr.encode("utf-8")),
    }


def compact_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "sha256": identity["sha256"],
        "bytes": identity["bytes"],
        "metadata": identity["metadata"],
    }


def compact_gate(gate: dict[str, Any]) -> dict[str, Any]:
    replacement = gate.get("replacement")
    def compact_probe(probe: dict[str, Any]) -> dict[str, Any]:
        return {
            "route": probe["route"],
            "status": probe["status"],
            "header_verified": probe["header_verified"],
            "sentinel_verified": probe["sentinel_verified"],
            "reader": probe["reader"],
            "reader_command": probe["reader_command"],
            "php_command": probe["php_command"],
        }

    return {
        "sha256": gate["sha256"],
        "metadata": gate["metadata"],
        "reconciled_from_live_identity": gate["reconciled_from_live_identity"],
        "prepared": (
            compact_identity(replacement["prepared"]) if replacement is not None else None
        ),
        "installed": (
            compact_identity(replacement["installed"]) if replacement is not None else None
        ),
        "origin_probe": compact_probe(gate["origin_probe"]),
        "public_probe": compact_probe(gate["public_probe"]),
    }


def separate_web_identity_probe(front_controller: Path, route: str) -> dict[str, Any]:
    reader_code = (
        "import hashlib,json,os,pathlib,sys;"
        "p=pathlib.Path(sys.argv[1]);b=p.read_bytes();"
        "print(json.dumps({'euid':os.geteuid(),'egid':os.getegid(),"
        "'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}))"
    )
    reader_command = [
        "/usr/bin/setpriv",
        f"--reuid={deploy.EXPECTED_WEB_UID}",
        f"--regid={deploy.EXPECTED_WEB_GID}",
        "--clear-groups",
        "/usr/bin/python3",
        "-c",
        reader_code,
        str(front_controller),
    ]
    reader = subprocess.run(
        reader_command,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    require(reader.returncode == 0, "The separate web identity could not read the gate.")
    payload = json.loads(reader.stdout)
    require(payload.get("euid") == deploy.EXPECTED_WEB_UID, "Reader UID differs.")
    require(payload.get("egid") == deploy.EXPECTED_WEB_GID, "Reader GID differs.")
    require(payload.get("sha256") == deploy.EXPECTED_GATE_SHA256, "Reader saw wrong bytes.")

    php_command = [
        "/usr/bin/setpriv",
        f"--reuid={deploy.EXPECTED_WEB_UID}",
        f"--regid={deploy.EXPECTED_WEB_GID}",
        "--clear-groups",
        "/usr/bin/php",
        str(front_controller),
    ]
    php = subprocess.run(
        php_command,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    require(php.returncode == 0, "The separate web identity could not execute the gate.")
    require(
        deploy.MAINTENANCE_GATE_SENTINEL in php.stdout,
        "The separate web identity did not execute the reviewed gate bytes.",
    )
    return {
        "route": route,
        "status": 503,
        "header_verified": True,
        "sentinel_verified": True,
        "reader": payload,
        "reader_command": command_identity(reader_command, reader),
        "php_command": command_identity(php_command, php),
        "front_controller": deploy.file_identity(front_controller),
    }


def restored_application_health_probe(
    front_controller: Path, original_sha256: str
) -> dict[str, Any]:
    identity = deploy.file_identity(front_controller)
    require(identity["sha256"] == original_sha256, "Health probe did not see the original.")
    require(
        identity["metadata"] == deploy.reviewed_front_controller_metadata(),
        "Health probe saw unexpected original metadata.",
    )
    return {
        "application_healthy": True,
        "front_controller": compact_identity(identity),
    }


def prove_mode_0600_is_not_readable(parent: Path) -> dict[str, Any]:
    path = parent / "negative-control-mode-0600.php"
    path.write_bytes(deploy.MAINTENANCE_GATE_BYTES)
    os.chown(path, deploy.EXPECTED_APP_UID, deploy.EXPECTED_APP_GID)
    os.chmod(path, 0o600)
    command = [
        "/usr/bin/setpriv",
        f"--reuid={deploy.EXPECTED_WEB_UID}",
        f"--regid={deploy.EXPECTED_WEB_GID}",
        "--clear-groups",
        "/usr/bin/python3",
        "-c",
        "import pathlib,sys;pathlib.Path(sys.argv[1]).read_bytes()",
        str(path),
    ]
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    identity = deploy.file_identity(path)
    path.unlink()
    require(completed.returncode != 0, "Mode-0600 negative control was unexpectedly readable.")
    return {
        "status": "pass",
        "identity": identity,
        "reader_uid": deploy.EXPECTED_WEB_UID,
        "reader_gid": deploy.EXPECTED_WEB_GID,
        "read_denied": True,
        "command": command_identity(command, completed),
    }


def fixture(rehearsal_root: Path, name: str) -> dict[str, Any]:
    root = rehearsal_root / name
    application = root / "application"
    public = application / "public"
    evidence = root / "evidence"
    for directory, mode in (
        (root, 0o755),
        (application, 0o755),
        (public, 0o755),
        (evidence, 0o700),
    ):
        directory.mkdir(mode=mode, parents=True, exist_ok=False)
        os.chmod(directory, mode)

    front_controller = public / "index.php"
    front_controller.write_bytes(ORIGINAL_BYTES)
    os.chown(front_controller, deploy.EXPECTED_APP_UID, deploy.EXPECTED_APP_GID)
    os.chmod(front_controller, deploy.EXPECTED_FRONT_CONTROLLER_MODE)
    original_sha256 = deploy.sha256_file(front_controller)

    backup = evidence / "front-controller-before.php"
    deploy.atomic_copy(front_controller, backup, 0o600)
    state_path = evidence / "state.json"
    state: dict[str, Any] = {
        "version": 1,
        "status": "rehearsal",
        "front_controller_backup": str(backup),
        "front_controller_metadata": deploy.reviewed_front_controller_metadata(),
        "front_controller_transitions": [],
        "static_gate_active": False,
        "containment_active": False,
        "migration_executed": False,
        "source_install_started": False,
    }
    deploy.write_state(state_path, state)
    return {
        "root": root,
        "application": application,
        "front_controller": front_controller,
        "evidence": evidence,
        "backup": backup,
        "state_path": state_path,
        "state": state,
        "original_sha256": original_sha256,
    }


def evidence_manifest(directory: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.is_symlink():
            records.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": deploy.sha256_file(path),
                    "bytes": path.stat().st_size,
                    "mode": oct(path.stat().st_mode & 0o777),
                }
            )
    return records


def scenario_receipt(item: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    state = json.loads(item["state_path"].read_text("utf-8"))
    final = deploy.file_identity(item["front_controller"])
    manifest = evidence_manifest(item["evidence"])
    receipt_payloads = {
        record["path"]: json.loads((item["evidence"] / record["path"]).read_text("utf-8"))
        for record in manifest
        if record["path"].endswith("receipt.json")
    }
    restoration_receipts = sorted(
        path for path in receipt_payloads if "automatic-original-restore-receipt.json" in path
    )
    receipt = {
        "status": "pass",
        "scenario": item["root"].name,
        "details": details,
        "final_front_controller": compact_identity(final),
        "final_is_original": final["sha256"] == item["original_sha256"],
        "final_is_exact_gate": (
            final["sha256"] == deploy.EXPECTED_GATE_SHA256
            and final["metadata"] == deploy.reviewed_front_controller_metadata()
        ),
        "durable_transitions": [
            {
                "sequence": transition["sequence"],
                "operation": transition["operation"],
                "phase": transition["phase"],
            }
            for transition in state["front_controller_transitions"]
        ],
        "final_durable_state": {
            "static_gate_active": state["static_gate_active"],
            "containment_active": state.get("containment_active", False),
            "migration_executed": state["migration_executed"],
            "source_install_started": state["source_install_started"],
            "status": state["status"],
            "gate_failure_receipt_present": "gate_failure_receipt" in state,
        },
        "evidence_manifest": manifest,
        "receipt_hashes": {
            record["path"]: record["sha256"]
            for record in manifest
            if record["path"].endswith("receipt.json")
        },
        "receipt_payloads": receipt_payloads,
        "automatic_original_restoration_receipts": restoration_receipts,
    }
    receipt["canonical_sha256"] = deploy.sha256_bytes(deploy.canonical_bytes(receipt))
    return receipt


def install_arguments(
    item: dict[str, Any],
    name: str,
    *,
    origin_probe: Callable[[], dict[str, Any]] | None = None,
    public_probe: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "state_directory": item["evidence"],
        "name": name,
        "state": item["state"],
        "state_path": item["state_path"],
        "original_backup": item["backup"],
        "original_sha256": item["original_sha256"],
        "metadata": deploy.reviewed_front_controller_metadata(),
        "front_controller": item["front_controller"],
        "application_root": item["application"],
        "origin_probe": origin_probe
        or (lambda: separate_web_identity_probe(item["front_controller"], "origin_loopback")),
        "public_probe": public_probe
        or (lambda: separate_web_identity_probe(item["front_controller"], "public_cloudflare")),
        "restored_health_probe": lambda: restored_application_health_probe(
            item["front_controller"], item["original_sha256"]
        ),
    }


def exact_restore(item: dict[str, Any], operation: str) -> dict[str, Any]:
    return deploy.restore_front_controller_exact(
        backup=item["backup"],
        expected_sha256=item["original_sha256"],
        metadata=deploy.reviewed_front_controller_metadata(),
        allowed_current_sha256={item["original_sha256"], deploy.EXPECTED_GATE_SHA256},
        state=item["state"],
        state_path=item["state_path"],
        state_directory=item["evidence"],
        operation=operation,
        receipt_name=f"{operation}-receipt.json",
        front_controller=item["front_controller"],
        application_root=item["application"],
    )


def injected_failure(stage_name: str) -> Callable[[str], None]:
    def inject(stage: str) -> None:
        if stage == stage_name:
            raise deploy.DeploymentError(f"rehearsed failure at {stage}")

    return inject


def expect_gate_failure(action: Callable[[], Any]) -> str:
    try:
        action()
    except deploy.DeploymentError as exception:
        return deploy.sha256_bytes(str(exception).encode("utf-8"))
    raise deploy.DeploymentError("Expected static-gate failure did not occur.")


def require_pre_mutation_restoration_evidence(receipt: dict[str, Any]) -> None:
    failures = [
        payload
        for path, payload in receipt["receipt_payloads"].items()
        if path.endswith("gate-failure-receipt.json")
    ]
    require(len(failures) == 1, "Expected one pre-mutation gate-failure receipt.")
    failure = failures[0]
    require(
        failure.get("original_restoration_performed") is True,
        "Pre-mutation failure did not record exact original restoration.",
    )
    require(
        failure.get("post_restoration_health", {}).get("status") == "pass",
        "Pre-mutation failure did not record a passing post-restoration health check.",
    )
    require(
        len(receipt["automatic_original_restoration_receipts"]) == 1,
        "Pre-mutation failure did not retain one original-restoration receipt.",
    )


def run_rehearsal(parent: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise deploy.DeploymentError(
            "Gate rehearsal requires root only to create UID 1000 fixtures and drop the reader to UID 33."
        )
    for executable in ("/usr/bin/python3", "/usr/bin/php", "/usr/bin/setpriv"):
        require(Path(executable).is_file(), f"Required rehearsal executable is absent: {executable}")
    parent = deploy.require_real_directory(parent)
    rehearsal_root = Path(
        tempfile.mkdtemp(prefix="buy-dtf-incoming-gate-rehearsal-", dir=parent)
    )
    os.chmod(rehearsal_root, 0o755)
    previous_umask = os.umask(0o077)
    previous_wait = deploy.OPCACHE_WAIT_SECONDS
    deploy.OPCACHE_WAIT_SECONDS = 0
    result: dict[str, Any] = {
        "artifact": "buy-dtf-incoming-order-front-controller-gate-rehearsal-v3",
        "runner_sha256": deploy.sha256_file(Path(deploy.__file__).resolve()),
        "rehearsal_script_sha256": deploy.sha256_file(Path(__file__).resolve()),
        "umask": "0077",
        "runner_identity": {"euid": os.geteuid(), "egid": os.getegid()},
        "web_identity": {
            "euid": deploy.EXPECTED_WEB_UID,
            "egid": deploy.EXPECTED_WEB_GID,
        },
        "static_gate_sha256": deploy.EXPECTED_GATE_SHA256,
        "scenarios": {},
    }
    try:
        negative_root = rehearsal_root / "negative-control"
        negative_root.mkdir(mode=0o755)
        os.chmod(negative_root, 0o755)
        result["mode_0600_negative_control"] = prove_mode_0600_is_not_readable(
            negative_root
        )

        success = fixture(rehearsal_root, "success-under-umask-077")
        gate = deploy.install_static_gate(
            **install_arguments(success, "successful-cutover-gate"),
        )
        require(
            gate["replacement"]["prepared"]["metadata"]
            == deploy.reviewed_front_controller_metadata(),
            "Prepared gate metadata was not exact before replacement.",
        )
        restore = exact_restore(success, "successful-cutover-reopen")
        result["scenarios"][success["root"].name] = scenario_receipt(
            success,
            {
                "gate": compact_gate(gate),
                "restore_receipt_sha256": restore["receipt_sha256"],
            },
        )

        before = fixture(rehearsal_root, "failure-before-replacement")
        before_failure = expect_gate_failure(
            lambda: deploy.install_static_gate(
                **install_arguments(before, "before-replacement-gate"),
                fault_injector=injected_failure("before_replacement"),
            )
        )
        before_receipt = scenario_receipt(
            before, {"expected_failure_sha256": before_failure}
        )
        require_pre_mutation_restoration_evidence(before_receipt)
        result["scenarios"][before["root"].name] = before_receipt

        after = fixture(rehearsal_root, "failure-after-replacement")
        after_failure = expect_gate_failure(
            lambda: deploy.install_static_gate(
                **install_arguments(after, "after-replacement-gate"),
                fault_injector=injected_failure("after_replacement"),
            )
        )
        after_receipt = scenario_receipt(
            after, {"expected_failure_sha256": after_failure}
        )
        require_pre_mutation_restoration_evidence(after_receipt)
        result["scenarios"][after["root"].name] = after_receipt

        verification = fixture(rehearsal_root, "failure-during-verification")

        def failed_verification() -> dict[str, Any]:
            observed = separate_web_identity_probe(
                verification["front_controller"], "public_cloudflare"
            )
            observed["status"] = 500
            observed["header_verified"] = False
            return observed

        verification_failure = expect_gate_failure(
            lambda: deploy.install_static_gate(
                **install_arguments(
                    verification,
                    "verification-failure-gate",
                    public_probe=failed_verification,
                ),
            )
        )
        verification_receipt = scenario_receipt(
            verification, {"expected_failure_sha256": verification_failure}
        )
        require_pre_mutation_restoration_evidence(verification_receipt)
        result["scenarios"][verification["root"].name] = verification_receipt

        unreadable = fixture(rehearsal_root, "recovery-from-live-mode-0600-gate")
        deploy.record_front_controller_transition(
            state=unreadable["state"],
            state_path=unreadable["state_path"],
            state_directory=unreadable["evidence"],
            operation="legacy-unreadable-gate",
            phase="replacement_pending",
            front_controller=unreadable["front_controller"],
            details={"rehearsed_legacy_failure": "gate_swapped_with_mode_0600"},
        )
        unreadable["front_controller"].write_bytes(deploy.MAINTENANCE_GATE_BYTES)
        os.chown(
            unreadable["front_controller"],
            deploy.EXPECTED_APP_UID,
            deploy.EXPECTED_APP_GID,
        )
        os.chmod(unreadable["front_controller"], 0o600)
        deploy.fsync_directory(unreadable["front_controller"].parent)
        unreadable_failure = expect_gate_failure(
            lambda: deploy.install_static_gate(
                **install_arguments(unreadable, "legacy-mode-0600-gate-recovery"),
            )
        )
        unreadable_receipt = scenario_receipt(
            unreadable,
            {
                "expected_failure_sha256": unreadable_failure,
                "unreadable_gate_identified_by_sha256_not_boolean": True,
            },
        )
        require_pre_mutation_restoration_evidence(unreadable_receipt)
        result["scenarios"][unreadable["root"].name] = unreadable_receipt

        pending = fixture(rehearsal_root, "recovery-from-pending-state-and-live-gate")
        deploy.record_front_controller_transition(
            state=pending["state"],
            state_path=pending["state_path"],
            state_directory=pending["evidence"],
            operation="interrupted-gate",
            phase="replacement_pending",
            front_controller=pending["front_controller"],
            details={"rehearsed_interruption": "after_swap_before_installed_state"},
        )
        staged_gate = pending["front_controller"].with_name(".interrupted-gate")
        staged_gate.write_bytes(deploy.MAINTENANCE_GATE_BYTES)
        os.chown(staged_gate, deploy.EXPECTED_APP_UID, deploy.EXPECTED_APP_GID)
        os.chmod(staged_gate, deploy.EXPECTED_FRONT_CONTROLLER_MODE)
        os.replace(staged_gate, pending["front_controller"])
        deploy.fsync_directory(pending["front_controller"].parent)
        pending["state"]["static_gate_active"] = False
        deploy.write_state(pending["state_path"], pending["state"])
        require(
            deploy.front_controller_recovery_required(
                pending["state"],
                front_controller=pending["front_controller"],
                original_sha256=pending["original_sha256"],
            ),
            "Live gate identity did not require recovery when the boolean was stale.",
        )
        reconciled = deploy.install_static_gate(
            **install_arguments(pending, "reconciled-recovery-gate"),
        )
        require(
            reconciled["reconciled_from_live_identity"] is True,
            "Pending-state recovery did not reconcile the actual gate identity.",
        )
        pending_restore = exact_restore(pending, "reconciled-recovery-reopen")
        result["scenarios"][pending["root"].name] = scenario_receipt(
            pending,
            {
                "gate": compact_gate(reconciled),
                "restore_receipt_sha256": pending_restore["receipt_sha256"],
                "stale_boolean_ignored": True,
            },
        )

        rollback = fixture(rehearsal_root, "later-phase-rollback-gate")
        rollback["state"]["migration_executed"] = True
        rollback["state"]["source_install_started"] = True
        rollback["state"]["static_gate_active"] = False
        deploy.write_state(rollback["state_path"], rollback["state"])
        require(
            deploy.front_controller_recovery_required(
                rollback["state"],
                front_controller=rollback["front_controller"],
                original_sha256=rollback["original_sha256"],
            ),
            "Later-phase durable mutation state did not require rollback gating.",
        )
        rollback_gate = deploy.establish_rollback_containment(
            **install_arguments(rollback, "later-phase-rollback-gate"),
        )
        rollback_restore = exact_restore(rollback, "later-phase-rollback-reopen")
        result["scenarios"][rollback["root"].name] = scenario_receipt(
            rollback,
            {
                "gate": compact_gate(rollback_gate),
                "restore_receipt_sha256": rollback_restore["receipt_sha256"],
                "durable_later_phase_state_used": True,
            },
        )

        containment_failure = fixture(
            rehearsal_root, "later-phase-gate-verification-failure"
        )
        containment_failure["state"]["migration_executed"] = True
        containment_failure["state"]["source_install_started"] = True
        deploy.write_state(
            containment_failure["state_path"], containment_failure["state"]
        )

        def failed_later_phase_public_probe() -> dict[str, Any]:
            observed = separate_web_identity_probe(
                containment_failure["front_controller"], "public_cloudflare"
            )
            observed["status"] = 522
            observed["header_verified"] = False
            observed["sentinel_verified"] = False
            return observed

        containment_failure_sha256 = expect_gate_failure(
            lambda: deploy.establish_rollback_containment(
                **install_arguments(
                    containment_failure,
                    "later-phase-verification-failure-gate",
                    public_probe=failed_later_phase_public_probe,
                )
            )
        )
        containment_receipt = scenario_receipt(
            containment_failure,
            {
                "expected_failure_sha256": containment_failure_sha256,
                "migration_executed": True,
                "source_install_started": True,
                "expected_fail_closed_result": "exact_gate_retained_without_original_restore",
            },
        )
        require(
            containment_receipt["final_is_exact_gate"],
            "Later-phase verification failure did not retain the exact gate.",
        )
        require(
            containment_receipt["final_durable_state"]["static_gate_active"] is True
            and containment_receipt["final_durable_state"]["containment_active"] is True,
            "Later-phase verification failure was not recorded as gated containment.",
        )
        require(
            containment_receipt["automatic_original_restoration_receipts"] == [],
            "Later-phase verification failure wrote an unsafe original-restoration receipt.",
        )
        result["scenarios"][containment_failure["root"].name] = containment_receipt

        require(len(result["scenarios"]) == 8, "Unexpected rehearsal scenario count.")
        require(
            all(item["status"] == "pass" for item in result["scenarios"].values()),
            "A gate rehearsal scenario did not pass.",
        )
        result["status"] = "pass"
        result["scenario_count"] = len(result["scenarios"])
        result["all_final_front_controllers_safe"] = all(
            item["final_is_original"] or item["final_is_exact_gate"]
            for item in result["scenarios"].values()
        )
        result["later_phase_failure_retained_exact_gate"] = containment_receipt[
            "final_is_exact_gate"
        ]
        result["later_phase_failure_original_restoration_receipts"] = containment_receipt[
            "automatic_original_restoration_receipts"
        ]
        result["canonical_sha256"] = deploy.sha256_bytes(deploy.canonical_bytes(result))
        return result
    finally:
        deploy.OPCACHE_WAIT_SECONDS = previous_wait
        os.umask(previous_umask)
        resolved_parent = parent.resolve(strict=True)
        resolved_root = rehearsal_root.resolve(strict=True)
        if (
            resolved_root.parent != resolved_parent
            or not resolved_root.name.startswith("buy-dtf-incoming-gate-rehearsal-")
        ):
            raise deploy.DeploymentError("Refusing to remove an unrecognized rehearsal path.")
        shutil.rmtree(resolved_root)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rehearsal-parent", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        result = run_rehearsal(parse_arguments().rehearsal_parent)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except deploy.DeploymentError as exception:
        print(
            json.dumps(
                {
                    "status": "stopped",
                    "reason": str(exception),
                    "reason_sha256": deploy.sha256_bytes(str(exception).encode("utf-8")),
                },
                sort_keys=True,
            ),
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
