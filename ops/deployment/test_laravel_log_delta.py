#!/usr/bin/env python3
"""Focused tests for the Laravel remember-cookie log-delta guard."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/Fixtures/Deployment/LaravelLogs"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import laravel_log_delta as guard  # noqa: E402


@contextmanager
def restrictive_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


class LaravelLogParserTest(unittest.TestCase):
    def fixture(self, name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    def test_empty_delta_passes(self) -> None:
        report = guard.inspect_log_bytes(b"")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["entry_count"], 0)
        self.assertEqual(report["sha256"], guard.sha256_bytes(b""))

    def test_reviewed_56_error_delta_is_nonfatal_and_exact(self) -> None:
        content = self.fixture("reviewed-56-error-delta.redacted.txt")
        provenance = json.loads(
            (FIXTURES / "reviewed-56-error-delta.provenance.json").read_text("utf-8")
        )
        report = guard.inspect_log_bytes(content)
        entries = guard.parse_laravel_entries(content.decode("utf-8"))

        self.assertEqual(
            guard.sha256_bytes(content),
            "d8bf0641949f96ac39240e92f0b5545c4ac5fb6a8fbfa4af2fe2f6029dd27f53",
        )
        self.assertEqual(report["sha256"], provenance["fixture"]["sha256"])
        self.assertEqual(report["bytes"], provenance["fixture"]["bytes"])
        self.assertEqual(report["entry_count"], 56)
        self.assertEqual(report["level_counts"], {"ERROR": 56})
        self.assertEqual(report["nonfatal_error_entry_count"], 56)
        self.assertEqual(report["fatal_finding_count"], 0)
        self.assertEqual([entry.message for entry in entries[:28]], [entry.message for entry in entries[28:]])
        self.assertFalse(provenance["redaction"]["customer_addresses_included"])
        self.assertFalse(provenance["redaction"]["full_carrier_payloads_included"])

    def test_fixture_manifest_pins_every_redacted_or_synthetic_input(self) -> None:
        manifest = json.loads((FIXTURES / "fixture-manifest.json").read_text("utf-8"))
        self.assertEqual(
            manifest["reviewed_transparency_source"]["commit"],
            "3db18d1fff3f599299eecd2aae21b9102fc45540",
        )
        self.assertEqual(
            manifest["reviewed_transparency_source"]["parser_sha256"],
            "4bdec766469e71568631dbcf7408e94696f2fd99c46c18dd58b8374f31a488c8",
        )
        for name, expected_sha256 in manifest["fixtures"].items():
            with self.subTest(fixture=name):
                self.assertEqual(guard.sha256_file(FIXTURES / name), expected_sha256)
        self.assertFalse(manifest["privacy"]["raw_production_logs_included"])

    def test_exact_stale_session_guard_hash_equals_failure_is_distinct(self) -> None:
        report = guard.analyze_log_bytes(self.fixture("stale-remember-cookie.txt"))
        self.assertEqual(report["status"], "fail")
        self.assertIn("stale_remember_cookie", report["signal_counts"])
        self.assertIn("exception", report["signal_counts"])
        self.assertIn("trace", report["signal_counts"])
        with self.assertRaises(guard.LaravelLogDeltaError):
            guard.inspect_log_bytes(self.fixture("stale-remember-cookie.txt"))

    def test_dependency_candidate_failure_is_fatal_but_normal_info_is_not(self) -> None:
        failed = guard.analyze_log_bytes(
            b"[2026-10-02 23:15:01] production.ERROR: "
            b"Laravel 12.69.1 candidate failed runtime verification\n"
        )
        self.assertIn("candidate_error", failed["signal_counts"])
        normal = guard.inspect_log_bytes(
            b"[2026-10-02 23:15:02] production.INFO: "
            b"Laravel 12.69.1 runtime verification complete\n"
        )
        self.assertEqual(normal["status"], "pass")

    def test_genuine_failure_fixtures_remain_fatal(self) -> None:
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
            "genuine-orphan-trace.txt": "unparsed_data",
        }
        for fixture, signal in cases.items():
            with self.subTest(fixture=fixture):
                report = guard.analyze_log_bytes(self.fixture(fixture))
                self.assertEqual(report["status"], "fail")
                self.assertIn(signal, report["signal_counts"])

    def test_critical_alert_and_emergency_fail_without_message_keywords(self) -> None:
        for level in ("CRITICAL", "ALERT", "EMERGENCY"):
            with self.subTest(level=level):
                report = guard.analyze_log_bytes(
                    f"[2026-10-02 23:20:00] production.{level}: unavailable\n".encode()
                )
                self.assertIn("severe_level", report["signal_counts"])

    def test_invalid_utf8_and_nonempty_unparsed_data_fail_closed(self) -> None:
        invalid = guard.analyze_log_bytes(
            b"[2026-10-02 23:21:00] production.INFO: invalid \xff\n"
        )
        self.assertTrue(invalid["invalid_utf8"])
        self.assertEqual(invalid["signal_counts"], {"invalid_utf8": 1})

        for content in (
            b"orphan data without a header\n",
            b"[2026-10-02 23:22:00] production.UNKNOWN: drift\n",
        ):
            with self.subTest(content=content):
                report = guard.analyze_log_bytes(content)
                self.assertIn("unparsed_data", report["signal_counts"])
                self.assertGreater(report["orphan_entry_count"], 0)

    def test_partial_trailing_header_or_continuation_fails_closed(self) -> None:
        for content in (
            b"[2026-10-02 23:22:00] production.ERR",
            (
                b"[2026-10-02 23:22:00] production.ERROR: checkout diagnostic\n"
                b"[stacktr"
            ),
        ):
            with self.subTest(content=content):
                report = guard.analyze_log_bytes(content)
                self.assertEqual(report["status"], "fail")
                self.assertIn("incomplete_trailing_data", report["signal_counts"])

    def test_multiline_entry_is_classified_as_one_complete_entry(self) -> None:
        entries = guard.parse_laravel_entries(self.fixture("genuine-trace.txt").decode())
        self.assertEqual(len(entries), 2)
        self.assertIn("[stacktrace]", entries[0].message)
        self.assertEqual(entries[1].level, "INFO")
        self.assertEqual(guard.classify_entry(entries[1]), ())

    def test_reports_never_copy_log_messages(self) -> None:
        secret = "synthetic-customer-value-never-in-summary"
        report = guard.analyze_log_bytes(
            (
                "[2026-10-02 23:23:00] production.ERROR: "
                f"RuntimeException: {secret}\n"
            ).encode()
        )
        self.assertNotIn(secret, json.dumps(report, sort_keys=True))


class RotationSafeCollectorTest(unittest.TestCase):
    BASELINE = b"[2026-10-02 23:00:00] production.INFO: baseline\n"

    def make_paths(self, root: Path) -> tuple[Path, Path]:
        logs = root / "storage" / "logs"
        logs.mkdir(parents=True)
        log = logs / "laravel.log"
        log.write_bytes(self.BASELINE)
        private = root / "private-log-evidence"
        return log, private

    def test_empty_monitoring_delta_passes_with_private_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            log, private = self.make_paths(Path(temporary))
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            result = collector.finish()

            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["summary"]["captured_bytes"], 0)
            self.assertEqual(result["summary"]["analysis"]["entry_count"], 0)
            self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
            for path in private.iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path)

    def test_rename_rotation_captures_old_and_new_inode_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            root = Path(temporary)
            log, private = self.make_paths(root)
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            old_writer = log.open("ab")
            try:
                old_writer.write(
                    b"[2026-10-02 23:01:00] production.INFO: before rotation\n"
                )
                old_writer.flush()
                log.replace(log.with_name("laravel.log.1"))
                log.write_bytes(
                    b"[2026-10-02 23:02:00] production.INFO: new generation\n"
                )
                old_writer.write(
                    b"[2026-10-02 23:02:01] production.INFO: late old generation write\n"
                )
                old_writer.flush()
            finally:
                old_writer.close()

            result = collector.finish()

            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["summary"]["segment_count"], 2)
            self.assertEqual(result["summary"]["analysis"]["entry_count"], 3)
            self.assertEqual(result["summary"]["analysis"]["level_counts"], {"INFO": 3})
            self.assertGreater(result["summary"]["captured_bytes"], 0)
            state = json.loads((private / "capture-state.json").read_text("utf-8"))
            self.assertEqual(state["rotation_count"], 1)
            self.assertEqual(state["active_segment_id"], "segment-0002")

    def test_truncation_fails_closed_before_any_result_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            log, private = self.make_paths(Path(temporary))
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            log.write_bytes(b"short\n")
            with self.assertRaises(guard.LogContinuityError) as raised:
                collector.capture()
            collector.close()

            self.assertEqual(raised.exception.signal, "log_truncated")
            state = json.loads((private / "capture-state.json").read_text("utf-8"))
            self.assertEqual(state["status"], "fail")
            self.assertEqual(state["events"][-1]["signal"], "log_truncated")

    def test_copytruncate_regrow_is_caught_by_boundary_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            root = Path(temporary)
            log, private = self.make_paths(root)
            with log.open("ab") as handle:
                handle.write(b"A" * 70000 + b"\n")
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            original_size = log.stat().st_size
            log.write_bytes(b"B" * original_size)
            with self.assertRaises(guard.LogContinuityError) as raised:
                collector.capture()
            collector.close()

            self.assertEqual(raised.exception.signal, "log_continuity_anchor_changed")

    def test_empty_log_write_then_truncate_is_not_silently_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            root = Path(temporary)
            log, private = self.make_paths(root)
            log.write_bytes(b"")
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            with log.open("ab") as handle:
                handle.write(b"bytes removed before the next sample")
                handle.flush()
                os.fsync(handle.fileno())
            with log.open("r+b") as handle:
                handle.truncate(0)
                handle.flush()
                os.fsync(handle.fileno())
            with self.assertRaises(guard.LogContinuityError) as raised:
                collector.capture()
            collector.close()

            self.assertEqual(raised.exception.signal, "log_modified_without_append")

    def test_raw_bytes_are_private_and_redacted_summary_is_message_free(self) -> None:
        secret = b"synthetic-customer-address-token"
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            log, private = self.make_paths(Path(temporary))
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            with log.open("ab") as handle:
                handle.write(
                    b"[2026-10-02 23:03:00] production.INFO: diagnostic "
                    + secret
                    + b"\n"
                )
            result = collector.finish()

            summary_bytes = Path(result["analysis_path"]).read_bytes()
            self.assertNotIn(secret, summary_bytes)
            chunk_paths = list(private.glob("segment-*-chunk-*.bin"))
            self.assertEqual(len(chunk_paths), 1)
            self.assertIn(secret, chunk_paths[0].read_bytes())
            self.assertEqual(stat.S_IMODE(chunk_paths[0].stat().st_mode), 0o600)

    def test_boundary_crossing_entry_has_replayable_private_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            root = Path(temporary)
            log, private = self.make_paths(root)
            log.write_bytes(
                b"[2026-10-02 23:03:00] production.ERROR: checkout diagnostic"
            )
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            with log.open("ab") as handle:
                handle.write(
                    b" continued\n"
                    b"[2026-10-02 23:03:01] production.INFO: complete\n"
                )
            result = collector.finish()

            self.assertEqual(result["status"], "pass")
            manifest = json.loads((private / "raw-manifest.json").read_text("utf-8"))
            segment = manifest["segments"][0]
            context = segment["analysis_context"]
            self.assertIsInstance(context, dict)
            context_path = private / context["name"]
            self.assertEqual(stat.S_IMODE(context_path.stat().st_mode), 0o600)
            delta = b"".join(
                (private / chunk["name"]).read_bytes()
                for chunk in segment["chunks"]
            )
            replay = context_path.read_bytes() + delta[segment["analysis_delta_offset"] :]
            report_segment = result["summary"]["segments"][0]
            self.assertEqual(guard.sha256_bytes(replay), report_segment["analysis_sha256"])
            self.assertEqual(len(replay), report_segment["analysis_bytes"])
            self.assertEqual(report_segment["analysis"]["entry_count"], 2)

    def test_line_boundary_continuation_before_next_header_is_not_discarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            root = Path(temporary)
            log, private = self.make_paths(root)
            log.write_bytes(
                b"[2026-10-02 23:03:00] production.ERROR: checkout diagnostic\n"
            )
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            with log.open("ab") as handle:
                handle.write(
                    b"[stacktrace]\n"
                    b"#0 /srv/app.php(1): synthetic()\n"
                    b"[2026-10-02 23:03:01] production.INFO: complete\n"
                )
            result = collector.finish(raise_on_failure=False)

            self.assertEqual(result["status"], "fail")
            self.assertIn("trace", result["summary"]["analysis"]["signal_counts"])
            manifest = json.loads((private / "raw-manifest.json").read_text("utf-8"))
            self.assertIsNotNone(manifest["segments"][0]["analysis_context"])

    def test_parser_failure_is_preserved_in_redacted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, restrictive_umask():
            log, private = self.make_paths(Path(temporary))
            collector = guard.RotationSafeLaravelLogCollector(log, private)
            with log.open("ab") as handle:
                handle.write((FIXTURES / "stale-remember-cookie.txt").read_bytes())
            result = collector.finish(raise_on_failure=False)

            self.assertEqual(result["status"], "fail")
            signals = result["summary"]["analysis"]["signal_counts"]
            self.assertIn("stale_remember_cookie", signals)
            serialized = json.dumps(result["summary"], sort_keys=True)
            self.assertNotIn("known_string", serialized)


class IndependentReviewReceiptTest(unittest.TestCase):
    def binding(self) -> dict[str, str]:
        return guard.build_independent_review_binding(
            **{
                field: guard.sha256_bytes(field.encode("utf-8"))
                for field in guard.REVIEW_BINDING_FIELDS
            }
        )

    def receipt(self, binding: dict[str, str]) -> dict[str, object]:
        return {
            "artifact": guard.INDEPENDENT_REVIEW_ARTIFACT,
            "status": "pass",
            "decision": "accept",
            "review_mode": "independent_read_only",
            "reviewed_at_utc": "2026-10-03T01:00:00Z",
            "reviewer_id": "independent-reviewer-synthetic",
            "evidence_binding": binding,
            "checks": guard.INDEPENDENT_REVIEW_CHECKS,
        }

    def test_exact_independent_review_receipt_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "review.json"
            path.write_bytes(guard.canonical_bytes(self.receipt(self.binding())))
            document = guard.validate_independent_review_receipt(
                path,
                expected_sha256=guard.sha256_file(path),
                expected_binding=self.binding(),
            )
            self.assertEqual(document["decision"], "accept")

    def test_review_receipt_rejects_binding_or_check_drift(self) -> None:
        binding = self.binding()
        for drift in ("binding", "checks"):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temporary:
                receipt = self.receipt(binding)
                if drift == "binding":
                    receipt["evidence_binding"] = dict(binding)
                    receipt["evidence_binding"]["parser_sha256"] = "0" * 64
                else:
                    receipt["checks"] = dict(guard.INDEPENDENT_REVIEW_CHECKS)
                    receipt["checks"]["raw_private_delta_reviewed_read_only"] = False
                path = Path(temporary) / "review.json"
                path.write_bytes(guard.canonical_bytes(receipt))
                with self.assertRaises(guard.IndependentReviewError):
                    guard.validate_independent_review_receipt(
                        path,
                        expected_sha256=guard.sha256_file(path),
                        expected_binding=binding,
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
