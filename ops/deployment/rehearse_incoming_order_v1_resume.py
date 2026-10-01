#!/usr/bin/env python3
"""Rehearse installed-schema receiver cutover and source-only rollback locally."""

from __future__ import annotations

from contextlib import contextmanager
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/incoming_order_v1_deploy.py"
MANIFEST_PATH = ROOT / "ops/deployment/incoming_order_v1_runtime_0799440.manifest"
HELPER_PATH = ROOT / "ops/deployment/incoming_order_v1_runtime_probe.php"
FIXTURE_PATH = (
    ROOT
    / "ops/evidence/incoming-order-v1-failed-cutover-20261001"
    / "0799440b-20261001T020405Z"
    / "post-migration-runtime-probe.stdout.txt"
)
OLD_SOURCE_ROOT = (
    ROOT
    / "ops/evidence/incoming-order-v1-failed-cutover-20261001"
    / "0799440b-20261001T020405Z"
    / "source-before"
)

SPEC = importlib.util.spec_from_file_location("incoming_order_v1_resume_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError("Unable to import incoming-order deployment runner.")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise deploy.DeploymentError(message)


@contextmanager
def patched(attributes: dict[str, Any]) -> Iterator[None]:
    previous = {name: getattr(deploy, name) for name in attributes}
    try:
        for name, value in attributes.items():
            setattr(deploy, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(deploy, name, value)


def copy_with_metadata(source: Path, destination: Path, mode: int = 0o664) -> None:
    destination.parent.mkdir(mode=0o775, parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chown(destination, deploy.EXPECTED_APP_UID, deploy.EXPECTED_APP_GID)
    os.chmod(destination, mode)


def build_fixture(parent: Path, name: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix=f"buy-dtf-resume-{name}-", dir=parent))
    application = root / "application"
    release = root / "release"
    candidate = release / "candidate"
    rollback = root / "rollbacks"
    for directory in (application, candidate, rollback):
        directory.mkdir(mode=0o775, parents=True)
    for row in rows:
        if row["action"] == "M":
            copy_with_metadata(OLD_SOURCE_ROOT / row["path"], application / row["path"])
        copy_with_metadata(ROOT / row["path"], candidate / row["path"], 0o600)

    front = application / "public/index.php"
    copy_with_metadata(ROOT / "public/index.php", front, 0o644)
    helper = release / HELPER_PATH.name
    shutil.copyfile(HELPER_PATH, helper)
    os.chmod(helper, 0o600)
    receipt_path = release / "release-receipt.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    os.chmod(receipt_path, 0o600)
    receipt = {
        "status": "pass",
        "scope": "schema-present-resume-read-only-preflight-and-restricted-staging-only",
        "schema_state": deploy.SCHEMA_STATE,
        "target_commit": deploy.TARGET_COMMIT,
        "release_directory": str(release),
        "inputs": {"helper": {"path": str(helper), "sha256": deploy.EXPECTED_HELPER_SHA256}},
    }
    return {
        "root": root,
        "application": application,
        "release": release,
        "candidate": candidate,
        "rollback": rollback,
        "front": front,
        "helper": helper,
        "receipt": receipt,
        "receipt_path": receipt_path,
    }


def write_mock_receipt(state_directory: Path, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = state_directory / f"{name}.json"
    deploy.atomic_json(path, payload)
    return {**payload, "path": str(path), "receipt_sha256": deploy.sha256_file(path)}


def partially_install_then_fail(
    candidate: Path,
    rows: list[dict[str, str]],
    state_directory: Path,
) -> dict[str, Any]:
    ordered = sorted(
        rows,
        key=lambda row: (
            0 if row["action"] == "A" else 1,
            1 if row["path"].startswith("routes/") else 0,
            row["path"],
        ),
    )
    for row in ordered[:9]:
        source = candidate / row["path"]
        destination = deploy.APP_ROOT / row["path"]
        created: list[str] = []
        deploy.ensure_runtime_parents(destination, created)
        if row["action"] == "M":
            metadata = deploy.path_metadata(destination)
        else:
            metadata = {
                "kind": "file",
                "mode": 0o664,
                "uid": deploy.EXPECTED_APP_UID,
                "gid": deploy.EXPECTED_APP_GID,
            }
        deploy.atomic_install_file(source, destination, metadata)
        deploy.append_event(
            state_directory,
            "rehearsed_partial_source_file_installed",
            {"path": row["path"], "sha256": row["target"]},
        )
    raise deploy.DeploymentError("rehearsed failure during source installation")


def run_scenario(
    parent: Path,
    rows: list[dict[str, str]],
    runtime_fixture: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    item = build_fixture(parent, name, rows)
    command_log: list[list[str]] = []
    installed_verification = deploy.verify_installed_schema(runtime_fixture)
    original_install = deploy.install_runtime_files

    def preflight(**_: Any) -> dict[str, Any]:
        source = deploy.live_manifest_snapshot(rows, target=False)
        return {
            "status": "pass",
            "runtime": copy.deepcopy(runtime_fixture),
            "runtime_command": {"rehearsal": True},
            "installed_schema_verification": copy.deepcopy(installed_verification),
            "live_source": source,
            "dependencies": {"rehearsal": "exact-pinned-production-baseline"},
        }

    runtime_calls = 0

    def runtime_probe(_helper: Path, _state_directory: Path, probe_name: str):
        nonlocal runtime_calls
        runtime_calls += 1
        if name == "failure-before-source-installation" and probe_name == "cutover-installed-schema-probe":
            raise deploy.DeploymentError("rehearsed failure before source installation")
        return copy.deepcopy(runtime_fixture), {
            "rehearsal": True,
            "name": probe_name,
            "sequence": runtime_calls,
        }

    def database_backups(
        _helper: Path, _snapshot: dict[str, Any], state_directory: Path
    ) -> dict[str, Any]:
        return write_mock_receipt(
            state_directory,
            "rehearsal-database-backup",
            {"status": "pass", "schema_only": True, "database_write": False},
        )

    def gate(**kwargs: Any) -> dict[str, Any]:
        state = kwargs["state"]
        state["static_gate_active"] = True
        state["containment_active"] = True
        deploy.write_state(kwargs["state_path"], state)
        return {"status": "pass", "rehearsal": True}

    def containment(**kwargs: Any) -> dict[str, Any]:
        state = kwargs["state"]
        state["static_gate_active"] = True
        state["containment_active"] = True
        deploy.write_state(kwargs["state_path"], state)
        return {"status": "pass", "rehearsal": True, "exact_gate": True}

    def restore_front(
        _backup: Path,
        _metadata: dict[str, Any],
        *,
        state: dict[str, Any],
        state_path: Path,
        state_directory: Path,
        name: str,
    ) -> dict[str, Any]:
        state["static_gate_active"] = False
        state["containment_active"] = False
        deploy.write_state(state_path, state)
        return write_mock_receipt(
            state_directory,
            f"{name}-rehearsal",
            {"status": "pass", "exact_original_restored": True},
        )

    def run_artisan(arguments: list[str], **_: Any) -> dict[str, Any]:
        command_log.append(list(arguments))
        require("migrate" not in arguments, "A migration command entered the resume rehearsal.")
        return {"status": "pass", "arguments": list(arguments)}

    def candidate_checks(*_: Any, **__: Any) -> dict[str, Any]:
        if name == "failure-during-candidate-checks":
            raise deploy.DeploymentError("rehearsed failure during candidate checks")
        deploy.validate_runtime_snapshot(runtime_fixture)
        return {
            "status": "pass",
            "schema_sha256": runtime_fixture["schema"]["sha256"],
            "source": deploy.live_manifest_snapshot(rows, target=True),
        }

    def post_open(*_: Any, **__: Any) -> dict[str, Any]:
        if name == "failure-after-reopening":
            raise deploy.DeploymentError("rehearsed failure after reopening")
        deploy.validate_runtime_snapshot(runtime_fixture)
        return {"status": "pass", "schema_sha256": runtime_fixture["schema"]["sha256"]}

    install = (
        partially_install_then_fail
        if name == "failure-during-source-installation"
        else original_install
    )
    release_receipt_hash = "b" * 64
    patches = {
        "APP_ROOT": item["application"],
        "RELEASE_ROOT": item["root"] / "releases",
        "ROLLBACK_ROOT": item["rollback"],
        "DEPLOYMENT_LOCK": item["root"] / "receiver.lock",
        "DEPENDENCY_LOCK": item["root"] / "dependency.lock",
        "LARAVEL_MAINTENANCE_FILE": item["application"] / "storage/framework/down",
        "FRONT_CONTROLLER": item["front"],
        "OPCACHE_WAIT_SECONDS": 0,
        "validate_release_receipt": lambda *_: (item["receipt"], item["release"], rows),
        "production_preflight": preflight,
        "database_backups": database_backups,
        "install_static_gate": gate,
        "establish_rollback_containment": containment,
        "front_controller_recovery_required": lambda state: True,
        "enter_laravel_maintenance": lambda *_: {"status": "pass"},
        "leave_laravel_maintenance": lambda *_: {"status": "pass"},
        "drain_runtime": lambda *_: {"status": "pass", "rehearsal": True},
        "dependency_identity": lambda: {"rehearsal": "exact-pinned-production-baseline"},
        "runtime_probe": runtime_probe,
        "install_runtime_files": install,
        "run_artisan": run_artisan,
        "candidate_cli_checks": candidate_checks,
        "restore_front_controller": restore_front,
        "post_open_health": post_open,
        "monitor_production": lambda *_: {"status": "pass", "samples": 30},
        "health_snapshot": lambda: {"status": "pass", "routes": "rehearsed"},
        "log_baseline": lambda: {"path": "rehearsal", "bytes": 0},
        "log_delta": lambda *_: {"bytes": 0, "sha256": deploy.sha256_bytes(b"")},
        "time": deploy.time,
    }

    expected_failure = name != "success-schema-present-resume"
    failure: dict[str, str] | None = None
    with patched(patches):
        original_sleep = deploy.time.sleep
        deploy.time.sleep = lambda _seconds: None
        try:
            try:
                final_path = deploy.deploy_release(
                    release_receipt_path=item["receipt_path"],
                    release_receipt_sha256=release_receipt_hash,
                    approval_token=deploy.DEPLOY_APPROVAL_TOKEN,
                )
                require(not expected_failure, f"Scenario {name} unexpectedly succeeded.")
                final_receipt = json.loads(final_path.read_text("utf-8"))
            except deploy.DeploymentError as exception:
                require(expected_failure, f"Scenario {name} unexpectedly failed: {exception}")
                failure = {
                    "type": type(exception).__name__,
                    "message_sha256": deploy.sha256_bytes(str(exception).encode("utf-8")),
                }
                final_receipt = None
        finally:
            deploy.time.sleep = original_sleep

        state_directories = sorted(path for path in item["rollback"].iterdir() if path.is_dir())
        require(len(state_directories) == 1, "Scenario did not create exactly one durable state.")
        state_directory = state_directories[0]
        state = json.loads((state_directory / "state.json").read_text("utf-8"))
        if expected_failure:
            source = deploy.live_manifest_snapshot(rows, target=False)
            require(
                source["sha256"] == deploy.EXPECTED_ORIGINAL_SOURCE_CAS_SHA256,
                "Rollback did not restore the exact original 37-path source CAS.",
            )
            require(state.get("rollback_complete") is True, "Automatic rollback did not complete.")
            schema_receipt_path = state_directory / "rollback-installed-schema-verification.json"
            require(schema_receipt_path.is_file(), "Rollback schema receipt is absent.")
            schema_receipt = json.loads(schema_receipt_path.read_text("utf-8"))
            require(
                schema_receipt["verification"]["schema_sha256"] == deploy.EXPECTED_SCHEMA_SHA256,
                "Rollback did not preserve the installed schema.",
            )
            require(
                schema_receipt["verification"]["migration_ledger"]["rows_sha256"]
                == deploy.EXPECTED_LEDGER_SHA256,
                "Rollback did not preserve the installed migration ledger.",
            )
        else:
            source = deploy.live_manifest_snapshot(rows, target=True)
            require(state.get("status") == "success", "Successful resume was not durable.")
            schema_receipt = json.loads(
                (state_directory / "cutover-installed-schema-receipt.json").read_text("utf-8")
            )
        require(
            schema_receipt["migration_executed_this_attempt"] is False,
            "A rehearsal recorded migration execution.",
        )
        require(
            not any("migrate" in argument for command in command_log for argument in command),
            "A rehearsal invoked a migration command.",
        )
        evidence = deploy.artifact_inventory(state_directory)

    return {
        "status": "pass",
        "scenario": name,
        "expected_failure": expected_failure,
        "observed_failure": failure,
        "final_state": state,
        "final_source": source,
        "schema_sha256": deploy.EXPECTED_SCHEMA_SHA256,
        "ledger_sha256": deploy.EXPECTED_LEDGER_SHA256,
        "target_migration_entries": deploy.EXPECTED_TARGET_MIGRATION_ENTRIES,
        "target_table_row_counts": {table: 0 for table in sorted(deploy.TARGET_TABLES)},
        "migration_command_invoked": False,
        "migration_pretend_invoked": False,
        "migration_executed_this_attempt": False,
        "artisan_commands": command_log,
        "evidence_manifest": evidence,
        "final_receipt": final_receipt,
    }


def run(parent: Path) -> dict[str, Any]:
    parent = parent.resolve(strict=True)
    rows = deploy.parse_manifest(MANIFEST_PATH)
    runtime_fixture = json.loads(FIXTURE_PATH.read_text("utf-8"))
    deploy.validate_runtime_snapshot(runtime_fixture)
    rehearsal_root = Path(
        tempfile.mkdtemp(prefix="buy-dtf-schema-present-resume-rehearsal-", dir=parent)
    )
    scenarios: dict[str, Any] = {}
    for name in (
        "success-schema-present-resume",
        "failure-before-source-installation",
        "failure-during-source-installation",
        "failure-during-candidate-checks",
        "failure-after-reopening",
    ):
        scenarios[name] = run_scenario(rehearsal_root, rows, runtime_fixture, name)
    result = {
        "status": "pass",
        "artifact": "buy-dtf-incoming-order-installed-schema-resume-rehearsal-v1",
        "runner_sha256": deploy.sha256_file(RUNNER_PATH),
        "rehearsal_script_sha256": deploy.sha256_file(Path(__file__).resolve()),
        "fixture_sha256": deploy.sha256_file(FIXTURE_PATH),
        "manifest_sha256": deploy.sha256_file(MANIFEST_PATH),
        "scenario_count": len(scenarios),
        "schema_state": deploy.SCHEMA_STATE,
        "schema_sha256": deploy.EXPECTED_SCHEMA_SHA256,
        "ledger_sha256": deploy.EXPECTED_LEDGER_SHA256,
        "original_source_cas_sha256": deploy.EXPECTED_ORIGINAL_SOURCE_CAS_SHA256,
        "migration_command_invoked": False,
        "migration_pretend_invoked": False,
        "migration_executed_this_attempt": False,
        "scenarios": scenarios,
    }
    receipt_path = rehearsal_root / "resume-rehearsal-receipt.json"
    deploy.atomic_json(receipt_path, result)
    return {
        "rehearsal_root": str(rehearsal_root),
        "receipt": str(receipt_path),
        "receipt_sha256": deploy.sha256_file(receipt_path),
        "scenario_count": len(scenarios),
        "status": "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=Path("/tmp"))
    arguments = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(run(arguments.parent), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
