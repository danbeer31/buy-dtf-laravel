#!/usr/bin/env python3
"""Focused, production-free tests for the v3 deployment control wiring."""

from __future__ import annotations

import ast
from contextlib import ExitStack
from contextlib import nullcontext
from contextlib import redirect_stderr
import copy
import importlib.util
import inspect
import io
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/laravel_remember_cookie_dependency_deploy.py"
SPEC = importlib.util.spec_from_file_location(
    "laravel_remember_cookie_dependency_deploy_v3_controls",
    RUNNER_PATH,
)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def state_status_values(function: object) -> list[str]:
    """Return literal values assigned to ``state['status']`` by a function."""

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    values: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        for target in targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Name) or target.value.id != "state":
                continue
            key = target.slice
            if isinstance(key, ast.Constant) and key.value == "status":
                values.append(value.value)
    return values


def database_envelope_pre_source_values(function: object) -> list[bool]:
    """Return literal ``pre_source`` values for all envelope calls in a function."""

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    values: list[bool] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        if not isinstance(called, ast.Name) or called.id != "validate_database_envelope":
            continue
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        value = keywords.get("pre_source")
        if not isinstance(value, ast.Constant) or not isinstance(value.value, bool):
            raise AssertionError("database-envelope call lacks a literal pre_source policy")
        values.append(value.value)
    return values


