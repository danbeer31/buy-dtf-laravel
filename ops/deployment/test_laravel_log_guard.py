#!/usr/bin/env python3
"""Regression tests for Laravel deployment-log classification."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/Fixtures/Deployment/LaravelLogs"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import laravel_log_guard as guard  # noqa: E402


class LaravelLogGuardTest(unittest.TestCase):
    def fixture(self, name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    def test_reviewed_56_error_delta_is_nonfatal_by_entry_content(self) -> None:
        content = self.fixture("reviewed-56-error-delta.redacted.txt")
        provenance = json.loads(
            (FIXTURES / "reviewed-56-error-delta.provenance.json").read_text("utf-8")
        )

        report = guard.inspect_log_bytes(content)
        entries = guard.parse_laravel_entries(content.decode("utf-8"))

        self.assertEqual(report["sha256"], provenance["fixture"]["sha256"])
        self.assertEqual(report["bytes"], provenance["fixture"]["bytes"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["entry_count"], 56)
        self.assertEqual(report["level_counts"], {"ERROR": 56})
        self.assertEqual(report["nonfatal_error_entry_count"], 56)
        self.assertEqual(report["fatal_entry_count"], 0)
        self.assertEqual(report["fatal_findings"], [])
        self.assertTrue(all(entry.level == "ERROR" for entry in entries))
        self.assertEqual(
            [entry.message for entry in entries[:28]],
            [entry.message for entry in entries[28:]],
        )

        fixture_text = content.decode("utf-8")
        self.assertIn("[customer address redacted]", fixture_text)
        self.assertIn("[carrier diagnostics redacted]", fixture_text)
        self.assertNotIn('"street1"', fixture_text)
        self.assertNotIn('"amount"', fixture_text)

    def test_provenance_pins_private_source_and_independent_review(self) -> None:
        provenance = json.loads(
            (FIXTURES / "reviewed-56-error-delta.provenance.json").read_text("utf-8")
        )
        self.assertEqual(
            provenance["private_source"]["sha256"],
            "81e429a215856b401d74a361c86a37453e65047af6faf3802127b04f61100a08",
        )
        self.assertEqual(provenance["private_source"]["reviewed_error_entries"], 56)
        self.assertEqual(
            provenance["independent_review"]["sha256"],
            "bbfd8079f73f5196ee4e519fbdee523058e0d843f375cb369fafe90c327fa760",
        )
        self.assertFalse(provenance["redaction"]["customer_addresses_included"])
        self.assertFalse(provenance["redaction"]["full_carrier_payloads_included"])

    def test_multiline_entries_attach_context_until_the_next_header(self) -> None:
        entries = guard.parse_laravel_entries(
            self.fixture("genuine-trace.txt").decode("utf-8")
        )
        self.assertEqual(len(entries), 2)
        self.assertIn("[stacktrace]", entries[0].message)
        self.assertIn("#1 {main}", entries[0].message)
        self.assertEqual(entries[1].level, "INFO")
        self.assertEqual(guard.classify_entry(entries[1]), ())

        exception_entries = guard.parse_laravel_entries(
            self.fixture("genuine-exception.txt").decode("utf-8")
        )
        self.assertEqual(len(exception_entries), 1)
        self.assertIn('"exception":"[object]', exception_entries[0].message)

    def test_genuine_failure_fixtures_trigger_the_expected_signal(self) -> None:
        cases = {
            "genuine-exception.txt": "exception",
            "genuine-trace.txt": "trace",
            "genuine-fatal.txt": "fatal",
            "genuine-sqlstate.txt": "sqlstate",
            "genuine-missing-class.txt": "missing_class",
            "genuine-missing-view.txt": "missing_view",
            "genuine-type-error.txt": "exception",
            "genuine-structured-exception.txt": "exception",
            "genuine-caught-failure-message.txt": "failure_message",
            "genuine-orphan-trace.txt": "trace",
        }
        for name, expected_signal in cases.items():
            with self.subTest(fixture=name):
                content = self.fixture(name)
                report = guard.analyze_log_bytes(content)
                self.assertEqual(report["status"], "fail")
                self.assertIn(expected_signal, report["signal_counts"])
                with self.assertRaises(guard.LaravelLogGuardError) as raised:
                    guard.inspect_log_bytes(content)
                self.assertEqual(raised.exception.report, report)

    def test_structured_exception_types_trigger_rollback(self) -> None:
        content = self.fixture("genuine-structured-exception.txt")
        report = guard.analyze_log_bytes(content)
        self.assertEqual(report["entry_count"], 2)
        self.assertEqual(report["fatal_entry_count"], 2)
        self.assertEqual(report["signal_counts"], {"exception": 2})
        with self.assertRaises(guard.LaravelLogGuardError):
            guard.inspect_log_bytes(content)

    def test_failure_level_with_failure_word_triggers_rollback(self) -> None:
        content = self.fixture("genuine-caught-failure-message.txt")
        report = guard.analyze_log_bytes(content)
        self.assertEqual(report["entry_count"], 2)
        self.assertEqual(report["fatal_entry_count"], 2)
        self.assertEqual(report["signal_counts"], {"failure_message": 2})
        with self.assertRaises(guard.LaravelLogGuardError):
            guard.inspect_log_bytes(content)

    def test_orphan_trace_is_retained_and_fails_closed(self) -> None:
        content = self.fixture("genuine-orphan-trace.txt")
        report = guard.analyze_log_bytes(content)
        entries = guard.parse_laravel_entries(content.decode("utf-8"))
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].orphan)
        self.assertEqual(report["orphan_entry_count"], 1)
        self.assertEqual(report["signal_counts"], {"trace": 1, "unparsed_data": 1})

    def test_critical_alert_and_emergency_always_fail_closed(self) -> None:
        for level, message in (
            ("CRITICAL", "service unavailable"),
            ("ALERT", "operator attention required"),
            ("EMERGENCY", "disk unavailable"),
        ):
            with self.subTest(level=level):
                content = (
                    f"[2026-10-02 01:07:00] production.{level}: {message}\n"
                ).encode("utf-8")
                report = guard.analyze_log_bytes(content)
                self.assertEqual(report["status"], "fail")
                self.assertIn("severe_level", report["signal_counts"])
                with self.assertRaises(guard.LaravelLogGuardError):
                    guard.inspect_log_bytes(content)

    def test_invalid_utf8_fails_closed_without_copying_log_bytes(self) -> None:
        secret = b"customer-secret-\xff-value"
        content = (
            b"[2026-10-02 01:07:01] production.ERROR: " + secret + b"\n"
        )
        report = guard.analyze_log_bytes(content)
        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["status"], "fail")
        self.assertTrue(report["invalid_utf8"])
        self.assertGreater(report["decode_replacement_count"], 0)
        self.assertEqual(report["signal_counts"], {"invalid_utf8": 1})
        self.assertEqual(report["fatal_entry_count"], 0)
        self.assertEqual(report["global_failure_count"], 1)
        self.assertEqual(report["fatal_finding_count"], 1)
        self.assertEqual(report["rollback_finding_count"], 1)
        self.assertNotIn("customer-secret", serialized)
        with self.assertRaises(guard.LaravelLogGuardError):
            guard.inspect_log_bytes(content)

    def test_invalid_utf8_does_not_double_count_its_parsed_entry(self) -> None:
        content = (
            b"[2026-10-02 01:07:01] production.CRITICAL: invalid byte \xff\n"
        )
        report = guard.analyze_log_bytes(content)
        self.assertEqual(report["entry_count"], 1)
        self.assertEqual(report["fatal_entry_count"], 1)
        self.assertEqual(report["global_failure_count"], 1)
        self.assertEqual(report["fatal_finding_count"], 2)
        self.assertEqual(report["rollback_finding_count"], 2)

    def test_valid_replacement_character_is_not_mislabeled_invalid_utf8(self) -> None:
        content = (
            "[2026-10-02 01:07:02] production.INFO: valid replacement \ufffd\n"
        ).encode("utf-8")
        report = guard.inspect_log_bytes(content)
        self.assertFalse(report["invalid_utf8"])
        self.assertEqual(report["decode_replacement_count"], 0)

    def test_nonempty_unparsed_data_fails_closed(self) -> None:
        for index, content in enumerate((
            b"format drift without a Laravel header\n",
            (
                b"[2026-10-02 01:07:03] production.INFO: parsed entry\n"
                b"[2026-10-02 01:07:04] production.UNKNOWN: format drift\n"
            ),
        ), start=1):
            with self.subTest(case=index):
                report = guard.analyze_log_bytes(content)
                self.assertGreater(report["orphan_entry_count"], 0)
                self.assertIn("unparsed_data", report["signal_counts"])
                with self.assertRaises(guard.LaravelLogGuardError):
                    guard.inspect_log_bytes(content)

    def test_each_actual_candidate_failure_phrase_is_fatal(self) -> None:
        content = self.fixture("genuine-candidate-error.txt")
        report = guard.analyze_log_bytes(content)
        self.assertEqual(report["entry_count"], 6)
        self.assertEqual(report["fatal_entry_count"], 6)
        self.assertEqual(report["signal_counts"], {"candidate_error": 6})
        with self.assertRaises(guard.LaravelLogGuardError):
            guard.inspect_log_bytes(content)

    def test_candidate_info_without_failure_word_is_nonfatal(self) -> None:
        content = (
            b"[2026-10-02 01:08:00] production.INFO: "
            b"ProductionHelper::addToProduction started for synthetic image\n"
        )
        report = guard.inspect_log_bytes(content)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["fatal_entry_count"], 0)

    def test_error_level_alone_is_not_a_failure_signal(self) -> None:
        content = (
            b"[2026-10-02 01:09:00] production.ERROR: "
            b"Routine checkout diagnostic; no exception occurred\n"
        )
        report = guard.inspect_log_bytes(content)
        self.assertEqual(report["level_counts"], {"ERROR": 1})
        self.assertEqual(report["nonfatal_error_entry_count"], 1)
        self.assertEqual(report["fatal_entry_count"], 0)

    def test_caught_exception_diagnostic_with_exception_colon_is_fatal(self) -> None:
        content = (
            b"[2026-10-02 01:09:01] production.ERROR: "
            b"DEBUG: Shippo createShipment Exception: synthetic transport failure\n"
        )
        report = guard.analyze_log_bytes(content)
        self.assertEqual(report["signal_counts"], {"exception": 1})
        with self.assertRaises(guard.LaravelLogGuardError):
            guard.inspect_log_bytes(content)

    def test_reports_do_not_copy_log_messages(self) -> None:
        secret = "synthetic-message-that-must-not-enter-report"
        content = (
            "[2026-10-02 01:10:00] production.ERROR: "
            f"RuntimeException: {secret}\n"
        ).encode("utf-8")
        report = guard.analyze_log_bytes(content)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertEqual(report["fatal_entry_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
