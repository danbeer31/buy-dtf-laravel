"""Local-only manifest refresh; retains the accepted application/dependency bytes."""
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import production_alpha_transparency_deploy as runner

root = Path(__file__).resolve().parents[2]
output = root / "ops/evidence/process-permission-rollback-20261005"
output.mkdir(parents=True, exist_ok=True)
old = root / "ops/evidence/production-alpha-transparency-source-only-v5-scheduler-20261005/APPLICATION_MANIFEST.json"
document = json.loads(old.read_text())
document["retired_runner_sha256s"] = sorted(runner.RETIRED_RUNNER_SHA256S)
document["scheduler_policy"] = runner.scheduler_controls.POLICY
document["scheduler_policy_sha256"] = runner.scheduler_controls.POLICY_SHA256
document["local_operations_correction"] = {"status": "review_only_non_stageable",
    "supersedes_runner_sha256": "d3c1a26bb1081bb47149eb2b34787d747e56a4db4ef0eb4668f62e3baf231a3d",
    "new_authorization_issued": False, "accepted_application_paths_unchanged": True,
    "process_scope_probe_sha256": runner.scheduler_controls.POLICY["process_scope_probe_sha256"]}
path = output / "APPLICATION_MANIFEST.json"
path.write_bytes(runner.canonical_bytes(document))
runner_path = root / "ops/deployment/production_alpha_transparency_deploy.py"
text = runner_path.read_text()
text = re.sub(r'EXPECTED_MANIFEST_SHA256 = "[0-9a-f]{64}"',
              'EXPECTED_MANIFEST_SHA256 = "' + hashlib.sha256(path.read_bytes()).hexdigest() + '"', text)
guard_hash = hashlib.sha256((root / "ops/deployment/production_alpha_scheduler_guard.py").read_bytes()).hexdigest()
text = re.sub(r"'production_alpha_scheduler_guard.py': '[0-9a-f]{64}'",
              "'production_alpha_scheduler_guard.py': '" + guard_hash + "'", text)
text = re.sub(r"'production_alpha_process_scope_probe.php': '[0-9a-f]{64}'",
              "'production_alpha_process_scope_probe.php': '" + runner.scheduler_controls.POLICY["process_scope_probe_sha256"] + "'", text)
runner_path.write_bytes(text.encode())
print(json.dumps({"manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "guard_sha256": guard_hash}))
