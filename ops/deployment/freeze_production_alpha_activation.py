"""Freeze local V6 controls without authorizations, network or production access."""
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-activation-v6-20261005"
EVIDENCE.mkdir(parents=True, exist_ok=True)
DEPLOYMENT = ROOT / "ops/deployment"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
helper = DEPLOYMENT / "production_alpha_activation_controls.py"
helper.write_bytes(re.sub(r'WITNESS_SHA256 = "[^"]+"',
    'WITNESS_SHA256 = "' + sha(DEPLOYMENT / "production_alpha_fpm_activation_probe.php") + '"', helper.read_text()).encode())
sys.path.insert(0, str(DEPLOYMENT))
import production_alpha_activation_controls as activation
import production_alpha_transparency_deploy as runner

accepted = ROOT / "ops/evidence/process-permission-rollback-20261005/APPLICATION_MANIFEST.json"
manifest = json.loads(accepted.read_text())
manifest["activation_package"] = {"generation": activation.GENERATION,
    "accepted_correction_commit": activation.ACCEPTED_CORRECTION_COMMIT,
    "accepted_manifest_sha256": sha(accepted), "source_members_unchanged": True,
    "execution_approval_tokens": {"stage": None, "deploy": None, "recover": None},
    "production_fpm_8_2_30_verification_required": True,
    "production_fpm_verification_performed_during_preparation": False,
    "retired_release_reuse_allowed": False}
path = EVIDENCE / "APPLICATION_MANIFEST.json"
path.write_bytes(runner.canonical_bytes(manifest))
controls = {**runner.CONTROL_FILES,
    "production_alpha_activation_controls.py": sha(helper),
    "production_alpha_fpm_activation_probe.php": sha(DEPLOYMENT / "production_alpha_fpm_activation_probe.php")}
runner_path = Path(runner.__file__)
code = runner_path.read_text()
code = re.sub(r'EXPECTED_MANIFEST_SHA256 = "[0-9a-f]{64}"', 'EXPECTED_MANIFEST_SHA256 = "' + sha(path) + '"', code)
code = re.sub(r"(?m)^CONTROL_FILES = .*", "CONTROL_FILES = " + repr(controls), code)
runner_path.write_bytes(code.encode())
print(json.dumps({"manifest_sha256": sha(path), "runner_sha256": sha(runner_path),
    "activation_control_sha256": sha(helper), "witness_sha256": controls["production_alpha_fpm_activation_probe.php"],
    "execution_tokens": "withheld"}))
