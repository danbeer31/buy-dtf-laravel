"""Bind local correction evidence; never connect to production or run deployment."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_alpha_transparency_deploy as runner

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops/evidence/process-permission-rollback-20261005"
BASE = "aa95711b6f09fda1207f97457aa056938b8f6c8b"
CLOSEOUT = ROOT / "ops/evidence/original-application-recovery-closeout-20261005"


def git(*args, text=False):
    # The worktree was created by Windows Git; its gitdir is a Windows path.
    windows_root = subprocess.check_output(["wslpath", "-w", str(ROOT)], text=True).strip()
    return subprocess.check_output(["/mnt/c/Program Files/Git/cmd/git.exe", "-C", windows_root, *args], text=text)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def write(name, value):
    (EVIDENCE / name).write_bytes(runner.canonical_bytes(value))


def run(linux_private: Path):
    controls = {name: sha(Path(runner.__file__).with_name(name)) for name in runner.CONTROL_FILES}
    require(controls == runner.CONTROL_FILES, "Control registry differs from actual bytes.")
    runner_sha = sha(Path(runner.__file__))
    old_manifest = json.loads((ROOT / "ops/evidence/production-alpha-transparency-source-only-v5-scheduler-20261005/APPLICATION_MANIFEST.json").read_text())
    manifest = read("APPLICATION_MANIFEST.json")
    require(manifest["paths"] == old_manifest["paths"], "Application members changed.")
    member_proof = []
    for row in manifest["paths"]:
        path = ROOT / row["path"]
        require(sha(path) == row["target_sha256"] and path.stat().st_size == row["target_bytes"], "Candidate member byte drift.")
        before = git("show", BASE + ":" + row["path"])
        require(before == path.read_bytes(), "Application code differs from accepted base.")
        member_proof.append({"path": row["path"], "sha256": sha(path), "bytes": path.stat().st_size, "unchanged_from_base": True})
    archive = ROOT / "storage/app/private/operations/production-alpha-transparency-source-only-package-20261002/production-alpha-transparency-b02fce32.tar"
    require(sha(archive) == runner.EXPECTED_ARCHIVE_SHA256, "Accepted archive changed.")
    validation = read("VALIDATION_RECEIPT.json")
    source = read("source-rehearsal/rehearsal-receipt.json")
    scheduler = read("scheduler-rehearsal/scheduler-rehearsal-receipt.json")
    linux = read("linux-rehearsal.json")
    opcache = read("opcache-http-rehearsal.json")
    gate = read("gate-transition-rehearsal.json")
    for receipt in (validation, source, scheduler, linux):
        require(receipt["status"] == "pass" and receipt["runner_sha256"] == runner_sha,
                "Receipt does not bind the final runner.")
    require(opcache["status"] == "pass" and gate["status"] == "pass", "Gate/OPcache rehearsal failed.")
    require(all(case["complete_original_source"] == runner.source_controls.frozen_envelope()["source"]
                for case in linux["scenarios"]), "Full original source restoration proof differs.")
    require(all(case["foreign_process_unchanged"] or (case["scenario"] in {"legacy-exit-before-fpm-read", "corrected-exit-before-fpm-read"}
                and case["owned_fixture_completed_normally"] and len(case["exit_race_events"]) == 1
                and case["exit_race_events"][0]["fixture_completion"]["normal_fixture_ipc_only"] is True)
                for case in linux["scenarios"]), "Observed foreign process lifecycle differs from the fixture plan.")
    exit_case = [case for case in linux["scenarios"] if case["scenario"] == "corrected-exit-before-fpm-read"]
    require(len(exit_case) == 1 and exit_case[0]["rollback_complete"] and exit_case[0]["final_state_status"] == "rolled_back"
        and len(exit_case[0]["confirmed_process_exits"]) == 1, "Complete fresh process-exit rollback proof is missing.")
    legacy_exit = [case for case in linux["scenarios"] if case["scenario"] == "legacy-exit-before-fpm-read"]
    require(len(legacy_exit) == 1 and legacy_exit[0]["final_state_status"] == "rollback_failed_site_gated"
        and not legacy_exit[0]["rollback_complete"], "Pre-correction failure control did not reproduce.")
    require(sha(linux_private / "PRIVATE_MANIFEST.json") == linux["private_manifest_sha256"], "Linux private manifest differs.")
    private = json.loads((linux_private / "PRIVATE_MANIFEST.json").read_text())
    for row in private["entries"]:
        path = linux_private / row["path"]
        require(sha(path) == row["sha256"] and path.stat().st_size == row["bytes"] and (path.stat().st_mode & 0o777) == row["mode"], "Private rehearsal evidence changed.")
    test_output = (EVIDENCE / "python-tests.stderr.txt").read_text()
    match = re.search(r"Ran (\d+) tests.*\n\nOK\s*$", test_output)
    require(match is not None, "Complete test suite did not pass.")
    require(sha(CLOSEOUT / "independent-acceptance.json") == "523ae6c3f6da33c04930929f2ba4194a4322090fb0f2e8ae9070c8d80f9935af", "Acceptance receipt changed.")
    local_shadow = Path("/tmp/buydtf-remember-v4-build-a/shadow")
    # Read-only identity recheck of the retained local dependency build.
    vendor = runner.source_controls.require_candidate_vendor(local_shadow / "vendor")
    autoload = runner.source_controls.require_application_autoload(local_shadow)
    require(sha(local_shadow / "composer.lock") == runner.EXPECTED_COMPOSER_LOCK_SHA256, "Retained local lock changed.")
    retained_dependencies = {"verification_scope": "retained local build only; no production access",
        "lock_sha256": sha(local_shadow / "composer.lock"), "vendor": vendor, "autoload": autoload,
        "production_bootstrap_cache_sha256_from_accepted_envelope": runner.EXPECTED_CACHE_MANIFEST_SHA256}
    write("retained-local-dependency-identities.json", retained_dependencies)
    write("UNCHANGED_APPLICATION_MEMBERS.json", {"status": "pass", "base_commit": BASE,
        "members": member_proof, "candidate_archive_sha256": sha(archive),
        "frozen_dependency_envelope_sha256": runner.source_controls.ENVELOPE_SHA256})
    report = {"artifact": "buy-dtf-process-permission-local-correction-review-v1", "status": "ready_for_independent_review",
        "branch": git("branch", "--show-current", text=True).strip(),
        "accepted_base_commit": BASE, "local_closeout_commit": "a993584bcfed29c651f6ae5ee7dcb337ec5bf1d6",
        "previous_local_correction_commit": "4ce447e4ac3712570d17ed334da03aec5adfe8a0",
        "remaining_blocker_correction": "Validated FPM rejection followed by fresh bound kernel absence proof; live, unreadable and reused PIDs remain rejected",
        "process_exit_race_proof": {"actor_uid": exit_case[0]["actor_uid"], "target_uid": exit_case[0]["target_uid"],
            "real_fpm_status": exit_case[0]["exit_race_events"][0]["fpm_status"],
            "fresh_kernel_proof": exit_case[0]["confirmed_process_exits"][0],
            "pre_correction_state": legacy_exit[0]["final_state_status"],
            "corrected_state": exit_case[0]["final_state_status"],
            "rollback_complete": exit_case[0]["rollback_complete"],
            "complete_original_source": exit_case[0]["complete_original_source"],
            "maintenance_active_after": exit_case[0]["maintenance_active"],
            "full_seven_second_waits": len(exit_case[0]["full_monotonic_wait_receipts"]),
            "state_sha256": exit_case[0]["state_sha256"], "raw_evidence_private": True},
        "runner_sha256": runner_sha, "controls": controls,
        "runtime_helper_sha256": runner.EXPECTED_HELPER_SHA256,
        "log_parser_sha256": runner.EXPECTED_LOG_GUARD_SHA256,
        "application_manifest_sha256": sha(EVIDENCE / "APPLICATION_MANIFEST.json"),
        "candidate_archive_sha256": sha(archive), "application_members_unchanged": len(member_proof),
        "accepted_original_source": runner.source_controls.frozen_envelope()["source"],
        "accepted_production_dependencies": {"php": "8.2.30", "laravel": "12.69.1",
            "lock": runner.EXPECTED_COMPOSER_LOCK_SHA256, "vendor": runner.EXPECTED_VENDOR_MANIFEST_SHA256,
            "cache": runner.EXPECTED_CACHE_MANIFEST_SHA256},
        "tests": {"complete_control_suite": int(match[1]), "linux_permission_full_rollback_scenarios": linux["scenario_count"],
            "source_cutover_rollback_recovery_scenarios": source["scenario_count"],
            "scheduler_monitor_scenarios": scheduler["scenario_count"],
            "gate_transition_monotonic_waits_verified": gate["shared_monotonic_revalidation_waits_verified"],
            "production_like_opcache_http": "pass", "php_8_2_30_lint_and_real_writer": "pass"},
        "recovery_closeout_sha256": sha(CLOSEOUT / "recovery-closeout.json"),
        "private_linux_manifest_sha256": linux["private_manifest_sha256"],
        "private_linux_entries_reverified": len(private["entries"]),
        "production_accessed": False, "pushed": False, "stageable": False, "deployable": False,
        "fresh_production_health_claimed": False, "new_action_tokens_issued": False,
        "existing_permissions_processes_and_services_changed": False,
        "transparency_deployment_remains_failed": True,
        "receiver_job_label_retention_enabled": False, "artwork_hosts": [],
        "limits": linux["limits"], "plan": "PROPOSED_PLAN.txt"}
    write("REVIEW_RECEIPT.json", report)
    files = set(path for path in EVIDENCE.rglob("*") if path.is_file() and path.name not in {"EVIDENCE_MANIFEST.json", "SHA256SUMS"})
    files.update(path for path in CLOSEOUT.rglob("*") if path.is_file())
    files.update(ROOT / "ops/deployment" / name for name in runner.CONTROL_FILES)
    for name in ("production_alpha_transparency_deploy.py", "production_alpha_transparency_runtime_probe.php", "laravel_log_guard.py",
            "test_production_alpha_process_scope.py", "test_production_alpha_transparency_runner.py", "test_production_alpha_nginx_inventory.py",
            "rehearse_production_alpha_process_permission.py", "rehearse_production_alpha_transparency.py",
            "refresh_production_alpha_process_manifest.py", "validate_production_alpha_process_permission.py", "build_production_alpha_process_evidence.py"):
        files.add(ROOT / "ops/deployment" / name)
    entries = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}
               for path in sorted(files)]
    write("EVIDENCE_MANIFEST.json", {"artifact": "buy-dtf-local-process-correction-evidence-manifest",
        "algorithm": "Sorted repository-relative paths; exact raw-byte SHA-256 and size; excludes this manifest and its checksum file.",
        "entries": entries, "entries_sha256": hashlib.sha256(runner.canonical_bytes(entries)).hexdigest(),
        "production_accessed": False, "raw_production_logs_headers_cookies_configuration": False})
    sums = entries + [{"path": (EVIDENCE / "EVIDENCE_MANIFEST.json").relative_to(ROOT).as_posix(),
                        "sha256": sha(EVIDENCE / "EVIDENCE_MANIFEST.json")}]
    (EVIDENCE / "SHA256SUMS").write_bytes("".join(f"{row['sha256']}  {row['path']}\n" for row in sorted(sums, key=lambda item: item["path"])).encode())
    print(json.dumps({"status": "pass", "tests": report["tests"], "runner_sha256": runner_sha,
        "evidence_manifest_sha256": sha(EVIDENCE / "EVIDENCE_MANIFEST.json"),
        "checksum_file_sha256": sha(EVIDENCE / "SHA256SUMS"), "entries": len(sums)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux-private-root", type=Path, required=True)
    run(parser.parse_args().linux_private_root)
