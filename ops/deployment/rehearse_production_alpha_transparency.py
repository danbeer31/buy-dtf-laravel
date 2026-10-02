#!/usr/bin/env python3
"""Exercise the production-alpha runner against disposable local files only.

The rehearsal imports the frozen runner, replaces every external production
operation with a deterministic local double, and leaves the real source swap,
raw-byte source backup/restore, durable state, static-gate, and rollback code active.
It never opens a network connection or invokes Artisan, MySQL, or production.
"""

from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/production_alpha_transparency_deploy.py"
PROBE_PATH = ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php"
LOG_GUARD_PATH = ROOT / "ops/deployment/laravel_log_guard.py"
LOG_FIXTURES = ROOT / "tests/Fixtures/Deployment/LaravelLogs"
MANIFEST_PATH = (
    ROOT
    / "ops/evidence/production-alpha-transparency-source-only-20261002/APPLICATION_MANIFEST.json"
)
DEFAULT_ARCHIVE_PATH = (
    ROOT
    / "storage/app/private/operations/production-alpha-transparency-source-only-package-20261002"
    / "production-alpha-transparency-b02fce32.tar"
)
DEFAULT_BASELINE_ROOTS = (
    ROOT.parent / "buy-dtf-receiver-validation-20261001",
    ROOT.parent / "buy-dtf-laravel",
)

