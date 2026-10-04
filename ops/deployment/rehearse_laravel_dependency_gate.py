#!/usr/bin/env python3
"""Exercise the dependency static-gate state machine on disposable paths."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


sys.path.insert(0, str(Path(__file__).resolve().parent))
import laravel_dependency_gate as gate  # noqa: E402


ORIGINAL_BYTES = b"<?php echo 'reviewed-original-application';\n"


def reviewed_fpm_probe(
    *,
    validate_timestamps: bool = True,
    revalidate_freq: int = 2,
    file_update_protection: int = 2,
) -> dict[str, Any]:
    normalized: dict[str, bool | int] = {
        "opcache.enable": True,
        "opcache.validate_timestamps": validate_timestamps,
        "opcache.revalidate_freq": revalidate_freq,
        "opcache.file_update_protection": file_update_protection,
    }
    return {
        "artifact": "buy-dtf-php-fpm-opcache-probe-v1",
        "sapi": "fpm-fcgi",
        "php_version": "8.2.30",
        "directives": {
            name: {"raw": str(int(value)), "normalized": value}
            for name, value in normalized.items()
        },
        "opcache_configuration_directives": normalized,
    }


class FakeClock:
    """Advance the monotonic clock only when the reviewed primitive sleeps."""

    def __init__(self) -> None:
        self.initial_ns = 40_000_000_000
        self.nanoseconds = self.initial_ns
        self.initial_wall_epoch = 1_700_000_000.0
        self.sleep_calls: list[float] = []

    def monotonic_ns(self) -> int:
        return self.nanoseconds

    def wall_clock(self) -> float:
        return self.initial_wall_epoch + (
            self.nanoseconds - self.initial_ns
        ) / 1_000_000_000

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.nanoseconds += round(seconds * 1_000_000_000)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise gate.GateError(message)


def command_identity(
    command: list[str], completed: subprocess.CompletedProcess[str]
) -> dict[str, Any]:
    return {
        "executable_chain": [Path(command[0]).name, Path(command[4]).name],
        "argv_sha256": gate.sha256_bytes("\0".join(command).encode("utf-8")),
        "exit_status": completed.returncode,
        "stdout_sha256": gate.sha256_bytes(completed.stdout.encode("utf-8")),
        "stderr_sha256": gate.sha256_bytes(completed.stderr.encode("utf-8")),
    }


def separate_web_identity_probe(
    front_controller: Path,
    route: str,
    cache_buster: str,
) -> dict[str, Any]:
    reader_code = (
        "import hashlib,json,os,pathlib,sys;"
        "p=pathlib.Path(sys.argv[1]);b=p.read_bytes();"
        "print(json.dumps({'euid':os.geteuid(),'egid':os.getegid(),"
        "'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}))"
    )
    reader_command = [
        "/usr/bin/setpriv",
        f"--reuid={gate.EXPECTED_WEB_UID}",
        f"--regid={gate.EXPECTED_WEB_GID}",
        "--clear-groups",
        "/usr/bin/python3",
        "-c",
        reader_code,
        str(front_controller),
    ]
    reader = subprocess.run(
        reader_command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    require(reader.returncode == 0, "The UID/GID 33 reader could not read the gate.")
    payload = json.loads(reader.stdout)
    require(payload.get("euid") == gate.EXPECTED_WEB_UID, "Reader UID differs.")
    require(payload.get("egid") == gate.EXPECTED_WEB_GID, "Reader GID differs.")
    require(payload.get("sha256") == gate.EXPECTED_GATE_SHA256, "Reader saw wrong bytes.")

    php_command = [
        "/usr/bin/setpriv",
        f"--reuid={gate.EXPECTED_WEB_UID}",
        f"--regid={gate.EXPECTED_WEB_GID}",
        "--clear-groups",
        "/usr/bin/php",
        "-r",
        '$_GET["ops_gate"]=$argv[1]; include $argv[2];',
        cache_buster,
        str(front_controller),
    ]
    php = subprocess.run(
        php_command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    require(php.returncode == 0, "The UID/GID 33 PHP process could not execute the gate.")
    require(
        gate.MAINTENANCE_GATE_SENTINEL in php.stdout,
        "The UID/GID 33 PHP process did not execute the reviewed gate bytes.",
    )
    require(cache_buster in php.stdout, "The gate did not echo the route-specific nonce.")
    return {
        "route": route,
        "status": 503,
        "header_verified": True,
        "sentinel_verified": True,
        "cache_buster_verified": True,
        "route_identity_verified": True,
        "cache_buster_sha256": gate.sha256_bytes(cache_buster.encode("ascii")),
        "request_url_sha256": gate.sha256_bytes(
            f"https://buy-dtf.com/?ops_gate={cache_buster}".encode("ascii")
        ),
        "reader": payload,
        "reader_command": command_identity(reader_command, reader),
        "php_command": command_identity(php_command, php),
        "front_controller": gate.file_identity(front_controller),
    }


def prove_mode_0600_is_not_readable(parent: Path) -> dict[str, Any]:
    path = parent / "negative-control-mode-0600.php"
    path.write_bytes(gate.MAINTENANCE_GATE_BYTES)
    os.chown(path, gate.EXPECTED_APP_UID, gate.EXPECTED_APP_GID)
    os.chmod(path, 0o600)
    command = [
        "/usr/bin/setpriv",
        f"--reuid={gate.EXPECTED_WEB_UID}",
        f"--regid={gate.EXPECTED_WEB_GID}",
        "--clear-groups",
        "/usr/bin/python3",
        "-c",
        "import pathlib,sys;pathlib.Path(sys.argv[1]).read_bytes()",
        str(path),
    ]
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    identity = gate.file_identity(path)
    path.unlink()
    require(completed.returncode != 0, "Mode-0600 negative control was readable by UID 33.")
    return {
        "status": "pass",
        "identity": identity,
        "reader_uid": gate.EXPECTED_WEB_UID,
        "reader_gid": gate.EXPECTED_WEB_GID,
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
    os.chown(front_controller, gate.EXPECTED_APP_UID, gate.EXPECTED_APP_GID)
    os.chmod(front_controller, gate.EXPECTED_FRONT_CONTROLLER_MODE)
    original_sha256 = gate.file_identity(front_controller)["sha256"]
    backup = evidence / "front-controller-before.php"
    backup.write_bytes(ORIGINAL_BYTES)
    os.chmod(backup, 0o600)
    state_path = evidence / "state.json"
    state: dict[str, Any] = {
        "version": 1,
        "status": "rehearsal",
        **gate.initial_gate_state(),
        "dependency_mutation_started": False,
        "rollback_complete": False,
    }
    gate.write_state(state_path, state)
    clock = FakeClock()
    opcache_policy = gate.derive_opcache_revalidation_policy(reviewed_fpm_probe())
    context = gate.GateContext(
        application_root=application,
        front_controller=front_controller,
        state_path=state_path,
        evidence_directory=evidence,
        original_backup=backup,
        original_sha256=original_sha256,
        opcache_policy=opcache_policy,
        sleep=clock.sleep,
        monotonic_ns=clock.monotonic_ns,
        wall_clock=clock.wall_clock,
    )
    return {
        "name": name,
        "root": root,
        "application": application,
        "evidence": evidence,
        "front_controller": front_controller,
        "state": state,
        "context": context,
        "original_sha256": original_sha256,
        "clock": clock,
        "opcache_policy": opcache_policy,
    }


def evidence_manifest(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.is_symlink():
            records.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "mode": oct(path.stat().st_mode & 0o777),
                }
            )
    return records


def scenario_receipt(item: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    state = gate.load_state(item["context"].state_path)
    final = gate.file_identity(item["front_controller"])
    manifest = evidence_manifest(item["evidence"])
    return {
        "status": "pass",
        "scenario": item["name"],
        "details": details,
        "final_front_controller": final,
        "final_is_original": final["sha256"] == item["original_sha256"],
        "final_is_exact_gate": (
            final["sha256"] == gate.EXPECTED_GATE_SHA256
            and final["metadata"] == gate.reviewed_front_controller_metadata()
        ),
        "durable_transitions": [
            {
                "sequence": transition["sequence"],
                "operation": transition["operation"],
                "phase": transition["phase"],
            }
            for transition in state.get("front_controller_transitions", [])
        ],
        "durable_revalidation_waits": [
            {
                "sequence": wait["sequence"],
                "operation": wait["operation"],
                "status": wait["status"],
                "configured_wait_seconds": wait["configured_wait_seconds"],
                "elapsed_monotonic_ns": wait.get("elapsed_monotonic_ns"),
                "identity_before_sha256": wait["identity_before"]["sha256"],
                "identity_after_sha256": wait.get("identity_after", {}).get("sha256"),
            }
            for wait in state.get("front_controller_revalidation_waits", [])
        ],
        "final_durable_state": {
            key: state.get(key)
            for key in (
                "status",
                "static_gate_active",
                "containment_active",
                "gate_verified",
                "dependency_mutation_started",
                "rollback_complete",
                "gate_failure_receipt",
            )
        },
        "evidence_manifest": manifest,
    }


def healthy_original(item: dict[str, Any]) -> dict[str, Any]:
    identity = gate.file_identity(item["front_controller"])
    require(identity["sha256"] == item["original_sha256"], "Health saw wrong bytes.")
    require(
        identity["metadata"] == gate.reviewed_front_controller_metadata(),
        "Health saw wrong original metadata.",
    )
    return {"application_healthy": True, "front_controller": identity}


def valid_probe(item: dict[str, Any], route: str, probe_identity: str) -> dict[str, Any]:
    cache_buster = gate.sha256_bytes(
        f"{item['name']}:{route}:{probe_identity}".encode("utf-8")
    )[:24]
    return separate_web_identity_probe(item["front_controller"], route, cache_buster)


def bad_probe(
    item: dict[str, Any], route: str, status: int, probe_identity: str
) -> dict[str, Any]:
    result = valid_probe(item, route, probe_identity)
    result["status"] = status
    result["header_verified"] = False
    result["sentinel_verified"] = False
    return result


def install(
    item: dict[str, Any],
    operation: str,
    *,
    origin_probe: Callable[[int], dict[str, Any]] | None = None,
    public_probe: Callable[[], dict[str, Any]] | None = None,
    fault_injector: gate.FaultInjector | None = None,
) -> dict[str, Any]:
    return gate.install_static_gate(
        context=item["context"],
        state=item["state"],
        operation=operation,
        origin_probe=origin_probe
        or (
            lambda ordinal: valid_probe(
                item, gate.ORIGIN_ROUTE, f"{operation}-origin-{ordinal}"
            )
        ),
        public_probe=public_probe
        or (lambda: valid_probe(item, gate.PUBLIC_ROUTE, f"{operation}-public")),
        restored_health_probe=lambda: healthy_original(item),
        fault_injector=fault_injector,
    )


def restore(
    item: dict[str, Any],
    operation: str,
    *,
    fault_injector: gate.FaultInjector | None = None,
) -> dict[str, Any]:
    return gate.restore_front_controller_exact(
        context=item["context"],
        state=item["state"],
        operation=operation,
        receipt_name=f"{operation}-receipt.json",
        fault_injector=fault_injector,
    )


def fault_at(stage_name: str, *, abrupt: bool = False) -> gate.FaultInjector:
    def inject(stage: str) -> None:
        if stage == stage_name:
            if abrupt:
                raise gate.GateInterruption(f"abrupt rehearsal interruption at {stage}")
            raise gate.GateError(f"rehearsed failure at {stage}")

    return inject


def expect_gate_error(action: Callable[[], Any]) -> str:
    try:
        action()
    except gate.GateError as exception:
        return gate.sha256_bytes(str(exception).encode("utf-8"))
    raise gate.GateError("Expected gate failure did not occur.")


def expect_interruption(action: Callable[[], Any]) -> str:
    try:
        action()
    except gate.GateInterruption as exception:
        return gate.sha256_bytes(str(exception).encode("utf-8"))
    raise gate.GateError("Expected abrupt gate interruption did not occur.")


def finish_recovery_restore(item: dict[str, Any], operation: str) -> dict[str, Any]:
    item["state"] = gate.load_state(item["context"].state_path)
    decision = gate.recovery_decision(context=item["context"], state=item["state"])
    require(
        decision["action"] == "restore_original",
        f"Expected original restoration recovery, got {decision['action']}.",
    )
    receipt = restore(item, operation)
    healthy_original(item)
    return {"decision": decision, "restore_receipt_sha256": receipt["receipt_sha256"]}


def assert_pre_mutation_failure(item: dict[str, Any]) -> None:
    state = gate.load_state(item["context"].state_path)
    require(state.get("static_gate_active") is False, "Failure left gate marked active.")
    require(state.get("containment_active") is False, "Failure left containment active.")
    failure_path = Path(str(state.get("gate_failure_receipt", "")))
    require(failure_path.is_file(), "Failure receipt is absent.")
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    require(failure.get("original_restoration_performed") is True, "Original was not restored.")
    require(
        failure.get("post_restoration_health", {}).get("status") == "pass",
        "Post-restoration health did not pass.",
    )
    healthy_original(item)


def run_rehearsal(parent: Path) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise gate.GateError(
            "Gate rehearsal requires root to create UID/GID 1000 files and run UID/GID 33."
        )
    for executable in ("/usr/bin/python3", "/usr/bin/php", "/usr/bin/setpriv"):
        require(Path(executable).is_file(), f"Required executable is absent: {executable}")
    parent = gate.require_real_directory(parent)
    rehearsal_root = Path(
        tempfile.mkdtemp(prefix="buy-dtf-laravel-dependency-gate-v4-", dir=parent)
    )
    os.chmod(rehearsal_root, 0o755)
    previous_umask = os.umask(0o077)
    result: dict[str, Any] = {
        "artifact": "buy-dtf-laravel-dependency-static-gate-rehearsal-v4",
        "gate_module_sha256": hashlib.sha256(Path(gate.__file__).read_bytes()).hexdigest(),
        "rehearsal_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "gate_sha256": gate.EXPECTED_GATE_SHA256,
        "gate_metadata": gate.reviewed_front_controller_metadata(),
        "opcache_policy": gate.derive_opcache_revalidation_policy(reviewed_fpm_probe()),
        "umask": "0077",
        "runner_identity": {"euid": os.geteuid(), "egid": os.getegid()},
        "web_identity": {"euid": gate.EXPECTED_WEB_UID, "egid": gate.EXPECTED_WEB_GID},
        "scenarios": {},
    }
    try:
        negative = rehearsal_root / "mode-negative-control"
        negative.mkdir(mode=0o755)
        os.chmod(negative, 0o755)
        result["mode_0600_negative_control"] = prove_mode_0600_is_not_readable(negative)

        item = fixture(rehearsal_root, "success-and-exact-restoration")
        installed = install(item, "success-gate")
        restored = restore(item, "success-original-restore")
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {
                "origin_readers": [
                    probe["reader"] for probe in installed["origin_probes"]
                ],
                "public_reader": installed["public_probe"]["reader"],
                "restore_receipt_sha256": restored["receipt_sha256"],
            },
        )

        item = fixture(rehearsal_root, "timestamp-validation-disabled-rejected")
        invalid_policy = dict(item["opcache_policy"])
        invalid_policy["validate_timestamps"] = False
        invalid_context = replace(item["context"], opcache_policy=invalid_policy)
        failure = expect_gate_error(
            lambda: gate.install_static_gate(
                context=invalid_context,
                state=item["state"],
                operation="disabled-timestamps-gate",
                origin_probe=lambda ordinal: valid_probe(
                    item, gate.ORIGIN_ROUTE, f"disabled-origin-{ordinal}"
                ),
                public_probe=lambda: valid_probe(
                    item, gate.PUBLIC_ROUTE, "disabled-public"
                ),
                restored_health_probe=lambda: healthy_original(item),
            )
        )
        require(
            gate.file_identity(item["front_controller"])["sha256"]
            == item["original_sha256"],
            "Disabled timestamp validation changed the front controller.",
        )
        require(
            gate.load_state(item["context"].state_path)["front_controller_transitions"]
            == [],
            "Disabled timestamp validation reached a durable transition.",
        )
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {
                "expected_failure_sha256": failure,
                "rejected_before_mutation": True,
            },
        )

        item = fixture(rehearsal_root, "v3-immediate-probe-regression")
        first_probe_monotonic_ns: list[int] = []

        def delayed_origin(ordinal: int) -> dict[str, Any]:
            first_probe_monotonic_ns.append(item["clock"].monotonic_ns())
            require(
                sum(item["clock"].sleep_calls)
                >= item["opcache_policy"]["minimum_wait_seconds"],
                "The origin probe ran before the reviewed revalidation delay.",
            )
            durable = gate.load_state(item["context"].state_path)
            require(
                durable["front_controller_transition"]["phase"]
                == "revalidation_wait_complete",
                "The origin probe ran before the durable wait-complete transition.",
            )
            return valid_probe(
                item, gate.ORIGIN_ROUTE, f"delayed-origin-{ordinal}"
            )

        installed = install(
            item,
            "v3-regression-gate",
            origin_probe=delayed_origin,
        )
        restored = restore(item, "v3-regression-original-restore")
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {
                "first_probe_monotonic_ns": first_probe_monotonic_ns,
                "gate_wait_receipt_sha256": installed[
                    "opcache_revalidation_wait"
                ]["receipt_sha256"],
                "restore_receipt_sha256": restored["receipt_sha256"],
                "would_fail_v3_without_shared_wait": True,
            },
        )

        for scenario, stage in (
            ("failure-after-prepared-before-pending", "after_prepared_verified"),
            ("failure-after-pending-before-replacement", "after_replacement_pending"),
            ("failure-after-installed-before-origin", "after_installed"),
            ("failure-after-gate-state-before-origin", "after_gate_state_persisted"),
        ):
            item = fixture(rehearsal_root, scenario)
            failure = expect_gate_error(
                lambda item=item, stage=stage: install(
                    item,
                    f"{scenario}-gate",
                    fault_injector=fault_at(stage),
                )
            )
            assert_pre_mutation_failure(item)
            result["scenarios"][scenario] = scenario_receipt(
                item, {"expected_failure_sha256": failure, "fault_stage": stage}
            )

        item = fixture(rehearsal_root, "failure-during-origin-verification")
        failure = expect_gate_error(
            lambda: install(
                item,
                "origin-failure-gate",
                origin_probe=lambda ordinal: bad_probe(
                    item,
                    gate.ORIGIN_ROUTE,
                    500,
                    f"origin-failure-{ordinal}",
                ),
            )
        )
        assert_pre_mutation_failure(item)
        result["scenarios"][item["name"]] = scenario_receipt(
            item, {"expected_failure_sha256": failure, "failed_route": gate.ORIGIN_ROUTE}
        )

        item = fixture(rehearsal_root, "failure-during-public-verification")
        failure = expect_gate_error(
            lambda: install(
                item,
                "public-failure-gate",
                public_probe=lambda: bad_probe(
                    item, gate.PUBLIC_ROUTE, 522, "public-failure"
                ),
            )
        )
        assert_pre_mutation_failure(item)
        result["scenarios"][item["name"]] = scenario_receipt(
            item, {"expected_failure_sha256": failure, "failed_route": gate.PUBLIC_ROUTE}
        )

        for scenario, stage in (
            ("interruption-after-pending", "after_replacement_pending"),
            ("interruption-after-swap-before-installed", "after_replace_before_installed"),
            ("interruption-after-installed", "after_installed"),
            ("interruption-after-origin", "after_origin_verified"),
            ("interruption-after-public", "after_public_verified"),
            ("interruption-after-verified", "after_verified"),
        ):
            item = fixture(rehearsal_root, scenario)
            interruption = expect_interruption(
                lambda item=item, stage=stage: install(
                    item,
                    f"{scenario}-gate",
                    fault_injector=fault_at(stage, abrupt=True),
                )
            )
            recovered = finish_recovery_restore(item, f"{scenario}-recovery-restore")
            result["scenarios"][scenario] = scenario_receipt(
                item,
                {
                    "expected_interruption_sha256": interruption,
                    "fault_stage": stage,
                    **recovered,
                },
            )

        item = fixture(rehearsal_root, "restore-original-already-present-interruption")
        interruption = expect_interruption(
            lambda: restore(
                item,
                "original-already-present-interrupted-restore",
                fault_injector=fault_at("after_original_already_present", abrupt=True),
            )
        )
        item["state"] = gate.load_state(item["context"].state_path)
        decision = gate.recovery_decision(context=item["context"], state=item["state"])
        require(decision["action"] == "none", "Exact live original required unsafe recovery.")
        completed = restore(item, "original-already-present-completed-restore")
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {
                "expected_interruption_sha256": interruption,
                "decision": decision,
                "restore_receipt_sha256": completed["receipt_sha256"],
            },
        )

        item = fixture(rehearsal_root, "stale-boolean-live-gate-recovery")
        install(item, "stale-boolean-gate")
        item["state"]["static_gate_active"] = False
        item["state"]["containment_active"] = False
        item["state"]["gate_verified"] = False
        gate.write_state(item["context"].state_path, item["state"])
        recovered = finish_recovery_restore(item, "stale-boolean-recovery-restore")
        require(
            recovered["decision"]["persisted_gate_boolean_ignored"] is True,
            "Recovery trusted stale gate booleans.",
        )
        result["scenarios"][item["name"]] = scenario_receipt(item, recovered)

        item = fixture(rehearsal_root, "interruption-after-live-gate-reconciliation")
        expect_interruption(
            lambda: install(
                item,
                "pre-reconciliation-interruption",
                fault_injector=fault_at("after_replace_before_installed", abrupt=True),
            )
        )
        item["state"] = gate.load_state(item["context"].state_path)
        interruption = expect_interruption(
            lambda: install(
                item,
                "live-gate-reconciliation",
                fault_injector=fault_at("after_installed_reconciled", abrupt=True),
            )
        )
        recovered = finish_recovery_restore(item, "reconciliation-recovery-restore")
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {"expected_interruption_sha256": interruption, **recovered},
        )

        for scenario, failed_route in (
            ("post-mutation-origin-failure-containment", gate.ORIGIN_ROUTE),
            ("post-mutation-public-failure-containment", gate.PUBLIC_ROUTE),
        ):
            item = fixture(rehearsal_root, scenario)
            item["state"]["dependency_mutation_started"] = True
            gate.write_state(item["context"].state_path, item["state"])
            origin_probe = (
                (
                    lambda ordinal, item=item: bad_probe(
                        item,
                        gate.ORIGIN_ROUTE,
                        500,
                        f"post-mutation-failed-origin-{ordinal}",
                    )
                )
                if failed_route == gate.ORIGIN_ROUTE
                else (
                    lambda ordinal, item=item: valid_probe(
                        item,
                        gate.ORIGIN_ROUTE,
                        f"post-mutation-valid-origin-{ordinal}",
                    )
                )
            )
            public_probe = (
                (
                    lambda item=item: bad_probe(
                        item, gate.PUBLIC_ROUTE, 522, "post-mutation-failed-public"
                    )
                )
                if failed_route == gate.PUBLIC_ROUTE
                else (
                    lambda item=item: valid_probe(
                        item, gate.PUBLIC_ROUTE, "post-mutation-valid-public"
                    )
                )
            )
            containment = gate.establish_rollback_containment(
                context=item["context"],
                state=item["state"],
                operation=f"{scenario}-rollback-gate",
                origin_probe=origin_probe,
                public_probe=public_probe,
                restored_health_probe=lambda item=item: healthy_original(item),
            )
            require(containment["http_verified"] is False, "Failed route was accepted.")
            require(
                containment["rollback_may_continue_boot_independently"] is True,
                "Contained rollback was not allowed to proceed.",
            )
            live = gate.file_identity(item["front_controller"])
            require(live["sha256"] == gate.EXPECTED_GATE_SHA256, "Gate was reopened early.")
            item["state"]["rollback_complete"] = True
            gate.write_state(item["context"].state_path, item["state"])
            restored = restore(item, f"{scenario}-post-rollback-restore")
            result["scenarios"][scenario] = scenario_receipt(
                item,
                {
                    "failed_route": failed_route,
                    "containment": containment,
                    "restore_receipt_sha256": restored["receipt_sha256"],
                },
            )

        item = fixture(rehearsal_root, "interruption-after-containment-transition")
        item["state"]["dependency_mutation_started"] = True
        gate.write_state(item["context"].state_path, item["state"])
        interruption = expect_interruption(
            lambda: gate.retain_static_gate_exact(
                context=item["context"],
                state=item["state"],
                operation="interrupted-containment",
                fault_injector=fault_at("after_containment_retained", abrupt=True),
            )
        )
        item["state"] = gate.load_state(item["context"].state_path)
        decision = gate.recovery_decision(context=item["context"], state=item["state"])
        require(decision["action"] == "rollback_dependencies", "Containment recovery reopened.")
        containment = gate.retain_static_gate_exact(
            context=item["context"],
            state=item["state"],
            operation="recovered-containment",
        )
        item["state"]["rollback_complete"] = True
        gate.write_state(item["context"].state_path, item["state"])
        restored = restore(item, "containment-post-rollback-restore")
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {
                "expected_interruption_sha256": interruption,
                "decision": decision,
                "containment_receipt_sha256": containment["receipt_sha256"],
                "restore_receipt_sha256": restored["receipt_sha256"],
            },
        )

        for scenario, stage in (
            ("restore-interruption-after-pending", "after_replacement_pending"),
            ("restore-interruption-after-swap-before-installed", "after_replace_before_installed"),
            ("restore-interruption-after-installed", "after_installed"),
            ("restore-interruption-after-exact-verification", "after_exact_original_verified"),
            ("restore-interruption-after-state-persisted", "after_original_state_persisted"),
        ):
            item = fixture(rehearsal_root, scenario)
            install(item, f"{scenario}-initial-gate")
            interruption = expect_interruption(
                lambda item=item, stage=stage: restore(
                    item,
                    f"{scenario}-interrupted-restore",
                    fault_injector=fault_at(stage, abrupt=True),
                )
            )
            item["state"] = gate.load_state(item["context"].state_path)
            decision = gate.recovery_decision(context=item["context"], state=item["state"])
            require(
                decision["action"] in {"restore_original", "none"},
                "Restoration interruption requested an unsafe action.",
            )
            completed = restore(item, f"{scenario}-completed-restore")
            result["scenarios"][scenario] = scenario_receipt(
                item,
                {
                    "expected_interruption_sha256": interruption,
                    "fault_stage": stage,
                    "decision": decision,
                    "restore_receipt_sha256": completed["receipt_sha256"],
                },
            )

        item = fixture(rehearsal_root, "legacy-mode-0600-gate-restoration")
        item["front_controller"].write_bytes(gate.MAINTENANCE_GATE_BYTES)
        os.chown(item["front_controller"], gate.EXPECTED_APP_UID, gate.EXPECTED_APP_GID)
        os.chmod(item["front_controller"], 0o600)
        failure = expect_gate_error(lambda: install(item, "legacy-mode-0600-gate"))
        assert_pre_mutation_failure(item)
        result["scenarios"][item["name"]] = scenario_receipt(
            item, {"expected_failure_sha256": failure, "incorrect_mode": "0600"}
        )

        item = fixture(rehearsal_root, "unknown-front-controller-bytes-rejected")
        unknown = b"<?php echo 'unknown-out-of-band-controller';\n"
        item["front_controller"].write_bytes(unknown)
        os.chown(item["front_controller"], gate.EXPECTED_APP_UID, gate.EXPECTED_APP_GID)
        os.chmod(item["front_controller"], gate.EXPECTED_FRONT_CONTROLLER_MODE)
        unknown_sha256 = gate.file_identity(item["front_controller"])["sha256"]
        failure = expect_gate_error(lambda: install(item, "unknown-bytes-gate"))
        require(
            gate.file_identity(item["front_controller"])["sha256"] == unknown_sha256,
            "Unknown front-controller bytes were overwritten.",
        )
        result["scenarios"][item["name"]] = scenario_receipt(
            item,
            {
                "expected_failure_sha256": failure,
                "unknown_sha256": unknown_sha256,
                "unknown_bytes_preserved": True,
            },
        )

        safe_scenarios = [
            receipt
            for name, receipt in result["scenarios"].items()
            if name != "unknown-front-controller-bytes-rejected"
        ]
        require(
            all(receipt["final_is_original"] for receipt in safe_scenarios),
            "A rehearsal scenario did not finish on the exact original front controller.",
        )
        complete_waits = [
            wait
            for receipt in result["scenarios"].values()
            for wait in receipt["durable_revalidation_waits"]
        ]
        require(complete_waits, "The rehearsal produced no OPcache waits.")
        require(
            all(
                wait["status"] == "complete"
                and wait["elapsed_monotonic_ns"]
                >= wait["configured_wait_seconds"] * 1_000_000_000
                and wait["identity_before_sha256"] == wait["identity_after_sha256"]
                for wait in complete_waits
            ),
            "A shared OPcache wait was incomplete, short, or crossed an identity change.",
        )
        result["scenario_count"] = len(result["scenarios"])
        result["status"] = "pass"
        result["all_reopenable_scenarios_restored_exact_original"] = True
        result["unknown_bytes_rejected_without_overwrite"] = True
        result["origin_and_public_routes_separately_verified"] = True
        result["post_mutation_probe_failure_rollback_permitted_under_exact_gate"] = True
        result["shared_monotonic_revalidation_waits_verified"] = len(complete_waits)
        result["v3_immediate_probe_regression_blocked"] = True
        result["timestamp_validation_disabled_rejected_before_mutation"] = True
        result["canonical_sha256"] = gate.sha256_bytes(gate.canonical_bytes(result))
        return result
    finally:
        os.umask(previous_umask)
        resolved_parent = parent.resolve(strict=True)
        resolved_rehearsal = rehearsal_root.resolve(strict=True)
        if (
            resolved_rehearsal.parent != resolved_parent
            or not rehearsal_root.name.startswith("buy-dtf-laravel-dependency-gate-v4-")
        ):
            raise gate.GateError("Refusing to remove an unrecognized rehearsal directory.")
        shutil.rmtree(rehearsal_root)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    result = run_rehearsal(arguments.parent)
    payload = gate.canonical_bytes(result)
    if arguments.output is None:
        sys.stdout.buffer.write(payload)
    else:
        output_parent = gate.require_real_directory(arguments.output.parent)
        if arguments.output.exists() or arguments.output.is_symlink():
            raise gate.GateError("Refusing to overwrite an existing rehearsal receipt.")
        gate.atomic_write(arguments.output, payload, 0o600)
        gate.fsync_directory(output_parent)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except gate.GateError as exception:
        print(f"ERROR: {exception}", file=sys.stderr)
        raise SystemExit(1)
