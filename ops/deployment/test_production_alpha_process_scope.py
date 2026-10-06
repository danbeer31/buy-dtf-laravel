"""Process permission guards: positive scope proof, not permission-error skips."""
import copy
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from test_production_alpha_scheduler import controls, snapshot, deploy, ROOT


class ProcessScopeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / "application"
        self.app.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        (self.proc / "uptime").write_text("1000.0 0.0\n")
        self.entry = self.proc / "424242"
        self.entry.mkdir()
        (self.entry / "cmdline").write_bytes(b"/usr/bin/php8.2\0artisan\0unapproved:work\0")
        (self.entry / "status").write_text("Uid:\t33\t33\t33\t33\n")
        fields = ["S"] + ["0"] * 19
        fields[19] = "99900"
        (self.entry / "stat").write_text("424242 (php) " + " ".join(fields))
        (self.entry / "cwd").symlink_to(self.app)
        (self.entry / "exe").symlink_to("/usr/bin/php8.2")
        self.identity = controls._process_identity(self.entry)
        self.receipt = {"identity": self.identity, "status": "pass", "observer_uid": 33, "observer_gid": 33,
            "working_directory": "/tmp/unrelated-application", "executable": "/usr/bin/php8.2",
            "read_only": True, "environments_read": False, "process_or_permission_actions": False}
        original = Path.resolve
        def permission(path, *args, **kwargs):
            if path == self.entry / "cwd":
                raise PermissionError(13, "Permission denied")
            return original(path, *args, **kwargs)
        self.patch = mock.patch.object(Path, "resolve", permission)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def observe(self, reader=None):
        payload = snapshot(active=False, success="2026-10-05T00:20:11Z")
        return controls.process_envelope(payload, self.app, proc_root=self.proc,
            ticks_per_second=100, wall_time=controls.timestamp(payload["generated_at_utc"], "test"), scope_reader=reader)

    def remove_pid_directory(self):
        for member in self.entry.iterdir():
            member.unlink()
        self.entry.rmdir()

    def test_same_uid_fpm_positive_foreign_scope_passes_with_redacted_receipt(self):
        reader = mock.Mock(return_value=self.receipt)
        result = self.observe(reader)
        reader.assert_called_once_with(self.identity)
        self.assertEqual(result["processes"], [])
        self.assertEqual(result["uid_33_scope_probes"], 1)
        self.assertEqual(result["verified_outside_application"][0]["scope_source"], "read_only_fpm_uid_33")
        self.assertNotIn("unapproved:work", json.dumps(result))
        self.assertNotIn("unrelated-application", json.dumps(result))

    def test_missing_or_unavailable_observer_rejects(self):
        with self.assertRaisesRegex(controls.SchedulerError, "no validated UID 33"):
            self.observe()
        with self.assertRaisesRegex(controls.SchedulerError, "unavailable"):
            self.observe(mock.Mock(side_effect=controls.SchedulerError("FPM unavailable")))

    def test_scoped_unexpected_artisan_remains_rejected(self):
        with self.assertRaisesRegex(controls.SchedulerError, "Unexpected or failing"):
            self.observe(lambda _: {**self.receipt, "working_directory": str(self.app)})

    def test_application_subdirectory_is_never_classified_as_foreign_scope(self):
        with self.assertRaisesRegex(controls.SchedulerError, "working directory"):
            self.observe(lambda _: {**self.receipt, "working_directory": str(self.app / "storage")})

    def test_valid_scoped_uid33_qbo_worker_keeps_the_same_schedule_and_age_bounds(self):
        (self.entry / "cmdline").write_bytes(f"/usr/bin/php8.2\0artisan\0{controls.TASK}\0".encode())
        identity = controls._process_identity(self.entry)
        result = controls.process_envelope(snapshot(), self.app, proc_root=self.proc, ticks_per_second=100,
            wall_time=controls.timestamp("2026-10-05T00:20:11Z", "test"),
            scope_reader=lambda _: {**self.receipt, "identity": identity, "working_directory": str(self.app)})
        self.assertEqual(result["processes"][0]["role"], "reviewed_qbo_worker")
        self.assertEqual(result["processes"][0]["uid"], 33)
        self.assertEqual(result["processes"][0]["scope_source"], "read_only_fpm_uid_33")
        with self.assertRaisesRegex(controls.SchedulerError, "idle before source mutation"):
            controls.require_idle(snapshot())

    def test_explicit_application_argument_cannot_be_excluded_by_foreign_cwd(self):
        (self.entry / "cmdline").write_bytes(f"/usr/bin/php8.2\0{self.app}/artisan\0unapproved:work\0".encode())
        identity = controls._process_identity(self.entry)
        with self.assertRaisesRegex(controls.SchedulerError, "working directory"):
            self.observe(lambda _: {**self.receipt, "identity": identity})

    def test_wrong_owner_missing_fields_malformed_paths_or_mutating_evidence_reject(self):
        changes = [{}, {"observer_uid": 1000}, {"observer_uid": True}, {"read_only": False},
            {"environments_read": True}, {"process_or_permission_actions": True},
            {"working_directory": "/tmp/../application"}, {"working_directory": "relative"},
            {"executable": "/usr/bin/php8.2 (deleted)"}, {"identity": {**self.identity, "start_ticks": 99901}},
            {"identity": {**self.identity, "pid": 424243}}, {"identity": {**self.identity, "argv_sha256": "0" * 64}}]
        for index, change in enumerate(changes):
            receipt = {} if index == 0 else {**self.receipt, **change}
            with self.subTest(change=change), self.assertRaises(controls.SchedulerError):
                self.observe(lambda _: receipt)

    def test_pid_reuse_or_command_change_during_probe_reject(self):
        def changed(_):
            (self.entry / "cmdline").write_bytes(b"/usr/bin/php8.2\0artisan\0different:work\0")
            return self.receipt
        with self.assertRaisesRegex(controls.SchedulerError, "identity changed"):
            self.observe(changed)

    def test_process_exit_during_probe_is_distinguished_from_pid_reuse(self):
        def exited(_):
            self.remove_pid_directory()
            return self.receipt
        result = self.observe(exited)
        self.assertEqual(result["processes"], [])
        self.assertEqual(result["verified_outside_application"], [])
        self.assertEqual(result["confirmed_process_exits"][0]["trigger"], "kernel_identity_unavailable_after_success")

    def test_exit_before_fpm_read_requires_fresh_bound_kernel_absence_proof(self):
        def rejected(_):
            self.remove_pid_directory()
            raise controls.ProcessScopeProbeRejected("a" * 64)
        result = self.observe(rejected)
        proof = result["confirmed_process_exits"][0]
        self.assertEqual(proof["identity"], self.identity)
        self.assertEqual(proof["trigger"], "validated_fpm_target_unavailable_rejection")
        self.assertEqual(proof["response_sha256"], "a" * 64)
        self.assertEqual(len(proof["checks"]), 2)
        self.assertTrue(all(row["pid_directory_errno"] == 2 for row in proof["checks"]))
        self.assertEqual(result["processes"], [])
        self.assertEqual(result["verified_outside_application"], [])

    def test_rejected_response_for_live_unreadable_process_is_not_an_exit(self):
        with self.assertRaisesRegex(controls.SchedulerError, "remains live"):
            self.observe(mock.Mock(side_effect=controls.ProcessScopeProbeRejected("a" * 64)))

    def test_reused_pid_after_rejected_response_fails_closed(self):
        def reused(_):
            text = (self.entry / "stat").read_text()
            (self.entry / "stat").write_text(text.replace("99900", "99901"))
            raise controls.ProcessScopeProbeRejected("a" * 64)
        with self.assertRaisesRegex(controls.SchedulerError, "PID reused"):
            self.observe(reused)

    def test_missing_fact_with_present_pid_is_not_confirmed_disappearance(self):
        for success in (False, True):
            with self.subTest(success=success):
                before = (self.entry / "stat").read_bytes()
                def partial(_):
                    (self.entry / "stat").unlink()
                    if success:
                        return self.receipt
                    raise controls.ProcessScopeProbeRejected("a" * 64)
                try:
                    with self.assertRaisesRegex(controls.SchedulerError, "disappearance is unproven"):
                        self.observe(partial)
                finally:
                    (self.entry / "stat").write_bytes(before)

    def test_access_denial_during_fresh_absence_check_remains_fatal(self):
        original = Path.lstat
        def denied(path):
            if path == self.entry:
                raise PermissionError(13, "Permission denied")
            return original(path)
        with mock.patch.object(Path, "lstat", denied), self.assertRaisesRegex(controls.SchedulerError, "disappearance is unproven"):
            self.observe(mock.Mock(side_effect=controls.ProcessScopeProbeRejected("a" * 64)))

    def test_pid_reappearing_between_absence_checks_is_rejected(self):
        original = Path.lstat
        lookups = 0
        def once_absent(path):
            nonlocal lookups
            if path == self.entry:
                lookups += 1
                if lookups == 1:
                    raise FileNotFoundError(2, "No such file")
            return original(path)
        with mock.patch.object(Path, "lstat", once_absent), self.assertRaisesRegex(controls.SchedulerError, "remains live"):
            self.observe(mock.Mock(side_effect=controls.ProcessScopeProbeRejected("a" * 64)))
        self.assertEqual(lookups, 2)

    def test_unrelated_observer_failure_is_never_ignored_even_after_exit(self):
        def unavailable(_):
            self.remove_pid_directory()
            raise controls.SchedulerError("FPM unavailable")
        with self.assertRaisesRegex(controls.SchedulerError, "FPM unavailable"):
            self.observe(unavailable)

    def test_other_unreadable_uid_is_not_silently_ignored(self):
        (self.entry / "status").write_text("Uid:\t1001\t1001\t1001\t1001\n")
        reader = mock.Mock(return_value=self.receipt)
        with self.assertRaisesRegex(controls.SchedulerError, "no validated UID 33"):
            self.observe(reader)
        reader.assert_not_called()

    def test_observer_work_is_bounded(self):
        with mock.patch.dict(controls.POLICY, maximum_process_scope_probes_per_observation=0):
            with self.assertRaisesRegex(controls.SchedulerError, "bounded probe count"):
                self.observe(lambda _: self.receipt)

    def test_kernel_facts_never_read_environment_or_change_permissions(self):
        before = {p.name: p.read_bytes() for p in self.entry.iterdir() if p.is_file() and not p.is_symlink()}
        self.observe(lambda _: self.receipt)
        self.assertFalse((self.entry / "environ").exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.entry.iterdir() if p.is_file() and not p.is_symlink()})

    def test_idle_preflight_guard_requires_positive_scope_and_rejects_every_scoped_artisan(self):
        (self.entry / "cgroup").write_text("0::/unrelated.service\n")
        original_iterdir = Path.iterdir
        def proc_entries(path):
            return iter([self.entry]) if path == Path("/proc") else original_iterdir(path)
        with mock.patch.object(Path, "iterdir", proc_entries), mock.patch.object(deploy, "APP_ROOT", self.app), mock.patch.object(controls, "FpmProcessScopeReader", return_value=lambda _: self.receipt):
            self.assertEqual(deploy.scoped_processes(), [])
        with mock.patch.object(Path, "iterdir", proc_entries), mock.patch.object(deploy, "APP_ROOT", self.app), mock.patch.object(controls, "FpmProcessScopeReader", return_value=lambda _: {**self.receipt, "working_directory": str(self.app)}):
            self.assertEqual(deploy.scoped_processes(), [{"pid": "424242", "classification": "scoped-conflict"}])
        with mock.patch.object(Path, "iterdir", proc_entries), mock.patch.object(deploy, "APP_ROOT", self.app), mock.patch.object(controls, "FpmProcessScopeReader", return_value=lambda _: {}):
            with self.assertRaisesRegex(deploy.DeploymentError, "unavailable or ambiguous"):
                deploy.scoped_processes()

    def test_idle_preflight_records_confirmed_exit_after_fpm_rejection(self):
        original_iterdir = Path.iterdir
        def proc_entries(path):
            return iter([self.entry]) if path == Path("/proc") else original_iterdir(path)
        def rejected(_):
            self.remove_pid_directory()
            raise controls.ProcessScopeProbeRejected("a" * 64)
        receipts = []
        with mock.patch.object(Path, "iterdir", proc_entries), mock.patch.object(deploy, "APP_ROOT", self.app), mock.patch.object(controls, "FpmProcessScopeReader", return_value=rejected):
            self.assertEqual(deploy.scoped_processes(scope_receipts=receipts), [])
        self.assertEqual(receipts[0]["identity"], self.identity)
        self.assertEqual(receipts[0]["status"], "confirmed_gone")

    @unittest.skipUnless(os.geteuid() == 0, "root-owned isolated Phase 0 inventory")
    def test_unreadable_process_scope_fails_actual_phase0_before_release_creation(self):
        from test_production_alpha_nginx_inventory import NginxInventoryFixture, ApprovedNginxInventoryTest, runner
        actual_scoped = runner.scoped_processes
        original_iterdir = Path.iterdir
        def proc_entries(path):
            return iter([self.entry]) if path == Path("/proc") else original_iterdir(path)
        with tempfile.TemporaryDirectory() as temporary:
            fixture = NginxInventoryFixture(Path(temporary))
            with fixture.phase0_environment(), mock.patch.object(Path, "iterdir", proc_entries), mock.patch.object(runner, "scoped_processes", actual_scoped), mock.patch.object(controls, "FpmProcessScopeReader", return_value=lambda _: {}):
                inputs = ApprovedNginxInventoryTest().inputs()
                with self.assertRaisesRegex(runner.DeploymentError, "unavailable or ambiguous"):
                    runner.preflight_guard(inputs["helper"], [])
                with self.assertRaisesRegex(runner.DeploymentError, "unavailable or ambiguous"):
                    runner.production_preflight(helper=inputs["helper"], manifest_rows=[], evidence_directory=Path(temporary), prefix="phase0")
                with self.assertRaisesRegex(runner.DeploymentError, "unavailable or ambiguous"):
                    runner.stage_release(**inputs)
                self.assertFalse(fixture.release_root.exists())


