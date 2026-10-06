"""V6 has no executable authorization and needs real production FPM evidence."""
import copy
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import production_alpha_activation_controls as activation
import production_alpha_transparency_deploy as runner

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "ops/evidence/production-alpha-transparency-activation-v6-20261005"


def witness(nonce="a" * 48):
    return {"artifact": "buy-dtf-process-scope-v1", "status": "pass", "nonce": nonce,
        "sapi": "fpm-fcgi", "php_version": "8.2.30", "observer_uid": 33, "observer_gid": 33,
        "identity": {"pid": 424242, "uid": 33, "start_ticks": 10000, "argv_sha256": "b" * 64},
        "working_directory": "/", "executable": "/usr/sbin/php-fpm8.2",
        "read_only": True, "environments_read": False, "process_or_permission_actions": False}


def proof():
    return {"artifact": "buy-dtf-production-fpm-scope-prerequisite-v1", "status": "pass",
        "generation": activation.GENERATION, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "monotonic_ns": 100000, "php_version": "8.2.30", "sapi": "fpm-fcgi", "actor_uid": 1000,
        "observer_uid": 33, "observer_gid": 33, "identity": witness()["identity"],
        "socket": {"path": str(activation.EXPECTED_SOCKET), "device": 1, "inode": 2, "uid": 33, "gid": 33, "mode": 0o660},
        "witness_sha256": activation.WITNESS_SHA256, "accepted_scope_probe_sha256": activation.ACCEPTED_PROCESS_PROBE_SHA256,
        "accepted_scheduler_sha256": activation.ACCEPTED_SCHEDULER_SHA256,
        **{k: "c" * 64 for k in ("witness_response_sha256", "scope_response_sha256", "working_directory_sha256", "executable_sha256", "nonce_sha256")},
        "read_only": True, "environments_read": False, "process_or_permission_actions": False}


