#!/usr/bin/env python3
"""Regression tests for the installed-schema incoming-order resume artifact."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/incoming_order_v1_deploy.py"
FIXTURE_PATH = (
    ROOT
    / "ops/evidence/incoming-order-v1-failed-cutover-20261001"
    / "0799440b-20261001T020405Z"
    / "post-migration-runtime-probe.stdout.txt"
)

SPEC = importlib.util.spec_from_file_location("incoming_order_v1_resume", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import bootstrap guard
    raise RuntimeError("Unable to load the incoming-order deployment runner.")
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


class InstalledSchemaResumeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text("utf-8"))

    def assert_refused(self, payload: dict, message: str | None = None) -> None:
        with self.assertRaises(deploy.DeploymentError) as raised:
            deploy.validate_runtime_snapshot(payload)
        if message is not None:
            self.assertIn(message, str(raised.exception))

    def test_exact_retained_post_migration_fixture_is_json_safe(self) -> None:
        result = deploy.verify_installed_schema(copy.deepcopy(self.fixture))
        encoded = deploy.canonical_bytes(result)
        self.assertEqual(json.loads(encoded), result)
        self.assertEqual(result["state"], deploy.SCHEMA_STATE)
        self.assertEqual(result["schema_sha256"], deploy.EXPECTED_SCHEMA_SHA256)
        self.assertEqual(
            result["migration_ledger"]["rows_sha256"],
            deploy.EXPECTED_LEDGER_SHA256,
        )
        self.assertEqual(result["target_table_row_counts"], {
            "api_asset_records": 0,
            "incoming_order_jobs": 0,
        })
        self.assertEqual(
            result["ascii_bin_columns"],
            [
                {
                    "table": "incoming_order_jobs",
                    "column": "idempotency_key",
                    "collation": "ascii_bin",
                },
                {
                    "table": "incoming_order_jobs",
                    "column": "integration_client",
                    "collation": "ascii_bin",
                },
                {
                    "table": "incoming_order_jobs",
                    "column": "lease_owner",
                    "collation": "ascii_bin",
                },
                {
                    "table": "incoming_order_jobs",
                    "column": "production_owner",
                    "collation": "ascii_bin",
                },
            ],
        )
        self.assertFalse(result["migration_executed_this_attempt"])

    def test_schema_hash_drift_is_refused(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["schema"]["sha256"] = "0" * 64
        self.assert_refused(payload, "schema differs")

    def test_schema_definition_and_index_drift_are_refused(self) -> None:
        payload = copy.deepcopy(self.fixture)
        payload["schema"]["target_definitions"]["statistics"].pop()
        self.assert_refused(payload, "definitions differ")

    def test_ledger_hash_count_and_entry_drift_are_refused(self) -> None:
        for key, value in (
            ("rows_sha256", "f" * 64),
            ("row_count", deploy.EXPECTED_LEDGER_ROW_COUNT + 1),
            ("target_entry_count", 0),
        ):
            with self.subTest(key=key):
                payload = copy.deepcopy(self.fixture)
                payload["migration_ledger"][key] = value
                self.assert_refused(payload, "ledger differs")

    def test_nonempty_target_tables_are_refused(self) -> None:
        for table in sorted(deploy.TARGET_TABLES):
            with self.subTest(table=table):
                payload = copy.deepcopy(self.fixture)
                payload["schema"]["target_table_row_counts"][table] = 1
                self.assert_refused(payload, "nonempty")

    def test_enabled_capabilities_and_artwork_hosts_are_refused(self) -> None:
        for field, value in (
            ("receiver_enabled", True),
            ("job_label_enabled", True),
            ("retention_enabled", True),
            ("allowed_host_count", 1),
        ):
            with self.subTest(field=field):
                payload = copy.deepcopy(self.fixture)
                payload["capabilities"][field] = value
                self.assert_refused(payload, "capability or artwork host")

    def test_original_source_drift_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "tracked.php"
            live.write_bytes(b"reviewed bytes\n")
            digest = deploy.sha256_file(live)
            original_root = deploy.APP_ROOT
            deploy.APP_ROOT = root
            try:
                with self.assertRaisesRegex(
                    deploy.DeploymentError, "Original 37-path source CAS differs"
                ):
                    deploy.live_manifest_snapshot(
                        [
                            {
                                "action": "M",
                                "expected": digest,
                                "target": digest,
                                "path": "tracked.php",
                            }
                        ],
                        target=False,
                    )
            finally:
                deploy.APP_ROOT = original_root

    def test_retired_receipt_hash_and_path_are_refused_before_io(self) -> None:
        retired_hash = next(iter(deploy.RETIRED_RELEASE_RECEIPT_SHA256S))
        with self.assertRaisesRegex(deploy.DeploymentError, "permanently retired"):
            deploy.validate_release_receipt(Path("/does/not/exist"), retired_hash)
        retired_path = Path(next(iter(deploy.RETIRED_RELEASE_RECEIPT_PATHS)))
        with self.assertRaisesRegex(deploy.DeploymentError, "permanently retired"):
            deploy.validate_release_receipt(retired_path, "a" * 64)

    def test_runner_contains_no_migration_command_path(self) -> None:
        source = RUNNER_PATH.read_text("utf-8")
        tree = ast.parse(source)
        self.assertFalse(hasattr(deploy, "staged_pretend"))
        self.assertFalse(hasattr(deploy, "execute_single_migration"))
        migrate_literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value == "migrate"
        ]
        self.assertEqual(migrate_literals, [])
        self.assertNotIn('"--pretend"', source)

    def test_describe_records_schema_resume_and_no_migration(self) -> None:
        description = deploy.describe()
        self.assertEqual(description["migration"]["schema_state"], deploy.SCHEMA_STATE)
        self.assertFalse(description["migration"]["command_invoked"])
        self.assertFalse(description["migration"]["pretend_invoked"])
        self.assertFalse(description["migration"]["executed_this_attempt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