class LaravelRememberCookieV3ControlTest(unittest.TestCase):
    def test_cutover_cannot_record_success_before_independent_review(self) -> None:
        cutover_statuses = state_status_values(RUNNER.cutover)
        finalize_statuses = state_status_values(RUNNER.finalize_monitor)

        self.assertIn("monitor_analysis_pass_pending_independent_review", cutover_statuses)
        self.assertIn("awaiting_independent_log_review", cutover_statuses)
        self.assertNotIn("success", cutover_statuses)
        self.assertIn("success", finalize_statuses)

        finalize_source = inspect.getsource(RUNNER.finalize_monitor)
        self.assertLess(
            finalize_source.index("validate_independent_review_receipt"),
            finalize_source.index("verify_live_candidate_after_monitor"),
        )
        self.assertLess(
            finalize_source.index("verify_live_candidate_after_monitor"),
            finalize_source.index('state["status"] = "success"'),
        )

    def test_finalize_monitor_cli_is_reachable_with_all_bound_arguments(self) -> None:
        state = Path("/private/deployment-state.json")
        receipt = Path("/private/independent-log-review-receipt.json")
        receipt_sha256 = "a" * 64
        token = "synthetic-finalization-token"
        helper = RUNNER_PATH.with_name("laravel_remember_cookie_runtime_probe.php")

        argv = [
            str(RUNNER_PATH),
            "--finalize-monitor",
            "--state",
            str(state),
            "--independent-review-receipt",
            str(receipt),
            "--independent-review-receipt-sha256",
            receipt_sha256,
            "--approval-token",
            token,
        ]
        with (
            patch.object(sys, "argv", argv),
            patch.object(RUNNER, "require_regular_file", return_value=helper) as require_file,
            patch.object(RUNNER, "deployment_lock", return_value=nullcontext()),
            patch.object(RUNNER, "finalize_monitor") as finalize,
        ):
            self.assertEqual(0, RUNNER.main())

        require_file.assert_called_once_with(helper, RUNNER.RUNTIME_HELPER_SHA256)
        finalize.assert_called_once_with(state, receipt, receipt_sha256, token, helper)

    def test_finalize_monitor_cli_rejects_missing_review_binding_without_dispatch(self) -> None:
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", [str(RUNNER_PATH), "--finalize-monitor"]),
            patch.object(RUNNER, "finalize_monitor") as finalize,
            redirect_stderr(stderr),
        ):
            self.assertEqual(1, RUNNER.main())
        finalize.assert_not_called()
        self.assertIn("independent-review-receipt-sha256", stderr.getvalue())

    def test_cutover_and_rollback_keep_the_pre_source_database_policy(self) -> None:
        functions = (
            RUNNER.cutover,
            RUNNER.rollback_from_state,
            RUNNER.verify_live_candidate_after_monitor,
            RUNNER.verify_recovered_old_live_state,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                values = database_envelope_pre_source_values(function)
                self.assertGreater(len(values), 0)
                self.assertEqual([True] * len(values), values)

    def test_cutover_and_recovery_hash_all_python_control_helpers_before_io(self) -> None:
        helper = Path("/reviewed/runtime-helper.php")
        control_helpers = (
            "require_database_envelope_validator",
            "require_gate_helper",
            "require_log_parser",
        )
        for action, invocation, stop_name in (
            (
                "cutover",
                lambda: RUNNER.cutover(
                    Path("/reviewed/release.json"),
                    "b" * 64,
                    RUNNER.CUTOVER_APPROVAL_TOKEN,
                    helper,
                ),
                "assert_production_baseline",
            ),
            (
                "recover",
                lambda: RUNNER.recover(
                    Path("/reviewed/state.json"),
                    RUNNER.RECOVERY_APPROVAL_TOKEN,
                    helper,
                ),
                "ensure_private_operations_root",
            ),
        ):
            with self.subTest(action=action):
                patches = [patch.object(RUNNER, name) for name in control_helpers]
                with ExitStack() as stack:
                    started = [stack.enter_context(item) for item in patches]
                    with patch.object(
                        RUNNER,
                        stop_name,
                        side_effect=RUNNER.DeploymentError("synthetic stop before filesystem IO"),
                    ):
                        with self.assertRaisesRegex(RUNNER.DeploymentError, "synthetic stop"):
                            invocation()
                    for mocked in started:
                        mocked.assert_called_once_with()

    def test_main_hashes_runtime_php_helper_for_cutover_and_recovery(self) -> None:
        helper = RUNNER_PATH.with_name("laravel_remember_cookie_runtime_probe.php")
        cases = (
            (
                [
                    "--cutover",
                    "--release-receipt",
                    "/private/release.json",
                    "--release-receipt-sha256",
                    "c" * 64,
                    "--approval-token",
                    "synthetic-cutover-token",
                ],
                "cutover",
            ),
            (
                [
                    "--recover",
                    "--state",
                    "/private/state.json",
                    "--approval-token",
                    "synthetic-recovery-token",
                ],
                "recover",
            ),
        )
        for arguments, target in cases:
            with self.subTest(target=target):
                with (
                    patch.object(sys, "argv", [str(RUNNER_PATH), *arguments]),
                    patch.object(
                        RUNNER,
                        "require_regular_file",
                        return_value=helper,
                    ) as require_file,
                    patch.object(RUNNER, "deployment_lock", return_value=nullcontext()),
                    patch.object(RUNNER, target),
                ):
                    self.assertEqual(0, RUNNER.main())
                require_file.assert_called_once_with(helper, RUNNER.RUNTIME_HELPER_SHA256)

    @unittest.skipUnless(
        hasattr(os, "getuid") and os.getuid() == RUNNER.EXPECTED_APP_UID,
        "private log identity check requires the reviewed application UID",
    )
    def test_private_log_validator_rejects_chunk_content_tampering(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-v3-log-chunk-") as temporary:
            root = Path(temporary)
            log = root / "laravel.log"
            log.write_bytes(b"[2026-10-02 23:00:00] production.INFO: baseline\n")
            private = root / "private"
            collector = RUNNER.laravel_log_delta.RotationSafeLaravelLogCollector(
                log,
                private,
            )
            with log.open("ab") as handle:
                handle.write(b"[2026-10-02 23:01:00] production.INFO: healthy\n")
            result = collector.finish()
            paths = self.log_evidence_paths(result)
            RUNNER.validate_private_log_evidence(private, *paths)

            chunk = next(private.glob("segment-*-chunk-*.bin"))
            value = chunk.read_bytes()
            chunk.write_bytes(bytes([value[0] ^ 1]) + value[1:])
            os.chmod(chunk, 0o600)
            with self.assertRaisesRegex(RUNNER.DeploymentError, "chunk content or range"):
                RUNNER.validate_private_log_evidence(private, *paths)

    @unittest.skipUnless(
        hasattr(os, "getuid") and os.getuid() == RUNNER.EXPECTED_APP_UID,
        "private log identity check requires the reviewed application UID",
    )
    def test_private_log_validator_rejects_boundary_context_tampering(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-v3-log-context-") as temporary:
            root = Path(temporary)
            log = root / "laravel.log"
            log.write_bytes(
                b"[2026-10-02 23:00:00] production.ERROR: checkout diagnostic"
            )
            private = root / "private"
            collector = RUNNER.laravel_log_delta.RotationSafeLaravelLogCollector(
                log,
                private,
            )
            with log.open("ab") as handle:
                handle.write(
                    b" continued\n"
                    b"[2026-10-02 23:01:00] production.INFO: healthy\n"
                )
            result = collector.finish()
            paths = self.log_evidence_paths(result)
            RUNNER.validate_private_log_evidence(private, *paths)

            context = next(private.glob("segment-*-analysis-context.bin"))
            value = context.read_bytes()
            context.write_bytes(bytes([value[0] ^ 1]) + value[1:])
            os.chmod(context, 0o600)
            with self.assertRaisesRegex(RUNNER.DeploymentError, "context identity"):
                RUNNER.validate_private_log_evidence(private, *paths)

    def test_invalid_independent_review_receipt_cannot_mutate_or_rollback(self) -> None:
        state_path = Path("/private/deployment-state.json")
        receipt_path = Path("/private/independent-log-review-receipt.json")
        helper = Path("/reviewed/runtime-helper.php")
        state = {
            "status": "awaiting_independent_log_review",
            "independent_log_review": {"binding": {"runner_sha256": "d" * 64}},
        }
        before = copy.deepcopy(state)

        with (
            patch.object(RUNNER, "require_database_envelope_validator"),
            patch.object(RUNNER, "require_gate_helper"),
            patch.object(RUNNER, "require_log_parser"),
            patch.object(
                RUNNER,
                "load_pending_monitor_state",
                return_value=(state, receipt_path),
            ),
            patch.object(RUNNER, "require_regular_file", return_value=receipt_path),
            patch.object(
                RUNNER.laravel_log_delta,
                "validate_independent_review_receipt",
                side_effect=RUNNER.laravel_log_delta.IndependentReviewError(
                    "synthetic binding mismatch"
                ),
            ),
            patch.object(RUNNER, "verify_live_candidate_after_monitor") as verify,
            patch.object(RUNNER, "contain_cutover_failure") as contain,
            patch.object(RUNNER, "rollback_from_state") as rollback,
            patch.object(RUNNER, "write_state") as write_state,
        ):
            with self.assertRaisesRegex(
                RUNNER.DeploymentError,
                "Independent Laravel log review rejected",
            ):
                RUNNER.finalize_monitor(
                    state_path,
                    receipt_path,
                    "e" * 64,
                    RUNNER.FINALIZE_MONITOR_APPROVAL_TOKEN,
                    helper,
                )

        self.assertEqual(before, state)
        verify.assert_not_called()
        contain.assert_not_called()
        rollback.assert_not_called()
        write_state.assert_not_called()

    def test_valid_independent_review_and_live_candidate_proof_finalize_success(self) -> None:
        state_path = Path("/private/deployment-state.json")
        receipt_path = Path("/private/independent-log-review-receipt.json")
        helper = Path("/reviewed/runtime-helper.php")
        binding = {"runner_sha256": "f" * 64}
        state = {
            "status": "awaiting_independent_log_review",
            "monitor_completed_at_utc": "2026-10-03T01:00:00Z",
            "independent_log_review": {"binding": binding},
        }
        review_receipt = {
            "artifact": RUNNER.laravel_log_delta.INDEPENDENT_REVIEW_ARTIFACT,
            "status": "pass",
            "decision": "accept",
            "reviewed_at_utc": "2026-10-03T01:01:00Z",
        }
        final_proof = {"status": "pass", "lock_sha256": RUNNER.CANDIDATE_LOCK_SHA256}

        with (
            patch.object(RUNNER, "require_database_envelope_validator"),
            patch.object(RUNNER, "require_gate_helper"),
            patch.object(RUNNER, "require_log_parser"),
            patch.object(
                RUNNER,
                "load_pending_monitor_state",
                return_value=(state, receipt_path),
            ),
            patch.object(RUNNER, "require_regular_file", return_value=receipt_path),
            patch.object(
                RUNNER.laravel_log_delta,
                "validate_independent_review_receipt",
                return_value=review_receipt,
            ) as validate_receipt,
            patch.object(
                RUNNER,
                "verify_live_candidate_after_monitor",
                return_value=final_proof,
            ) as verify,
            patch.object(RUNNER, "contain_cutover_failure") as contain,
            patch.object(RUNNER, "rollback_from_state") as rollback,
            patch.object(RUNNER, "write_state") as write_state,
        ):
            RUNNER.finalize_monitor(
                state_path,
                receipt_path,
                "1" * 64,
                RUNNER.FINALIZE_MONITOR_APPROVAL_TOKEN,
                helper,
            )

        validate_receipt.assert_called_once_with(
            receipt_path,
            expected_sha256="1" * 64,
            expected_binding=binding,
        )
        verify.assert_called_once_with(state, state_path, helper)
        contain.assert_not_called()
        rollback.assert_not_called()
        self.assertEqual("success", state["status"])
        self.assertEqual("accepted", state["independent_log_review"]["status"])
        self.assertEqual(final_proof, state["final_candidate_verification"])
        write_state.assert_called_once_with(state_path, state)

    def test_live_candidate_drift_after_valid_review_contains_and_rolls_back(self) -> None:
        state_path = Path("/private/deployment-state.json")
        receipt_path = Path("/private/independent-log-review-receipt.json")
        helper = Path("/reviewed/runtime-helper.php")
        state = {
            "status": "awaiting_independent_log_review",
            "monitor_completed_at_utc": "2026-10-03T01:00:00Z",
            "independent_log_review": {"binding": {"runner_sha256": "2" * 64}},
        }
        drift = RUNNER.DeploymentError("synthetic live candidate drift")

        with (
            patch.object(RUNNER, "require_database_envelope_validator"),
            patch.object(RUNNER, "require_gate_helper"),
            patch.object(RUNNER, "require_log_parser"),
            patch.object(
                RUNNER,
                "load_pending_monitor_state",
                return_value=(state, receipt_path),
            ),
            patch.object(RUNNER, "require_regular_file", return_value=receipt_path),
            patch.object(
                RUNNER.laravel_log_delta,
                "validate_independent_review_receipt",
                return_value={
                    "status": "pass",
                    "decision": "accept",
                    "reviewed_at_utc": "2026-10-03T01:01:00Z",
                },
            ),
            patch.object(
                RUNNER,
                "verify_live_candidate_after_monitor",
                side_effect=drift,
            ),
            patch.object(
                RUNNER,
                "contain_cutover_failure",
                return_value=True,
            ) as contain,
            patch.object(RUNNER, "rollback_from_state") as rollback,
            patch.object(RUNNER, "write_state") as write_state,
        ):
            with self.assertRaisesRegex(RUNNER.DeploymentError, "candidate drift"):
                RUNNER.finalize_monitor(
                    state_path,
                    receipt_path,
                    "3" * 64,
                    RUNNER.FINALIZE_MONITOR_APPROVAL_TOKEN,
                    helper,
                )

        contain.assert_called_once_with(state, state_path, drift)
        rollback.assert_called_once_with(state, state_path, helper)
        write_state.assert_not_called()
        self.assertNotEqual("success", state["status"])

    @staticmethod
    def log_evidence_paths(result: dict[str, object]) -> tuple[Path, Path, Path]:
        return (
            Path(str(result["raw_manifest_path"])),
            Path(str(result["analysis_path"])),
            Path(str(result["capture_state_path"])),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
