"""Freeze all expected V6 bindings locally; no execution or production access."""
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
bindings = runner.expected_authorization_bindings()
expected = {action: prefix + "-BUYDTF-ALPHA-V6-" + runner.TARGET_COMMIT[:16]
    for action, prefix in {"stage": "STAGE", "deploy": "DEPLOY", "recover": "RECOVER"}.items()}
if bindings != expected or len(set(bindings.values())) != 3:
    raise RuntimeError("All three final V6 bindings must be frozen together.")
group_sha256 = runner.sha256_bytes(runner.canonical_bytes(bindings))
binding_record = EVIDENCE / "AUTHORIZATION_BINDINGS.json"
binding_record.write_bytes(runner.canonical_bytes({
    "artifact": "buy-dtf-v6-expected-authorization-bindings-v1",
    "accepted_activation_commit": "2b94d6c5e70459351a2f7b530552a73b0a5c3ea2",
    "generation": activation.GENERATION, "application_target_commit": runner.TARGET_COMMIT,
    "expected_values": bindings, "binding_group_sha256": group_sha256,
    "frozen_together": True, "runner_must_remain_identical_between_staging_and_cutover": True,
    "production_php_fpm_required": "8.2.30", "production_fpm_verification_performed": False,
    "separate_execution_authorizations_required": ["stage", "deploy", "recover"],
    "cutover_requires_new_release_receipt": True, "recovery_requires_state_bound_authorization": True,
    "execution_authorization_granted": False, "production_accessed": False}))
manifest = json.loads(accepted.read_text())
manifest["activation_package"] = {"generation": activation.GENERATION,
    "accepted_correction_commit": activation.ACCEPTED_CORRECTION_COMMIT,
    "accepted_activation_commit": "2b94d6c5e70459351a2f7b530552a73b0a5c3ea2",
    "accepted_manifest_sha256": sha(accepted), "source_members_unchanged": True,
    "expected_authorization_bindings": bindings, "binding_group_sha256": group_sha256,
    "authorization_bindings_receipt_sha256": sha(binding_record),
    "execution_authorization_granted": False,
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
    "binding_group_sha256": group_sha256, "expected_bindings": bindings,
    "execution_authorization": "not_granted"}))
