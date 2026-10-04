from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch


DEPLOYMENT_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOYMENT_DIRECTORY))
import laravel_dependency_gate as GATE  # noqa: E402
import rehearse_laravel_dependency_gate as REHEARSAL  # noqa: E402


def reviewed_fpm_probe(
    *,
    validate_timestamps: bool = True,
    revalidate_freq: int = 2,
    file_update_protection: int = 2,
) -> dict[str, object]:
    normalized: dict[str, bool | int] = {
        "opcache.enable": True,
        "opcache.validate_timestamps": validate_timestamps,
        "opcache.revalidate_freq": revalidate_freq,
        "opcache.file_update_protection": file_update_protection,
    }
    return {
        "artifact": "buy-dtf-php-fpm-opcache-probe-v1",
        "sapi": "fpm-fcgi",
        "php_version": "8.2.30",
        "directives": {
            name: {"raw": str(int(value)), "normalized": value}
            for name, value in normalized.items()
        },
        "opcache_configuration_directives": normalized,
    }


class FakeClock:
    """Deterministic monotonic and wall clocks for gate tests."""

    def __init__(self) -> None:
        self.nanoseconds = 30_000_000_000
        self.wall_epoch = 1_700_000_000.0
        self.sleep_calls: list[float] = []

    def monotonic_ns(self) -> int:
        return self.nanoseconds

    def wall_clock(self) -> float:
        return self.wall_epoch + (self.nanoseconds - 30_000_000_000) / 1_000_000_000

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.nanoseconds += round(seconds * 1_000_000_000)


