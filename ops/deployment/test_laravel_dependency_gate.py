from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


DEPLOYMENT_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOYMENT_DIRECTORY))
import laravel_dependency_gate as GATE  # noqa: E402
import rehearse_laravel_dependency_gate as REHEARSAL  # noqa: E402


class LaravelDependencyGatePolicyTest(unittest.TestCase):
    def test_reviewed_gate_identity_and_metadata_are_frozen(self) -> None:
        self.assertEqual(
            "94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03",
            GATE.sha256_bytes(GATE.MAINTENANCE_GATE_BYTES),
        )
        self.assertEqual(
            {"kind": "file", "mode": 0o644, "uid": 1000, "gid": 1000},
            GATE.reviewed_front_controller_metadata(),
        )
        description = GATE.describe()
        self.assertTrue(description["recovery_uses_actual_identity_and_history"])
        self.assertEqual("origin_loopback", description["origin_route"])
        self.assertEqual("public_cloudflare", description["public_route"])


class LaravelDependencyGateUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.constants = patch.multiple(
            GATE,
            EXPECTED_APP_UID=os.geteuid(),
            EXPECTED_APP_GID=os.getegid(),
        )
        self.constants.start()
        self.temporary = tempfile.TemporaryDirectory(prefix="buy-dtf-gate-unit-")
        root = Path(self.temporary.name)
        self.application = root / "application"
        self.public = self.application / "public"
        self.evidence = root / "evidence"
        self.public.mkdir(parents=True)
        self.evidence.mkdir(mode=0o700)
        self.front = self.public / "index.php"
        self.original = b"<?php echo 'unit-original';\n"
        self.front.write_bytes(self.original)
        os.chmod(self.front, 0o644)
        self.original_sha256 = GATE.file_identity(self.front)["sha256"]
        self.backup = self.evidence / "front-controller-before.php"
        self.backup.write_bytes(self.original)
        os.chmod(self.backup, 0o600)
        self.state_path = self.evidence / "state.json"
        self.state: dict[str, object] = {
            "status": "unit",
            **GATE.initial_gate_state(),
            "dependency_mutation_started": False,
        }
        GATE.write_state(self.state_path, self.state)
        self.context = GATE.GateContext(
            application_root=self.application,
            front_controller=self.front,
            state_path=self.state_path,
            evidence_directory=self.evidence,
            original_backup=self.backup,
            original_sha256=self.original_sha256,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()
        self.constants.stop()

    @staticmethod
    def probe(route: str, status: int = 503) -> dict[str, object]:
        return {
            "route": route,
            "status": status,
            "header_verified": status == 503,
            "sentinel_verified": status == 503,
        }

    def health(self) -> dict[str, object]:
        identity = GATE.file_identity(self.front)
        if identity["sha256"] != self.original_sha256:
            raise GATE.GateError("unit health saw wrong front controller")
        return {"healthy": True, "front_controller": identity}

    def install(
        self,
        operation: str,
        *,
        origin_status: int = 503,
        public_status: int = 503,
        fault=None,
    ) -> dict[str, object]:
        return GATE.install_static_gate(
            context=self.context,
            state=self.state,
            operation=operation,
            origin_probe=lambda: self.probe(GATE.ORIGIN_ROUTE, origin_status),
            public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, public_status),
            restored_health_probe=self.health,
            fault_injector=fault,
        )

    def restore(self, operation: str) -> dict[str, object]:
        return GATE.restore_front_controller_exact(
            context=self.context,
            state=self.state,
            operation=operation,
            receipt_name=f"{operation}-receipt.json",
        )

    def test_success_persists_pending_installed_verified_then_exact_restore(self) -> None:
        order: list[str] = []
        result = GATE.install_static_gate(
            context=self.context,
            state=self.state,
            operation="success",
            origin_probe=lambda: order.append(GATE.ORIGIN_ROUTE)
            or self.probe(GATE.ORIGIN_ROUTE),
            public_probe=lambda: order.append(GATE.PUBLIC_ROUTE)
            or self.probe(GATE.PUBLIC_ROUTE),
            restored_health_probe=self.health,
        )
        self.assertEqual([GATE.ORIGIN_ROUTE, GATE.PUBLIC_ROUTE], order)
        self.assertEqual(GATE.EXPECTED_GATE_SHA256, result["sha256"])
        persisted = GATE.load_state(self.state_path)
        self.assertEqual(
            ["replacement_pending", "installed", "verified"],
            [item["phase"] for item in persisted["front_controller_transitions"]],
        )
        receipt = self.restore("success-restore")
        self.assertTrue(receipt["exact_original_restored"])
        self.assertEqual(self.original_sha256, GATE.file_identity(self.front)["sha256"])

    def test_pre_mutation_origin_failure_restores_and_health_checks(self) -> None:
        with self.assertRaisesRegex(GATE.GateError, "normal health passed"):
            self.install("origin-failure", origin_status=500)
        persisted = GATE.load_state(self.state_path)
        failure = json.loads(
            Path(persisted["gate_failure_receipt"]).read_text(encoding="utf-8")
        )
        self.assertTrue(failure["original_restoration_performed"])
        self.assertEqual("pass", failure["post_restoration_health"]["status"])
        self.assertEqual(self.original_sha256, GATE.file_identity(self.front)["sha256"])
        self.assertFalse(persisted["static_gate_active"])

    def test_post_mutation_public_failure_retains_gate_and_permits_rollback(self) -> None:
        self.state["dependency_mutation_started"] = True
        GATE.write_state(self.state_path, self.state)
        containment = GATE.establish_rollback_containment(
            context=self.context,
            state=self.state,
            operation="rollback-entry",
            origin_probe=lambda: self.probe(GATE.ORIGIN_ROUTE),
            public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, 522),
            restored_health_probe=self.health,
        )
        self.assertFalse(containment["http_verified"])
        self.assertTrue(containment["rollback_may_continue_boot_independently"])
        self.assertEqual(GATE.EXPECTED_GATE_SHA256, GATE.file_identity(self.front)["sha256"])
        persisted = GATE.load_state(self.state_path)
        self.assertTrue(persisted["containment_active"])
        self.assertTrue(persisted["static_gate_active"])

    def test_swap_before_installed_interruption_uses_actual_live_identity(self) -> None:
        def interrupt(stage: str) -> None:
            if stage == "after_replace_before_installed":
                raise GATE.GateInterruption(stage)

        with self.assertRaises(GATE.GateInterruption):
            self.install("interrupted", fault=interrupt)
        self.state = GATE.load_state(self.state_path)
        self.state["static_gate_active"] = False
        GATE.write_state(self.state_path, self.state)
        decision = GATE.recovery_decision(context=self.context, state=self.state)
        self.assertEqual("restore_original", decision["action"])
        self.assertTrue(decision["persisted_gate_boolean_ignored"])
        self.assertEqual(GATE.EXPECTED_GATE_SHA256, decision["live"]["sha256"])
        self.restore("interrupted-recovery")

    def test_unknown_live_bytes_are_rejected_without_overwrite(self) -> None:
        unknown = b"<?php echo 'unknown';\n"
        self.front.write_bytes(unknown)
        os.chmod(self.front, 0o644)
        unknown_sha256 = GATE.file_identity(self.front)["sha256"]
        with self.assertRaisesRegex(GATE.GateError, "unknown front-controller bytes"):
            self.install("unknown")
        self.assertEqual(unknown_sha256, GATE.file_identity(self.front)["sha256"])

    def test_recovery_rejects_inconsistent_transition_history(self) -> None:
        self.install("history")
        self.state = GATE.load_state(self.state_path)
        self.state["front_controller_transition"] = dict(
            self.state["front_controller_transitions"][0]
        )
        with self.assertRaisesRegex(GATE.GateError, "inconsistent durable"):
            GATE.recovery_decision(context=self.context, state=self.state)

    def test_all_dependency_intent_and_completion_fields_are_fail_closed(self) -> None:
        for field in GATE.DEPENDENCY_MUTATION_FIELDS:
            with self.subTest(field=field):
                self.assertTrue(GATE.dependency_mutation_has_started({field: True}))
        self.assertFalse(GATE.dependency_mutation_has_started({}))

    def test_exclusive_receipts_refuse_overwrite(self) -> None:
        path = self.evidence / "exclusive.json"
        GATE.write_new_json(path, {"one": 1})
        with self.assertRaisesRegex(GATE.GateError, "Refusing to overwrite"):
            GATE.write_new_json(path, {"two": 2})
        self.assertEqual({"one": 1}, json.loads(path.read_text(encoding="utf-8")))

    def test_origin_and_public_curl_routes_are_distinct(self) -> None:
        fake_curl = Path(self.temporary.name) / "curl"
        fake_curl.write_bytes(b"fake curl\n")
        os.chmod(fake_curl, 0o755)
        commands: list[list[str]] = []

        def fake_run(command, **_kwargs):
            commands.append(command)
            headers = Path(command[command.index("--dump-header") + 1])
            body = Path(command[command.index("--output") + 1])
            headers.write_text(
                "HTTP/1.1 503 Service Unavailable\r\n"
                "X-BuyDTF-Dependency-Maintenance: static-v2\r\n\r\n",
                encoding="utf-8",
            )
            body.write_text(GATE.MAINTENANCE_GATE_SENTINEL, encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="503", stderr="")

        with patch.object(GATE.subprocess, "run", side_effect=fake_run):
            origin = GATE.gate_origin_probe(
                evidence_directory=self.evidence,
                operation="origin",
                public_url="https://buy-dtf.com/",
                cwd=self.application,
                curl_path=fake_curl,
            )
            public = GATE.gate_public_probe(
                evidence_directory=self.evidence,
                operation="public",
                public_url="https://buy-dtf.com/",
                cwd=self.application,
                curl_path=fake_curl,
            )
        self.assertTrue(GATE.gate_probe_passed(origin, GATE.ORIGIN_ROUTE))
        self.assertTrue(GATE.gate_probe_passed(public, GATE.PUBLIC_ROUTE))
        self.assertIn("--resolve", commands[0])
        self.assertIn("--noproxy", commands[0])
        self.assertNotIn("--resolve", commands[1])
        self.assertNotIn("--noproxy", commands[1])


