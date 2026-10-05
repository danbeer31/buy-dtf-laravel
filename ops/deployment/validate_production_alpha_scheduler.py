#!/usr/bin/env python3
"""Record local operations validation without network/production/task execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-source-only-v4-scheduler-20261004"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def command(name, argv, cwd=ROOT):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=600)
    stdout = EVIDENCE / (name + ".stdout.txt")
    stderr = EVIDENCE / (name + ".stderr.txt")
    stdout.write_text(result.stdout, encoding="utf-8", newline="\n")
    stderr.write_text(result.stderr, encoding="utf-8", newline="\n")
    receipt = {"status": "pass" if result.returncode == 0 else "fail", "exit_code": result.returncode,
        "argv": argv, "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
        "scope": "local disposable validation; no production access"}
    write(EVIDENCE / (name + ".receipt.json"), receipt)
    print(f"{name}: {receipt['status']}", flush=True)
    if result.returncode: raise RuntimeError(f"Local {name} failed; see private-free validation output in {EVIDENCE}")
    return receipt


def run():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    receipts = {}
    receipts["source-rehearsal"] = command("source-rehearsal", [sys.executable, "ops/deployment/rehearse_production_alpha_transparency.py", "--portable-output", str(EVIDENCE / "source-rehearsal")])
    receipts["scheduler-rehearsal"] = command("scheduler-rehearsal", [sys.executable, "ops/deployment/rehearse_production_alpha_scheduler.py", "--output", str(EVIDENCE / "scheduler-rehearsal")])
    modules = ["test_production_alpha_scheduler", "test_production_alpha_transparency_runner", "test_production_alpha_gate_controls", "test_production_alpha_nginx_inventory", "test_laravel_log_guard", "test_laravel_dependency_gate"]
    receipts["python-tests"] = command("python-tests", [sys.executable, "-m", "unittest", "-v", *modules], ROOT / "ops/deployment")
    with tempfile.TemporaryDirectory(prefix="buydtf-source-scheduler-gate-") as temporary:
        receipt_path = Path(temporary) / "gate-rehearsal.json"
        receipts["gate-rehearsal"] = command("gate-rehearsal", [sys.executable, "ops/deployment/rehearse_laravel_dependency_gate.py", "--parent", "/tmp", "--output", str(receipt_path)])
        write(EVIDENCE / "gate-transition-rehearsal.json", json.loads(receipt_path.read_text()))
    # The accepted Windows 8.2.30 binary is used for the changed operations PHP.
    native_php = Path("/mnt/c/tools/php8230/php.exe")
    if sha(native_php) != "132075655257b1558c5d896dce117081bc068c90c50dfc5fd9c24c93dbc4312a":
        raise RuntimeError("PHP 8.2.30 binary identity differs")
    lint = []
    for relative in ("ops/deployment/production_alpha_transparency_runtime_probe.php", "ops/deployment/production_alpha_scheduler_probe.php", "ops/deployment/test_production_alpha_scheduler_probe.php"):
        windows_path = "C:\\Users\\danie\\projects\\bdtf-alpha-sched-v4\\" + relative.replace("/", "\\")
        result = subprocess.run([str(native_php), "-l", windows_path], capture_output=True, text=True, timeout=30)
        if result.returncode: raise RuntimeError("PHP 8.2.30 lint failed")
        lint.append({"path": relative, "sha256": sha(ROOT / relative), "exit_code": result.returncode,
                     "stdout": result.stdout.strip(), "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest()})
    write(EVIDENCE / "php8230-operations-lint.json", {"status": "pass", "php_version": "8.2.30", "binary_sha256": sha(native_php), "files": lint})
    receipts["php8230-lint"] = {"status": "pass", "files": len(lint)}
    write(EVIDENCE / "VALIDATION_RECEIPT.json", {"status": "pass", "scope": "local operations-only correction",
        "runner_sha256": sha(ROOT / "ops/deployment/production_alpha_transparency_deploy.py"),
        "scheduler_guard_sha256": sha(ROOT / "ops/deployment/production_alpha_scheduler_guard.py"),
        "scheduler_probe_sha256": sha(ROOT / "ops/deployment/production_alpha_scheduler_probe.php"),
        "runtime_probe_sha256": sha(ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php"),
        "laravel_log_guard_sha256": sha(ROOT / "ops/deployment/laravel_log_guard.py"),
        "receipts": receipts, "production_accessed": False, "accounting_tasks_executed": False,
        "cron_disabled": False, "mutexes_cleared": False, "application_or_dependency_changes": False})
    print("Local operations validation complete", flush=True)


if __name__ == "__main__":
    run()
