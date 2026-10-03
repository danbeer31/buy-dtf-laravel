from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))
import rehearse_laravel_dependency_opcache as REHEARSAL


class LaravelDependencyOpcacheRehearsalStaticTest(unittest.TestCase):
    def test_source_is_loopback_disposable_and_has_no_service_or_production_access(self) -> None:
        source = inspect.getsource(REHEARSAL)
        lowered = source.lower()
        self.assertNotIn("134.209.175.25", source)
        self.assertNotIn("buy-dtf.com", lowered)
        self.assertNotIn("systemctl", lowered)
        self.assertNotIn("service restart", lowered)
        self.assertNotIn("sudo ", lowered)
        self.assertIn('"127.0.0.1"', source)
        self.assertIn("tempfile.TemporaryDirectory", source)
        self.assertIn("start_new_session=True", source)
        self.assertIn("_stop_process(nginx_process)", source)
        self.assertIn("_stop_process(fpm_process)", source)

    def test_daemon_configs_are_foreground_isolated_and_enable_nonzero_revalidation(self) -> None:
        if os.name != "posix":
            self.skipTest("POSIX account database is required to render FPM configuration")
        with tempfile.TemporaryDirectory(prefix="buy-dtf-opcache-config-") as temporary:
            root = Path(temporary)
            fpm = REHEARSAL.render_fpm_configuration(
                root=root,
                socket_path=root / "runtime/fpm.sock",
                pid_path=root / "runtime/fpm.pid",
                error_log=root / "private/fpm.log",
            )
            nginx = REHEARSAL.render_nginx_configuration(
                root=root,
                public_root=root / "application/public",
                socket_path=root / "runtime/fpm.sock",
                origin_port=18081,
                public_port=18082,
                pid_path=root / "runtime/nginx.pid",
                error_log=root / "private/nginx-error.log",
                access_log=root / "private/nginx-access.log",
            )
        self.assertIn("daemonize = no", fpm)
        self.assertIn("pm = static", fpm)
        self.assertIn("listen = ", fpm)
        self.assertIn("php_admin_value[opcache.enable] = 1", fpm)
        self.assertIn("php_admin_value[opcache.validate_timestamps] = 1", fpm)
        self.assertIn(
            f"php_admin_value[opcache.revalidate_freq] = "
            f"{REHEARSAL.REVALIDATE_FREQUENCY_SECONDS}",
            fpm,
        )
        self.assertGreater(REHEARSAL.REVALIDATE_FREQUENCY_SECONDS, 0)
        self.assertIn("listen 127.0.0.1:18081", nginx)
        self.assertIn("listen 127.0.0.1:18082", nginx)
        self.assertIn("fastcgi_pass unix:", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:18081", nginx)
        self.assertIn(f"add_header {REHEARSAL.ROUTE_HEADER} origin always", nginx)
        self.assertIn(f"add_header {REHEARSAL.ROUTE_HEADER} public always", nginx)
        self.assertNotIn("listen 80;", nginx)
        self.assertNotIn("listen 443", nginx)

    def test_original_probe_payload_matches_shared_policy_contract(self) -> None:
        source = REHEARSAL.original_front_controller().decode("utf-8")
        self.assertIn("buy-dtf-php-fpm-opcache-probe-v1", source)
        self.assertIn("PHP_SAPI", source)
        for name in (
            "opcache.enable",
            "opcache.validate_timestamps",
            "opcache.revalidate_freq",
            "opcache.file_update_protection",
        ):
            self.assertIn(name, source)
        self.assertIn("opcache_get_configuration", source)

    def test_rehearsal_orders_both_stale_controls_around_derived_waits(self) -> None:
        source = inspect.getsource(REHEARSAL.run_rehearsal)
        ordered_markers = (
            "gate_install = atomic_install",
            "immediate_original = http_probe",
            "gate_wait = revalidation_wait",
            "gate_probes: list",
            "original_restore = atomic_install",
            "immediate_gate = http_probe",
            "original_wait = revalidation_wait",
            "final_probes: list",
        )
        offsets = [source.index(marker) for marker in ordered_markers]
        self.assertEqual(sorted(offsets), offsets)
        self.assertIn('("origin-1", ORIGIN_ROUTE, origin_port)', source)
        self.assertIn('("origin-2", ORIGIN_ROUTE, origin_port)', source)
        self.assertIn('("public", PUBLIC_ROUTE, public_port)', source)
        self.assertIn("gate.derive_opcache_revalidation_policy(warm_payload)", source)

    def test_revalidation_wait_uses_monotonic_deadline_and_rechecks_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-opcache-wait-") as temporary:
            path = Path(temporary) / "index.php"
            path.write_bytes(b"<?php echo 'stable';\n")
            times = iter((1_000_000_000, 3_000_000_000, 6_000_000_000, 6_000_000_000))
            sleeps: list[float] = []
            receipt = REHEARSAL.revalidation_wait(
                minimum_wait_seconds=5,
                path=path,
                expected_sha256=REHEARSAL.file_identity(path)["sha256"],
                monotonic_ns=lambda: next(times),
                wall_time=iter((1_700_000_000.0, 1_700_000_005.0)).__next__,
                sleeper=sleeps.append,
            )
        self.assertEqual(5, receipt["configured_wait_seconds"])
        self.assertEqual(5_000_000_000, receipt["elapsed_monotonic_ns"])
        self.assertEqual([3.0], sleeps)
        self.assertEqual(receipt["identity_before"], receipt["identity_after"])
        self.assertEqual("2023-11-14T22:13:25.000000Z", receipt["earliest_probe_at_utc"])

    def test_revalidation_wait_rejects_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-opcache-drift-") as temporary:
            path = Path(temporary) / "index.php"
            path.write_bytes(b"original")
            expected = REHEARSAL.file_identity(path)["sha256"]
            monotonic_values = iter((0, 0, 5_000_000_000, 5_000_000_000))

            def mutate(_seconds: float) -> None:
                path.write_bytes(b"drift")

            with self.assertRaisesRegex(REHEARSAL.RehearsalError, "changed during"):
                REHEARSAL.revalidation_wait(
                    minimum_wait_seconds=5,
                    path=path,
                    expected_sha256=expected,
                    monotonic_ns=lambda: next(monotonic_values),
                    wall_time=iter((1_700_000_000.0, 1_700_000_005.0)).__next__,
                    sleeper=mutate,
                )

    def test_graceful_prerequisite_report_lists_missing_tools(self) -> None:
        with patch.object(REHEARSAL, "discover_binary", return_value=None):
            report = REHEARSAL.prerequisite_report()
        self.assertEqual("unavailable", report["status"])
        self.assertIn("nginx executable", report["missing"])
        self.assertIn("PHP-FPM executable", report["missing"])
        self.assertTrue(report["local_only"])
        json.dumps(report)

    def test_gate_validation_requires_status_route_nonce_header_and_sentinel(self) -> None:
        valid = {
            "status": 503,
            "route_bound": True,
            "nonce_bound": True,
            "gate_header_verified": True,
            "gate_probe_header_verified": True,
            "gate_sentinel_verified": True,
            "original_sentinel_verified": False,
        }
        REHEARSAL.require_gate(valid)
        for field, invalid_value in (
            ("status", 200),
            ("route_bound", False),
            ("nonce_bound", False),
            ("gate_header_verified", False),
            ("gate_probe_header_verified", False),
            ("gate_sentinel_verified", False),
            ("original_sentinel_verified", True),
        ):
            with self.subTest(field=field):
                invalid = dict(valid)
                invalid[field] = invalid_value
                with self.assertRaises(REHEARSAL.RehearsalError):
                    REHEARSAL.require_gate(invalid)


@unittest.skipUnless(
    os.name == "posix"
    and hasattr(os, "geteuid")
    and os.geteuid() == 0
    and REHEARSAL.prerequisite_report()["status"] == "ready",
    "root nginx/PHP-FPM prerequisites are unavailable",
)
class LaravelDependencyOpcacheProductionLikeRehearsalTest(unittest.TestCase):
    def test_warm_swap_stale_wait_gate_restore_stale_wait_original(self) -> None:
        receipt = REHEARSAL.run_rehearsal(Path("/tmp"))
        self.assertEqual("pass", receipt["status"])
        self.assertTrue(receipt["loopback_only"])
        self.assertFalse(receipt["production_accessed"])
        self.assertFalse(receipt["system_services_changed"])
        self.assertGreater(receipt["opcache_policy"]["revalidate_freq_seconds"], 0)
        self.assertGreater(
            receipt["opcache_policy"]["minimum_wait_seconds"],
            receipt["opcache_policy"]["complete_revalidation_interval_seconds"],
        )
        sequence = receipt["sequence"]
        self.assertEqual(
            200,
            sequence["immediate_stale_original_after_gate_install"]["status"],
        )
        self.assertEqual(
            [
                REHEARSAL.ORIGIN_ROUTE,
                REHEARSAL.ORIGIN_ROUTE,
                REHEARSAL.PUBLIC_ROUTE,
            ],
            [probe["route"] for probe in sequence["gate_probes"]],
        )
        self.assertTrue(all(probe["status"] == 503 for probe in sequence["gate_probes"]))
        self.assertEqual(
            503,
            sequence["immediate_stale_gate_after_original_restore"]["status"],
        )
        self.assertTrue(
            all(probe["status"] == 200 for probe in sequence["final_original_probes"])
        )
        self.assertTrue(receipt["cache_busters"]["unique"])
        self.assertEqual(
            receipt["cache_busters"]["count"],
            len(set(receipt["cache_busters"]["sha256_values"])),
        )
        self.assertTrue(
            all(item["mode"] == 0o600 for item in receipt["private_evidence_manifest"])
        )


if __name__ == "__main__":
    unittest.main()