@unittest.skipUnless(
    os.name == "posix"
    and os.geteuid() == 0
    and Path("/usr/bin/setpriv").is_file()
    and Path("/usr/bin/php").is_file(),
    "root-only UID/GID 33 gate rehearsal",
)
class LaravelDependencyGateRootRehearsalTest(unittest.TestCase):
    def test_umask_077_uid33_and_transition_rehearsal(self) -> None:
        result = REHEARSAL.run_rehearsal(Path("/tmp"))
        self.assertEqual("pass", result["status"])
        self.assertEqual(26, result["scenario_count"])
        self.assertTrue(result["mode_0600_negative_control"]["read_denied"])
        self.assertTrue(result["all_reopenable_scenarios_restored_exact_original"])
        self.assertTrue(result["unknown_bytes_rejected_without_overwrite"])
        self.assertIn("failure-during-origin-verification", result["scenarios"])
        self.assertIn("failure-during-public-verification", result["scenarios"])
        self.assertIn("interruption-after-swap-before-installed", result["scenarios"])
        self.assertIn("stale-boolean-live-gate-recovery", result["scenarios"])
        self.assertIn("post-mutation-public-failure-containment", result["scenarios"])
        self.assertIn("restore-interruption-after-exact-verification", result["scenarios"])
        self.assertIn("restore-original-already-present-interruption", result["scenarios"])


if __name__ == "__main__":
    unittest.main()