class ActivationPrerequisiteTests(unittest.TestCase):
    def test_final_bindings_are_exact_distinct_and_action_specific(self):
        expected = {action: prefix + "-BUYDTF-ALPHA-V6-b02fce3213fc6328"
            for action, prefix in {"stage": "STAGE", "deploy": "DEPLOY", "recover": "RECOVER"}.items()}
        self.assertEqual(runner.expected_authorization_bindings(), expected)
        self.assertEqual(len(set(expected.values())), 3)
        for action, correct in expected.items():
            runner.require_action_approval(action, correct)
            for wrong in (None, "", "DEPLOY-BUYDTF-ALPHA-V5-b02fce3213fc6328", "DEPLOY-BUYDTF-ALPHA-V6-UNISSUED", *[value for value in expected.values() if value != correct]):
                with self.subTest(action=action, wrong=wrong), self.assertRaises(runner.DeploymentError):
                    runner.require_action_approval(action, wrong)

    def test_binding_group_matches_frozen_manifest_and_receipt(self):
        bindings = runner.expected_authorization_bindings()
        document = json.loads((EVIDENCE / "APPLICATION_MANIFEST.json").read_text())
        receipt = json.loads((EVIDENCE / "AUTHORIZATION_BINDINGS.json").read_text())
        digest = runner.sha256_bytes(runner.canonical_bytes(bindings))
        self.assertEqual(document["activation_package"]["expected_authorization_bindings"], bindings)
        self.assertEqual(document["activation_package"]["binding_group_sha256"], digest)
        self.assertEqual(receipt["expected_values"], bindings)
        self.assertEqual(receipt["binding_group_sha256"], digest)
        self.assertEqual(document["activation_package"]["authorization_bindings_receipt_sha256"],
            runner.sha256_file(EVIDENCE / "AUTHORIZATION_BINDINGS.json"))
        self.assertFalse(receipt["execution_authorization_granted"])
        self.assertTrue(receipt["runner_must_remain_identical_between_staging_and_cutover"])

    @mock.patch.object(runner, "STAGE_APPROVAL_TOKEN", None)
    @mock.patch.object(runner, "DEPLOY_APPROVAL_TOKEN", None)
    @mock.patch.object(runner, "RECOVERY_APPROVAL_TOKEN", None)
    def test_withheld_values_and_none_can_never_authorize_execution(self):
        for action in ("stage", "deploy", "recover"):
            for value in (None, "", "DEPLOY-BUYDTF-ALPHA-V5-b02fce3213fc6328", "DEPLOY-BUYDTF-ALPHA-V6-UNISSUED"):
                with self.subTest(action=action, value=value), self.assertRaisesRegex(runner.DeploymentError, "withheld"):
                    runner.require_action_approval(action, value)

    def test_retired_or_wrong_action_authorization_cannot_be_enabled(self):
        with mock.patch.object(runner, "STAGE_APPROVAL_TOKEN", "STAGE-BUYDTF-ALPHA-V5-b02fce3213fc6328"):
            with self.assertRaisesRegex(runner.DeploymentError, "withheld"):
                runner.require_action_approval("stage", runner.STAGE_APPROVAL_TOKEN)
        with mock.patch.object(runner, "STAGE_APPROVAL_TOKEN", "STAGE-BUYDTF-ALPHA-V6-LOCAL-FIXTURE"):
            runner.require_action_approval("stage", runner.STAGE_APPROVAL_TOKEN)
            with self.assertRaises(runner.DeploymentError):
                runner.require_action_approval("stage", "DEPLOY-BUYDTF-ALPHA-V6-LOCAL-FIXTURE")

    def test_exact_fpm_version_sapi_nonce_owner_and_identity_are_required(self):
        self.assertEqual(activation.validate_witness(witness(), "a" * 48), witness()["identity"])
        changes = [("php_version", "8.3.6"), ("sapi", "cli"), ("nonce", "0" * 48),
            ("observer_uid", 1000), ("observer_gid", 1000), ("read_only", False),
            ("environments_read", True), ("identity", {}), ("identity", {**witness()["identity"], "pid": True})]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(activation.ActivationError):
                activation.validate_witness({**witness(), key: value}, "a" * 48)

    def test_complete_staged_proof_rejects_missing_local_wrong_version_and_drift(self):
        value = proof()
        self.assertEqual(activation.validate_proof(value), value)
        for key, value in [("php_version", "8.3.6"), ("generation", "v5"), ("witness_sha256", "0" * 64),
                ("accepted_scheduler_sha256", "0" * 64), ("monotonic_ns", True), ("checked_at_utc", "2026-10-05T00:00:00"),
                ("nonce_sha256", "invalid"), ("socket", {}), ("identity", {})]:
            with self.subTest(key=key), self.assertRaises(activation.ActivationError):
                activation.validate_proof({**proof(), key: value})
        for value in (None, {}, {**proof(), "local_evidence": True}):
            with self.assertRaises(activation.ActivationError):
                activation.validate_proof(value)

    def transport(self, change=lambda x: x, response=None, scope_failure=None):
        temporary = []
        real_mkdtemp = tempfile.mkdtemp
        def new_directory(*args, **kwargs):
            directory = real_mkdtemp(*args, **kwargs)
            temporary.append(Path(directory))
            return directory
        def run(argv, **kwargs):
            self.assertEqual(argv, ["/usr/bin/cgi-fcgi", "-bind", "-connect", "/run/php/php8.2-fpm.sock"])
            self.assertEqual(kwargs["timeout"], 5)
            self.assertFalse(set(kwargs["env"]) & {"PATH", "APP_KEY", "HOME", "LD_PRELOAD", "PHP_INI_SCAN_DIR"})
            value = change(witness(kwargs["env"]["BUYDTF_FPM_ACTIVATION_NONCE"]))
            return subprocess.CompletedProcess(argv, 0, response if response is not None else b"Content-Type: application/json\r\n\r\n" + json.dumps(value).encode(), b"")
        with mock.patch.object(activation.os, "geteuid", return_value=1000), mock.patch.object(activation, "require_control", return_value=b"<?php /* test only */"), mock.patch.object(activation, "socket_identity", return_value=proof()["socket"]), mock.patch.object(activation.tempfile, "mkdtemp", side_effect=new_directory), mock.patch.object(activation.scheduler, "_process_identity", return_value=witness()["identity"], side_effect=scope_failure), mock.patch.object(activation.scheduler.FpmProcessScopeReader, "_verify_execution_copy"), mock.patch.object(activation.subprocess, "run", side_effect=run) as transport:
            try:
                result = activation.verify_production_fpm_scope()
                self.assertEqual(transport.call_count, 1)
                return result
            finally:
                self.assertTrue(temporary and all(not p.exists() for p in temporary))

    def test_same_request_fpm_proof_has_exact_version_and_bound_kernel_identity(self):
        result = self.transport()
        self.assertEqual(activation.validate_proof(result)["php_version"], "8.2.30")

    def test_83_cli_or_stale_witness_is_not_accepted(self):
        for change in (("php_version", "8.3.6"), ("sapi", "cli"), ("nonce", "0" * 48)):
            with self.subTest(change=change), self.assertRaises(activation.ActivationError):
                self.transport(lambda value: {**value, change[0]: change[1]})

    def test_rejected_malformed_duplicate_and_unparsed_responses_are_fatal(self):
        for raw in (b"Status: 503 Service Unavailable\n\n{}", b"not CGI", b"Content-Type: application/json\n\n\xff",
                b'Content-Type: application/json\n\n{"status":"pass","status":"pass"}'):
            with self.subTest(raw=raw), self.assertRaises(activation.ActivationError):
                self.transport(response=raw)

    def test_accepted_probe_unavailable_or_target_gone_is_fatal_before_mutation(self):
        for error in (activation.scheduler.SchedulerError("Unavailable"), activation.scheduler.ProcessScopeProbeRejected("a" * 64)):
            with self.subTest(error=type(error).__name__), self.assertRaises(activation.ActivationError):
                self.transport(scope_failure=error)

    def test_checkpoint_is_private_and_binds_current_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = {"source_install_started": False, "release_receipt_sha256": "d" * 64}
            with mock.patch.object(activation, "verify_production_fpm_scope", return_value=proof()):
                item = runner.activation_fpm_checkpoint(state, path, phase="before-static-gate")
            receipt = json.loads(Path(item["path"]).read_text())
            self.assertEqual(receipt["release_receipt_sha256"], "d" * 64)
            self.assertEqual(Path(item["path"]).stat().st_mode & 0o777, 0o600)
            self.assertEqual(item["sha256"], hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest())
            self.assertEqual(json.loads(path.read_text())["activation_fpm_checkpoints"], [item])

    def test_post_mutation_cannot_establish_new_prerequisite_or_block_offline_rollback(self):
        with mock.patch.object(activation, "verify_production_fpm_scope") as probe:
            with self.assertRaisesRegex(runner.DeploymentError, "after source mutation"):
                runner.activation_fpm_checkpoint({"source_install_started": True}, Path("unused"), phase="late")
            probe.assert_not_called()
        import inspect
        self.assertNotIn("activation_fpm_verification", inspect.getsource(runner.rollback_operation))

    @unittest.skipUnless(os.geteuid() == 0, "isolated root-owned Phase 0 inventory")
    def test_real_phase0_and_stage_fail_before_release_creation_without_exact_fpm(self):
        from test_production_alpha_nginx_inventory import NginxInventoryFixture, ApprovedNginxInventoryTest
        original = runner.activation_fpm_verification
        with tempfile.TemporaryDirectory() as directory:
            fixture = NginxInventoryFixture(Path(directory))
            with fixture.phase0_environment(), mock.patch.object(runner, "activation_fpm_verification", original), mock.patch.object(activation, "verify_production_fpm_scope", side_effect=activation.ActivationError("Exact PHP 8.2.30 required")):
                inputs = ApprovedNginxInventoryTest().inputs()
                for action in (lambda: runner.preflight_guard(inputs["helper"], []),
                    lambda: runner.production_preflight(helper=inputs["helper"], manifest_rows=[], evidence_directory=Path(directory), prefix="phase0"),
                    lambda: runner.stage_release(**inputs)):
                    with self.assertRaisesRegex(runner.DeploymentError, "8.2.30"):
                        action()
                    self.assertFalse(fixture.release_root.exists())


