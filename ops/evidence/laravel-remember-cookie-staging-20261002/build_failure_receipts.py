#!/usr/bin/env python3
"""Build deterministic receipts for the failed-closed restricted stage."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_json(name: str) -> dict[str, object]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256_file(name: str) -> str:
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def equal_without(
    before: dict[str, object], after: dict[str, object], excluded: set[str]
) -> bool:
    left = copy.deepcopy(before)
    right = copy.deepcopy(after)
    for key in excluded:
        left.pop(key, None)
        right.pop(key, None)
    return left == right


def write_json(name: str, document: dict[str, object]) -> None:
    (ROOT / name).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    before = read_json("preflight-before.json")
    after = read_json("preflight-after-failed-stage.json")
    schema_before = read_json("schema-ledger-before.json")
    schema_after = read_json("schema-ledger-after-failed-stage.json")
    shadow = read_json("failed-stage-shadow-identities.json")
    packages = read_json("partial-shadow-package-identity.json")
    mismatch = read_json("vendor-mismatch-analysis.json")

    config_equal = (ROOT / "configuration-before.txt").read_bytes() == (
        ROOT / "configuration-after-failed-stage.txt"
    ).read_bytes()
    services_equal = (ROOT / "services-before.txt").read_bytes() == (
        ROOT / "services-after-failed-stage.txt"
    ).read_bytes()
    preflight_equal = equal_without(before, after, {"checked_at_utc"})
    schema_equal = equal_without(
        schema_before, schema_after, {"generated_at_utc"}
    )

    capabilities = after["runtime"]["disabled_capabilities"]
    queue_tables = after["runtime"]["queue_tables"]
    ledger = schema_after["migration_ledger"]
    schema = schema_after["schema"]

    immutability = {
        "artifact": "buy-dtf-laravel-remember-cookie-post-failure-immutability-v1",
        "status": "pass",
        "observed_at_utc": after["checked_at_utc"],
        "comparison": {
            "configuration_snapshots_byte_identical": config_equal,
            "preflight_equal_except_checked_at_utc": preflight_equal,
            "schema_probe_equal_except_generated_at_utc": schema_equal,
            "service_snapshots_byte_identical": services_equal,
        },
        "production": {
            "cache_identity": after["cache_identity"],
            "capabilities": capabilities,
            "composer_json_sha256": after["live_composer_json_sha256"],
            "composer_lock_sha256": after["live_lock_sha256"],
            "configuration": {
                "database_config_sha256": after["database_config_sha256"],
                "snapshot_sha256": sha256_file(
                    "configuration-after-failed-stage.txt"
                ),
                "unchanged": config_equal,
            },
            "front_controller": after["front_controller"],
            "health": after["health"],
            "laravel_version": after["runtime"]["laravel_version"],
            "maintenance_active": after["maintenance_active"],
            "migration_ledger": {
                "row_count": ledger["row_count"],
                "rows_sha256": ledger["rows_sha256"],
                "unchanged": schema_equal,
            },
            "php_version": after["runtime"]["php_version"],
            "queue": {
                "connection": after["runtime"]["queue_connection"],
                "failed_jobs": queue_tables["failed_jobs"],
                "jobs": queue_tables["jobs"],
            },
            "savedimages_item_meta_nonnull_rows": schema[
                "savedimages_item_meta"
            ]["nonnull_rows"],
            "schema_sha256": schema["sha256"],
            "scoped_processes": after["scoped_processes"],
            "services": {
                "snapshot_sha256": sha256_file("services-after-failed-stage.txt"),
                "unchanged": services_equal,
            },
            "source_manifest": after["source_manifest"],
            "vendor_manifest": after["vendor_manifest"],
        },
        "unchanged_assertions": {
            "cache": before["cache_identity"] == after["cache_identity"],
            "capability_flags": before["runtime"]["disabled_capabilities"]
            == capabilities,
            "configuration": config_equal,
            "front_controller": before["front_controller"]
            == after["front_controller"],
            "health": before["health"] == after["health"],
            "live_lock": before["live_lock_sha256"] == after["live_lock_sha256"],
            "queues": before["runtime"]["queue_tables"] == queue_tables,
            "schema_and_ledger": schema_equal,
            "services_and_restart_counts": services_equal,
            "source": before["source_manifest"] == after["source_manifest"],
            "vendor": before["vendor_manifest"] == after["vendor_manifest"],
        },
    }
    if not all(immutability["comparison"].values()) or not all(
        immutability["unchanged_assertions"].values()
    ):
        raise RuntimeError("post-failure production immutability comparison failed")
    if capabilities != {
        "incoming_order_allowed_host_count": 0,
        "incoming_order_job_label_enabled": False,
        "incoming_order_receiver_enabled": False,
        "incoming_order_retention_enabled": False,
    }:
        raise RuntimeError("capability flags are not all disabled")
    if queue_tables != {"failed_jobs": 0, "jobs": 0}:
        raise RuntimeError("queue tables are not empty")
    if ledger["row_count"] != 21:
        raise RuntimeError("migration ledger is not exactly 21 rows")
    if schema["savedimages_item_meta"]["nonnull_rows"] != 0:
        raise RuntimeError("savedimages.item_meta has unexpected data")
    write_json("POST_FAILURE_IMMUTABILITY.json", immutability)

    stage_metadata = dict(
        line.split("=", 1)
        for line in (ROOT / "stage-command-metadata.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if "=" in line
    )
    expected_vendor = shadow["expected_vendor"]
    actual_vendor = shadow["actual_vendor"]
    receipt = {
        "artifact": "buy-dtf-laravel-remember-cookie-restricted-stage-failure-v1",
        "status": "failed_closed_before_release_receipt",
        "candidate": {
            "branch": "fix/laravel-12.69.1-remember-cookie-20261002",
            "commit": "6a98c74686f1ceffded8012d332318ac075b444e",
            "candidate_lock_sha256": "77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d",
            "live_lock_sha256": "22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9",
            "portable_archive_sha256": "e87f4bc7a7d1dc5f79df99b0cb2873b7a749e5c8000e5014aef4495c48e6ed3e",
            "runner_sha256": "2cae23d816e358c91ce512da4b3db3ee4e7fdff268c51afddafb0995b2feef9e",
            "runtime_helper_sha256": "74ae751d18f0396e86c066e908a006b1a170e223b1ad56c59168c94491925362",
        },
        "authorization": {
            "cutover_authorized": False,
            "operation": "restricted_stage_only",
            "stage_token_recorded_in_evidence": False,
            "stage_token_verified": True,
        },
        "attempt": {
            "exit_code": int(stage_metadata["stage_exit"]),
            "finished_at_utc": stage_metadata["stage_finished_at_utc"],
            "partial_release_path": "/var/www/buy-dtf/storage/app/private/operations/laravel-remember-cookie-releases/77055fc8acf8-20261003T000251Z",
            "partial_shadow_private": True,
            "release_receipt_exists": shadow["receipt_exists"],
            "started_at_utc": stage_metadata["stage_started_at_utc"],
            "stop_message": (ROOT / "stage-command.stderr")
            .read_text(encoding="utf-8")
            .strip(),
        },
        "checks_completed": {
            "candidate_cache_identity": "exact_match",
            "composer_audit_locked_no_dev": "pass_zero_advisories",
            "composer_install": "completed_80_packages",
            "composer_validate_strict": "pass",
            "package_discovery": "pass",
            "php_8_2_30_platform_check": "pass",
            "production_preflight": "pass",
            "route_discovery": "pass_178_routes",
            "shadow_package_identity": packages,
        },
        "command_receipts": {
            name: sha256_file(f"failed-stage-logs/{name}.txt")
            for name in (
                "composer-audit",
                "composer-install",
                "composer-validate",
                "platform",
                "shadow-package-discovery",
                "shadow-routes",
            )
        },
        "production_after_attempt": {
            "immutability_receipt": "POST_FAILURE_IMMUTABILITY.json",
            "immutability_status": immutability["status"],
            "preflight_status": after["status"],
        },
        "prohibited_actions": {
            "cutover_or_recovery_invoked": False,
            "live_lock_replaced": False,
            "maintenance_entered": False,
            "migrations_run": False,
            "services_restarted": False,
            "source_deployed": False,
            "static_gate_installed": False,
            "transparency_candidate_staged": False,
            "vendor_or_cache_exchanged": False,
        },
        "review_disposition": {
            "cutover_eligible": False,
            "existing_partial_shadow_eligible": False,
            "independent_review_required": True,
            "retry_under_existing_review": False,
            "required_correction": (
                "Revise the runner so source is present before optimized autoload generation "
                "and freeze a production-equivalent vendor identity; then repeat independent review."
            ),
        },
        "transparency_candidate": {
            "commit": "3db18d1fff3f599299eecd2aae21b9102fc45540",
            "dependency_envelope_frozen": False,
            "staged_or_deployed": False,
        },
        "vendor_gate": {
            "actual_shadow": actual_vendor,
            "expected_reviewed": expected_vendor,
            "mismatch_analysis": "vendor-mismatch-analysis.json",
            "result": "fail_closed",
            "root_cause": mismatch["result"]["reason"],
            "byte_accounting": mismatch["byte_accounting"],
        },
    }
    if receipt["attempt"]["release_receipt_exists"] is not False:
        raise RuntimeError("unexpected staged release receipt exists")
    if shadow["actual_cache"] != shadow["expected_cache"]:
        raise RuntimeError("candidate cache identity did not match")
    if actual_vendor == expected_vendor:
        raise RuntimeError("vendor gate unexpectedly matched")
    write_json("FAILED_STAGE_RECEIPT.json", receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