SPEC = importlib.util.spec_from_file_location("production_alpha_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import guard
    raise RuntimeError("Unable to import the production-alpha runner.")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


SCENARIOS = (
    "success",
    "pre-source-failure",
    "source-swap-failure",
    "candidate-check-failure",
    "post-reopen-failure",
    "genuine-log-failure",
    "schema-preserving-rollback",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise deploy.DeploymentError(message)


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def copy_with_metadata(source: Path, destination: Path, mode: int) -> None:
    destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chown(destination, deploy.EXPECTED_APP_UID, deploy.EXPECTED_APP_GID)
    os.chmod(destination, mode)


def resolve_baseline_sources(
    roots: list[Path], rows: list[dict[str, Any]]
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    resolved: dict[str, Path] = {}
    evidence: list[dict[str, Any]] = []
    for row in rows:
        if row["action"] != "M":
            continue
        matches: list[tuple[int, Path]] = []
        for index, root in enumerate(roots, start=1):
            candidate = root / row["path"]
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and deploy.sha256_file(candidate) == row["expected"]
                and candidate.stat().st_size == row["expected_bytes"]
            ):
                matches.append((index, candidate))
        if not matches:
            raise deploy.DeploymentError(
                f"No local baseline root contains exact raw bytes for {row['path']}."
            )
        root_index, selected = matches[0]
        resolved[row["path"]] = selected
        evidence.append(
            {
                "path": row["path"],
                "baseline_root_index": root_index,
                "sha256": row["expected"],
                "bytes": row["expected_bytes"],
            }
        )
    return resolved, evidence


def runtime_snapshot() -> dict[str, Any]:
    table_definition = [
        {
            "TABLE_NAME": "savedimages",
            "TABLE_TYPE": "BASE TABLE",
            "ENGINE": "InnoDB",
            "TABLE_COLLATION": "utf8mb4_unicode_ci",
            "CREATE_OPTIONS": "",
        }
    ]
    item_definition = [
        {
            "TABLE_NAME": "savedimages",
            "ORDINAL_POSITION": 11,
            "COLUMN_NAME": "item_meta",
            "COLUMN_TYPE": "text",
            "IS_NULLABLE": "YES",
            "COLUMN_DEFAULT": None,
            "EXTRA": "",
            "CHARACTER_SET_NAME": "utf8mb4",
            "COLLATION_NAME": "utf8mb4_unicode_ci",
            "GENERATION_EXPRESSION": "",
        }
    ]
    required_counts = {
        "businesses": 41,
        "dtforders": 73,
        "dtfimages": 109,
        "savedimages": 7,
    }
    return {
        "probe_version": 2,
        "artifact": "buy-dtf-production-alpha-transparency-runtime-probe-v1",
        "generated_at_utc": "2026-10-01T00:00:00Z",
        "application_environment": "local",
        "application_debug": False,
        "runtime": {
            "php_version": "8.2.30",
            "laravel_version": "12.69.0",
            "composer_classmap_authoritative": False,
            "imagick_loaded": True,
        },
        "connections": {
            "configured_fuel_connection": "fuelmysql",
            "expected_fuel_connection": "fuelmysql",
            "migration_invocation_connection": "fuelmysql",
            "fuel_driver": "mysql",
            "connection_match": True,
            "fuel_database_name_sha256": "0" * 64,
        },
        "migration_ledger": {
            "table": "migrations",
            "exists": True,
            "row_count": deploy.EXPECTED_LEDGER_ROW_COUNT,
            "rows_sha256": deploy.EXPECTED_LEDGER_SHA256,
            "target_migration": deploy.TARGET_MIGRATION,
            "target_entry_count": deploy.EXPECTED_TARGET_MIGRATION_ENTRIES,
            "without_target_row_count": deploy.EXPECTED_LEDGER_WITHOUT_TARGET_ROW_COUNT,
            "without_target_rows_sha256": deploy.EXPECTED_LEDGER_WITHOUT_TARGET_SHA256,
        },
        "schema": {
            "sha256": deploy.EXPECTED_SCHEMA_SHA256,
            "without_item_meta_sha256": deploy.EXPECTED_SCHEMA_WITHOUT_ITEM_META_SHA256,
            "section_row_counts": {"tables": 36, "columns": 411},
            "target_definitions": {
                "tables": table_definition,
                "columns": item_definition,
                "statistics": [],
                "table_constraints": [],
                "key_column_usage": [],
                "referential_constraints": [],
            },
            "required_tables": {name: True for name in required_counts},
            "required_table_row_counts": required_counts,
            "savedimages_item_meta": {
                "exists": True,
                "definition": item_definition,
                "nonnull_rows": 0,
                "savedimages_rows": required_counts["savedimages"],
                "data_columns_without_item_meta": [
                    "id",
                    "business_id",
                    "image",
                    "image_name",
                ],
                "data_sha256_without_item_meta": "3" * 64,
            },
        },
        "capabilities": {
            "receiver_enabled": False,
            "job_label_enabled": False,
            "retention_enabled": False,
            "allowed_host_count": 0,
        },
        "queue": {
            "connection": "sync",
            "counts": {
                "jobs_table_exists": False,
                "failed_jobs_table_exists": True,
                "jobs": None,
                "failed_jobs": 0,
            },
        },
        "scheduler": {
            "event_count": 3,
            "stripe_payout_sync_event_count": 1,
            "overlap_mutexes": [
                {
                    "command_sha256": "1" * 64,
                    "mutex_name_sha256": "2" * 64,
                    "exists": False,
                }
            ],
            "active_overlap_mutex_count": 0,
        },
    }


def build_fixture(
    parent: Path,
    scenario: str,
    rows: list[dict[str, Any]],
    baseline_sources: dict[str, Path],
) -> dict[str, Path | dict[str, Any]]:
    root = Path(tempfile.mkdtemp(prefix=f"buy-dtf-alpha-{scenario}-", dir=parent))
    os.chmod(root, 0o755)
    application = root / "application"
    release = root / "release"
    candidate = release / "candidate"
    rollback = root / "rollbacks"
    for directory, mode in (
        (application, 0o755),
        (application / "public", 0o755),
        (application / "storage/framework", 0o775),
        (candidate, 0o755),
        (rollback, 0o700),
    ):
        directory.mkdir(mode=mode, parents=True, exist_ok=True)
        os.chmod(directory, mode)

    for row in rows:
        if row["action"] == "M":
            copy_with_metadata(baseline_sources[row["path"]], application / row["path"], 0o664)
        copy_with_metadata(ROOT / row["path"], candidate / row["path"], 0o600)

    front = application / "public/index.php"
    copy_with_metadata(ROOT / "public/index.php", front, 0o644)
    helper = release / PROBE_PATH.name
    shutil.copyfile(PROBE_PATH, helper)
    os.chmod(helper, 0o600)
    log_guard = release / LOG_GUARD_PATH.name
    shutil.copyfile(LOG_GUARD_PATH, log_guard)
    os.chmod(log_guard, 0o600)
    receipt_path = release / "release-receipt.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    os.chmod(receipt_path, 0o600)
    receipt = {
        "status": "pass",
        "scope": "alpha-repair-schema-present-source-only-staging",
        "target_commit": deploy.TARGET_COMMIT,
        "release_directory": str(release),
        "inputs": {
            "helper": {"path": str(helper), "sha256": deploy.EXPECTED_HELPER_SHA256},
            "log_guard": {
                "path": str(log_guard),
                "sha256": deploy.EXPECTED_LOG_GUARD_SHA256,
            },
        },
    }
    return {
        "root": root,
        "application": application,
        "release": release,
        "candidate": candidate,
        "rollback": rollback,
        "front": front,
        "helper": helper,
        "log_guard": log_guard,
        "receipt": receipt,
        "receipt_path": receipt_path,
    }


def run_scenario(
    parent: Path,
    scenario: str,
    rows: list[dict[str, Any]],
    baseline_sources: dict[str, Path],
) -> dict[str, Any]:
    item = build_fixture(parent, scenario, rows, baseline_sources)
    application = item["application"]
    rollback = item["rollback"]
    front = item["front"]
    assert isinstance(application, Path)
    assert isinstance(rollback, Path)
    assert isinstance(front, Path)

    command_log: list[list[str]] = []
    web_probe_log: list[dict[str, Any]] = []
    original_install = deploy.install_runtime_files
    original_gate = deploy.install_static_gate
    original_containment = deploy.establish_rollback_containment
    original_restore_exact = deploy.restore_front_controller_exact
    original_recovery_required = deploy.front_controller_recovery_required
    original_log_baseline = deploy.log_baseline
    original_log_delta = deploy.log_delta

    def snapshot() -> dict[str, Any]:
        return runtime_snapshot()

    def preflight(**_: Any) -> dict[str, Any]:
        current = snapshot()
        verification = deploy.validate_runtime_snapshot(current)
        return {
            "status": "pass",
            "runtime": current,
            "runtime_command": {"rehearsal": True},
            "runtime_verification": verification,
            "live_source": deploy.live_manifest_snapshot(rows, target=False),
            "dependencies": {"identity": "reviewed-production-baseline"},
        }

    runtime_sequence = 0

    def fake_runtime_probe(_helper: Path, _directory: Path, name: str):
        nonlocal runtime_sequence
        runtime_sequence += 1
        if scenario == "pre-source-failure" and name == "cutover-installed-schema-probe":
            raise deploy.DeploymentError("rehearsed pre-source failure")
        return copy.deepcopy(snapshot()), {
            "rehearsal": True,
            "name": name,
            "sequence": runtime_sequence,
        }

    def web_identity_probe(route: str) -> dict[str, Any]:
        completed = subprocess.run(
            [
                "/usr/bin/setpriv",
                f"--reuid={deploy.EXPECTED_WEB_UID}",
                f"--regid={deploy.EXPECTED_WEB_GID}",
                "--clear-groups",
                "/usr/bin/php",
                str(front),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        passed = (
            completed.returncode == 0
            and completed.stdout == deploy.MAINTENANCE_GATE_SENTINEL
            and completed.stderr == ""
        )
        record = {
            "route": route,
            "uid": deploy.EXPECTED_WEB_UID,
            "gid": deploy.EXPECTED_WEB_GID,
            "exit_status": completed.returncode,
            "sentinel_verified": completed.stdout == deploy.MAINTENANCE_GATE_SENTINEL,
            "stderr_sha256": deploy.sha256_bytes(completed.stderr.encode("utf-8")),
            "readable_by_separate_web_identity": passed,
        }
        web_probe_log.append(record)
        require(passed, "The separate web identity could not read and execute the 0644 gate.")
        return {
            "route": route,
            "status": 503,
            "header_verified": True,
            "sentinel_verified": True,
            "web_identity": record,
        }

    def local_gate(**kwargs: Any) -> dict[str, Any]:
        kwargs["front_controller"] = front
        kwargs["application_root"] = application
        kwargs["origin_probe"] = lambda: web_identity_probe("origin_loopback")
        kwargs["public_probe"] = lambda: web_identity_probe("public_cloudflare")
        kwargs["restored_health_probe"] = lambda: {"status": "healthy", "rehearsal": True}
        return original_gate(**kwargs)

    def local_containment(**kwargs: Any) -> dict[str, Any]:
        kwargs["front_controller"] = front
        kwargs["application_root"] = application
        kwargs["origin_probe"] = lambda: web_identity_probe("origin_loopback")
        kwargs["public_probe"] = lambda: web_identity_probe("public_cloudflare")
        kwargs["restored_health_probe"] = lambda: {"status": "healthy", "rehearsal": True}
        return original_containment(**kwargs)

    def local_restore(
        backup: Path,
        metadata: dict[str, Any],
        *,
        state: dict[str, Any],
        state_path: Path,
        state_directory: Path,
        name: str,
    ) -> dict[str, Any]:
        return original_restore_exact(
            backup=backup,
            expected_sha256=deploy.EXPECTED_FRONT_CONTROLLER_SHA256,
            metadata=metadata,
            allowed_current_sha256={
                deploy.EXPECTED_FRONT_CONTROLLER_SHA256,
                deploy.EXPECTED_GATE_SHA256,
            },
            state=state,
            state_path=state_path,
            state_directory=state_directory,
            operation=name,
            receipt_name=f"{name}-receipt.json",
            front_controller=front,
            application_root=application,
        )

    def enter_maintenance(directory: Path, name: str) -> dict[str, Any]:
        command_log.append(["artisan", "down", name])
        marker = application / "storage/framework/down"
        deploy.atomic_write(marker, b"rehearsal\n", 0o664)
        return {"status": "pass", "rehearsal": True}

    def leave_maintenance(directory: Path, name: str) -> dict[str, Any]:
        command_log.append(["artisan", "up", name])
        marker = application / "storage/framework/down"
        marker.unlink(missing_ok=True)
        return {"status": "pass", "rehearsal": True}

    def local_install(
        candidate: Path,
        install_rows: list[dict[str, Any]],
        directory: Path,
        **kwargs: Any,
    ) -> dict[str, Any]:
        installed_count = 0

        def injector(phase: str, _path: str) -> None:
            nonlocal installed_count
            if phase == "after_replacement":
                installed_count += 1
                if scenario == "source-swap-failure" and installed_count == 3:
                    raise deploy.DeploymentError("rehearsed source-swap failure")

        return original_install(
            candidate,
            install_rows,
            directory,
            state=kwargs.get("state"),
            state_path=kwargs.get("state_path"),
            fault_injector=injector,
        )

    def candidate_checks(_helper: Path, install_rows: list[dict[str, Any]], _directory: Path):
        if scenario == "candidate-check-failure":
            raise deploy.DeploymentError("rehearsed candidate-check failure")
        verification = deploy.validate_runtime_snapshot(snapshot())
        return {
            "status": "pass",
            "source": deploy.live_manifest_snapshot(install_rows, target=True),
            "runtime_verification": verification,
        }

    def post_open(_helper: Path, _directory: Path, _name: str) -> dict[str, Any]:
        if scenario == "post-reopen-failure":
            raise deploy.DeploymentError("rehearsed post-reopen failure")
        return {
            "status": "pass",
            "runtime": copy.deepcopy(snapshot()),
            "runtime_verification": deploy.validate_runtime_snapshot(snapshot()),
        }

    def monitor(
        _helper: Path,
        install_rows: list[dict[str, Any]],
        directory: Path,
        log_checkpoint: dict[str, Any],
    ):
        final_log_checkpoint = deploy.verify_log_continuity(log_checkpoint)
        receipt = {
            "status": "pass",
            "samples": 30,
            "schema_state": deploy.SCHEMA_STATE,
            "source_sha256": deploy.live_manifest_snapshot(
                install_rows, target=True
            )["sha256"],
            "final_log_checkpoint": final_log_checkpoint,
        }
        path = directory / "monitoring-samples.json"
        deploy.atomic_json(path, receipt)
        if scenario == "schema-preserving-rollback":
            raise deploy.DeploymentError("rehearsed monitor failure requiring source rollback")
        return {**receipt, "path": str(path), "sha256": deploy.sha256_file(path)}

    log_path = application / "storage/logs/laravel.log"

    def baseline_logs() -> dict[str, Any]:
        log_path.parent.mkdir(mode=0o775, parents=True, exist_ok=True)
        if not log_path.exists():
            deploy.atomic_write(
                log_path,
                b"[2026-10-02 00:00:00] local.INFO: rehearsal baseline\n",
                0o664,
            )
        return original_log_baseline()

    def inspect_logs(
        baseline: dict[str, Any],
        directory: Path,
        guard_path: Path,
        *,
        evidence_label: str,
    ) -> dict[str, Any]:
        fixture_name = (
            "genuine-exception.txt"
            if scenario == "genuine-log-failure"
            else "reviewed-56-error-delta.redacted.txt"
        )
        content = (LOG_FIXTURES / fixture_name).read_bytes()
        log_path.parent.mkdir(mode=0o775, parents=True, exist_ok=True)
        with log_path.open("ab") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return original_log_delta(
            baseline,
            directory,
            guard_path,
            evidence_label=evidence_label,
        )

    expected_failure = scenario != "success"
    failure: dict[str, Any] | None = None
    release_receipt_hash = "b" * 64
    patches = {
        "APP_ROOT": application,
        "RELEASE_ROOT": item["root"] / "releases",
        "ROLLBACK_ROOT": rollback,
        "DEPLOYMENT_LOCK": item["root"] / "alpha-repair.lock",
        "DEPENDENCY_LOCK": item["root"] / "dependency.lock",
        "LARAVEL_MAINTENANCE_FILE": application / "storage/framework/down",
        "FRONT_CONTROLLER": front,
        "OPCACHE_WAIT_SECONDS": 0,
        "validate_release_receipt": lambda *_args, **_kwargs: (
            item["receipt"],
            item["release"],
            rows,
        ),
        "production_preflight": preflight,
        "install_static_gate": local_gate,
        "establish_rollback_containment": local_containment,
        "front_controller_recovery_required": lambda state: original_recovery_required(
            state, front_controller=front
        ),
        "restore_front_controller": local_restore,
        "enter_laravel_maintenance": enter_maintenance,
        "leave_laravel_maintenance": leave_maintenance,
        "drain_runtime": lambda *_: {"status": "pass", "samples": 1},
        "dependency_identity": lambda: {"identity": "reviewed-production-baseline"},
        "runtime_probe": fake_runtime_probe,
        "install_runtime_files": local_install,
        "candidate_cli_checks": candidate_checks,
        "post_open_health": post_open,
        "monitor_production": monitor,
        "health_snapshot": lambda: {"status": "pass", "rehearsal": True},
        "log_baseline": baseline_logs,
        "log_delta": inspect_logs,
    }

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
                require(not expected_failure, f"Scenario {scenario} unexpectedly succeeded.")
                final_receipt = json.loads(final_path.read_text("utf-8"))
            except deploy.DeploymentError as exception:
                require(expected_failure, f"Scenario {scenario} unexpectedly failed: {exception}")
                failure = {
                    "type": type(exception).__name__,
                    "message_sha256": deploy.sha256_bytes(str(exception).encode("utf-8")),
                }
                final_receipt = None
        finally:
            deploy.time.sleep = original_sleep

        state_directories = sorted(path for path in rollback.iterdir() if path.is_dir())
        require(len(state_directories) == 1, "Scenario did not create exactly one durable state.")
        state_directory = state_directories[0]
        state_path = state_directory / "state.json"
        state = json.loads(state_path.read_text("utf-8"))
        require(
            "database_backup_receipt" not in state,
            "Source-only state recorded a database backup receipt.",
        )
        require(
            not (state_directory / "database-before").exists(),
            "Source-only rehearsal created a database backup directory.",
        )
        if final_receipt is not None:
            require(
                "database_backup_receipt_sha256" not in final_receipt,
                "Source-only final receipt recorded a database backup.",
            )
        front_identity = deploy.file_identity(front)
        require(
            front_identity["sha256"] == deploy.EXPECTED_FRONT_CONTROLLER_SHA256,
            "Scenario did not finish with the exact original front controller.",
        )
        require(front_identity["metadata"]["mode"] == 0o644, "Front mode changed.")

        final_schema = deploy.validate_runtime_snapshot(snapshot())
        require(
            final_schema["schema_state"] == deploy.SCHEMA_STATE,
            "Scenario changed the installed schema state.",
        )
        if expected_failure:
            require(state.get("rollback_complete") is True, "Automatic rollback did not complete.")
            source = deploy.live_manifest_snapshot(rows, target=False)
            schema_receipt = json.loads(
                (state_directory / "rollback-schema-preservation-receipt.json").read_text(
                    "utf-8"
                )
            )
            require(
                schema_receipt["observed_schema_state"] == deploy.SCHEMA_STATE,
                "Rollback receipt recorded the wrong schema state.",
            )
            require(
                schema_receipt["additive_schema_preserved"] is True,
                "Rollback did not preserve the installed schema.",
            )
        else:
            require(state.get("status") == "success", "Success was not durable.")
            source = deploy.live_manifest_snapshot(rows, target=True)
            schema_receipt = {
                "observed_schema_state": deploy.SCHEMA_STATE,
                "additive_schema_preserved": True,
            }

        forbidden = [
            command
            for command in command_log
            if any(
                token in {"migrate:rollback", "db:wipe", "cache:clear", "optimize:clear"}
                for token in command
            )
        ]
        require(not forbidden, "A prohibited command entered the rehearsal.")
        migration_commands = [command for command in command_log if "migrate" in command]
        require(
            not migration_commands,
            "A migration command entered the schema-present source-only rehearsal.",
        )
        require(state.get("migration_command_invoked") is False, "Migration flag changed.")
        require(state.get("migration_pretend_invoked") is False, "Pretend flag changed.")
        require(
            state.get("migration_executed_this_attempt") is False,
            "Migration execution flag changed.",
        )

        raw_inventory = deploy.artifact_inventory(state_directory)
        raw_manifest_sha256 = deploy.sha256_bytes(deploy.canonical_bytes(raw_inventory))
        state_sha256 = deploy.sha256_file(state_path)

    return {
        "status": "pass",
        "scenario": scenario,
        "expected_failure": expected_failure,
        "observed_failure": failure,
        "final_state_status": state.get("status"),
        "rollback_complete": bool(state.get("rollback_complete")),
        "migration_command_invoked": bool(state.get("migration_command_invoked")),
        "migration_pretend_invoked": bool(state.get("migration_pretend_invoked")),
        "migration_executed_this_attempt": bool(
            state.get("migration_executed_this_attempt")
        ),
        "schema_state": deploy.SCHEMA_STATE,
        "additive_schema_preserved": schema_receipt["additive_schema_preserved"],
        "source_expectation": source["expectation"],
        "source_cas_sha256": source["sha256"],
        "front_controller_sha256": front_identity["sha256"],
        "front_controller_mode": oct(int(front_identity["metadata"]["mode"])),
        "separate_web_identity_probe_count": len(web_probe_log),
        "separate_web_identity_all_passed": all(
            row["readable_by_separate_web_identity"] for row in web_probe_log
        ),
        "migration_command_count": len(migration_commands),
        "prohibited_command_count": len(forbidden),
        "state_sha256": state_sha256,
        "raw_evidence_entries": len(raw_inventory),
        "raw_evidence_manifest_sha256": raw_manifest_sha256,
        "raw_state_directory_name": state_directory.name,
        "final_receipt_sha256": (
            deploy.sha256_file(Path(str(state["final_receipt"])))
            if final_receipt is not None
            else None
        ),
    }


def portable_inventory(root: Path, excluded: set[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    excluded_resolved = {path.resolve(strict=False) for path in excluded}
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if path.is_dir():
            continue
        if path.resolve(strict=False) in excluded_resolved:
            continue
        require(path.is_file() and not path.is_symlink(), "Portable evidence has invalid path.")
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": deploy.sha256_file(path),
            }
        )
    return records


def run(
    private_parent: Path,
    portable_output: Path,
    baseline_roots: list[Path],
    archive: Path,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise deploy.DeploymentError(
            "Run the local rehearsal as root so setpriv can prove www-data readability."
        )
    private_parent = private_parent.resolve(strict=True)
    rows = deploy.parse_manifest(MANIFEST_PATH)
    baseline_sources, baseline_evidence = resolve_baseline_sources(baseline_roots, rows)
    private_root = Path(
        tempfile.mkdtemp(prefix="buy-dtf-alpha-rehearsal-", dir=private_parent)
    )
    # Permit traversal only so the distinct www-data identity can execute the
    # disposable 0644 front controller; scenario evidence remains 0600/0700.
    os.chmod(private_root, 0o711)
    archive = deploy.require_regular_file(archive, deploy.EXPECTED_ARCHIVE_SHA256)
    archive_evidence = private_root / "archive-verification"
    archive_evidence.mkdir(mode=0o700)
    archive_candidate = private_root / "archive-candidate"
    archive_extraction = deploy.extract_candidate(
        archive,
        archive_candidate,
        rows,
        archive_evidence,
    )
    archive_verification = deploy.candidate_verification(
        archive_candidate,
        rows,
        archive_evidence,
    )
    scenarios: dict[str, Any] = {}
    for scenario in SCENARIOS:
        scenarios[scenario] = run_scenario(
            private_root, scenario, rows, baseline_sources
        )

    private_manifest_path = private_root / "PRIVATE_MANIFEST.json"
    private_inventory = deploy.artifact_inventory(
        private_root,
        exclude={private_manifest_path},
    )
    deploy.atomic_json(
        private_manifest_path,
        {
            "algorithm": (
                "sort every regular file by POSIX path relative to the private rehearsal "
                "root; record relative path, raw-byte SHA-256, byte count, and mode; "
                "exclude PRIVATE_MANIFEST.json itself"
            ),
            "entries": private_inventory,
            "entries_sha256": deploy.sha256_bytes(
                deploy.canonical_bytes(private_inventory)
            ),
        },
    )

    portable_output.mkdir(mode=0o755, parents=True, exist_ok=True)
    aggregate = {
        "status": "pass",
        "artifact": "buy-dtf-production-alpha-transparency-source-only-local-rehearsal-v2",
        "scope": "disposable-local-filesystem-only-no-production-access",
        "scenario_count": len(scenarios),
        "scenarios_required": list(SCENARIOS),
        "runner_sha256": deploy.sha256_file(RUNNER_PATH),
        "runtime_probe_sha256": deploy.sha256_file(PROBE_PATH),
        "laravel_log_guard_sha256": deploy.sha256_file(LOG_GUARD_PATH),
        "rehearsal_script_sha256": deploy.sha256_file(Path(__file__).resolve()),
        "application_manifest_sha256": deploy.sha256_file(MANIFEST_PATH),
        "candidate_archive_sha256": deploy.EXPECTED_ARCHIVE_SHA256,
        "candidate_archive_verification": {
            "extraction": {
                "files": archive_extraction["files"],
                "rows_sha256": archive_extraction["rows_sha256"],
                "tree": archive_extraction["tree"],
                "log_sha256": archive_extraction["log"]["sha256"],
                "log_bytes": archive_extraction["log"]["bytes"],
            },
            "verification": {
                "files": archive_verification["files"],
                "records_sha256": archive_verification["records_sha256"],
                "tree": archive_verification["tree"],
                "evidence_sha256": archive_verification["evidence"]["sha256"],
                "evidence_bytes": archive_verification["evidence"]["bytes"],
            },
        },
        "private_evidence_manifest": {
            "entries": len(private_inventory),
            "entries_sha256": deploy.sha256_bytes(
                deploy.canonical_bytes(private_inventory)
            ),
            "manifest_sha256": deploy.sha256_file(private_manifest_path),
        },
        "target_application_commit": deploy.TARGET_COMMIT,
        "artifact_base_commit": deploy.ARTIFACT_BASE_COMMIT,
        "baseline_source_records": baseline_evidence,
        "umask": "0o077",
        "production_accessed": False,
        "production_staged": False,
        "migration_command_invoked": False,
        "migration_pretend_invoked": False,
        "migration_executed_this_attempt": False,
        "external_command_allowlist": ["setpriv", "php <disposable static gate>"],
        "scenarios": scenarios,
    }
    for name, result in scenarios.items():
        deploy.atomic_json(portable_output / f"{name}-receipt.json", result)
    aggregate_path = portable_output / "rehearsal-receipt.json"
    deploy.atomic_json(aggregate_path, aggregate)
    manifest_path = portable_output / "PORTABLE_MANIFEST.json"
    inventory = portable_inventory(portable_output, {manifest_path})
    deploy.atomic_json(
        manifest_path,
        {
            "algorithm": (
                "sort regular files by POSIX relative path; for each record store path, "
                "exact byte count, and lowercase SHA-256 of raw bytes; serialize as "
                "UTF-8 JSON with sorted keys, two-space indentation, and one LF"
            ),
            "entries": inventory,
            "entries_sha256": deploy.sha256_bytes(deploy.canonical_bytes(inventory)),
        },
    )
    return {
        "status": "pass",
        "scenario_count": len(scenarios),
        "private_rehearsal_directory": str(private_root),
        "portable_receipt": str(aggregate_path),
        "portable_receipt_sha256": deploy.sha256_file(aggregate_path),
        "portable_manifest": str(manifest_path),
        "portable_manifest_sha256": deploy.sha256_file(manifest_path),
        "portable_entries": len(inventory),
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-parent", type=Path, default=Path("/tmp"))
    parser.add_argument("--portable-output", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, action="append")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE_PATH)
    return parser.parse_args()


def main() -> int:
    os.umask(0o077)
    arguments = parse_arguments()
    roots = [path.resolve(strict=True) for path in (arguments.baseline_root or DEFAULT_BASELINE_ROOTS)]
    result = run(
        arguments.private_parent,
        arguments.portable_output,
        roots,
        arguments.archive.resolve(strict=True),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
