#!/usr/bin/env python3
"""Regression tests for the production-alpha deployment artifact."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/production_alpha_transparency_deploy.py"
REHEARSAL_PATH = ROOT / "ops/deployment/rehearse_production_alpha_transparency.py"
MANIFEST_PATH = (
    ROOT
    / "ops/evidence/production-alpha-transparency-20261001/APPLICATION_MANIFEST.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deploy = load_module("production_alpha_runner_test", RUNNER_PATH)
rehearsal = load_module("production_alpha_rehearsal_test", REHEARSAL_PATH)


class ProductionAlphaRunnerTest(unittest.TestCase):
    def before(self) -> dict:
        return rehearsal.runtime_snapshot(False)

    def after(self) -> dict:
        return rehearsal.runtime_snapshot(True)

    def assert_refused(
        self,
        payload: dict,
        *,
        target_absent: bool,
        phrase: str,
        all_null: bool = False,
    ) -> None:
        with self.assertRaises(deploy.DeploymentError) as raised:
            deploy.validate_runtime_snapshot(
                payload,
                require_target_absent=target_absent,
                require_all_item_meta_null=all_null,
            )
        self.assertIn(phrase, str(raised.exception))

    def test_manifest_pins_all_seven_raw_byte_counts(self) -> None:
        rows = deploy.parse_manifest(MANIFEST_PATH)
        expected = {
            "app/Helpers/ImageHelper.php": 28229,
            "app/Helpers/ProductionHelper.php": 17594,
            "app/Http/Controllers/Admin/OrderImageController.php": 14948,
            "app/Http/Controllers/CartController.php": 32079,
            "app/Http/Controllers/TeamCustomizationController.php": 9957,
            "app/Models/DtfImage.php": 8990,
            "app/Models/SavedImage.php": 1043,
        }
        replacements = {row["path"]: row["expected_bytes"] for row in rows if row["action"] == "M"}
        self.assertEqual(replacements, expected)
        self.assertEqual(sum(row["action"] == "A" for row in rows), 1)
        self.assertEqual(sum(row["action"] == "M" for row in rows), 7)

    def test_exact_pre_and_post_schema_states_are_accepted(self) -> None:
        before = deploy.validate_runtime_snapshot(self.before(), require_target_absent=True)
        after = deploy.validate_runtime_snapshot(
            self.after(),
            require_target_absent=False,
            require_all_item_meta_null=True,
        )
        self.assertEqual(before["schema_state"], "absent")
        self.assertEqual(after["schema_state"], "installed")
        self.assertEqual(after["target_migration_entries"], 1)
        self.assertEqual(after["item_meta_nonnull_rows"], 0)

    def test_schema_drift_outside_item_meta_is_refused(self) -> None:
        payload = self.after()
        payload["schema"]["without_item_meta_sha256"] = "0" * 64
        self.assert_refused(
            payload,
            target_absent=False,
            phrase="outside the reviewed additive change",
        )

    def test_ledger_drift_outside_target_row_is_refused(self) -> None:
        payload = self.after()
        payload["migration_ledger"]["without_target_rows_sha256"] = "f" * 64
        self.assert_refused(
            payload,
            target_absent=False,
            phrase="outside the reviewed additive change",
        )

    def test_wrong_column_definition_is_refused(self) -> None:
        for key, value in (
            ("COLUMN_TYPE", "longtext"),
            ("IS_NULLABLE", "NO"),
            ("COLUMN_DEFAULT", "{}"),
            ("EXTRA", "generated"),
        ):
            with self.subTest(key=key):
                payload = self.after()
                payload["schema"]["savedimages_item_meta"]["definition"][0][key] = value
                self.assert_refused(
                    payload,
                    target_absent=False,
                    phrase="nullable TEXT definition",
                )

    def test_nonnull_preexisting_metadata_is_refused_at_migration_boundary(self) -> None:
        payload = self.after()
        payload["schema"]["savedimages_item_meta"]["nonnull_rows"] = 1
        self.assert_refused(
            payload,
            target_absent=False,
            all_null=True,
            phrase="pre-existing Saved Image",
        )
        relaxed = deploy.validate_runtime_snapshot(payload, require_target_absent=False)
        self.assertEqual(relaxed["item_meta_nonnull_rows"], 1)

    def test_enabled_capability_or_host_is_refused(self) -> None:
        for key, value in (
            ("receiver_enabled", True),
            ("job_label_enabled", True),
            ("retention_enabled", True),
            ("allowed_host_count", 1),
        ):
            with self.subTest(key=key):
                payload = self.before()
                payload["capabilities"][key] = value
                self.assert_refused(
                    payload,
                    target_absent=True,
                    phrase="capability or artwork host",
                )

    def test_post_migration_requires_unchanged_savedimages_rows(self) -> None:
        after = self.after()
        after["schema"]["savedimages_item_meta"]["savedimages_rows"] += 1
        with self.assertRaisesRegex(deploy.DeploymentError, "row count changed"):
            deploy.verify_post_migration(self.before(), after)

    def test_post_migration_requires_unchanged_savedimages_data(self) -> None:
        after = self.after()
        after["schema"]["savedimages_item_meta"]["data_sha256_without_item_meta"] = "4" * 64
        with self.assertRaisesRegex(deploy.DeploymentError, "row data changed"):
            deploy.verify_post_migration(self.before(), after)

    def test_rollback_accepts_only_exact_absent_or_installed_schema(self) -> None:
        absent = deploy.verify_rollback_schema_state(
            self.before(),
            {"migration_execution_started": True, "migration_executed": False},
        )
        installed = deploy.verify_rollback_schema_state(
            self.after(),
            {"migration_execution_started": True, "migration_executed": False},
        )
        self.assertFalse(absent["additive_schema_preserved"])
        self.assertTrue(installed["additive_schema_preserved"])

        partial = self.after()
        partial["migration_ledger"]["target_entry_count"] = 0
        with self.assertRaisesRegex(deploy.DeploymentError, "partial or drifted"):
            deploy.verify_rollback_schema_state(
                partial,
                {"migration_execution_started": True, "migration_executed": False},
            )

    def test_completed_migration_can_never_roll_back_to_absent_schema(self) -> None:
        with self.assertRaisesRegex(deploy.DeploymentError, "was not preserved"):
            deploy.verify_rollback_schema_state(
                self.before(),
                {"migration_execution_started": True, "migration_executed": True},
            )

    def test_migration_start_is_the_fail_closed_boundary(self) -> None:
        self.assertFalse(
            deploy.mutation_has_started(
                {"migration_execution_started": False, "source_install_started": False}
            )
        )
        self.assertTrue(
            deploy.mutation_has_started(
                {"migration_execution_started": True, "source_install_started": False}
            )
        )

    def test_pretend_allows_only_the_one_reviewed_statement(self) -> None:
        reviewed = deploy.EXPECTED_PRETEND_STATEMENT
        deploy.validate_pretend_statements(reviewed + "\n", [reviewed])
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_pretend_statements(
                reviewed + "\nalter table `dtfimages` add `bad` int null\n",
                [reviewed, "alter table `dtfimages` add `bad` int null"],
            )
        with self.assertRaises(deploy.DeploymentError):
            deploy.validate_pretend_statements(
                "drop table `savedimages`\n",
                ["drop table `savedimages`"],
            )

    def test_runner_has_no_database_destructive_or_dependency_command(self) -> None:
        source = RUNNER_PATH.read_text("utf-8")
        tree = ast.parse(source)
        literal_strings = {
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertNotIn("migrate:rollback", literal_strings)
        self.assertNotIn("db:wipe", literal_strings)
        # Composer phrases occur once each only as process-conflict detectors.
        self.assertEqual(source.count('"composer install"'), 1)
        self.assertEqual(source.count('"composer update"'), 1)
        self.assertNotIn('["/usr/bin/composer"', source)
        self.assertNotIn('["composer"', source)
        self.assertNotIn("systemctl restart", literal_strings)
        self.assertNotIn("git pull", literal_strings)

    def test_candidate_fpm_probe_source_is_valid_php(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "candidate-fpm-probe.php"
            probe.write_bytes(deploy.candidate_fpm_probe_source())
            completed = subprocess.run(
                ["/usr/bin/php", "-l", str(probe)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_describe_declares_schema_preserving_safety(self) -> None:
        description = deploy.describe()
        self.assertFalse(description["migration"]["general_migrate_allowed"])
        self.assertFalse(description["migration"]["rollback_command_allowed"])
        self.assertFalse(description["safety"]["source_rollback_drops_additive_schema"])
        self.assertTrue(description["safety"]["schema_preserved_after_successful_migration"])
        self.assertEqual(description["runtime_paths"], {
            "total": 8,
            "additions": 1,
            "replacements": 7,
        })

    def test_portable_rehearsal_covers_every_required_scenario(self) -> None:
        receipt_path = (
            ROOT
            / "ops/evidence/production-alpha-transparency-20261001"
            / "deployment-rehearsal/rehearsal-receipt.json"
        )
        receipt = json.loads(receipt_path.read_text("utf-8"))
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(set(receipt["scenarios"]), set(rehearsal.SCENARIOS))
        self.assertTrue(
            all(
                result["separate_web_identity_all_passed"]
                for result in receipt["scenarios"].values()
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
