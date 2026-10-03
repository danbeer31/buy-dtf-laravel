from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch


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
        self.assertEqual(RUNNER.NEW_PACKAGE_VERSIONS, RUNNER.locked_package_versions(lock))
        self.assertEqual("12.69.0", RUNNER.OLD_PACKAGE_VERSIONS["laravel/framework"])

    def test_v2_candidate_identity_is_fully_pinned(self) -> None:
        self.assertEqual(
            "f198e8658848f64ac003528e45d925a606ef6788769e81b5d7269ec8be345dcb",
            RUNNER.HANDOFF_SHA256,
        )
        self.assertEqual(
            {
                "bytes": 26481661,
                "directories": 925,
                "files": 6460,
                "sha256": "7df0a101ceb0386b72ec4cfc71f2be8576fc5a5d4b777d11c05e5b7f1ed770d8",
            },
            RUNNER.EXPECTED_CANDIDATE_VENDOR_MANIFEST,
        )
        self.assertEqual(
            "db8aba0a4f49d0cecaeaac0b5b742c5f94b1a514a8d4452c361cb61e2dbacf0d",
            RUNNER.EXPECTED_CANDIDATE_VENDOR_METADATA_SHA256,
        )
        self.assertEqual(10, len(RUNNER.CANDIDATE_VENDOR_EXECUTABLE_PATHS))
        self.assertEqual(
            "551df886bc842a49ea87d8d9bb0cfe3478e3cc5eeea841c83409e8349d120154",
            RUNNER.executable_allowlist_sha256(),
        )
        self.assertEqual(126, RUNNER.EXPECTED_APPLICATION_AUTOLOAD_ENTRIES)
        self.assertEqual(
            "342f417d353f8742f116898d307c34a2677e0a1cb0f814f3e8088f0bb2be1a91",
            RUNNER.EXPECTED_APPLICATION_AUTOLOAD_SHA256,
        )
        self.assertNotIn("PENDING", RUNNER.EXPECTED_APPLICATION_AUTOLOAD_SHA256)
        self.assertEqual(
            "468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9",
            RUNNER.EXPECTED_CANDIDATE_CACHE_IDENTITY["manifest"]["sha256"],
        )

    def test_describe_is_review_only_v2_and_preserves_scope_boundaries(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            RUNNER.describe()
        payload = json.loads(output.getvalue())
        self.assertEqual("buy-dtf-laravel-remember-cookie-dependency-review-v2", payload["artifact"])
        self.assertEqual("review-only; not staged or deployed", payload["artifact_review_status"])
        self.assertEqual("proxy", payload["composer_bin_compat"])
        self.assertEqual(178, payload["expected_route_count"])
        self.assertIn("laravel-remember-cookie-v2-releases", payload["release_root"])
        self.assertNotEqual(
            RUNNER.STAGE_APPROVAL_TOKEN,
            "STAGE-BUYDTF-LARAVEL-REMEMBER-77055fc8acf89149",
        )
        self.assertFalse(payload["git_operations"])
        self.assertFalse(payload["migration_operations"])
        self.assertFalse(payload["dependency_update_operations"])
        self.assertFalse(payload["service_restart_operations"])

    def test_source_precedes_single_canonical_autoload_generation(self) -> None:
        source = inspect.getsource(RUNNER.stage_release)
        self.assertLess(source.index("copy_runtime_shadow"), source.index('"install"'))
        self.assertIn('"--no-autoloader"', source)
        self.assertIn('"dump-autoload"', source)
        self.assertIn('"--optimize"', source)
        self.assertEqual(
            "proxy",
            RUNNER.safe_environment(Path("/tmp/composer"))["COMPOSER_BIN_COMPAT"],
        )

    @unittest.skipUnless(hasattr(os, "chown"), "POSIX ownership policy")
    def test_candidate_vendor_normalization_and_rejection_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-vendor-policy-") as directory:
            vendor = Path(directory) / "vendor"
            (vendor / "bin").mkdir(parents=True)
            (vendor / "pkg").mkdir()
            tool = vendor / "bin/tool"
            ordinary = vendor / "pkg/data.txt"
            tool.write_text("tool\n", encoding="utf-8")
            ordinary.write_text("data\n", encoding="utf-8")
            os.chmod(tool, 0o755)
            os.chmod(ordinary, 0o755)
            allowlist_hash = hashlib.sha256(b"bin/tool\n").hexdigest()
            with patch.multiple(
                RUNNER,
                EXPECTED_APP_UID=os.getuid(),
                EXPECTED_APP_GID=os.getgid(),
                CANDIDATE_VENDOR_EXECUTABLE_PATHS=("bin/tool",),
                CANDIDATE_VENDOR_EXECUTABLE_ALLOWLIST_SHA256=allowlist_hash,
                EXPECTED_CANDIDATE_VENDOR_FILE_COUNT=2,
                EXPECTED_CANDIDATE_VENDOR_DIRECTORY_COUNT=2,
                EXPECTED_CANDIDATE_VENDOR_ORDINARY_FILE_COUNT=1,
            ):
                identity = RUNNER.normalize_candidate_vendor(vendor)
                self.assertEqual(1, identity["executable_files"])
                self.assertEqual(0o775, stat.S_IMODE(tool.stat().st_mode))
                self.assertEqual(0o664, stat.S_IMODE(ordinary.stat().st_mode))
                os.chmod(ordinary, 0o775)
                with self.assertRaisesRegex(RUNNER.DeploymentError, "metadata differs"):
                    RUNNER.candidate_vendor_identity(vendor)

        with tempfile.TemporaryDirectory(prefix="buy-dtf-vendor-bat-") as directory:
            vendor = Path(directory) / "vendor"
            (vendor / "bin").mkdir(parents=True)
            (vendor / "bin/tool.bat").write_text("bat\n", encoding="utf-8")
            with self.assertRaisesRegex(RUNNER.DeploymentError, "Windows proxy"):
                RUNNER.normalize_candidate_vendor(vendor)

        with tempfile.TemporaryDirectory(prefix="buy-dtf-vendor-link-") as directory:
            vendor = Path(directory) / "vendor"
            vendor.mkdir()
            target = vendor / "target"
            target.write_text("target\n", encoding="utf-8")
            (vendor / "link").symlink_to(target)
            with self.assertRaisesRegex(RUNNER.DeploymentError, "invalid file"):
                RUNNER.normalize_candidate_vendor(vendor)

    def test_application_autoload_requires_matching_confined_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-autoload-") as directory:
            shadow = Path(directory) / "shadow"
            (shadow / "app").mkdir(parents=True)
            (shadow / "vendor/composer").mkdir(parents=True)
            for name in ("Foo.php", "Bar.php"):
                (shadow / "app" / name).write_text("<?php\n", encoding="utf-8")
            classmap = """<?php
'App\\\\Bar' => $baseDir . '/app/Bar.php',
'App\\\\Foo' => $baseDir . '/app/Foo.php',
"""
            static = """<?php
'App\\\\Bar' => __DIR__ . '/../..' . '/app/Bar.php',
'App\\\\Foo' => __DIR__ . '/../..' . '/app/Foo.php',
"""
            (shadow / "vendor/composer/autoload_classmap.php").write_text(classmap, encoding="utf-8")
            (shadow / "vendor/composer/autoload_static.php").write_text(static, encoding="utf-8")
            with patch.object(RUNNER, "EXPECTED_APPLICATION_AUTOLOAD_ENTRIES", 2):
                identity = RUNNER.application_autoload_identity(shadow)
                with patch.object(RUNNER, "EXPECTED_APPLICATION_AUTOLOAD_SHA256", identity["sha256"]):
                    self.assertEqual(identity, RUNNER.require_application_autoload(shadow))
                (shadow / "vendor/composer/autoload_static.php").write_text(
                    static.replace("/app/Bar.php", "/app/Foo.php", 1),
                    encoding="utf-8",
                )
                with self.assertRaises(RUNNER.DeploymentError):
                    RUNNER.application_autoload_identity(shadow)

            (shadow / "escape.php").write_text("<?php\n", encoding="utf-8")
            escaped = "<?php\n'App\\\\Escape' => $baseDir . '/app/../escape.php';\n"
            for name in ("autoload_classmap.php", "autoload_static.php"):
                (shadow / "vendor/composer" / name).write_text(escaped, encoding="utf-8")
            with patch.object(RUNNER, "EXPECTED_APPLICATION_AUTOLOAD_ENTRIES", 1):
                with self.assertRaisesRegex(RUNNER.DeploymentError, "escapes app"):
                    RUNNER.application_autoload_identity(shadow)

    def test_shadow_copy_uses_only_the_pinned_source_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-source-copy-") as directory:
            base = Path(directory)
            source = base / "source"
            destination = base / "shadow"
            (source / "app").mkdir(parents=True)
            destination.mkdir()
            (source / "artisan").write_text("artisan\n", encoding="utf-8")
            (source / "composer.json").write_text("{}\n", encoding="utf-8")
            (source / "app/Only.php").write_text("<?php\n", encoding="utf-8")
            with patch.object(RUNNER, "SOURCE_ROOTS", ("app",)), patch.object(
                RUNNER, "SOURCE_TOP_LEVEL_FILES", ("artisan", "composer.json")
            ):
                expected = RUNNER.source_manifest(source)
                with patch.object(RUNNER, "EXPECTED_SOURCE_MANIFEST", expected):
                    self.assertEqual(expected, RUNNER.copy_runtime_shadow(source, destination))
            self.assertTrue((destination / "app/Only.php").is_file())
            self.assertTrue((destination / "bootstrap/cache").is_dir())

    def test_private_operations_roots_reject_symlinks_and_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-private-operations-") as directory:
            app_root = Path(directory) / "app"
            operations = app_root / "storage/app/private/operations"
            operations.mkdir(parents=True)
            release_root = operations / "laravel-remember-cookie-v2-releases"
            with patch.object(RUNNER, "APP_ROOT", app_root), patch.object(
                RUNNER, "PRIVATE_OPERATIONS_ROOT", operations
            ), patch.object(RUNNER, "EXPECTED_APP_UID", os.getuid()), patch.object(
                RUNNER, "EXPECTED_WEB_GID", os.getgid()
            ):
                self.assertEqual(
                    release_root.resolve(),
                    RUNNER.ensure_private_operations_root(release_root, create=True),
                )
                self.assertEqual(0o700, stat.S_IMODE(release_root.stat().st_mode))
                os.chmod(release_root, 0o755)
                with self.assertRaisesRegex(RUNNER.DeploymentError, "ownership or mode"):
                    RUNNER.ensure_private_operations_root(release_root, create=False)

                real_target = operations / "real-target"
                real_target.mkdir(mode=0o700)
                symbolic_root = operations / "symbolic-root"
                symbolic_root.symlink_to(real_target, target_is_directory=True)
                with self.assertRaisesRegex(RUNNER.DeploymentError, "must not be symbolic"):
                    RUNNER.ensure_private_operations_root(symbolic_root, create=True)

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
        self.assertEqual(25, result["scenario_count"])
        self.assertTrue(all(status == "pass" for status in result["scenarios"].values()))
        self.assertIn("failure_between_vendor_and_cache_exchange", result["scenarios"])
        self.assertIn("completely_unbootable_candidate_auto_rollback", result["scenarios"])
        self.assertIn("recovery_interruption_after_rollback_lock", result["scenarios"])
        self.assertIn("identical_cache_recovery_is_idempotent", result["scenarios"])
        self.assertIn("candidate_owner_drift_fails_closed", result["scenarios"])

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def valid_runtime_payload() -> dict[str, object]:
        package_paths = {
            package: f"/var/www/buy-dtf/vendor/{package}/"
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