def staging_receipt_actor(action, root):
    """Generate/validate disposable receipts as actual UID/GID 1000.

    External production observations are explicit local doubles. Staging,
    extraction, lint, proof writing, metadata and receipt validation are real.
    No production paths, socket, database or network are accessed.
    """
    if os.geteuid() != 1000 or os.getegid() != 1000 or action not in {"stage", "validate"}:
        raise RuntimeError("A disposable UID/GID 1000 receipt actor is required.")
    root = root.resolve(strict=True)
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith("buydtf-v6-receipt-test-"):
        raise RuntimeError("Receipt actor is outside its disposable fixture root.")
    os.umask(0o077)
    release_root = root / "v6-releases"
    test_record = root / "stage-test.json"
    if action == "stage":
        import rehearse_production_alpha_transparency as rehearsal
        app = root / "application"
        app.mkdir(mode=0o755)
        front = app / "public/index.php"
        front.parent.mkdir(mode=0o755)
        front.write_bytes((ROOT / "public/index.php").read_bytes())
        front.chmod(0o644)
        manifest = EVIDENCE / "APPLICATION_MANIFEST.json"
        rows = runner.parse_manifest(manifest)
        originals, _ = rehearsal.resolve_baseline_sources(
            [Path("/tmp/buydtf-remember-v4-build-a/shadow"), *rehearsal.DEFAULT_BASELINE_ROOTS], rows)
        for row in rows:
            if row["action"] == "M":
                destination = app / row["path"]
                destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                destination.write_bytes(originals[row["path"]].read_bytes())
                destination.chmod(0o664)
        runtime = rehearsal.runtime_snapshot()
        controls = {"frozen_envelope_sha256": runner.source_controls.ENVELOPE_SHA256,
            "fpm_opcache": runner.source_controls.frozen_envelope()["fpm_opcache"]}
        with ExitStack() as stack:
            for name, value in {"APP_ROOT": app, "FRONT_CONTROLLER": front,
                "RELEASE_ROOT": release_root, "EXPECTED_APP_DEVICE": app.stat().st_dev,
                "LARAVEL_MAINTENANCE_FILE": app / "storage/framework/down",
                "DEPENDENCY_LOCK": app / "storage/framework/dependency.lock",
                "DEPLOYMENT_LOCK": app / "storage/framework/deployment.lock",
                "FPM_SOCKET": mock.Mock(is_socket=mock.Mock(return_value=True)),
                "STAGE_APPROVAL_TOKEN": "STAGE-BUYDTF-ALPHA-V6-LOCAL-FIXTURE"}.items():
                stack.enter_context(mock.patch.object(runner, name, value))
            stack.enter_context(mock.patch.object(runner.sys, "version_info", (3, 10, 12)))
            for name, value in {"environment_identity": controls,
                "full_source_identity": runner.source_controls.frozen_envelope()["source"],
                "dependency_identity": {"composer_lock_sha256": runner.EXPECTED_COMPOSER_LOCK_SHA256},
                "scoped_processes": [], "runtime_probe_memory": runtime,
                "runtime_probe": (runtime, {"scope": "isolated schema/ledger fixture"}),
                "health_snapshot": {"scope": "isolated health fixture"},
                "active_fpm_connections": []}.items():
                stack.enter_context(mock.patch.object(runner, name, return_value=value))
            stack.enter_context(mock.patch.object(activation, "verify_production_fpm_scope", side_effect=proof))
            path = runner.stage_release(
                archive=ROOT / "storage/app/private/operations/production-alpha-transparency-source-only-package-20261002/production-alpha-transparency-b02fce32.tar",
                manifest=manifest, helper=ROOT / "ops/deployment/production_alpha_transparency_runtime_probe.php",
                log_guard=ROOT / "ops/deployment/laravel_log_guard.py", approval_token=runner.STAGE_APPROVAL_TOKEN)
        runner.atomic_json(test_record, {"path": str(path), "sha256": runner.sha256_file(path)})
        return {"status": "created", "path": str(path), "actor_uid": os.geteuid(), "actor_gid": os.getegid()}
    record = json.loads(test_record.read_text())
    with mock.patch.object(runner, "RELEASE_ROOT", release_root):
        try:
            receipt, release, rows = runner.validate_release_receipt(Path(record["path"]), record["sha256"])
        except (runner.DeploymentError, OSError) as error:
            return {"status": "rejected", "error_type": type(error).__name__, "reason": str(error),
                "actor_uid": os.geteuid(), "actor_gid": os.getegid()}
    return {"status": "pass", "actor_uid": os.geteuid(), "actor_gid": os.getegid(),
        "release_receipt_sha256": record["sha256"], "generation": receipt["activation_generation"],
        "source_members": len(rows), "control_inputs": len(receipt["control_inputs"]),
        "proof_metadata": {key: runner.path_metadata(Path(receipt[key]["path"]))
            for key in ("activation_fpm", "activation_fpm_after")}}


