from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/laravel_remember_cookie_dependency_deploy.py"
SPEC = importlib.util.spec_from_file_location("laravel_remember_cookie_dependency_deploy", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


class LaravelRememberCookieDependencyRunnerTest(unittest.TestCase):
    def test_reviewed_lock_and_package_versions_are_exact(self) -> None:
        composer_json = ROOT / "composer.json"
        lock = ROOT / "composer.lock"

        self.assertEqual(RUNNER.EXPECTED_LIVE_COMPOSER_JSON_SHA256, self.sha256(composer_json))
        self.assertEqual(RUNNER.CANDIDATE_LOCK_SHA256, self.sha256(lock))
        self.assertEqual(
            {
                "guzzlehttp/guzzle": "7.15.2",
                "laravel/framework": "12.69.1",
                "league/commonmark": "2.10.2",
                "league/flysystem": "3.35.3",
                "league/flysystem-local": "3.35.3",
            },
            RUNNER.locked_package_versions(lock),
        )
        self.assertEqual("12.69.0", RUNNER.OLD_PACKAGE_VERSIONS["laravel/framework"])

    def test_review_handoff_and_live_production_baseline_are_pinned(self) -> None:
        self.assertEqual(
            "ba9fd4dcf5fa5854b2e23418e0cd6ed8799874494a0341c726302b92a5acc127",
            RUNNER.HANDOFF_SHA256,
        )
        self.assertEqual(
            "22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9",
            RUNNER.EXPECTED_LIVE_LOCK_SHA256,
        )
        self.assertEqual(326, RUNNER.EXPECTED_SOURCE_MANIFEST["files"])
        self.assertEqual(
            "7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed",
            RUNNER.EXPECTED_LIVE_VENDOR_MANIFEST["sha256"],
        )

    def test_deterministic_candidate_vendor_and_cache_are_pinned(self) -> None:
        self.assertEqual(
            {
                "bytes": 26482354,
                "directories": 925,
                "files": 6465,
                "sha256": "b8e0e3afa65171a66ad3d1875404fe209d7598c9b3f690e494d40c4fde4408f8",
            },
            RUNNER.EXPECTED_CANDIDATE_VENDOR_MANIFEST,
        )
        self.assertEqual(
            "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9",
            RUNNER.EXPECTED_CANDIDATE_CACHE_IDENTITY["manifest"]["sha256"],
        )

    def test_describe_is_review_only_and_preserves_scope_boundaries(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            RUNNER.describe()
        payload = json.loads(output.getvalue())

        self.assertEqual("review-only; not staged or deployed", payload["artifact_review_status"])
        self.assertEqual(RUNNER.HANDOFF_SHA256, payload["handoff"]["sha256"])
        self.assertFalse(payload["git_operations"])
        self.assertFalse(payload["migration_operations"])
        self.assertFalse(payload["dependency_update_operations"])
        self.assertFalse(payload["service_restart_operations"])

    def test_runtime_validation_requires_all_incoming_order_capabilities_disabled(self) -> None:
        payload = self.valid_runtime_payload()
        RUNNER.validate_runtime_baseline(payload, expected_versions=RUNNER.OLD_PACKAGE_VERSIONS)

        for field, value in (
            ("incoming_order_receiver_enabled", True),
            ("incoming_order_job_label_enabled", True),
            ("incoming_order_retention_enabled", True),
            ("incoming_order_allowed_host_count", 1),
        ):
            with self.subTest(field=field):
                invalid = self.valid_runtime_payload()
                invalid["disabled_capabilities"][field] = value
                with self.assertRaisesRegex(RUNNER.DeploymentError, "capability is enabled"):
                    RUNNER.validate_runtime_baseline(
                        invalid,
                        expected_versions=RUNNER.OLD_PACKAGE_VERSIONS,
                    )

    def test_atomic_rehearsal_exercises_cutover_rollback_and_recovery_failures(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-remember-runner-test-") as directory:
            result = RUNNER.rehearse(Path(directory))

        self.assertEqual("pass", result["status"])
        self.assertEqual(23, result["scenario_count"])
        self.assertTrue(all(status == "pass" for status in result["scenarios"].values()))
        self.assertIn("failure_between_vendor_and_cache_exchange", result["scenarios"])
        self.assertIn("completely_unbootable_candidate_auto_rollback", result["scenarios"])
        self.assertIn("recovery_interruption_after_rollback_lock", result["scenarios"])

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def valid_runtime_payload() -> dict[str, object]:
        package_paths = {
            package: f"/var/www/buy-dtf/vendor/{package.replace('/', '/')}/"
            for package in RUNNER.OLD_PACKAGE_VERSIONS
        }
        return {
            "app_environment": "local",
            "app_debug": False,
            "queue_connection": "sync",
            "disabled_capabilities": {
                "incoming_order_receiver_enabled": False,
                "incoming_order_job_label_enabled": False,
                "incoming_order_retention_enabled": False,
                "incoming_order_allowed_host_count": 0,
            },
            "queue_tables": {"jobs": 0, "failed_jobs": 0},
            "php_version": "8.2.30",
            "php_extensions": ["Core"],
            "package_versions": RUNNER.OLD_PACKAGE_VERSIONS,
            "package_install_paths": package_paths,
            "laravel_version": "12.69.0",
            "guzzle_version": "7.15.2",
            "laravel_class_path": "/var/www/buy-dtf/vendor/laravel/framework/Application.php",
            "guzzle_class_path": "/var/www/buy-dtf/vendor/guzzlehttp/guzzle/Client.php",
        }


if __name__ == "__main__":
    unittest.main()
