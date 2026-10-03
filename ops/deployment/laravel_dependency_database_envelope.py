#!/usr/bin/env python3
"""Validate the read-only production database envelope for the Laravel repair.

The companion PHP probe emits the raw, credential-free facts.  This module
keeps the reviewed production identities and the policy decisions separate
from that probe so staging, cutover, monitoring, rollback, and recovery can
apply one fail-closed contract.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


EXPECTED_SCHEMA_SHA256 = "5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da"
EXPECTED_FUEL_DATABASE_NAME_SHA256 = (
    "9566898c6940c2248e1e0ee02d8460bfb42d6b407d3108ad60044bab86ac4567"
)
EXPECTED_SCHEMA_SECTION_COUNTS = {
    "tables": 36,
    "columns": 411,
    "statistics": 76,
    "table_constraints": 46,
    "key_column_usage": 49,
    "referential_constraints": 2,
}
EXPECTED_LEDGER_ROW_COUNT = 21
EXPECTED_LEDGER_SHA256 = "f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53"
ITEM_META_MIGRATION = "2026_10_01_120000_add_item_meta_to_savedimages_table"
INCOMING_ORDER_MIGRATION = "2026_09_27_120000_create_incoming_order_v1_tables"
EXPECTED_TARGET_MIGRATION_ENTRY_COUNT = 1
EXPECTED_INCOMING_ORDER_MIGRATION_ENTRY_COUNT = 1
INCOMING_ORDER_TABLES = frozenset({"incoming_order_jobs", "api_asset_records"})
EXPECTED_INCOMING_ORDER_TABLE_DEFINITIONS_SHA256 = (
    "aa0a038110dc355ffcd0ed12768c2adb7b0954ecbcc9aeb0fc4ef0efb5d287dc"
)
EXPECTED_INCOMING_ORDER_INDEXES = frozenset(
    {
        "PRIMARY",
        "incoming_order_jobs_dtfimage_id_unique",
        "incoming_jobs_client_key_unique",
        "incoming_jobs_state_lease_index",
        "incoming_jobs_label_status_index",
        "incoming_jobs_production_state_index",
        "incoming_jobs_production_lease_index",
        "api_assets_job_role_path_unique",
        "api_assets_retention_index",
        "api_assets_path_hash_index",
    }
)
EXPECTED_ITEM_META_DEFINITION = {
    "TABLE_NAME": "savedimages",
    "ORDINAL_POSITION": 12,
    "COLUMN_NAME": "item_meta",
    "COLUMN_TYPE": "text",
    "IS_NULLABLE": "YES",
    "COLUMN_DEFAULT": None,
    "EXTRA": "",
    "CHARACTER_SET_NAME": "utf8mb4",
    "COLLATION_NAME": "utf8mb4_unicode_ci",
    "GENERATION_EXPRESSION": "",
}
EXPECTED_DISABLED_CAPABILITIES = {
    "incoming_order_receiver_enabled": False,
    "incoming_order_job_label_enabled": False,
    "incoming_order_retention_enabled": False,
    "incoming_order_allowed_host_count": 0,
}


class DatabaseEnvelopeError(RuntimeError):
    """The live read-only database envelope differs from the reviewed state."""


def canonical_bytes(payload: Any) -> bytes:
    """Match the canonical serializer used to freeze target table definitions."""

    return (
        json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    ).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _require_dict(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DatabaseEnvelopeError(f"{label} is unavailable or malformed.")
    return payload


def _require_plain_nonnegative_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise DatabaseEnvelopeError(f"{label} is not a nonnegative integer.")
    return value


def _validate_common(payload: dict[str, Any]) -> dict[str, Any]:
    if type(payload.get("database_envelope_version")) is not int or payload.get(
        "database_envelope_version"
    ) != 1:
        raise DatabaseEnvelopeError("The database-envelope probe identity is unexpected.")

    connections = _require_dict(payload.get("connections"), "Database connection proof")
    if (
        connections.get("configured_fuel_connection") != "fuelmysql"
        or connections.get("expected_fuel_connection") != "fuelmysql"
        or connections.get("fuel_driver") != "mysql"
        or connections.get("fuel_database_name_sha256")
        != EXPECTED_FUEL_DATABASE_NAME_SHA256
        or connections.get("default_connection") != "mysql"
        or connections.get("connection_match") is not True
    ):
        raise DatabaseEnvelopeError("The Fuel database connection differs from the reviewed envelope.")

    ledger = _require_dict(payload.get("migration_ledger"), "Migration ledger proof")
    if ledger.get("table") != "migrations" or ledger.get("exists") is not True:
        raise DatabaseEnvelopeError("The Fuel migration ledger is missing or unexpected.")
    if type(ledger.get("row_count")) is not int or ledger.get(
        "row_count"
    ) != EXPECTED_LEDGER_ROW_COUNT:
        raise DatabaseEnvelopeError("The Fuel migration-ledger row count differs from baseline.")
    if ledger.get("rows_sha256") != EXPECTED_LEDGER_SHA256:
        raise DatabaseEnvelopeError("The Fuel migration-ledger identity differs from baseline.")
    if (
        ledger.get("target_migration") != ITEM_META_MIGRATION
        or type(ledger.get("target_entry_count")) is not int
        or ledger.get("target_entry_count") != EXPECTED_TARGET_MIGRATION_ENTRY_COUNT
    ):
        raise DatabaseEnvelopeError("The item_meta target migration is not recorded exactly once.")
    if (
        ledger.get("incoming_order_migration") != INCOMING_ORDER_MIGRATION
        or type(ledger.get("incoming_order_entry_count")) is not int
        or ledger.get("incoming_order_entry_count")
        != EXPECTED_INCOMING_ORDER_MIGRATION_ENTRY_COUNT
    ):
        raise DatabaseEnvelopeError("The incoming-order migration is not recorded exactly once.")

    schema = _require_dict(payload.get("schema"), "Fuel schema proof")
    if schema.get("sha256") != EXPECTED_SCHEMA_SHA256:
        raise DatabaseEnvelopeError("The Fuel schema identity differs from baseline.")
    section_counts = schema.get("section_row_counts")
    if (
        not isinstance(section_counts, dict)
        or set(section_counts) != set(EXPECTED_SCHEMA_SECTION_COUNTS)
        or any(
            type(section_counts.get(section)) is not int
            or section_counts.get(section) != count
            for section, count in EXPECTED_SCHEMA_SECTION_COUNTS.items()
        )
    ):
        raise DatabaseEnvelopeError("The Fuel schema section counts differ from baseline.")

    required_tables = _require_dict(schema.get("required_tables"), "Required-table proof")
    for table in (
        "businesses",
        "dtforders",
        "dtfimages",
        "savedimages",
        "incoming_order_jobs",
        "api_asset_records",
    ):
        if required_tables.get(table) is not True:
            raise DatabaseEnvelopeError(f"Required Fuel table is missing: {table}.")

    item_meta = _require_dict(
        schema.get("savedimages_item_meta"), "savedimages.item_meta proof"
    )
    definition = item_meta.get("definition")
    if item_meta.get("exists") is not True or definition != [EXPECTED_ITEM_META_DEFINITION]:
        raise DatabaseEnvelopeError(
            "savedimages.item_meta does not have the exact reviewed nullable TEXT definition."
        )
    item_meta_nonnull_rows = _require_plain_nonnegative_integer(
        item_meta.get("nonnull_rows"), "savedimages.item_meta non-null row count"
    )

    incoming_tables = _require_dict(
        schema.get("incoming_order_tables"), "Incoming-order table proof"
    )
    expected_incoming_tables = {name: True for name in sorted(INCOMING_ORDER_TABLES)}
    if set(incoming_tables) != INCOMING_ORDER_TABLES or any(
        incoming_tables.get(name) is not True for name in INCOMING_ORDER_TABLES
    ):
        raise DatabaseEnvelopeError("The installed incoming-order table set differs from baseline.")

    incoming_counts = _require_dict(
        schema.get("incoming_order_row_counts"), "Incoming-order row-count proof"
    )
    expected_incoming_counts = {name: 0 for name in sorted(INCOMING_ORDER_TABLES)}
    if set(incoming_counts) != INCOMING_ORDER_TABLES or any(
        type(incoming_counts.get(name)) is not int or incoming_counts.get(name) != 0
        for name in INCOMING_ORDER_TABLES
    ):
        raise DatabaseEnvelopeError("An incoming-order table is nonempty or unavailable.")

    incoming_definitions = _require_dict(
        schema.get("incoming_order_definitions"), "Incoming-order definition proof"
    )
    definitions_sha256 = canonical_sha256(incoming_definitions)
    if definitions_sha256 != EXPECTED_INCOMING_ORDER_TABLE_DEFINITIONS_SHA256:
        raise DatabaseEnvelopeError("Incoming-order table definitions differ from baseline.")
    table_rows = incoming_definitions.get("tables")
    if not isinstance(table_rows, list) or {
        row.get("TABLE_NAME") for row in table_rows if isinstance(row, dict)
    } != INCOMING_ORDER_TABLES:
        raise DatabaseEnvelopeError("Incoming-order table definitions are incomplete.")
    if any(
        not isinstance(row, dict) or str(row.get("ENGINE", "")).lower() != "innodb"
        for row in table_rows
    ):
        raise DatabaseEnvelopeError("An incoming-order table is not InnoDB.")
    statistics = incoming_definitions.get("statistics")
    if not isinstance(statistics, list):
        raise DatabaseEnvelopeError("Incoming-order index definitions are unavailable.")
    observed_indexes = {
        str(row.get("INDEX_NAME")) for row in statistics if isinstance(row, dict)
    }
    if observed_indexes != EXPECTED_INCOMING_ORDER_INDEXES:
        raise DatabaseEnvelopeError("Incoming-order index definitions differ from baseline.")

    disabled_capabilities = payload.get("disabled_capabilities")
    if (
        not isinstance(disabled_capabilities, dict)
        or set(disabled_capabilities) != set(EXPECTED_DISABLED_CAPABILITIES)
        or any(
            disabled_capabilities.get(name) is not False
            for name in (
                "incoming_order_receiver_enabled",
                "incoming_order_job_label_enabled",
                "incoming_order_retention_enabled",
            )
        )
        or type(disabled_capabilities.get("incoming_order_allowed_host_count"))
        is not int
        or disabled_capabilities.get("incoming_order_allowed_host_count") != 0
    ):
        raise DatabaseEnvelopeError("An incoming-order, job-label, or retention capability is enabled.")
    if payload.get("queue_connection") != "sync":
        raise DatabaseEnvelopeError("The queue connection differs from the reviewed sync setting.")
    queue_tables = _require_dict(payload.get("queue_tables"), "Queue table proof")
    if set(queue_tables) != {"jobs", "failed_jobs"} or any(
        type(queue_tables.get(name)) is not int or queue_tables.get(name) != 0
        for name in ("jobs", "failed_jobs")
    ):
        raise DatabaseEnvelopeError("The jobs or failed_jobs queue table is absent or nonempty.")

    return {
        "status": "pass",
        "database_envelope_version": 1,
        "schema_sha256": EXPECTED_SCHEMA_SHA256,
        "schema_section_row_counts": dict(EXPECTED_SCHEMA_SECTION_COUNTS),
        "migration_ledger": {
            "row_count": EXPECTED_LEDGER_ROW_COUNT,
            "rows_sha256": EXPECTED_LEDGER_SHA256,
            "target_migration": ITEM_META_MIGRATION,
            "target_entry_count": EXPECTED_TARGET_MIGRATION_ENTRY_COUNT,
            "incoming_order_migration": INCOMING_ORDER_MIGRATION,
            "incoming_order_entry_count": EXPECTED_INCOMING_ORDER_MIGRATION_ENTRY_COUNT,
        },
        "savedimages_item_meta": {
            "definition": dict(EXPECTED_ITEM_META_DEFINITION),
            "nonnull_rows": item_meta_nonnull_rows,
        },
        "incoming_order_tables": expected_incoming_tables,
        "incoming_order_row_counts": expected_incoming_counts,
        "incoming_order_definitions_sha256": definitions_sha256,
        "capabilities_disabled": True,
        "queues_empty": True,
    }


def validate_pre_source_database_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Require the exact installed schema while item_meta is still unused."""

    result = _validate_common(payload)
    if result["savedimages_item_meta"]["nonnull_rows"] != 0:
        raise DatabaseEnvelopeError(
            "savedimages.item_meta must have zero non-null rows before source deployment."
        )
    result["item_meta_row_policy"] = "pre_source_exactly_zero"
    return result


def validate_post_cutover_database_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep schema/ledger fixed while allowing legitimate post-source growth."""

    result = _validate_common(payload)
    result["item_meta_row_policy"] = "post_source_nonnegative_growth_allowed"
    return result


__all__ = [
    "DatabaseEnvelopeError",
    "validate_pre_source_database_envelope",
    "validate_post_cutover_database_envelope",
]