class LaravelDependencyGatePolicyTest(unittest.TestCase):
    def test_reviewed_gate_identity_and_metadata_are_frozen(self) -> None:
        self.assertEqual(
            "d18fc1520808b10814a6e86ef41ce22f9c6d326318f96fc3db78aed153199ea4",
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

    def test_reviewed_fpm_values_include_two_revalidation_windows(self) -> None:
        policy = GATE.derive_opcache_revalidation_policy(reviewed_fpm_probe())
        self.assertEqual(4, policy["complete_revalidation_interval_seconds"])
        self.assertEqual(2, policy["second_revalidation_window_seconds"])
        self.assertEqual(7, policy["minimum_wait_seconds"])
        GATE.validate_opcache_revalidation_policy(policy)

        floor_policy = GATE.derive_opcache_revalidation_policy(
            reviewed_fpm_probe(revalidate_freq=0, file_update_protection=0)
        )
        self.assertEqual(5, floor_policy["minimum_wait_seconds"])

    def test_larger_interval_derives_a_strictly_larger_safe_wait(self) -> None:
        policy = GATE.derive_opcache_revalidation_policy(
            reviewed_fpm_probe(revalidate_freq=12, file_update_protection=3)
        )
        self.assertEqual(15, policy["complete_revalidation_interval_seconds"])
        self.assertEqual(12, policy["second_revalidation_window_seconds"])
        self.assertEqual(28, policy["minimum_wait_seconds"])

    def test_disabled_timestamp_validation_is_rejected(self) -> None:
        with self.assertRaisesRegex(GATE.GateError, "validate_timestamps"):
            GATE.derive_opcache_revalidation_policy(
                reviewed_fpm_probe(validate_timestamps=False)
            )

    def test_unreviewed_or_under_waiting_policy_is_rejected(self) -> None:
        policy = GATE.derive_opcache_revalidation_policy(reviewed_fpm_probe())
        policy["revalidate_freq_seconds"] = 20
        with self.assertRaisesRegex(GATE.GateError, "safely exceed"):
            GATE.validate_opcache_revalidation_policy(policy)

        wrong_sapi = reviewed_fpm_probe()
        wrong_sapi["sapi"] = "cli"
        with self.assertRaisesRegex(GATE.GateError, "PHP-FPM SAPI"):
            GATE.derive_opcache_revalidation_policy(wrong_sapi)

    def test_ini_and_opcache_configuration_must_agree(self) -> None:
        probe = reviewed_fpm_probe()
        probe["opcache_configuration_directives"] = dict(
            probe["opcache_configuration_directives"]
        )
        probe["opcache_configuration_directives"]["opcache.revalidate_freq"] = 60
        with self.assertRaisesRegex(GATE.GateError, "differ"):
            GATE.derive_opcache_revalidation_policy(probe)


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
        self.clock = FakeClock()
        self.policy = GATE.derive_opcache_revalidation_policy(reviewed_fpm_probe())
        self.context = GATE.GateContext(
            application_root=self.application,
            front_controller=self.front,
            state_path=self.state_path,
            evidence_directory=self.evidence,
            original_backup=self.backup,
            original_sha256=self.original_sha256,
            opcache_policy=self.policy,
            sleep=self.clock.sleep,
            monotonic_ns=self.clock.monotonic_ns,
            wall_clock=self.clock.wall_clock,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()
        self.constants.stop()

    @staticmethod
    def probe(route: str, token: str, status: int = 503) -> dict[str, object]:
        return {
            "route": route,
            "status": status,
            "header_verified": status == 503,
            "sentinel_verified": status == 503,
            "cache_buster_verified": status == 503,
            "route_identity_verified": status == 503,
            "cache_buster_sha256": GATE.sha256_bytes(token.encode("utf-8")),
            "request_url_sha256": GATE.sha256_bytes(
                f"https://buy-dtf.com/?ops_gate={token}".encode("utf-8")
            ),
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
            origin_probe=lambda ordinal: self.probe(
                GATE.ORIGIN_ROUTE,
                f"{operation}-origin-{ordinal}",
                origin_status,
            ),
            public_probe=lambda: self.probe(
                GATE.PUBLIC_ROUTE,
                f"{operation}-public",
                public_status,
            ),
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
            origin_probe=lambda ordinal: order.append(f"{GATE.ORIGIN_ROUTE}-{ordinal}")
            or self.probe(GATE.ORIGIN_ROUTE, f"success-origin-{ordinal}"),
            public_probe=lambda: order.append(GATE.PUBLIC_ROUTE)
            or self.probe(GATE.PUBLIC_ROUTE, "success-public"),
            restored_health_probe=self.health,
        )
        self.assertEqual(
            [f"{GATE.ORIGIN_ROUTE}-1", f"{GATE.ORIGIN_ROUTE}-2", GATE.PUBLIC_ROUTE],
            order,
        )
        self.assertEqual(GATE.EXPECTED_GATE_SHA256, result["sha256"])
        persisted = GATE.load_state(self.state_path)
        self.assertEqual(
            ["replacement_pending", "installed", "revalidation_wait_complete", "verified"],
            [item["phase"] for item in persisted["front_controller_transitions"]],
        )
        self.assertEqual(1, len(persisted["front_controller_revalidation_waits"]))
        wait_record = persisted["front_controller_revalidation_waits"][0]
        expected_wait_seconds = self.policy["minimum_wait_seconds"]
        expected_wait_ns = expected_wait_seconds * 1_000_000_000
        self.assertGreaterEqual(
            wait_record["elapsed_monotonic_ns"],
            expected_wait_ns,
        )
        self.assertEqual(expected_wait_seconds, wait_record["configured_wait_seconds"])
        self.assertEqual(
            wait_record["start_monotonic_ns"] + expected_wait_ns,
            wait_record["deadline_monotonic_ns"],
        )
        self.assertEqual(wait_record["identity_before"], wait_record["identity_after"])
        self.assertTrue(Path(wait_record["receipt"]["path"]).is_file())
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
            origin_probe=lambda ordinal: self.probe(
                GATE.ORIGIN_ROUTE, f"rollback-origin-{ordinal}"
            ),
            public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, "rollback-public", 522),
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

    def test_v3_immediate_probe_regression_is_blocked_by_monotonic_wait(self) -> None:
        first_probe_at: list[int] = []

        def origin(ordinal: int) -> dict[str, object]:
            first_probe_at.append(self.clock.monotonic_ns())
            self.assertGreaterEqual(
                sum(self.clock.sleep_calls),
                self.policy["minimum_wait_seconds"],
            )
            persisted = GATE.load_state(self.state_path)
            self.assertEqual(
                "revalidation_wait_complete",
                persisted["front_controller_transition"]["phase"],
            )
            return self.probe(GATE.ORIGIN_ROUTE, f"regression-origin-{ordinal}")

        GATE.install_static_gate(
            context=self.context,
            state=self.state,
            operation="v3-immediate-probe-regression",
            origin_probe=origin,
            public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, "regression-public"),
            restored_health_probe=self.health,
        )
        first_allowed_probe_ns = (
            30_000_000_000
            + self.policy["minimum_wait_seconds"] * 1_000_000_000
        )
        self.assertEqual([first_allowed_probe_ns, first_allowed_probe_ns], first_probe_at)

    def test_wall_clock_regression_cannot_shorten_monotonic_wait(self) -> None:
        wall_values = iter([1_700_000_000.0, 1_699_999_000.0])
        context = replace(self.context, wall_clock=lambda: next(wall_values))
        result = GATE.install_static_gate(
            context=context,
            state=self.state,
            operation="wall-clock-regression",
            origin_probe=lambda ordinal: self.probe(
                GATE.ORIGIN_ROUTE, f"wall-origin-{ordinal}"
            ),
            public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, "wall-public"),
            restored_health_probe=self.health,
        )
        wait = result["opcache_revalidation_wait"]
        self.assertEqual(
            self.policy["minimum_wait_seconds"] * 1_000_000_000,
            wait["elapsed_monotonic_ns"],
        )
        self.assertGreater(wait["started_at_utc"], wait["ended_at_utc"])

    def test_interruption_after_elapsed_wait_before_receipt_is_retryable(self) -> None:
        def interrupt(stage: str) -> None:
            if stage == "after_revalidation_elapsed_before_receipt":
                raise GATE.GateInterruption(stage)

        with self.assertRaises(GATE.GateInterruption):
            self.install("elapsed-before-receipt", fault=interrupt)

        self.state = GATE.load_state(self.state_path)
        waits = self.state["front_controller_revalidation_waits"]
        self.assertEqual(1, len(waits))
        self.assertEqual("waiting", waits[0]["status"])
        self.assertNotIn("elapsed_monotonic_ns", waits[0])
        self.assertNotIn("receipt", waits[0])
        self.assertFalse(
            (
                self.evidence
                / "elapsed-before-receipt-opcache-revalidation-wait-0001-receipt.json"
            ).exists()
        )
        self.assertEqual(
            "restore_original",
            GATE.recovery_decision(context=self.context, state=self.state)["action"],
        )

        recovery = self.restore("elapsed-before-receipt-recovery")
        self.assertTrue(recovery["exact_original_restored"])
        recovered_waits = GATE.load_state(self.state_path)[
            "front_controller_revalidation_waits"
        ]
        self.assertEqual(["waiting", "complete"], [wait["status"] for wait in recovered_waits])
        self.assertEqual(
            [self.policy["minimum_wait_seconds"]] * 2,
            self.clock.sleep_calls,
        )
        self.assertTrue(Path(recovered_waits[-1]["receipt"]["path"]).is_file())

    def test_interruption_after_wait_receipt_before_state_link_is_retryable(self) -> None:
        def interrupt(stage: str) -> None:
            if stage == "after_revalidation_receipt_created":
                raise GATE.GateInterruption(stage)

        with self.assertRaises(GATE.GateInterruption):
            self.install("receipt-before-state", fault=interrupt)

        orphan = (
            self.evidence
            / "receipt-before-state-opcache-revalidation-wait-0001-receipt.json"
        )
        self.assertTrue(orphan.is_file())
        self.assertEqual(
            "complete",
            json.loads(orphan.read_text(encoding="utf-8"))["status"],
        )
        self.state = GATE.load_state(self.state_path)
        self.assertEqual(
            "waiting",
            self.state["front_controller_revalidation_waits"][0]["status"],
        )
        self.assertNotIn("receipt", self.state["front_controller_revalidation_waits"][0])
        self.assertEqual(
            "restore_original",
            GATE.recovery_decision(context=self.context, state=self.state)["action"],
        )

        repeated = GATE.wait_for_front_controller_revalidation(
            context=self.context,
            state=self.state,
            operation="receipt-before-state",
            target_sha256=GATE.EXPECTED_GATE_SHA256,
            target_metadata=GATE.reviewed_front_controller_metadata(),
        )
        recovered_waits = GATE.load_state(self.state_path)[
            "front_controller_revalidation_waits"
        ]
        self.assertEqual(
            ["waiting", "complete"],
            [wait["status"] for wait in recovered_waits],
        )
        self.assertEqual(
            [self.policy["minimum_wait_seconds"]] * 2,
            self.clock.sleep_calls,
        )
        self.assertNotEqual(str(orphan), repeated["path"])
        self.assertEqual(
            "receipt-before-state-opcache-revalidation-wait-0002-receipt.json",
            Path(repeated["path"]).name,
        )

    def test_interrupted_emergency_containment_wait_restarts_full_wait(self) -> None:
        self.state["dependency_mutation_started"] = True
        GATE.write_state(self.state_path, self.state)

        def interrupt(stage: str) -> None:
            if stage == "after_revalidation_sleep":
                raise GATE.GateInterruption(stage)

        with self.assertRaises(GATE.GateInterruption):
            GATE.establish_rollback_containment(
                context=self.context,
                state=self.state,
                operation="emergency-interrupted",
                origin_probe=lambda ordinal: self.probe(
                    GATE.ORIGIN_ROUTE,
                    f"emergency-interrupted-origin-{ordinal}",
                ),
                public_probe=lambda: self.probe(
                    GATE.PUBLIC_ROUTE,
                    "emergency-interrupted-public",
                ),
                restored_health_probe=self.health,
                fault_injector=interrupt,
            )

        self.state = GATE.load_state(self.state_path)
        self.assertEqual(
            "waiting",
            self.state["front_controller_revalidation_waits"][0]["status"],
        )
        recovered = GATE.establish_rollback_containment(
            context=self.context,
            state=self.state,
            operation="emergency-retry",
            origin_probe=lambda ordinal: self.probe(
                GATE.ORIGIN_ROUTE,
                f"emergency-retry-origin-{ordinal}",
            ),
            public_probe=lambda: self.probe(
                GATE.PUBLIC_ROUTE,
                "emergency-retry-public",
            ),
            restored_health_probe=self.health,
        )
        self.assertTrue(recovered["http_verified"])
        waits = GATE.load_state(self.state_path)["front_controller_revalidation_waits"]
        self.assertEqual(["waiting", "complete"], [item["status"] for item in waits])
        self.assertEqual(
            [self.policy["minimum_wait_seconds"]] * 2,
            self.clock.sleep_calls,
        )

    def test_wait_is_shared_by_install_reassert_containment_restore_and_recovery(self) -> None:
        self.install("initial-install")
        self.install("gate-reassertion")
        self.restore("pre-mutation-restoration")

        self.state["dependency_mutation_started"] = True
        GATE.write_state(self.state_path, self.state)
        GATE.retain_static_gate_exact(
            context=self.context,
            state=self.state,
            operation="rollback-containment-install",
        )
        GATE.retain_static_gate_exact(
            context=self.context,
            state=self.state,
            operation="rollback-containment-reassertion",
        )
        self.state["dependency_mutation_started"] = False
        GATE.write_state(self.state_path, self.state)
        self.state = GATE.load_state(self.state_path)
        self.state["static_gate_active"] = False
        GATE.write_state(self.state_path, self.state)
        self.assertEqual(
            "restore_original",
            GATE.recovery_decision(context=self.context, state=self.state)["action"],
        )
        self.restore("recovery-restoration")

        waits = GATE.load_state(self.state_path)["front_controller_revalidation_waits"]
        operations = [record["operation"] for record in waits]
        self.assertEqual(
            [
                "initial-install",
                "gate-reassertion",
                "pre-mutation-restoration",
                "rollback-containment-install-exact-containment-install",
                "rollback-containment-reassertion",
                "recovery-restoration",
            ],
            operations,
        )
        self.assertTrue(all(record["status"] == "complete" for record in waits))
        expected_wait_ns = self.policy["minimum_wait_seconds"] * 1_000_000_000
        self.assertTrue(
            all(record["elapsed_monotonic_ns"] >= expected_wait_ns for record in waits)
        )
        self.assertEqual(6, len(self.clock.sleep_calls))

    def test_invalid_policy_rejects_before_front_controller_mutation(self) -> None:
        invalid = dict(self.policy)
        invalid["validate_timestamps"] = False
        invalid_context = GATE.GateContext(
            application_root=self.application,
            front_controller=self.front,
            state_path=self.state_path,
            evidence_directory=self.evidence,
            original_backup=self.backup,
            original_sha256=self.original_sha256,
            opcache_policy=invalid,
            sleep=self.clock.sleep,
            monotonic_ns=self.clock.monotonic_ns,
            wall_clock=self.clock.wall_clock,
        )
        with self.assertRaisesRegex(GATE.GateError, "timestamp validation is disabled"):
            GATE.install_static_gate(
                context=invalid_context,
                state=self.state,
                operation="invalid-policy",
                origin_probe=lambda ordinal: self.probe(
                    GATE.ORIGIN_ROUTE, f"invalid-origin-{ordinal}"
                ),
                public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, "invalid-public"),
                restored_health_probe=self.health,
            )
        self.assertEqual(self.original_sha256, GATE.file_identity(self.front)["sha256"])
        self.assertEqual([], GATE.load_state(self.state_path)["front_controller_transitions"])

    def test_duplicate_probe_nonce_fails_closed_and_restores_original(self) -> None:
        duplicate = "same-cache-buster"
        with self.assertRaisesRegex(GATE.GateError, "normal health passed"):
            GATE.install_static_gate(
                context=self.context,
                state=self.state,
                operation="duplicate-probe",
                origin_probe=lambda _ordinal: self.probe(GATE.ORIGIN_ROUTE, duplicate),
                public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, "unique-public"),
                restored_health_probe=self.health,
            )
        self.assertEqual(self.original_sha256, GATE.file_identity(self.front)["sha256"])
        persisted = GATE.load_state(self.state_path)
        receipt = json.loads(
            Path(persisted["gate_failure_receipt"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            GATE.sha256_bytes(
                b"Direct-origin static-gate probes reused a cache buster."
            ),
            receipt["failure_message_sha256"],
        )

    def test_identity_drift_between_origin_probes_fails_closed(self) -> None:
        def origin(ordinal: int) -> dict[str, object]:
            result = self.probe(GATE.ORIGIN_ROUTE, f"drift-origin-{ordinal}")
            if ordinal == 1:
                self.front.write_bytes(self.original)
                os.chmod(self.front, 0o644)
            return result

        with self.assertRaisesRegex(GATE.GateError, "normal health passed"):
            GATE.install_static_gate(
                context=self.context,
                state=self.state,
                operation="identity-drift",
                origin_probe=origin,
                public_probe=lambda: self.probe(GATE.PUBLIC_ROUTE, "drift-public"),
                restored_health_probe=self.health,
            )
        self.assertEqual(self.original_sha256, GATE.file_identity(self.front)["sha256"])
        persisted = GATE.load_state(self.state_path)
        receipt = json.loads(
            Path(persisted["gate_failure_receipt"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            GATE.sha256_bytes(
                b"Static-gate identity changed between direct-origin probes."
            ),
            receipt["failure_message_sha256"],
        )

    def test_origin_and_public_curl_routes_are_distinct(self) -> None:
        fake_curl = Path(self.temporary.name) / "curl"
        fake_curl.write_bytes(b"fake curl\n")
        os.chmod(fake_curl, 0o755)
        commands: list[list[str]] = []
        environments: list[dict[str, str]] = []
        private_cookie_values = [secrets.token_hex(24), secrets.token_hex(24)]
        response_variant = "valid"

        def fake_run(command, **kwargs):
            commands.append(command)
            environments.append(dict(kwargs["env"]))
            headers = Path(command[command.index("--dump-header") + 1])
            body = Path(command[command.index("--output") + 1])
            request_url = command[-1]
            cache_buster = parse_qs(urlsplit(request_url).query)["ops_gate"][0]
            gate_headers = "X-BuyDTF-Dependency-Maintenance: static-v2\r\n"
            probe_header = f"X-BuyDTF-Dependency-Probe: {cache_buster}\r\n"
            if response_variant == "duplicate-gate-header":
                gate_headers += "X-BuyDTF-Dependency-Maintenance: static-v2\r\n"
            if response_variant == "embedded-probe-value":
                probe_header = f"X-BuyDTF-Dependency-Probe: prefix-{cache_buster}\r\n"
            headers.write_text(
                "HTTP/1.1 503 Service Unavailable\r\n"
                + gate_headers
                + probe_header
                + ("Server: cloudflare\r\nCf-Ray: abc123-DFW\r\n" if "--resolve" not in command else "")
                + f"Set-Cookie: laravel_session={private_cookie_values[0]}; Secure\r\n"
                + f"Cookie: remember_web={private_cookie_values[1]}\r\n\r\n",
                encoding="utf-8",
            )
            body_suffix = "-unexpected" if response_variant == "body-suffix" else ""
            body.write_text(
                f"{GATE.MAINTENANCE_GATE_SENTINEL}\n{cache_buster}{body_suffix}",
                encoding="utf-8",
            )
            remote_ip = "127.0.0.1" if "--resolve" in command else "104.16.0.1"
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=f"503\n{remote_ip}\n443\n",
                stderr="",
            )

        hostile_environment = {
            "HOME": str(Path(self.temporary.name) / "hostile-home"),
            "CURL_HOME": str(Path(self.temporary.name) / "hostile-curl-home"),
            "HTTPS_PROXY": "http://127.0.0.1:9999",
            "ALL_PROXY": "http://127.0.0.1:9998",
        }
        with patch.dict(os.environ, hostile_environment, clear=False), patch.object(
            GATE.subprocess, "run", side_effect=fake_run
        ):
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
        self.assertIn("--noproxy", commands[1])
        self.assertEqual("--disable", commands[0][1])
        self.assertEqual("--disable", commands[1][1])
        self.assertEqual([{"LANG": "C", "LC_ALL": "C"}] * 2, environments)
        for operation, result in (("origin", origin), ("public", public)):
            raw_path = self.evidence / f"{operation}.{operation}.headers.txt"
            redacted_path = Path(result["redacted_headers_path"])
            self.assertEqual(0o600, raw_path.stat().st_mode & 0o777)
            self.assertEqual(0o600, redacted_path.stat().st_mode & 0o777)
            raw = raw_path.read_text(encoding="utf-8")
            redacted = redacted_path.read_text(encoding="utf-8")
            for private_value in private_cookie_values:
                self.assertIn(private_value, raw)
                self.assertNotIn(private_value, redacted)
                self.assertNotIn(private_value, json.dumps(result))
                self.assertNotIn(
                    private_value,
                    Path(__file__).read_text(encoding="utf-8"),
                )
            self.assertEqual(2, result["cookie_header_count"])

        for response_variant in (
            "duplicate-gate-header",
            "embedded-probe-value",
            "body-suffix",
        ):
            with self.subTest(response_variant=response_variant):
                with patch.object(GATE.subprocess, "run", side_effect=fake_run):
                    rejected = GATE.gate_origin_probe(
                        evidence_directory=self.evidence,
                        operation=f"reject-{response_variant}",
                        public_url="https://buy-dtf.com/",
                        cwd=self.application,
                        curl_path=fake_curl,
                    )
                self.assertFalse(GATE.gate_probe_passed(rejected, GATE.ORIGIN_ROUTE))

        def public_loopback_run(command, **kwargs):
            result = fake_run(command, **kwargs)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="503\n127.0.0.1\n443\n",
                stderr=result.stderr,
            )

        with patch.object(GATE.subprocess, "run", side_effect=public_loopback_run):
            public_loopback = GATE.gate_public_probe(
                evidence_directory=self.evidence,
                operation="reject-public-loopback",
                public_url="https://buy-dtf.com/",
                cwd=self.application,
                curl_path=fake_curl,
            )
        self.assertFalse(public_loopback["route_identity_verified"])
        self.assertFalse(GATE.gate_probe_passed(public_loopback, GATE.PUBLIC_ROUTE))


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
        self.assertEqual(28, result["scenario_count"])
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
        self.assertIn("timestamp-validation-disabled-rejected", result["scenarios"])
        self.assertIn("v3-immediate-probe-regression", result["scenarios"])
        self.assertGreater(result["shared_monotonic_revalidation_waits_verified"], 0)
        self.assertTrue(result["v3_immediate_probe_regression_blocked"])
        self.assertTrue(
            result["timestamp_validation_disabled_rejected_before_mutation"]
        )


if __name__ == "__main__":
    unittest.main()
