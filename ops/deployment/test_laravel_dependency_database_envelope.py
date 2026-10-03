from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ops/deployment/laravel_dependency_database_envelope.py"
SPEC = importlib.util.spec_from_file_location(
    "laravel_dependency_database_envelope", MODULE_PATH
)
ENVELOPE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ENVELOPE)


class LaravelDependencyDatabaseEnvelopeTest(unittest.TestCase):
    def validate_pre_source(self, payload: dict) -> dict:
        return ENVELOPE.validate_pre_source_database_envelope(payload)

    def validate_post_cutover(self, payload: dict) -> dict:
        return ENVELOPE.validate_post_cutover_database_envelope(payload)

    def assert_pre_source_rejected(self, payload: dict, message: str) -> None:
        with self.assertRaisesRegex(ENVELOPE.DatabaseEnvelopeError, message):
            self.validate_pre_source(payload)

    def test_reviewed_database_identities_are_exact(self) -> None:
        self.assertEqual(
            "5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da",
            ENVELOPE.EXPECTED_SCHEMA_SHA256,
        )
        self.assertEqual(
            "9566898c6940c2248e1e0ee02d8460bfb42d6b407d3108ad60044bab86ac4567",
            ENVELOPE.EXPECTED_FUEL_DATABASE_NAME_SHA256,
        )
        self.assertEqual(21, ENVELOPE.EXPECTED_LEDGER_ROW_COUNT)
        self.assertEqual(
            "f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53",
            ENVELOPE.EXPECTED_LEDGER_SHA256,
        )
        self.assertEqual(
            "aa0a038110dc355ffcd0ed12768c2adb7b0954ecbcc9aeb0fc4ef0efb5d287dc",
            ENVELOPE.EXPECTED_INCOMING_ORDER_TABLE_DEFINITIONS_SHA256,
        )
        definitions = json.loads(
            (
                ROOT
                / "tests/Fixtures/Deployment/database-envelope-incoming-table-definitions.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            ENVELOPE.EXPECTED_INCOMING_ORDER_TABLE_DEFINITIONS_SHA256,
            ENVELOPE.canonical_sha256(definitions),
        )
        self.assertEqual(10, len(ENVELOPE.EXPECTED_INCOMING_ORDER_INDEXES))

    def test_php_probe_uses_only_the_reviewed_read_only_schema_queries(self) -> None:
        source = (
            ROOT / "ops/deployment/laravel_remember_cookie_runtime_probe.php"
        ).read_text(encoding="utf-8")
        for section in (
            "information_schema.TABLES",
            "information_schema.COLUMNS",
            "information_schema.STATISTICS",
            "information_schema.TABLE_CONSTRAINTS",
            "information_schema.KEY_COLUMN_USAGE",
            "information_schema.REFERENTIAL_CONSTRAINTS",
        ):
            self.assertIn(section, source)
        upper = source.upper()
        for mutation in (
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "ALTER ",
            "CREATE ",
            "DROP ",
            "TRUNCATE ",
        ):
            self.assertNotIn(mutation, upper)
        self.assertNotIn("ARTISAN MIGRATE", upper)

    def test_pre_source_and_post_cutover_item_meta_policies_are_distinct(self) -> None:
        payload = self.valid_payload()
        before = self.validate_pre_source(payload)
        self.assertEqual("pre_source_exactly_zero", before["item_meta_row_policy"])

        grown = deepcopy(payload)
        grown["schema"]["savedimages_item_meta"]["nonnull_rows"] = 7
        after = self.validate_post_cutover(grown)
        self.assertEqual(
            "post_source_nonnegative_growth_allowed", after["item_meta_row_policy"]
        )
        self.assertEqual(7, after["savedimages_item_meta"]["nonnull_rows"])
        self.assert_pre_source_rejected(grown, "zero non-null rows")

        invalid = deepcopy(payload)
        invalid["schema"]["savedimages_item_meta"]["nonnull_rows"] = -1
        with self.assertRaisesRegex(ENVELOPE.DatabaseEnvelopeError, "nonnegative integer"):
            self.validate_post_cutover(invalid)

    def test_schema_hash_and_each_section_count_drift_fail_closed(self) -> None:
        invalid = self.valid_payload()
        invalid["schema"]["sha256"] = "0" * 64
        self.assert_pre_source_rejected(invalid, "schema identity")

        for section in ENVELOPE.EXPECTED_SCHEMA_SECTION_COUNTS:
            with self.subTest(section=section):
                invalid = self.valid_payload()
                invalid["schema"]["section_row_counts"][section] += 1
                self.assert_pre_source_rejected(invalid, "section counts")

    def test_each_ledger_and_target_migration_invariant_fails_closed(self) -> None:
        changes = {
            "row_count": 22,
            "rows_sha256": "0" * 64,
            "target_migration": "wrong_item_meta_migration",
            "target_entry_count": 0,
            "incoming_order_migration": "wrong_incoming_order_migration",
            "incoming_order_entry_count": 0,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                invalid = self.valid_payload()
                invalid["migration_ledger"][field] = value
                self.assert_pre_source_rejected(invalid, "ledger|migration")

    def test_each_item_meta_definition_field_drift_fails_closed(self) -> None:
        changes = {
            "TABLE_NAME": "other_table",
            "ORDINAL_POSITION": 13,
            "COLUMN_NAME": "other_meta",
            "COLUMN_TYPE": "longtext",
            "IS_NULLABLE": "NO",
            "COLUMN_DEFAULT": "{}",
            "EXTRA": "DEFAULT_GENERATED",
            "CHARACTER_SET_NAME": "latin1",
            "COLLATION_NAME": "utf8mb4_bin",
            "GENERATION_EXPRESSION": "1",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                invalid = self.valid_payload()
                invalid["schema"]["savedimages_item_meta"]["definition"][0][field] = value
                self.assert_pre_source_rejected(invalid, "nullable TEXT definition")

        invalid = self.valid_payload()
        invalid["schema"]["savedimages_item_meta"]["definition"].append(
            deepcopy(ENVELOPE.EXPECTED_ITEM_META_DEFINITION)
        )
        self.assert_pre_source_rejected(invalid, "nullable TEXT definition")

    def test_each_required_table_definition_and_row_count_drift_fails_closed(self) -> None:
        for table in self.valid_payload()["schema"]["required_tables"]:
            with self.subTest(required_table=table):
                invalid = self.valid_payload()
                invalid["schema"]["required_tables"][table] = False
                self.assert_pre_source_rejected(invalid, "Required Fuel table")

        for table in ENVELOPE.INCOMING_ORDER_TABLES:
            with self.subTest(installed_table=table):
                invalid = self.valid_payload()
                invalid["schema"]["incoming_order_tables"][table] = False
                self.assert_pre_source_rejected(invalid, "table set")
            with self.subTest(row_count=table):
                invalid = self.valid_payload()
                invalid["schema"]["incoming_order_row_counts"][table] = 1
                self.assert_pre_source_rejected(invalid, "nonempty")

        invalid = self.valid_payload()
        invalid["schema"]["incoming_order_definitions"]["tables"][0]["ENGINE"] = "MyISAM"
        self.assert_pre_source_rejected(invalid, "definitions differ")

    def test_connection_capability_and_queue_drift_fail_closed(self) -> None:
        connection_changes = {
            "configured_fuel_connection": "mysql",
            "expected_fuel_connection": "mysql",
            "fuel_driver": "sqlite",
            "fuel_database_name_sha256": "0" * 64,
            "default_connection": "sqlite",
            "connection_match": False,
        }
        for field, value in connection_changes.items():
            with self.subTest(connection=field):
                invalid = self.valid_payload()
                invalid["connections"][field] = value
                self.assert_pre_source_rejected(invalid, "connection differs")

        for field in ENVELOPE.EXPECTED_DISABLED_CAPABILITIES:
            with self.subTest(capability=field):
                invalid = self.valid_payload()
                invalid["disabled_capabilities"][field] = (
                    1 if field.endswith("count") else True
                )
                self.assert_pre_source_rejected(invalid, "capability is enabled")

        invalid = self.valid_payload()
        invalid["queue_connection"] = "database"
        self.assert_pre_source_rejected(invalid, "queue connection")
        for table in ("jobs", "failed_jobs"):
            with self.subTest(queue_table=table):
                invalid = self.valid_payload()
                invalid["queue_tables"][table] = 1
                self.assert_pre_source_rejected(invalid, "absent or nonempty")
                invalid["queue_tables"][table] = None
                self.assert_pre_source_rejected(invalid, "absent or nonempty")

    def test_boolean_values_cannot_impersonate_integer_counts(self) -> None:
        mutations = (
            (lambda payload: payload.__setitem__("database_envelope_version", True), "identity"),
            (
                lambda payload: payload["migration_ledger"].__setitem__(
                    "target_entry_count", True
                ),
                "migration",
            ),
            (
                lambda payload: payload["schema"]["incoming_order_row_counts"].__setitem__(
                    "incoming_order_jobs", False
                ),
                "nonempty",
            ),
            (
                lambda payload: payload["queue_tables"].__setitem__("jobs", False),
                "absent or nonempty",
            ),
        )
        for mutate, message in mutations:
            with self.subTest(message=message):
                invalid = self.valid_payload()
                mutate(invalid)
                self.assert_pre_source_rejected(invalid, message)

    @staticmethod
    def valid_payload() -> dict:
        incoming_definitions = json.loads(
            (
                ROOT
                / "tests/Fixtures/Deployment/database-envelope-incoming-table-definitions.json"
            ).read_text(encoding="utf-8")
        )
        return {
            "database_envelope_version": 1,
            "connections": {
                "configured_fuel_connection": "fuelmysql",
                "expected_fuel_connection": "fuelmysql",
                "fuel_driver": "mysql",
                "fuel_database_name_sha256": ENVELOPE.EXPECTED_FUEL_DATABASE_NAME_SHA256,
                "default_connection": "mysql",
                "connection_match": True,
            },
            "migration_ledger": {
                "table": "migrations",
                "exists": True,
                "row_count": ENVELOPE.EXPECTED_LEDGER_ROW_COUNT,
                "rows_sha256": ENVELOPE.EXPECTED_LEDGER_SHA256,
                "target_migration": ENVELOPE.ITEM_META_MIGRATION,
                "target_entry_count": 1,
                "incoming_order_migration": ENVELOPE.INCOMING_ORDER_MIGRATION,
                "incoming_order_entry_count": 1,
            },
            "schema": {
                "sha256": ENVELOPE.EXPECTED_SCHEMA_SHA256,
                "section_row_counts": deepcopy(
                    ENVELOPE.EXPECTED_SCHEMA_SECTION_COUNTS
                ),
                "required_tables": {
                    "businesses": True,
                    "dtforders": True,
                    "dtfimages": True,
                    "savedimages": True,
                    "incoming_order_jobs": True,
                    "api_asset_records": True,
                },
                "savedimages_item_meta": {
                    "exists": True,
                    "definition": [deepcopy(ENVELOPE.EXPECTED_ITEM_META_DEFINITION)],
                    "nonnull_rows": 0,
                },
                "incoming_order_tables": {
                    "api_asset_records": True,
                    "incoming_order_jobs": True,
                },
                "incoming_order_row_counts": {
                    "api_asset_records": 0,
                    "incoming_order_jobs": 0,
                },
                "incoming_order_definitions": incoming_definitions,
            },
            "disabled_capabilities": deepcopy(
                ENVELOPE.EXPECTED_DISABLED_CAPABILITIES
            ),
            "queue_connection": "sync",
            "queue_tables": {"jobs": 0, "failed_jobs": 0},
        }


if __name__ == "__main__":
    unittest.main()
