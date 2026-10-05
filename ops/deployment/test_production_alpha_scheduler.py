"""Scheduler regressions use disposable files and clocks; no accounting command runs."""
import copy
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest import mock

from test_production_alpha_transparency_runner import deploy, rehearsal, ROOT


controls = deploy.scheduler_controls
REAL_OBSERVE = controls.observe
FIXTURE = ROOT / "ops/evidence/production-alpha-transparency-source-only-v5-scheduler-20261005/sample-19.redacted.json"


def snapshot(at="2026-10-05T00:20:11Z", *, active=True, start="2026-10-05T00:20:00Z", success=None, startup=False, attempt=None):
    payload = rehearsal.runtime_snapshot()
    payload["generated_at_utc"] = at
    payload["scheduler"] = rehearsal.scheduler_snapshot(at, active=active, started_at=start, success_at=success, startup=startup, attempt_at=attempt)
    return payload


def step(payload, previous=None, phase="monitor", **kwargs):
    epoch = controls.timestamp(payload["generated_at_utc"], "test")
    return REAL_OBSERVE(payload, previous, phase=phase, monotonic_ns=kwargs.get("monotonic_ns", epoch * 10**9), wall_time=kwargs.get("wall_time", epoch))


class SchedulerPolicyTests(unittest.TestCase):
    def test_sample_19_is_still_rejected_before_mutation_but_bounded_after_open(self):
        fixture = json.loads(FIXTURE.read_text())
        payload = snapshot()
        for field in ("event_count", "stripe_payout_sync_event_count", "active_overlap_mutex_count"):
            self.assertEqual(payload["scheduler"][field], fixture["scheduler"][field])
        old_mutex = fixture["scheduler"]["overlap_mutexes"][0]
        for field, value in old_mutex.items():
            self.assertEqual(payload["scheduler"]["overlap_mutexes"][0][field], value)
        with self.assertRaisesRegex(controls.SchedulerError, "idle before source mutation"):
            controls.require_idle(payload)
        state, receipt = step(payload)
        self.assertEqual(receipt["transitions"], ["acquired"])
        done = snapshot("2026-10-05T00:20:16Z", active=False, success=fixture["independent_review_confirmed_success_at_utc"])
        state, receipt = step(done, state)
        self.assertIsNone(state["pending"])
        self.assertEqual(receipt["transitions"], ["completed", "released"])

    def test_phase_policies_never_allow_active_pre_source_work(self):
        active = snapshot()
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_pre_source_runtime_snapshot(active)
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_runtime_snapshot(active)
        for phase in ("post_open", "monitor", "rollback", "recovery"):
            self.assertTrue(step(active, phase=phase)[1]["active"])
        with self.assertRaises(controls.SchedulerError):
            step(active, phase="preflight")

    def test_exact_schedule_command_sources_and_mutex_are_pinned(self):
        mutations = [
            lambda s: s.update(event_count=4),
            lambda s: s.update(stripe_payout_sync_event_count=0),
            lambda s: s["events"][0].update(expression="* * * * *"),
            lambda s: s["events"][0].update(timezone="UTC"),
            lambda s: s.update(application_timezone="UTC"),
            lambda s: s.update(php_default_timezone="UTC"),
            lambda s: s["events"][0].update(command_sha256="0" * 64),
            lambda s: s["events"][0].update(run_in_background=True),
            lambda s: s["source_sha256"].update({"routes/console.php": "0" * 64}),
            lambda s: s["overlap_mutexes"][0].update(command_sha256="0" * 64),
            lambda s: s["overlap_mutexes"][0].update(mutex_name_sha256="0" * 64),
            lambda s: s["overlap_mutexes"].append(copy.deepcopy(s["overlap_mutexes"][0])),
            lambda s: s.update(active_overlap_mutex_count=2),
            lambda s: s.update(read_only=False),
            lambda s: s.update(cache_driver="redis"),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                payload = snapshot()
                mutation(payload["scheduler"])
                with self.assertRaises(controls.SchedulerError):
                    step(payload)

    def test_malformed_unknown_stale_and_stuck_activity_is_rejected(self):
        mutations = [
            lambda s: s["overlap_mutexes"][0].update(exists="true"),
            lambda s: s["overlap_mutexes"][0].update(expires_at_unix=None),
            lambda s: s["overlap_mutexes"][0].update(expires_at_unix=True),
            lambda s: s["overlap_mutexes"][0].update(owner_sha256="bad"),
            lambda s: s["refresh_status"].update(last_attempt_at="bad"),
            lambda s: s["refresh_status"].update(last_attempt_at="2026-10-05T00:30:00Z"),
            lambda s: s["refresh_status"].update(linked_businesses="4"),
            lambda s: s["refresh_status"].update(exists=False),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                payload = snapshot()
                mutation(payload["scheduler"])
                with self.assertRaises(controls.SchedulerError):
                    step(payload)
        for at, start in (("2026-10-05T00:22:01Z", "2026-10-05T00:20:00Z"),
                          ("2026-10-05T00:20:31Z", "2026-10-05T00:20:20Z"),
                          ("2026-10-05T00:20:11Z", "2026-10-05T00:00:00Z")):
            with self.assertRaises(controls.SchedulerError):
                step(snapshot(at, start=start))
        with self.assertRaisesRegex(controls.SchedulerError, "status is stale"):
            step(snapshot(active=False, success="2026-10-05T00:00:12Z"))

    def test_failing_and_deferred_work_is_never_permitted(self):
        for active in (True, False):
            for change in ({"state": "error"}, {"state": "deferred"}, {"last_error_present": True},
                           {"last_error_at": "2026-10-05T00:20:10Z"}, {"circuit_retry_at": "2026-10-05T00:30:00Z"}):
                payload = snapshot(active=active)
                payload["scheduler"]["refresh_status"].update(change)
                with self.assertRaisesRegex(controls.SchedulerError, "failing or deferred"):
                    step(payload)

    def test_mutex_release_needs_success_and_success_needs_prompt_release(self):
        state, _ = step(snapshot())
        cleared = snapshot("2026-10-05T00:20:16Z", active=False, success="2026-10-05T00:10:12Z")
        with self.assertRaisesRegex(controls.SchedulerError, "without bounded successful|status regressed"):
            step(cleared, state)
        stuck = snapshot("2026-10-05T00:20:18Z", success="2026-10-05T00:20:12Z")
        with self.assertRaisesRegex(controls.SchedulerError, "mutex is stuck"):
            step(stuck, state)
        orphan = snapshot(active=False)
        orphan["scheduler"]["refresh_status"]["last_attempt_at"] = "2026-10-05T00:20:00Z"
        with self.assertRaisesRegex(controls.SchedulerError, "orphaned"):
            step(orphan)

    def test_interruption_does_not_reset_expiry_or_durable_bounds(self):
        state, _ = step(snapshot())
        resumed = json.loads(json.dumps(state))
        with self.assertRaises(controls.SchedulerError):
            step(snapshot("2026-10-05T00:22:12Z"), resumed, phase="recovery")
        with self.assertRaisesRegex(controls.SchedulerError, "clock continuity"):
            step(snapshot("2026-10-05T00:20:16Z"), state, monotonic_ns=state["last_monotonic_ns"] + 20 * 10**9)
        with self.assertRaisesRegex(controls.SchedulerError, "Stale scheduler"):
            step(snapshot(), wall_time=controls.timestamp("2026-10-05T00:22:00Z", "test"))
        for bad in ({}, {**state, "policy_sha256": "0" * 64}, {**state, "pending": {"bad": 1}}):
            with self.assertRaises(controls.SchedulerError):
                step(snapshot("2026-10-05T00:20:16Z"), bad)

    def test_identity_change_during_active_work_is_rejected(self):
        state, _ = step(snapshot())
        payload = snapshot("2026-10-05T00:20:16Z")
        payload["scheduler"]["overlap_mutexes"][0]["owner_sha256"] = "b" * 64
        with self.assertRaisesRegex(controls.SchedulerError, "changed before verified"):
            step(payload, state)

    def test_completion_between_samples_is_observed_and_unscheduled_completion_rejected(self):
        state, _ = step(snapshot(active=False))
        state, receipt = step(snapshot("2026-10-05T00:20:16Z", active=False, success="2026-10-05T00:20:12Z"), state)
        self.assertEqual(receipt["transitions"], ["completed_between_samples"])
        baseline, _ = step(snapshot("2026-10-05T00:23:45Z", active=False, success="2026-10-05T00:20:12Z"))
        with self.assertRaisesRegex(controls.SchedulerError, "Unscheduled"):
            step(snapshot("2026-10-05T00:25:00Z", active=False, success="2026-10-05T00:25:00Z"), baseline)
        with self.assertRaisesRegex(controls.SchedulerError, "observation gap"):
            step(snapshot("2026-10-05T00:22:00Z", active=False, success="2026-10-05T00:20:12Z"), state)

    def test_non_scheduler_runtime_protections_remain_active(self):
        mutations = [lambda p: p["queue"]["counts"].update(jobs=1),
            lambda p: p["queue"]["counts"].update(failed_jobs=1),
            lambda p: p["schema"].update(sha256="0" * 64),
            lambda p: p["migration_ledger"].update(row_count=20),
            lambda p: p["capabilities"].update(receiver_enabled=True),
            lambda p: p["capabilities"].update(allowed_host_count=1),
            lambda p: p["runtime"].update(laravel_version="12.69.0")]
        with tempfile.TemporaryDirectory() as temporary:
            guard = deploy.SchedulerGuard(Path(temporary))
            for mutation in mutations:
                payload = snapshot()
                mutation(payload)
                with self.assertRaises(deploy.DeploymentError):
                    deploy.validate_runtime_snapshot(payload, scheduler_guard=guard, scheduler_phase="monitor")

    def test_durable_observations_are_private_and_rejections_are_redacted(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            guard = deploy.SchedulerGuard(directory)
            with mock.patch.object(controls, "observe", side_effect=lambda p, prev, **k: step(p, prev, k["phase"])):
                deploy.validate_runtime_snapshot(snapshot(), scheduler_guard=guard, scheduler_phase="post_open")
                deploy.validate_runtime_snapshot(snapshot("2026-10-05T00:20:16Z", active=False, success="2026-10-05T00:20:12Z"), scheduler_guard=guard, scheduler_phase="monitor")
            for path in directory.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIsNone(json.loads(guard.path.read_text())["pending"])
            malformed = snapshot()
            malformed["scheduler"]["refresh_status"]["state"] = "error"
            # Use the real function for the rejection, with a current wall time.
            with mock.patch.object(controls.time, "time", return_value=controls.timestamp(malformed["generated_at_utc"], "test")):
                with self.assertRaises(deploy.DeploymentError):
                    deploy.validate_runtime_snapshot(malformed, scheduler_guard=guard, scheduler_phase="monitor")
            failure = next(directory.glob("scheduler-rejection-*.json"))
            self.assertEqual(json.loads(failure.read_text())["status"], "rejected")
            self.assertNotIn("last_error", failure.read_text())

    @unittest.skipUnless(os.geteuid() == 0, "root-owned disposable Phase 0 fixture required")
    def test_actual_phase0_and_stage_refuse_sample19_before_release_creation(self):
        from test_production_alpha_nginx_inventory import NginxInventoryFixture, ApprovedNginxInventoryTest, runner
        with tempfile.TemporaryDirectory() as temporary:
            fixture = NginxInventoryFixture(Path(temporary))
            with fixture.phase0_environment(), mock.patch.object(runner, "runtime_probe_memory", return_value=snapshot()), mock.patch.object(runner, "runtime_probe", return_value=(snapshot(), {})):
                inputs = ApprovedNginxInventoryTest().inputs()
                with self.assertRaisesRegex(runner.DeploymentError, "idle before source mutation"):
                    runner.preflight_guard(inputs["helper"], [])
                with self.assertRaisesRegex(runner.DeploymentError, "idle before source mutation"):
                    runner.production_preflight(helper=inputs["helper"], manifest_rows=[], evidence_directory=Path(temporary), prefix="phase0")
                with mock.patch.object(runner, "extract_candidate") as extract:
                    with self.assertRaisesRegex(runner.DeploymentError, "idle before source mutation"):
                        runner.stage_release(**inputs)
                    extract.assert_not_called()
                self.assertFalse(fixture.release_root.exists())

    def test_actual_post_open_and_monitor_paths_replay_completion_and_failures(self):
        import rehearse_production_alpha_scheduler as monitor_rehearsal
        with tempfile.TemporaryDirectory() as temporary:
            for scenario in monitor_rehearsal.SCENARIOS:
                result = monitor_rehearsal.run_case(scenario, Path(temporary) / scenario)
                self.assertEqual(result["status"], "pass")
                if scenario == "sample-19-normal-completion":
                    self.assertEqual(result["samples_completed"], 30)
                    self.assertTrue(any(row["generated_at_utc"] == "2026-10-05T00:20:11Z" and row["active"] for row in result["probes"]))
                    self.assertGreaterEqual(result["elapsed_virtual_seconds"], 1800)

    def test_qbo_warning_failure_is_fatal_even_between_runtime_samples(self):
        guard = deploy.load_laravel_log_guard(ROOT / "ops/deployment/laravel_log_guard.py")
        content = b'[2026-10-05 00:20:12] local.WARNING: QBO admin snapshot refresh failed {"exception":"RuntimeException","error":"[REDACTED]"}\n'
        report = guard.analyze_log_bytes(content)
        self.assertEqual(report["status"], "fail")
        self.assertIn("scheduled_qbo_refresh_failure", str(report))
        success = guard.analyze_log_bytes(b'[2026-10-05 00:20:12] local.INFO: QBO admin snapshots refreshed {"linked_businesses":4,"updated_businesses":4,"invoice_count":10}\n')
        self.assertEqual(success["status"], "pass")

    def test_real_laravel_read_only_file_and_database_observer(self):
        vendor_root = Path(os.environ.get("BUYDTF_REHEARSAL_VENDOR_ROOT", "/tmp/buydtf-alpha-v3-build-a-20261004-r3"))
        with tempfile.TemporaryDirectory(prefix="buydtf-scheduler-php-") as temporary:
            result = subprocess.run(["/usr/bin/php", str(ROOT / "ops/deployment/test_production_alpha_scheduler_probe.php"), str(vendor_root), temporary, str(ROOT)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["laravel_version"], "12.69.1")
        self.assertEqual(receipt["source_sha256"], controls.SOURCE_SHA256)
        self.assertEqual(receipt["normalized_commands"], ["php artisan stripe:sync-payouts", "php artisan accounting:reconcile-stripe-holding", "php artisan qbo:refresh-admin-cache"])
        self.assertTrue(receipt["active_mutex_read_only"])
        self.assertTrue(receipt["expired_mutex_read_only"])
        self.assertTrue(receipt["malformed_mutex_read_only_rejected"])
        self.assertTrue(receipt["database_observer_select_only"])
        # The WSL binary path differs; Laravel's mutex normalization is stable.
        qbo = [row for row in receipt["events"] if row["without_overlapping"]][0]
        self.assertEqual(qbo["mutex_name_sha256"], controls.MUTEX_SHA256)
        self.assertEqual(qbo["expression"], controls.POLICY["expression"])
        self.assertEqual(qbo["timezone"], "America/Chicago")
        self.assertEqual(receipt["real_writer_class"], "App\\Services\\QboAdminSnapshotStore")
        self.assertEqual(receipt["real_writer_sha256"], controls.SOURCE_SHA256["app/Services/QboAdminSnapshotStore.php"])
        for label, rows in receipt["lifecycles"].items():
            with self.subTest(real_writer_lifecycle=label):
                expected_offset = "-05:00" if label in {"summer", "fall_first_fold"} else "-06:00"
                state = None
                for row in rows:
                    self.assertTrue(row["raw_writer_last_attempt_at"].endswith(expected_offset))
                    self.assertTrue(row["raw_writer_last_success_at"].endswith(expected_offset))
                    self.assertTrue(row["observer_cache_unchanged"])
                    payload = rehearsal.runtime_snapshot()
                    payload["generated_at_utc"] = row["generated_at_utc"]
                    scheduler = copy.deepcopy(row["scheduler"])
                    # WSL PHP is 8.3, while the frozen production command uses
                    # 8.2. Project only that tested binary path in this local
                    # fixture; source, real mutex, timezone and writer/cache
                    # lifecycle facts must match without any projection.
                    expected = {e["expression"]: e for e in controls.expected_events()}
                    for event in scheduler["events"]:
                        projected = {**event, "command_sha256": expected[event["expression"]]["command_sha256"]}
                        self.assertEqual(projected, expected[event["expression"]])
                        event["command_sha256"] = projected["command_sha256"]
                    scheduler["events"].sort(key=lambda e: e["command_sha256"])
                    scheduler["overlap_mutexes"][0]["command_sha256"] = controls.COMMAND_SHA256
                    self.assertEqual(scheduler["overlap_mutexes"][0]["mutex_name_sha256"], controls.MUTEX_SHA256)
                    payload["scheduler"] = scheduler
                    if row["phase"] == "startup":
                        with self.assertRaises(controls.SchedulerError): controls.require_idle(payload)
                    state, observation = step(payload, state)
                    if row["phase"] == "startup":
                        self.assertEqual(state["pending"]["stage"], "startup")
                        self.assertEqual(observation["transitions"], ["acquired", "startup"])
                    if row["phase"] == "running":
                        self.assertEqual(state["pending"]["stage"], "running")
                        self.assertIn("startup_progress_confirmed", observation["transitions"])
                self.assertIsNone(state["pending"])
                self.assertEqual(observation["transitions"], ["completed", "released"])
        for row in receipt["laravel_due_cases"]:
            self.assertEqual(controls.due_commands(controls.timestamp(row["at_utc"], "test")), row["due_commands"])
        self.assertEqual(receipt["timestamp_cases"]["2026-10-04T19:20:12-05:00"], "2026-10-05T00:20:12Z")
        self.assertEqual(receipt["timestamp_cases"]["2026-12-10T01:20:12-06:00"], "2026-12-10T07:20:12Z")
        self.assertGreaterEqual(receipt["invalid_timestamp_cases_rejected"], 9)
        failure = rehearsal.runtime_snapshot()
        failure["scheduler"] = copy.deepcopy(receipt["writer_failure"])
        expected = {e["expression"]: e for e in controls.expected_events()}
        for event in failure["scheduler"]["events"]:
            event["command_sha256"] = expected[event["expression"]]["command_sha256"]
        failure["scheduler"]["events"].sort(key=lambda e: e["command_sha256"])
        failure["scheduler"]["overlap_mutexes"][0]["command_sha256"] = controls.COMMAND_SHA256
        with self.assertRaisesRegex(controls.SchedulerError, "failing or deferred"): controls.validate_identity(failure)

    def test_explicit_offset_timestamp_normalization_and_strict_calendar(self):
        self.assertEqual(controls.timestamp("2026-10-04T19:20:12-05:00", "test"), controls.timestamp("2026-10-05T00:20:12Z", "test"))
        self.assertEqual(controls.timestamp("2026-12-10T01:20:12-06:00", "test"), controls.timestamp("2026-12-10T07:20:12Z", "test"))
        self.assertEqual(controls.timestamp("2026-10-05T09:20:12+09:00", "test"), controls.timestamp("2026-10-05T00:20:12.123456Z", "test"))
        for value in ("2026-02-30T19:20:12-05:00", "2026-10-04T25:20:12-05:00", "2026-10-04T19:20:12-05:99",
                      "2026-10-04T19:20:12-24:00", "2026-10-04T19:20:12", "2026-10-04T19:20:12-00:00",
                      "2026-10-04T19:20:12.1234567Z", "0000-01-01T00:00:00Z", "2026-10-04T19:20:12-05:00 trailing"):
            with self.subTest(value=value), self.assertRaises(controls.SchedulerError): controls.timestamp(value, "test")
        payload = snapshot()
        payload["scheduler"]["refresh_status"]["last_attempt_at"] = "2026-10-04T19:20:00-05:00"
        payload["scheduler"]["refresh_status"]["last_success_at"] = "2026-10-04T19:10:12-05:00"
        self.assertTrue(step(payload)[1]["active"])

    def test_chicago_due_windows_include_both_dst_folds_and_spring_gap(self):
        cases = {"2026-07-10T06:30:01Z": ["accounting:reconcile-stripe-holding", controls.TASK],
            "2026-12-10T07:30:01Z": ["accounting:reconcile-stripe-holding", controls.TASK],
            "2026-11-01T06:30:01Z": ["accounting:reconcile-stripe-holding", controls.TASK],
            "2026-11-01T07:30:01Z": ["accounting:reconcile-stripe-holding", controls.TASK],
            "2026-03-08T07:30:01Z": ["accounting:reconcile-stripe-holding", controls.TASK],
            "2026-03-08T08:30:01Z": [controls.TASK],
            "2026-07-10T07:00:01Z": ["stripe:sync-payouts", controls.TASK]}
        for at, expected in cases.items():
            self.assertEqual(controls.due_commands(controls.timestamp(at, "test")), expected)
        first = controls.schedule_local(controls.timestamp("2026-11-01T06:30:01Z", "test"))
        second = controls.schedule_local(controls.timestamp("2026-11-01T07:30:01Z", "test"))
        self.assertEqual((first.hour, second.hour, first.fold, second.fold), (1, 1, 0, 1))

    def test_mutex_before_mark_attempt_is_durable_and_bounded_in_every_post_open_phase(self):
        for phase in ("post_open", "monitor", "rollback", "recovery"):
            startup = snapshot("2026-10-05T00:20:01Z", startup=True)
            with self.assertRaises(controls.SchedulerError): controls.require_idle(startup)
            state, receipt = step(startup, phase=phase)
            deadline = state["pending"]["startup_deadline_monotonic_ns"]
            self.assertEqual(receipt["transitions"], ["acquired", "startup"])
            state, _ = step(snapshot("2026-10-05T00:20:06Z", startup=True), json.loads(json.dumps(state)), phase=phase)
            self.assertEqual(deadline, state["pending"]["startup_deadline_monotonic_ns"])
            running = snapshot("2026-10-05T00:20:09Z", attempt="2026-10-05T00:20:08Z")
            state, receipt = step(running, state, phase=phase)
            self.assertEqual(state["pending"]["stage"], "running")
            self.assertIn("startup_progress_confirmed", receipt["transitions"])
            state, receipt = step(snapshot("2026-10-05T00:20:16Z", active=False, success="2026-10-05T00:20:12Z"), state, phase=phase)
            self.assertIsNone(state["pending"])
            self.assertEqual(receipt["transitions"], ["completed", "released"])

    def test_startup_timeout_late_progress_orphan_failure_and_regression_fail_closed(self):
        startup = snapshot("2026-10-05T00:20:01Z", startup=True)
        state, _ = step(startup)
        late = snapshot("2026-10-05T00:20:11Z", startup=True)
        for previous in (None, state, json.loads(json.dumps(state))):
            with self.assertRaisesRegex(controls.SchedulerError, "startup.*timely"):
                step(late, previous, phase="recovery")
        for payload in (snapshot("2026-10-05T00:20:11Z", attempt="2026-10-05T00:20:11Z"),
                        snapshot("2026-10-05T00:20:16Z", active=False, success="2026-10-05T00:20:12Z"),
                        snapshot("2026-10-05T00:20:06Z", active=False, success="2026-10-05T00:10:12Z")):
            with self.assertRaises(controls.SchedulerError): step(payload, state)
        failed = copy.deepcopy(startup); failed["scheduler"]["refresh_status"].update(state="error", last_error_present=True)
        with self.assertRaises(controls.SchedulerError): step(failed, state)
        changed = copy.deepcopy(startup); changed["scheduler"]["overlap_mutexes"][0]["owner_sha256"] = "b" * 64
        with self.assertRaises(controls.SchedulerError): step(changed, state)
        malformed = copy.deepcopy(state); malformed["pending"]["startup_deadline_monotonic_ns"] += 20 * 10**9
        with self.assertRaises(controls.SchedulerError): step(startup, malformed)
        running_state, _ = step(snapshot("2026-10-05T00:20:06Z", attempt="2026-10-05T00:20:05Z"), state)
        with self.assertRaises(controls.SchedulerError): step(snapshot("2026-10-05T00:20:07Z", startup=True), running_state)

    def test_fast_startup_completion_requires_success_within_fixed_startup_bound(self):
        state, _ = step(snapshot("2026-10-05T00:20:01Z", startup=True))
        state, receipt = step(snapshot("2026-10-05T00:20:09Z", active=False, success="2026-10-05T00:20:08Z"), state)
        self.assertIsNone(state["pending"])
        self.assertEqual(receipt["transitions"], ["startup_progress_confirmed", "completed", "released"])

    def test_scoped_process_envelope_allows_only_exact_bounded_qbo_work(self):
        def fixture(root, argv, age=11, uid=1000, exe="/usr/bin/php8.2"):
            application = root / "application"
            application.mkdir()
            proc = root / "proc"
            proc.mkdir()
            (proc / "uptime").write_text("1000.0 0.0\n")
            entry = proc / "424242"
            entry.mkdir()
            (entry / "cwd").symlink_to(application)
            (entry / "exe").symlink_to(exe)
            (entry / "cmdline").write_bytes(b"\0".join(x.encode() for x in argv) + b"\0")
            (entry / "status").write_text(f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n")
            fields = ["S"] + ["0"] * 19
            fields[19] = str(round((1000 - age) * 100))
            (entry / "stat").write_text("424242 (php) " + " ".join(fields))
            return application, proc
        payload = snapshot()
        now = controls.timestamp(payload["generated_at_utc"], "fixture")
        valid = ["/usr/bin/php8.2", "artisan", controls.TASK]
        with tempfile.TemporaryDirectory() as temporary:
            app, proc = fixture(Path(temporary), valid)
            result = controls.process_envelope(payload, app, proc_root=proc, ticks_per_second=100, wall_time=now)
            self.assertEqual(result["processes"][0]["role"], "reviewed_qbo_worker")
            self.assertFalse(result["environments_read"])
        # The mutex may be acquired at second 14, with its legitimate child
        # starting at second 20. Bind that start to the acquisition, not just
        # the original cron grace. A child outside the ten-second grace fails.
        for at, age, permitted in (("2026-10-05T00:20:23Z", 3, True),
                                   ("2026-10-05T00:20:28Z", 3, False),
                                   ("2026-10-05T00:20:23Z", 20, False)):
            late_slot = snapshot(at, start="2026-10-05T00:20:14Z", attempt="2026-10-05T00:20:22Z")
            with tempfile.TemporaryDirectory() as temporary:
                app, proc = fixture(Path(temporary), valid, age=age)
                args = dict(proc_root=proc, ticks_per_second=100, wall_time=controls.timestamp(at, "test"))
                if permitted:
                    self.assertEqual(controls.process_envelope(late_slot, app, **args)["processes"][0]["role"], "reviewed_qbo_worker")
                    self.assertTrue(step(late_slot)[1]["active"])
                else:
                    with self.assertRaises(controls.SchedulerError): controls.process_envelope(late_slot, app, **args)
        with tempfile.TemporaryDirectory() as temporary:
            app, proc = fixture(Path(temporary), ["/usr/bin/php8.2", "artisan", "schedule:run"], age=4)
            late_slot = snapshot("2026-10-05T00:20:18Z", start="2026-10-05T00:20:14Z", attempt="2026-10-05T00:20:17Z")
            self.assertEqual(controls.process_envelope(late_slot, app, proc_root=proc, ticks_per_second=100,
                wall_time=controls.timestamp(late_slot["generated_at_utc"], "test"))["processes"][0]["role"], "reviewed_qbo_only_dispatcher")
        cases = [(valid, 121, 1000, "/usr/bin/php8.2"), (valid, 11, 0, "/usr/bin/php8.2"),
                 (valid, 11, 1000, "/usr/bin/php8.3"),
                 (["/usr/bin/php8.2", "artisan", "stripe:sync-payouts"], 11, 1000, "/usr/bin/php8.2"),
                 (["/usr/bin/php8.2", "artisan", "accounting:reconcile-stripe-holding"], 11, 1000, "/usr/bin/php8.2"),
                 (["/usr/bin/php8.2", "artisan", controls.TASK, "--status"], 11, 1000, "/usr/bin/php8.2")]
        for argv, age, uid, exe in cases:
            with tempfile.TemporaryDirectory() as temporary:
                app, proc = fixture(Path(temporary), argv, age, uid, exe)
                with self.assertRaises(controls.SchedulerError):
                    controls.process_envelope(payload, app, proc_root=proc, ticks_per_second=100, wall_time=now)
        mutex = "framework/schedule-" + hashlib.sha1(b"*/10 * * * *php artisan qbo:refresh-admin-cache").hexdigest()
        self.assertEqual(hashlib.sha256(mutex.encode()).hexdigest(), controls.MUTEX_SHA256)
        for code in ("0", "1"):
            with tempfile.TemporaryDirectory() as temporary:
                app, proc = fixture(Path(temporary), ["/usr/bin/php8.2", "artisan", "schedule:finish", mutex, code], age=1)
                completed = snapshot("2026-10-05T00:20:13Z", active=False, success="2026-10-05T00:20:12Z")
                if code == "0":
                    self.assertEqual(controls.process_envelope(completed, app, proc_root=proc, ticks_per_second=100, wall_time=now + 2)["processes"][0]["role"], "reviewed_qbo_successful_finish")
                else:
                    with self.assertRaises(controls.SchedulerError):
                        controls.process_envelope(completed, app, proc_root=proc, ticks_per_second=100, wall_time=now + 2)

    def test_dispatcher_is_allowed_only_for_qbo_only_schedule_slot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "application"; app.mkdir()
            proc = root / "proc"; proc.mkdir()
            (proc / "uptime").write_text("1000.0 0\n")
            entry = proc / "424242"; entry.mkdir()
            (entry / "cwd").symlink_to(app); (entry / "exe").symlink_to("/usr/bin/php8.2")
            (entry / "cmdline").write_bytes(b"php\0artisan\0schedule:run\0")
            (entry / "status").write_text("Uid:\t1000\t1000\t1000\t1000\n")
            fields = ["S"] + ["0"] * 19; fields[19] = "99900"
            (entry / "stat").write_text("424242 (php) " + " ".join(fields))
            for at in ("2026-10-05T00:20:01Z", "2026-10-05T01:30:01Z", "2026-10-05T01:00:01Z", "2026-10-05T06:30:01Z", "2026-12-10T07:30:01Z", "2026-11-01T06:30:01Z", "2026-11-01T07:30:01Z", "2026-10-05T00:21:01Z"):
                payload = snapshot(at, start=at[:-3] + "00Z")
                if at in {"2026-10-05T00:20:01Z", "2026-10-05T01:30:01Z"}:
                    self.assertEqual(controls.process_envelope(payload, app, proc_root=proc, ticks_per_second=100, wall_time=controls.timestamp(at, "test"))["processes"][0]["role"], "reviewed_qbo_only_dispatcher")
                else:
                    with self.assertRaises(controls.SchedulerError):
                        controls.process_envelope(payload, app, proc_root=proc, ticks_per_second=100, wall_time=controls.timestamp(at, "test"))

    def test_missing_or_malformed_deployment_scheduler_binding_fails_closed(self):
        for state in ({}, {"scheduler_policy_sha256": controls.POLICY_SHA256, "scheduler_identity_sha256": "0" * 64}):
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                deploy.atomic_json(directory / "state.json", state)
                with self.assertRaisesRegex(deploy.DeploymentError, "not bound"):
                    deploy.SchedulerGuard(directory).observe(snapshot(), "monitor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
