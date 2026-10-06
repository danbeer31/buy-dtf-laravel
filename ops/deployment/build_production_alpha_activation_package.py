"""Build deterministic local V6 review inputs; no tokens or production access."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops/deployment"))
import production_alpha_transparency_deploy as runner

BASE = "2c14d6e401c9d24a7153c12f6ee4b74bd96f8582"
EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-activation-v6-20261005"
ACCEPTED = ROOT / "ops/evidence/process-permission-rollback-20261005"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def git(*args, text=False):
    windows_root = subprocess.check_output(["wslpath", "-w", str(ROOT)], text=True).strip()
    return subprocess.check_output(["/mnt/c/Program Files/Git/cmd/git.exe", "-C", windows_root, *args], text=text)


def write(name, value):
    (EVIDENCE / name).write_bytes(runner.canonical_bytes(value))


def run(private_linux_root: Path):
    controls = {name: sha(ROOT / "ops/deployment" / name) for name in runner.CONTROL_FILES}
    require(controls == runner.CONTROL_FILES, "Current control bytes differ from freeze.")
    accepted_controls = json.loads((ACCEPTED / "REVIEW_RECEIPT.json").read_text())["controls"]
    require(all(controls[name] == digest for name, digest in accepted_controls.items()), "Accepted control bytes changed.")
    old_rows = [line.split("  ", 1) for line in (ACCEPTED / "SHA256SUMS").read_text().splitlines()]
    for digest, name in old_rows:
        require(hashlib.sha256(git("show", BASE + ":" + name)).hexdigest() == digest, "Accepted evidence Git bytes changed.")
        if name.startswith("ops/evidence/"):
            require(sha(ROOT / name) == digest, "Retained evidence worktree bytes changed.")
    accepted_manifest = json.loads((ACCEPTED / "APPLICATION_MANIFEST.json").read_text())
    manifest = json.loads((EVIDENCE / "APPLICATION_MANIFEST.json").read_text())
    require(manifest["paths"] == accepted_manifest["paths"], "Application inventory changed.")
    for row in manifest["paths"]:
        data = (ROOT / row["path"]).read_bytes()
        require(data == git("show", BASE + ":" + row["path"])
            and sha(ROOT / row["path"]) == row["target_sha256"] and len(data) == row["target_bytes"], "Application bytes changed.")
    require((runner.STAGE_APPROVAL_TOKEN, runner.DEPLOY_APPROVAL_TOKEN, runner.RECOVERY_APPROVAL_TOKEN) == (None, None, None), "Execution tokens must remain withheld.")
    require(not runner.LOCAL_CORRECTION_REVIEW_ONLY, "Activation must use explicit withheld authorization bindings.")
    archive = ROOT / "storage/app/private/operations/production-alpha-transparency-source-only-package-20261002/production-alpha-transparency-b02fce32.tar"
    require(sha(archive) == runner.EXPECTED_ARCHIVE_SHA256, "Unchanged source archive differs.")
    sources = [archive, EVIDENCE / "APPLICATION_MANIFEST.json", Path(runner.__file__),
        ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php", ROOT / "ops/deployment/laravel_log_guard.py",
        *[ROOT / "ops/deployment" / name for name in runner.CONTROL_FILES]]
    require(len(sources) == 15 and len({p.name for p in sources}) == 15, "Frozen input set is not fifteen unique members.")
    entries = [{"name": p.name, "source_path": p.relative_to(ROOT).as_posix(), "sha256": sha(p),
        "bytes": p.stat().st_size, "uid": 1000, "gid": 1000, "mode": "0600"} for p in sorted(sources, key=lambda p: p.name)]
    write("INPUT_MANIFEST.json", {"generation": runner.activation_controls.GENERATION, "input_count": 15,
        "inputs": entries, "execution_approval_tokens": {"stage": None, "deploy": None, "recover": None}})
    bundle_directory = ROOT / "storage/app/private/operations/production-alpha-activation-v6-local-package-20261005"
    bundle_directory.mkdir(parents=True, exist_ok=True)
    bundle = bundle_directory / "production-alpha-transparency-v6-inputs.tar"
    def render_bundle():
        result = io.BytesIO()
        with tarfile.open(fileobj=result, mode="w", format=tarfile.USTAR_FORMAT) as handle:
            for path in sorted(sources, key=lambda p: p.name):
                data = path.read_bytes()
                info = tarfile.TarInfo(path.name)
                info.size, info.mode, info.uid, info.gid, info.mtime = len(data), 0o600, 1000, 1000, 0
                handle.addfile(info, io.BytesIO(data))
        return result.getvalue()
    first, second = render_bundle(), render_bundle()
    require(first == second, "Local input bundle is not deterministic.")
    bundle.write_bytes(first)
    with tarfile.open(bundle) as handle:
        members = handle.getmembers()
        require(len(members) == 15 and all(m.isfile() and m.uid == 1000 and m.gid == 1000 and m.mode == 0o600 and m.mtime == 0 for m in members), "Bundle metadata differs.")
        require(all(hashlib.sha256(handle.extractfile(m).read()).hexdigest() == next(e["sha256"] for e in entries if e["name"] == m.name) for m in members), "Bundle input hashes differ.")
    receipts = {key: json.loads((EVIDENCE / name).read_text()) for key, name in {
        "validation": "VALIDATION_RECEIPT.json", "source": "source-rehearsal/rehearsal-receipt.json",
        "scheduler": "scheduler-rehearsal/scheduler-rehearsal-receipt.json", "linux": "linux-rehearsal.json",
        "fresh_v6": "fresh-v6-receipt-validation.json"}.items()}
    runner_sha = sha(Path(runner.__file__))
    require(all(value["status"] == "pass" and value["runner_sha256"] == runner_sha for value in receipts.values()), "Validation does not bind this runner.")
    linux = receipts["linux"]
    require(all(case["activation_php83_rejection"]["status"] == "rejected_before_mutation" and case["activation_php83_rejection"]["production_requirement_relaxed"] is False for case in linux["scenarios"]), "Real local PHP 8.3.6 rejection proof missing.")
    private_manifest = private_linux_root / "PRIVATE_MANIFEST.json"
    require(sha(private_manifest) == linux["private_manifest_sha256"], "Private Linux manifest differs.")
    private_entries = json.loads(private_manifest.read_text())["entries"]
    for row in private_entries:
        path = private_linux_root / row["path"]
        require(sha(path) == row["sha256"] and path.stat().st_size == row["bytes"] and path.stat().st_mode & 0o777 == row["mode"], "Private Linux evidence differs.")
    output = (EVIDENCE / "python-tests.stderr.txt").read_text()
    match = re.search(r"Ran (\d+) tests.*\n\nOK\s*$", output)
    require(match is not None, "Complete controls suite failed.")
    gate = json.loads((EVIDENCE / "gate-transition-rehearsal.json").read_text())
    require(gate["status"] == "pass", "Gate rehearsals failed.")
    fresh_v6 = receipts["fresh_v6"]
    require(fresh_v6["fresh_receipts"] == 23 and fresh_v6["negative_cases"] == 22
        and fresh_v6["stage_release_mocked"] is False and fresh_v6["validate_release_receipt_mocked"] is False
        and fresh_v6["path_metadata_mocked"] is False, "Fresh V6 receipt round-trip coverage is incomplete.")
    shadow = Path("/tmp/buydtf-remember-v4-build-a/shadow")
    write("RETAINED_LOCAL_DEPENDENCIES.json", {"scope": "read-only retained local build; no production access",
        "vendor": runner.source_controls.require_candidate_vendor(shadow / "vendor"),
        "application_autoload": runner.source_controls.require_application_autoload(shadow),
        "lock_sha256": sha(shadow / "composer.lock"), "expected_cache_sha256": runner.EXPECTED_CACHE_MANIFEST_SHA256})
    require(sha(shadow / "composer.lock") == runner.EXPECTED_COMPOSER_LOCK_SHA256, "Local retained lock differs.")
    report = {"artifact": "buy-dtf-local-activation-v6-review-package", "status": "ready_for_independent_review_tokens_withheld",
        "branch": git("branch", "--show-current", text=True).strip(), "accepted_correction_commit": BASE,
        "runner_sha256": runner_sha, "controls": controls, "accepted_controls_unchanged": accepted_controls,
        "accepted_evidence_checksum_entries_verified": len(old_rows), "application_members_unchanged": len(manifest["paths"]),
        "application_manifest_sha256": sha(EVIDENCE / "APPLICATION_MANIFEST.json"), "source_archive_sha256": sha(archive),
        "input_manifest_sha256": sha(EVIDENCE / "INPUT_MANIFEST.json"), "input_count": 15,
        "local_private_input_bundle": {"path": str(bundle), "sha256": sha(bundle), "bytes": bundle.stat().st_size,
            "two_serializations_byte_identical": True, "metadata": "1000:1000/0600; mtime 0; regular files only"},
        "tests": {"control_suite": int(match[1]), "source_scenarios": receipts["source"]["scenario_count"],
            "scheduler_scenarios": receipts["scheduler"]["scenario_count"], "linux_uid_1000_33_scenarios": linux["scenario_count"],
            "fresh_v6_staged_receipts_real_validator": fresh_v6["fresh_receipts"], "real_receipt_negative_cases": fresh_v6["negative_cases"],
            "real_php83_activation_rejections": len(linux["scenarios"]),
            "gate_monotonic_waits": gate["shared_monotonic_revalidation_waits_verified"], "native_php_8_2_30_lint_writer": "pass"},
        "private_linux_manifest_sha256": linux["private_manifest_sha256"], "private_linux_entries_verified": len(private_entries),
        "production_php_8_2_30_fpm_prerequisite": {"required": True, "status": "pending_future_authorized_production_verification",
            "witness_sha256": runner.activation_controls.WITNESS_SHA256, "accepted_scope_probe_sha256": runner.activation_controls.ACCEPTED_PROCESS_PROBE_SHA256},
        "execution_approval_tokens": {"stage": None, "deploy": None, "recover": None},
        "production_accessed": False, "pushed": False, "stageable": False, "deployable": False,
        "application_dependencies_configuration_artwork_changed": False, "receiver_job_label_retention_enabled": False,
        "artwork_hosts": [], "retained_evidence_preserved": True, "new_authorizations_issued": False,
        "plan": "ACTIVATION_PLAN.txt", "limits": linux["limits"]}
    write("REVIEW_RECEIPT.json", report)
    files = {p for p in EVIDENCE.rglob("*") if p.is_file() and p.name not in {"EVIDENCE_MANIFEST.json", "SHA256SUMS"}}
    files.update(ROOT / "ops/deployment" / name for name in runner.CONTROL_FILES)
    files.add(Path(runner.__file__))
    for name in ("production_alpha_transparency_runtime_probe.php", "laravel_log_guard.py", "test_production_alpha_activation.py",
        "freeze_production_alpha_activation.py", "build_production_alpha_activation_package.py", "validate_production_alpha_activation.py",
        "rehearse_production_alpha_process_permission.py", "rehearse_production_alpha_transparency.py", "test_production_alpha_process_scope.py",
        "test_production_alpha_transparency_runner.py", "test_production_alpha_nginx_inventory.py"):
        files.add(ROOT / "ops/deployment" / name)
    hashes = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(files)]
    write("EVIDENCE_MANIFEST.json", {"artifact": "buy-dtf-activation-v6-evidence-manifest", "entries": hashes,
        "algorithm": "Sorted repo-relative path, raw SHA-256 and size; excludes manifest and checksum file themselves",
        "production_accessed": False, "raw_production_data_in_git": False})
    sums = hashes + [{"path": (EVIDENCE / "EVIDENCE_MANIFEST.json").relative_to(ROOT).as_posix(), "sha256": sha(EVIDENCE / "EVIDENCE_MANIFEST.json")}]
    (EVIDENCE / "SHA256SUMS").write_bytes("".join(f"{x['sha256']}  {x['path']}\n" for x in sorted(sums, key=lambda x: x["path"])).encode())
    print(json.dumps({"status": "pass", "runner_sha256": runner_sha, "tests": report["tests"],
        "input_bundle_sha256": sha(bundle), "evidence_manifest_sha256": sha(EVIDENCE / "EVIDENCE_MANIFEST.json"),
        "checksum_file_sha256": sha(EVIDENCE / "SHA256SUMS"), "checksum_entries": len(sums), "execution_tokens": "withheld"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-linux-root", type=Path, required=True)
    run(parser.parse_args().private_linux_root)