class ScopeTransportTests(unittest.TestCase):
    """Transport schema/nonce failures; real UID/files/socket covered in Linux rehearsal."""
    def transport(self, change=lambda value: value, raw=None, timeout=False):
        identity = {"pid": 424242, "uid": 33, "start_ticks": 1000, "argv_sha256": "a" * 64}
        helper = ROOT / "ops/deployment/production_alpha_process_scope_probe.php"
        socket_path = Path("/isolated/fpm.sock")
        original_lstat = Path.lstat
        def metadata(path):
            if path == helper:
                return SimpleNamespace(st_mode=0o100644, st_uid=1000, st_gid=1000)
            if path == socket_path:
                return SimpleNamespace(st_mode=0o140660, st_uid=1000, st_gid=33)
            return original_lstat(path)
        def run(argv, **kwargs):
            self.assertEqual(argv, ["/usr/bin/cgi-fcgi", "-bind", "-connect", str(socket_path)])
            self.assertEqual(kwargs["timeout"], 5)
            self.assertFalse(any(name in kwargs["env"] for name in ("LD_PRELOAD", "PHP_INI_SCAN_DIR", "PATH", "APP_KEY", "HOME")))
            request = json.loads(base64.b64decode(kwargs["env"]["BUYDTF_PROCESS_SCOPE_REQUEST"]))
            self.assertEqual({k: v for k, v in request.items() if k != "nonce"}, identity)
            if timeout:
                raise subprocess.TimeoutExpired(argv, 5)
            receipt = {"artifact": "buy-dtf-process-scope-v1", "status": "pass", "identity": identity,
                "nonce": request["nonce"], "observer_uid": 33, "observer_gid": 33,
                "sapi": "fpm-fcgi", "php_version": "8.2.30", "working_directory": "/tmp/unrelated",
                "executable": "/usr/bin/php8.2", "read_only": True,
                "environments_read": False, "process_or_permission_actions": False}
            body = json.dumps(change(receipt)).encode()
            return subprocess.CompletedProcess(argv, 0,
                raw if raw is not None else b"Content-Type: application/json\r\n\r\n" + body, b"")
        directories = []
        original_mkdtemp = tempfile.mkdtemp
        def temporary(*args, **kwargs):
            value = original_mkdtemp(*args, **kwargs)
            directories.append(Path(value))
            return value
        with mock.patch.object(controls.os, "geteuid", return_value=1000), mock.patch.object(Path, "lstat", metadata), mock.patch.object(controls.FpmProcessScopeReader, "_verify_execution_copy"), mock.patch.object(controls.subprocess, "run", side_effect=run), mock.patch.object(controls.tempfile, "mkdtemp", side_effect=temporary):
            try:
                return controls.FpmProcessScopeReader(helper, socket_path)(identity)
            finally:
                self.assertTrue(directories and all(not path.exists() for path in directories))

    def test_exact_nonce_fpm_uid_gid_version_and_closed_environment(self):
        self.assertEqual(self.transport()["status"], "pass")

    def test_stale_wrong_sapi_owner_group_version_and_identity_reject(self):
        for field, value in (("nonce", "0" * 48), ("sapi", "cli"), ("observer_uid", 1000),
                ("observer_gid", 1000), ("php_version", "8.3.30"), ("read_only", False),
                ("identity", {}), ("status", "rejected")):
            with self.subTest(field=field), self.assertRaises(controls.SchedulerError):
                self.transport(lambda receipt: {**receipt, field: value})

    def test_unparsed_invalid_utf8_duplicate_or_conflicting_http_data_reject(self):
        for raw in (b"not CGI", b"Content-Type: application/json\n\n\xff",
                b'Content-Type: application/json\n\n{"status":"pass","status":"pass"}',
                b"Status: 503 Unavailable\nStatus: 200 OK\n\n{}",
                b"Content-Type: application/json\n\n" + b"x" * 17000):
            with self.subTest(raw=raw[:35]), self.assertRaises(controls.SchedulerError):
                self.transport(raw=raw)

    def test_timeout_fails_closed_and_disposable_copy_is_removed(self):
        with self.assertRaisesRegex(controls.SchedulerError, "unavailable or malformed"):
            self.transport(timeout=True)

    def test_only_exact_target_unavailable_rejection_has_exit_check_disposition(self):
        body = {"artifact": "buy-dtf-process-scope-v1", "status": "rejected",
            "reason": "Process scope evidence unavailable or malformed.", "read_only": True}
        raw = b"Status: 503 Service Unavailable\nContent-Type: application/json\n\n" + json.dumps(body).encode()
        with self.assertRaises(controls.ProcessScopeProbeRejected):
            self.transport(raw=raw)
        for change in ({"reason": "Read-only observer is not UID/GID 33."}, {"read_only": False}, {"extra": "data"}):
            changed = b"Status: 503 Service Unavailable\n\n" + json.dumps({**body, **change}).encode()
            with self.subTest(change=change), self.assertRaises(controls.SchedulerError) as error:
                self.transport(raw=changed)
            self.assertNotIsInstance(error.exception, controls.ProcessScopeProbeRejected)