@unittest.skipUnless(os.geteuid() in (0, 1000), "actual Linux UID/GID 1000 receipt actor required")
class FreshV6StagingReceiptTests(unittest.TestCase):
    """The generator and validator are real; no metadata/validator mocks."""
    def actor(self, action, root):
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--receipt-actor", action, str(root)]
        if os.geteuid() == 0:
            command = ["/usr/bin/setpriv", "--reuid=1000", "--regid=1000", "--clear-groups", *command]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @contextmanager
    def fresh_receipt(self):
        with tempfile.TemporaryDirectory(prefix="buydtf-v6-receipt-test-") as directory:
            root = Path(directory)
            if os.geteuid() == 0:
                os.chown(root, 1000, 1000)
            created = self.actor("stage", root)
            self.assertEqual(created["status"], "created")
            path = Path(created["path"])
            result = self.actor("validate", root)
            self.assertEqual(result["status"], "pass", result)
            self.assertEqual((result["actor_uid"], result["actor_gid"]), (1000, 1000))
            self.assertEqual((result["generation"], result["source_members"], result["control_inputs"]),
                (activation.GENERATION, 11, 10))
            self.assertEqual(result["proof_metadata"], {key: {"kind": "file", "uid": 1000, "gid": 1000, "mode": 0o600}
                for key in ("activation_fpm", "activation_fpm_after")})
            print("V6_RECEIPT_VALIDATION " + json.dumps({"case": "fresh_stage_real_validator", **result}, sort_keys=True))
            yield root, path, json.loads(path.read_text())

    def rebind_receipt(self, root, path, receipt):
        # In-place writes preserve real UID/GID 1000 and mode 0600.
        path.write_bytes(runner.canonical_bytes(receipt))
        (root / "stage-test.json").write_bytes(runner.canonical_bytes({"path": str(path), "sha256": runner.sha256_file(path)}))

    def rejected(self, case, root, phrase=None):
        result = self.actor("validate", root)
        self.assertEqual(result["status"], "rejected", result)
        if phrase is not None:
            self.assertIn(phrase, result["reason"])
        print("V6_RECEIPT_VALIDATION " + json.dumps({"case": case, **result}, sort_keys=True))

    def test_fresh_v6_staging_receipt_passes_real_validator_and_metadata(self):
        with self.fresh_receipt():
            pass

    def test_proof_permission_drift_is_rejected(self):
        for key in ("activation_fpm", "activation_fpm_after"):
            for mode in (0o644, 0o640):
                with self.subTest(key=key, mode=mode), self.fresh_receipt() as (root, path, receipt):
                    Path(receipt[key]["path"]).chmod(mode)
                    self.rejected("permission_drift:" + key, root, "not private or receipt-bound")

    @unittest.skipUnless(os.geteuid() == 0, "ownership drift needs root in disposable fixture only")
    def test_proof_uid_or_gid_drift_is_rejected(self):
        for key in ("activation_fpm", "activation_fpm_after"):
            for owner in ((33, 1000), (1000, 33)):
                with self.subTest(key=key, owner=owner), self.fresh_receipt() as (root, path, receipt):
                    os.chown(Path(receipt[key]["path"]), *owner)
                    self.rejected("ownership_drift:" + key, root)

    def test_proof_tampering_is_rejected_with_original_and_rebound_hash(self):
        for key in ("activation_fpm", "activation_fpm_after"):
            for rebound in (False, True):
                with self.subTest(key=key, rebound=rebound), self.fresh_receipt() as (root, path, receipt):
                    target = Path(receipt[key]["path"])
                    payload = json.loads(target.read_text())
                    payload["proof"]["php_version"] = "8.3.6"
                    target.write_bytes(runner.canonical_bytes(payload))
                    if rebound:
                        receipt[key]["sha256"] = runner.sha256_file(target)
                        self.rebind_receipt(root, path, receipt)
                    self.rejected("proof_tampering:" + key, root, "receipt differs" if rebound else "Checksum mismatch")

    def test_missing_proof_binding_or_file_is_rejected(self):
        for key in ("activation_fpm", "activation_fpm_after"):
            for missing_binding in (False, True):
                with self.subTest(key=key, missing_binding=missing_binding), self.fresh_receipt() as (root, path, receipt):
                    if missing_binding:
                        receipt.pop(key)
                        self.rebind_receipt(root, path, receipt)
                    else:
                        Path(receipt[key]["path"]).unlink()
                    self.rejected("missing_proof:" + key, root, "Required file is missing")

    def test_hash_valid_proof_paths_outside_evidence_are_rejected(self):
        for key in ("activation_fpm", "activation_fpm_after"):
            for inside_release in (False, True):
                with self.subTest(key=key, inside_release=inside_release), self.fresh_receipt() as (root, path, receipt):
                    original = Path(receipt[key]["path"])
                    outside = (path.parent / "inputs" if inside_release else root) / "escaped-proof.json"
                    outside.write_bytes(original.read_bytes())
                    os.chown(outside, 1000, 1000)
                    outside.chmod(0o600)
                    receipt[key]["path"] = str(outside)
                    self.rebind_receipt(root, path, receipt)
                    self.rejected("escaping_path:" + key, root, "not private or receipt-bound")

    def test_symlink_proof_is_rejected(self):
        for key in ("activation_fpm", "activation_fpm_after"):
            with self.subTest(key=key), self.fresh_receipt() as (root, path, receipt):
                original = Path(receipt[key]["path"])
                alias = original.with_name("symbolic-proof.json")
                alias.symlink_to(original)
                receipt[key]["path"] = str(alias)
                self.rebind_receipt(root, path, receipt)
                self.rejected("symbolic_proof:" + key, root, "Required file is missing")

    def test_staged_runner_must_equal_executing_runner_even_with_rebound_hash(self):
        with self.fresh_receipt() as (root, path, receipt):
            staged = Path(receipt["inputs"]["runner"]["path"])
            staged.write_bytes(staged.read_bytes() + b"\n# changed after staging\n")
            receipt["inputs"]["runner"]["sha256"] = runner.sha256_file(staged)
            self.rebind_receipt(root, path, receipt)
            self.rejected("runner_bytes_changed_after_staging", root, "Executing runner differs")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--receipt-actor":
        print(json.dumps(staging_receipt_actor(sys.argv[2], Path(sys.argv[3]))))
    else:
        unittest.main()
