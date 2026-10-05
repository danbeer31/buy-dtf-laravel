#!/usr/bin/env python3
"""Freeze local operations controls and inventory the review packet. No network."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import production_alpha_scheduler_guard as scheduler

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-source-only-v5-scheduler-20261005"
BASE_EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-source-only-v3-20261004"
RUNNER = ROOT / "ops/deployment/production_alpha_transparency_deploy.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def freeze():
    manifest = json.loads((BASE_EVIDENCE / "APPLICATION_MANIFEST.json").read_text())
    manifest["retired_runner_sha256s"] = sorted(set(manifest["retired_runner_sha256s"]) | {"25da4ddef0b4eb088cdedadf4848b1286a389760942493717e52d00f02c014df", "880d6ec6cb1ca5cee95964cf48843384afbaaeb73e835d03850e32de92aa21ab"})
    manifest["scheduler_policy_sha256"] = scheduler.POLICY_SHA256
    manifest["scheduler_policy"] = scheduler.POLICY
    write(EVIDENCE / "APPLICATION_MANIFEST.json", manifest)
    source = RUNNER.read_text()
    for constant, path in {
        "EXPECTED_HELPER_SHA256": ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php",
        "EXPECTED_LOG_GUARD_SHA256": ROOT / "ops/deployment/laravel_log_guard.py",
        "EXPECTED_MANIFEST_SHA256": EVIDENCE / "APPLICATION_MANIFEST.json",
    }.items():
        source, count = re.subn(rf'{constant} = "[0-9a-f]{{64}}"', f'{constant} = "{sha(path)}"', source)
        if count != 1: raise RuntimeError(f"Expected one frozen {constant}")
    for name in ("production_alpha_scheduler_guard.py", "production_alpha_scheduler_probe.php"):
        source, count = re.subn(rf"'{re.escape(name)}': '[0-9a-f]{{64}}'", f"'{name}': '{sha(ROOT / 'ops/deployment' / name)}'", source)
        if count != 1: raise RuntimeError(f"Expected one frozen {name}")
    RUNNER.write_text(source, encoding="utf-8", newline="\n")
    if manifest["paths"] != json.loads((BASE_EVIDENCE / "APPLICATION_MANIFEST.json").read_text())["paths"]:
        raise RuntimeError("Candidate application members changed")
    print(json.dumps({"status": "pass", "manifest_sha256": sha(EVIDENCE / "APPLICATION_MANIFEST.json"), "runner_sha256": sha(RUNNER), "application_paths_unchanged": True}))


def inventory():
    import production_alpha_transparency_deploy as runner
    excluded = {EVIDENCE / "EVIDENCE_MANIFEST.json", EVIDENCE / "SHA256SUMS"}
    paths = sorted(set(EVIDENCE.rglob("*")) | {
        RUNNER, ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php",
        ROOT / "ops/deployment/production_alpha_scheduler_guard.py",
        ROOT / "ops/deployment/production_alpha_scheduler_probe.php",
        ROOT / "ops/deployment/laravel_log_guard.py",
        ROOT / "ops/deployment/rehearse_production_alpha_transparency.py",
        ROOT / "ops/deployment/rehearse_production_alpha_scheduler.py",
        ROOT / "ops/deployment/test_production_alpha_transparency_runner.py",
        ROOT / "ops/deployment/test_production_alpha_nginx_inventory.py",
        ROOT / "ops/deployment/test_production_alpha_scheduler.py",
        ROOT / "ops/deployment/test_production_alpha_scheduler_probe.php",
        ROOT / "ops/deployment/validate_production_alpha_scheduler.py",
        Path(__file__).resolve(),
        ROOT / "ops/PRODUCTION_ALPHA_TRANSPARENCY_SCHEDULER_CORRECTION_PLAN_2026-10-05.md",
    } | {ROOT / "ops/deployment" / name for name in runner.CONTROL_FILES}, key=lambda path: path.as_posix())
    entries = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
               for p in paths if p.is_file() and p not in excluded]
    write(EVIDENCE / "EVIDENCE_MANIFEST.json", {"artifact": "buy-dtf-source-scheduler-local-review-v5", "status": "local_review_only_no_deployment_authority",
        "base_commit": "8678872c337f1e1c56347a16329b4d0a212281ce", "production_accessed": False,
        "raw_logs_headers_cookies_customer_data_included": False, "entries": entries})
    entries.append({"path": (EVIDENCE / "EVIDENCE_MANIFEST.json").relative_to(ROOT).as_posix(), "sha256": sha(EVIDENCE / "EVIDENCE_MANIFEST.json")})
    (EVIDENCE / "SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in sorted(entries, key=lambda row: row["path"])), encoding="utf-8", newline="\n")
    print(json.dumps({"status": "pass", "entries": len(entries), "evidence_manifest_sha256": sha(EVIDENCE / "EVIDENCE_MANIFEST.json"), "checksums_sha256": sha(EVIDENCE / "SHA256SUMS")}))


def preserve():
    import production_alpha_transparency_deploy as runner
    vendor_root = Path("/tmp/buydtf-alpha-v3-build-a-20261004-r3")
    old = json.loads((BASE_EVIDENCE / "APPLICATION_MANIFEST.json").read_text())
    new = json.loads((EVIDENCE / "APPLICATION_MANIFEST.json").read_text())
    if old["paths"] != new["paths"]: raise RuntimeError("Application member bytes changed")
    for name, expected in runner.CONTROL_FILES.items():
        if sha(ROOT / "ops/deployment" / name) != expected: raise RuntimeError(f"Control identity differs: {name}")
    vendor = runner.source_controls.require_candidate_vendor(vendor_root / "vendor")
    autoload = runner.source_controls.require_application_autoload(vendor_root)
    cache = runner.tree_manifest(vendor_root / "bootstrap/cache")
    if cache["sha256"] != runner.EXPECTED_CACHE_MANIFEST_SHA256 or sha(vendor_root / "composer.lock") != runner.EXPECTED_COMPOSER_LOCK_SHA256:
        raise RuntimeError("Local accepted cache/lock identity changed")
    archive = ROOT / "storage/app/private/operations/production-alpha-transparency-source-only-package-20261002/production-alpha-transparency-b02fce32.tar"
    if sha(archive) != runner.EXPECTED_ARCHIVE_SHA256: raise RuntimeError("Source archive changed")
    write(EVIDENCE / "artifact-identities.json", {
        "status": "pass", "base_commit": "8678872c337f1e1c56347a16329b4d0a212281ce",
        "scope": "local operations-only; no fresh production verification",
        "runner_sha256": sha(RUNNER), "scheduler_guard_sha256": sha(ROOT / "ops/deployment/production_alpha_scheduler_guard.py"),
        "scheduler_probe_sha256": sha(ROOT / "ops/deployment/production_alpha_scheduler_probe.php"),
        "runtime_probe_sha256": sha(ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php"),
        "laravel_log_guard_sha256": sha(ROOT / "ops/deployment/laravel_log_guard.py"),
        "application_manifest_sha256": sha(EVIDENCE / "APPLICATION_MANIFEST.json"),
        "candidate_archive_sha256": sha(archive), "application_member_count": len(new["paths"]),
        "application_member_definitions_unchanged": True,
        "frozen_control_sha256s": runner.CONTROL_FILES,
        "scheduler_policy": scheduler.POLICY, "scheduler_policy_sha256": scheduler.POLICY_SHA256,
        "preserved_local_vendor": vendor, "preserved_local_autoload": autoload,
        "preserved_local_cache": cache, "preserved_lock_sha256": sha(vendor_root / "composer.lock"),
        "production_accessed": False, "accounting_tasks_executed": False,
        "retired_runner_sha256s": sorted(runner.RETIRED_RUNNER_SHA256S),
        "retired_release_receipt_sha256s": sorted(runner.RETIRED_RELEASE_RECEIPT_SHA256S),
    })
    print(json.dumps({"status": "pass", "identities_sha256": sha(EVIDENCE / "artifact-identities.json"), "application_members_unchanged": len(new["paths"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "inventory", "preserve"])
    arguments = parser.parse_args()
    {"freeze": freeze, "inventory": inventory, "preserve": preserve}[arguments.action]()