class LocalReviewOnlyTests(unittest.TestCase):
    def test_direct_production_entrypoints_reject_before_path_access(self):
        with mock.patch.object(deploy, "APP_ROOT", Path("/var/www/buy-dtf")), mock.patch.object(deploy, "require_regular_file") as read:
            for action in (
                    lambda: deploy.stage_release(archive=Path("unused"), manifest=Path("unused"), helper=Path("unused"), log_guard=Path("unused"), approval_token=deploy.STAGE_APPROVAL_TOKEN),
                    lambda: deploy.deploy_release(release_receipt_path=Path("unused"), release_receipt_sha256="a" * 64, approval_token=deploy.DEPLOY_APPROVAL_TOKEN),
                    lambda: deploy.recover_state(state_path=Path("unused"), approval_token=deploy.RECOVERY_APPROVAL_TOKEN)):
                with self.assertRaisesRegex(deploy.DeploymentError, "non-stageable"):
                    action()
            read.assert_not_called()

    def test_all_cli_mutations_reject_before_access_even_with_consumed_token(self):
        for action in ("--stage", "--deploy", "--recover"):
            result = subprocess.run(["python3", str(ROOT / "ops/deployment/production_alpha_transparency_deploy.py"),
                action, "--approval-token", deploy.DEPLOY_APPROVAL_TOKEN], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertIn("non-stageable", result.stderr)
        self.assertEqual(deploy.describe()["approval_tokens"]["stage"], None)

    def test_failed_v5_controls_and_receipt_are_permanently_retired(self):
        self.assertIn("d3c1a26bb1081bb47149eb2b34787d747e56a4db4ef0eb4668f62e3baf231a3d", deploy.RETIRED_RUNNER_SHA256S)
        self.assertIn("6734f82816d511623e54d68718ae10ff55376ecfdf56b03782e6d6caab87642e", deploy.RETIRED_RELEASE_RECEIPT_SHA256S)


if __name__ == "__main__":
    unittest.main()
