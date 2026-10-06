"""V6 has no executable authorization and needs real production FPM evidence."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import production_alpha_activation_controls as activation
import production_alpha_transparency_deploy as runner

ROOT = Path(__file__).resolve().parents[2]


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
    def test_all_tokens_are_withheld_and_none_is_never_an_authorization(self):
        self.assertEqual((runner.STAGE_APPROVAL_TOKEN, runner.DEPLOY_APPROVAL_TOKEN, runner.RECOVERY_APPROVAL_TOKEN), (None, None, None))
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


if __name__ == "__main__":
    unittest.main()
