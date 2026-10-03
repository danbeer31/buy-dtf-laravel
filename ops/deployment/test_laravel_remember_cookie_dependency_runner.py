from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
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

    def test_v4_candidate_identity_is_fully_pinned(self) -> None:
        self.assertEqual(
            "6539058cf602fc23b03552665faf9a32c6975e29e6cb11fb5b2deb2c7e02afa9",
            RUNNER.HANDOFF_SHA256,
        )
        self.assertEqual(
            RUNNER.HANDOFF_SHA256,
            self.sha256(
                ROOT
                / "ops/evidence/laravel-remember-cookie-runner-v4-20261003/HANDOFF.md"
            ),
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

    def test_every_reviewed_helper_hash_matches_its_exact_bytes(self) -> None:
        deployment = ROOT / "ops/deployment"
        bindings = {
            "laravel_remember_cookie_runtime_probe.php": RUNNER.RUNTIME_HELPER_SHA256,
            "laravel_dependency_database_envelope.py": RUNNER.DATABASE_ENVELOPE_VALIDATOR_SHA256,
            "laravel_dependency_gate.py": RUNNER.GATE_HELPER_SHA256,
            "laravel_log_delta.py": RUNNER.LOG_PARSER_SHA256,
            "laravel_fpm_opcache_probe.php": RUNNER.FPM_OPCACHE_PROBE_SHA256,
            "laravel_nginx_identity.py": RUNNER.NGINX_IDENTITY_HELPER_SHA256,
            "laravel_remember_cookie_retired_controls.json": RUNNER.RETIRED_CONTROLS_SHA256,
        }
        for name, expected in bindings.items():
            with self.subTest(name=name):
                self.assertEqual(expected, self.sha256(deployment / name))

    def test_emergency_containment_precedes_nginx_capture_and_survives_capture_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-emergency-nginx-") as directory:
            state_path = Path(directory) / "deployment-state.json"
            state: dict[str, object] = {}
            order: list[str] = []

            def contained(**_kwargs):
                order.append("gate")
                return {"status": "verified", "http_verified": True}

            def nginx_failure(*_args, **_kwargs):
                order.append("nginx")
                raise RUNNER.DeploymentError("injected nginx capture failure")

            with patch.object(RUNNER, "require_gate_helper"), patch.object(
                RUNNER, "post_mutation_emergency_gate_context", return_value=object()
            ) as gate_context_mock, patch.object(
                RUNNER.dependency_gate,
                "establish_rollback_containment",
                side_effect=contained,
            ), patch.object(
                RUNNER,
                "require_current_nginx_for_gate",
                side_effect=nginx_failure,
            ):
                result = RUNNER.establish_rollback_gate(
                    state,
                    state_path,
                    "cutover_failure",
                )

            self.assertEqual(["gate", "nginx"], order)
            gate_context_mock.assert_called_once_with(state, state_path)
            self.assertEqual(
                "unavailable_fail_closed",
                result["nginx_route_verification"]["status"],
            )
            self.assertTrue(
                result["nginx_route_verification"][
                    "rollback_may_continue_boot_independently"
                ]
            )
            self.assertTrue(
                (Path(directory) / "cutover_failure-0001-emergency-nginx-verification.json").is_file()
            )

    def test_rollback_failure_retains_gate_before_unavailable_nginx_proof(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-rollback-nginx-") as directory:
            state_path = Path(directory) / "deployment-state.json"
            state: dict[str, object] = {}
            order: list[str] = []

            def retained(**_kwargs):
                order.append("gate")
                return {"status": "retained"}

            def nginx_failure(*_args, **_kwargs):
                order.append("nginx")
                raise RUNNER.DeploymentError("injected nginx capture failure")

            with patch.object(RUNNER, "require_gate_helper"), patch.object(
                RUNNER, "post_mutation_emergency_gate_context", return_value=object()
            ) as gate_context_mock, patch.object(
                RUNNER.dependency_gate,
                "retain_static_gate_exact",
                side_effect=retained,
            ), patch.object(
                RUNNER,
                "require_current_nginx_for_gate",
                side_effect=nginx_failure,
            ):
                RUNNER.contain_rollback_failure(
                    state,
                    state_path,
                    RUNNER.DeploymentError("injected rollback failure"),
                )

            self.assertEqual(["gate", "nginx"], order)
            gate_context_mock.assert_called_once_with(state, state_path)
            self.assertEqual("rollback_failed_static_gate_retained", state["status"])
            containment = state["rollback_failure_containment"]
            self.assertEqual(
                "unavailable_fail_closed",
                containment["nginx_route_verification"]["status"],
            )

    def test_initial_gate_install_requires_current_fpm_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-initial-gate-policy-") as directory:
            state_path = Path(directory) / "deployment-state.json"
            state: dict[str, object] = {}
            context = object()
            with patch.object(RUNNER, "require_gate_helper"), patch.object(
                RUNNER,
                "require_current_nginx_for_gate",
            ), patch.object(
                RUNNER,
                "gate_context",
                return_value=context,
            ) as gate_context_mock, patch.object(
                RUNNER.dependency_gate,
                "install_static_gate",
                return_value={"status": "verified", "http_verified": True},
            ):
                RUNNER.install_static_gate(state, state_path, "cutover_entry")
            gate_context_mock.assert_called_once_with(state, state_path)

    def test_exact_existing_gate_can_use_frozen_policy_for_emergency_restoration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-emergency-frozen-policy-") as directory:
            root = Path(directory)
            state_path = root / "deployment-state.json"
            backup = root / "public-index.before.php"
            front_controller = root / "index.php"
            original = b"<?php echo 'original';\n"
            gate = b"<?php echo 'reviewed-gate';\n"
            backup.write_bytes(original)
            front_controller.write_bytes(gate)
            os.chmod(backup, 0o600)
            os.chmod(front_controller, 0o644)
            fpm_opcache = self.valid_fpm_opcache_envelope()
            policy = fpm_opcache["policy"]
            state: dict[str, object] = {
                "front_controller_backup": str(backup),
                "front_controller_backup_sha256": hashlib.sha256(original).hexdigest(),
                "fpm_opcache": fpm_opcache,
            }
            RUNNER.write_state(state_path, state)
            metadata = {
                "kind": "file",
                "mode": 0o644,
                "uid": front_controller.stat().st_uid,
                "gid": front_controller.stat().st_gid,
            }
            with patch.object(RUNNER, "FRONT_CONTROLLER", front_controller), patch.object(
                RUNNER,
                "MAINTENANCE_GATE_SHA256",
                hashlib.sha256(gate).hexdigest(),
            ), patch.object(
                RUNNER,
                "probe_fpm_opcache",
                side_effect=RUNNER.FpmProbeUnavailable("FPM unavailable"),
            ), patch.object(
                RUNNER.dependency_gate,
                "reviewed_front_controller_metadata",
                return_value=metadata,
            ):
                context = RUNNER.gate_context(
                    state,
                    state_path,
                    allow_frozen_policy_for_exact_existing_gate=True,
                )
                self.assertEqual(policy, context.opcache_policy)
                self.assertEqual(
                    "exact_existing_gate_retained_with_frozen_policy",
                    state["emergency_existing_gate_opcache_fallbacks"][0]["status"],
                )
                front_controller.write_bytes(original)
                os.chmod(front_controller, 0o644)
                with self.assertRaisesRegex(RUNNER.FpmProbeUnavailable, "FPM unavailable"):
                    RUNNER.gate_context(
                        state,
                        state_path,
                        allow_frozen_policy_for_exact_existing_gate=True,
                    )
                front_controller.write_bytes(b"<?php echo 'unknown';\n")
                os.chmod(front_controller, 0o644)
                with self.assertRaisesRegex(RUNNER.FpmProbeUnavailable, "FPM unavailable"):
                    RUNNER.gate_context(
                        state,
                        state_path,
                        allow_frozen_policy_for_exact_existing_gate=True,
                    )

    def test_structural_fpm_record_validation_does_not_require_live_fpm(self) -> None:
        frozen = self.valid_fpm_opcache_envelope()
        with patch.object(
            RUNNER,
            "probe_fpm_opcache",
            side_effect=RUNNER.DeploymentError("FPM unavailable"),
        ):
            self.assertIs(frozen, RUNNER.validate_frozen_fpm_opcache_record(frozen))
            with self.assertRaisesRegex(RUNNER.DeploymentError, "FPM unavailable"):
                RUNNER.require_frozen_fpm_opcache(frozen)
        validation_source = inspect.getsource(RUNNER.validate_rollback_state_paths)
        self.assertIn("validate_frozen_fpm_opcache_record", validation_source)
        self.assertNotIn("require_frozen_fpm_opcache(", validation_source)

    def test_both_fpm_probes_use_closed_fastcgi_environments(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-fpm-env-") as directory:
            root = Path(directory)
            (root / "public").mkdir(parents=True)
            (root / "storage/framework").mkdir(parents=True)
            opcache_probe = root / "opcache-probe.php"
            opcache_probe.write_text("<?php\n", encoding="utf-8")
            socket = unittest.mock.MagicMock()
            socket.is_socket.return_value = True
            captured_environments: list[dict[str, str]] = []

            def completed_with(payload: dict[str, object]):
                return type(
                    "Completed",
                    (),
                    {
                        "stdout": (
                            "Content-Type: application/json\r\n\r\n"
                            + json.dumps(payload, sort_keys=True)
                        )
                    },
                )()

            def opcache_run(*_args, **kwargs):
                captured_environments.append(dict(kwargs["env"]))
                return completed_with(self.valid_fpm_opcache_envelope()["probe"])

            runtime_payload = {
                "laravel_version": RUNNER.OLD_PACKAGE_VERSIONS["laravel/framework"],
                "guzzle_version": RUNNER.OLD_PACKAGE_VERSIONS["guzzlehttp/guzzle"],
                "package_versions": RUNNER.OLD_PACKAGE_VERSIONS,
                "package_install_paths": {
                    package: str(root / "vendor" / package)
                    for package in RUNNER.OLD_PACKAGE_VERSIONS
                },
                "php_version": RUNNER.EXPECTED_PHP_VERSION,
                "php_extensions": ["Core"],
                "laravel_path": str(
                    root / "vendor/laravel/framework/src/Illuminate/Foundation/Application.php"
                ),
                "guzzle_path": str(root / "vendor/guzzlehttp/guzzle/src/Client.php"),
            }

            def runtime_run(*_args, **kwargs):
                captured_environments.append(dict(kwargs["env"]))
                return completed_with(runtime_payload)

            hostile = {
                "PHP_VALUE": "auto_prepend_file=/tmp/hostile.php",
                "PHP_ADMIN_VALUE": "opcache.validate_timestamps=0",
                "HTTP_COOKIE": "secret=value",
                "LD_PRELOAD": "/tmp/hostile.so",
            }
            with patch.dict(os.environ, hostile, clear=False), patch.object(
                RUNNER,
                "APP_ROOT",
                root,
            ), patch.object(
                RUNNER,
                "FPM_SOCKET",
                socket,
            ), patch.object(
                RUNNER,
                "require_fpm_opcache_probe",
                return_value=opcache_probe,
            ), patch.object(
                RUNNER,
                "require_nginx_identity_helper",
            ), patch.object(
                RUNNER,
                "run",
                side_effect=opcache_run,
            ):
                RUNNER.probe_fpm_opcache()

            with patch.dict(os.environ, hostile, clear=False), patch.object(
                RUNNER,
                "APP_ROOT",
                root,
            ), patch.object(
                RUNNER,
                "FPM_SOCKET",
                socket,
            ), patch.object(
                RUNNER.os,
                "chown",
            ), patch.object(
                RUNNER,
                "run",
                side_effect=runtime_run,
            ):
                RUNNER.fpm_probe(RUNNER.OLD_PACKAGE_VERSIONS)

            self.assertEqual(2, len(captured_environments))
            expected_keys = {
                "DOCUMENT_ROOT",
                "GATEWAY_INTERFACE",
                "HTTPS",
                "QUERY_STRING",
                "REDIRECT_STATUS",
                "REMOTE_ADDR",
                "REQUEST_METHOD",
                "REQUEST_URI",
                "SCRIPT_FILENAME",
                "SCRIPT_NAME",
                "SERVER_NAME",
                "SERVER_PORT",
                "SERVER_PROTOCOL",
            }
            for environment in captured_environments:
                self.assertEqual(expected_keys, set(environment))
                self.assertTrue(hostile.keys().isdisjoint(environment))

    def test_public_health_and_runtime_probes_use_closed_environments(self) -> None:
        hostile = {
            "APP_ENV": "hostile",
            "DB_CONNECTION": "hostile",
            "DB_DATABASE": "hostile",
            "PHP_VALUE": "auto_prepend_file=/tmp/hostile.php",
            "PHPRC": "/tmp/hostile.ini",
            "PHP_INI_SCAN_DIR": "/tmp/hostile-conf.d",
            "LD_PRELOAD": "/tmp/hostile.so",
            "HOME": "/tmp/hostile-home",
            "CURL_HOME": "/tmp/hostile-curl-home",
            "HTTPS_PROXY": "http://127.0.0.1:9999",
            "ALL_PROXY": "http://127.0.0.1:9998",
        }
        calls: list[tuple[list[str], dict[str, str]]] = []

        def fake_run(command, **kwargs):
            calls.append((list(command), dict(kwargs["env"])))
            if command[0] == "/usr/bin/curl":
                return type("Completed", (), {"stdout": "200\n104.16.0.1\n443\n"})()
            return type("Completed", (), {"stdout": "{}"})()

        helper = Path("/tmp/reviewed-runtime-helper.php")
        with patch.dict(os.environ, hostile, clear=False), patch.object(
            RUNNER,
            "run",
            side_effect=fake_run,
        ):
            self.assertEqual(200, RUNNER.http_status("https://buy-dtf.com/", cache_buster=True))
            self.assertEqual({}, RUNNER.runtime_probe(helper))

        expected_environment = RUNNER.closed_control_environment()
        self.assertEqual(2, len(calls))
        for _command, environment in calls:
            self.assertEqual(expected_environment, environment)
            self.assertTrue(hostile.keys().isdisjoint(environment))
        curl_command = calls[0][0]
        self.assertEqual("--disable", curl_command[1])
        self.assertIn("--noproxy", curl_command)
        with patch.object(
            RUNNER,
            "run",
            return_value=type(
                "Completed",
                (),
                {"stdout": "200\n127.0.0.1\n443\n"},
            )(),
        ):
            with self.assertRaisesRegex(RUNNER.DeploymentError, "Invalid HTTP status"):
                RUNNER.http_status("https://buy-dtf.com/")

    def test_post_mutation_fpm_timeout_with_original_uses_frozen_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-emergency-original-") as directory:
            root = Path(directory)
            application = root / "application"
            public = application / "public"
            public.mkdir(parents=True)
            front_controller = public / "index.php"
            original = b"<?php echo 'original';\n"
            front_controller.write_bytes(original)
            os.chmod(front_controller, 0o644)
            backup = root / "public-index.before.php"
            backup.write_bytes(original)
            os.chmod(backup, 0o600)
            state_path = root / "deployment-state.json"
            state = {
                **RUNNER.dependency_gate.initial_gate_state(),
                "front_controller_backup": str(backup),
                "front_controller_backup_sha256": hashlib.sha256(original).hexdigest(),
                "release_receipt_sha256": "a" * 64,
                "fpm_opcache": self.valid_fpm_opcache_envelope(),
                "dependency_mutation_started": False,
            }
            RUNNER.write_state(state_path, state)
            with patch.object(
                RUNNER,
                "probe_fpm_opcache",
                return_value=state["fpm_opcache"],
            ):
                RUNNER.record_fpm_opcache_before_mutation(state, state_path)
            state["dependency_mutation_started"] = True
            RUNNER.write_state(state_path, state)
            metadata = {
                "kind": "file",
                "mode": 0o644,
                "uid": front_controller.stat().st_uid,
                "gid": front_controller.stat().st_gid,
            }
            with patch.object(RUNNER, "APP_ROOT", application), patch.object(
                RUNNER, "FRONT_CONTROLLER", front_controller
            ), patch.object(
                RUNNER,
                "EXPECTED_FRONT_CONTROLLER_SHA256",
                hashlib.sha256(original).hexdigest(),
            ), patch.object(
                RUNNER,
                "probe_fpm_opcache",
                side_effect=RUNNER.FpmProbeUnavailable("timed out"),
            ) as probe, patch.object(
                RUNNER.dependency_gate,
                "reviewed_front_controller_metadata",
                return_value=metadata,
            ):
                context = RUNNER.post_mutation_emergency_gate_context(state, state_path)
            probe.assert_called_once_with()
            self.assertEqual(state["fpm_opcache"]["policy"], context.opcache_policy)
            self.assertEqual(
                "exact_original_gate_install_with_frozen_policy",
                state["post_mutation_emergency_fpm_fallbacks"][0]["status"],
            )

    def test_post_mutation_timeout_installs_gate_then_automatically_invokes_rollback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-emergency-install-") as directory:
            root = Path(directory)
            application = root / "application"
            public = application / "public"
            public.mkdir(parents=True)
            front_controller = public / "index.php"
            original = b"<?php echo 'original';\n"
            front_controller.write_bytes(original)
            os.chmod(front_controller, 0o644)
            backup = root / "public-index.before.php"
            backup.write_bytes(original)
            os.chmod(backup, 0o600)
            state_path = root / "deployment-state.json"
            state: dict[str, object] = {
                **RUNNER.dependency_gate.initial_gate_state(),
                "front_controller_backup": str(backup),
                "front_controller_backup_sha256": hashlib.sha256(original).hexdigest(),
                "release_receipt_sha256": "c" * 64,
                "fpm_opcache": self.valid_fpm_opcache_envelope(),
                "dependency_mutation_started": False,
            }
            RUNNER.write_state(state_path, state)
            with patch.object(
                RUNNER,
                "probe_fpm_opcache",
                return_value=state["fpm_opcache"],
            ):
                RUNNER.record_fpm_opcache_before_mutation(state, state_path)
            state["dependency_mutation_started"] = True
            RUNNER.write_state(state_path, state)

            metadata = {
                "kind": "file",
                "mode": 0o644,
                "uid": front_controller.stat().st_uid,
                "gid": front_controller.stat().st_gid,
            }
            probe_sequence = iter(("origin-1", "origin-2", "public-1"))

            class FakeClock:
                def __init__(self) -> None:
                    self.nanoseconds = 30_000_000_000
                    self.wall_epoch = 1_700_000_000.0

                def monotonic_ns(self) -> int:
                    return self.nanoseconds

                def wall_clock(self) -> float:
                    return self.wall_epoch + (
                        self.nanoseconds - 30_000_000_000
                    ) / 1_000_000_000

                def sleep(self, seconds: float) -> None:
                    self.nanoseconds += round(seconds * 1_000_000_000)

            clock = FakeClock()
            build_context = RUNNER._gate_context_from_frozen_envelope

            def deterministic_context(*args, **kwargs):
                return replace(
                    build_context(*args, **kwargs),
                    sleep=clock.sleep,
                    monotonic_ns=clock.monotonic_ns,
                    wall_clock=clock.wall_clock,
                )

            def successful_probe(route: str) -> dict[str, object]:
                nonce = next(probe_sequence)
                return {
                    "route": route,
                    "status": 503,
                    "header_verified": True,
                    "sentinel_verified": True,
                    "cache_buster_verified": True,
                    "route_identity_verified": True,
                    "cache_buster_sha256": hashlib.sha256(
                        nonce.encode("utf-8")
                    ).hexdigest(),
                    "request_url_sha256": hashlib.sha256(
                        f"url-{nonce}".encode("utf-8")
                    ).hexdigest(),
                }

            with patch.object(RUNNER, "APP_ROOT", application), patch.object(
                RUNNER,
                "FRONT_CONTROLLER",
                front_controller,
            ), patch.object(
                RUNNER,
                "EXPECTED_FRONT_CONTROLLER_SHA256",
                hashlib.sha256(original).hexdigest(),
            ), patch.multiple(
                RUNNER.dependency_gate,
                EXPECTED_APP_UID=os.getuid(),
                EXPECTED_APP_GID=os.getgid(),
            ), patch.object(
                RUNNER.dependency_gate,
                "reviewed_front_controller_metadata",
                return_value=metadata,
            ), patch.object(
                RUNNER,
                "probe_fpm_opcache",
                side_effect=RUNNER.FpmProbeUnavailable("timed out after mutation"),
            ), patch.object(
                RUNNER,
                "_gate_context_from_frozen_envelope",
                side_effect=deterministic_context,
            ), patch.object(
                RUNNER,
                "_gate_origin_probe",
                side_effect=lambda _directory, _operation, _ordinal: successful_probe(
                    RUNNER.dependency_gate.ORIGIN_ROUTE
                ),
            ), patch.object(
                RUNNER,
                "_gate_public_probe",
                side_effect=lambda _directory, _operation: successful_probe(
                    RUNNER.dependency_gate.PUBLIC_ROUTE
                ),
            ), patch.object(
                RUNNER,
                "record_emergency_nginx_verification",
                return_value={"status": "pass", "route_verified": True},
            ), patch.object(
                RUNNER,
                "rollback_from_state",
            ) as rollback:
                RUNNER.handle_cutover_failure(
                    state,
                    state_path,
                    Path("/reviewed/runtime-helper.php"),
                    RUNNER.FpmProbeUnavailable("candidate FPM unavailable"),
                )

            rollback.assert_called_once()
            self.assertEqual(
                RUNNER.MAINTENANCE_GATE_SHA256,
                RUNNER.dependency_gate.file_identity(front_controller)["sha256"],
            )
            persisted = RUNNER.dependency_gate.load_state(state_path)
            waits = persisted["front_controller_revalidation_waits"]
            self.assertGreaterEqual(
                waits[0]["elapsed_monotonic_seconds"],
                state["fpm_opcache"]["policy"]["minimum_wait_seconds"],
            )
            self.assertEqual("complete", waits[0]["status"])
            self.assertEqual(
                "exact_original_gate_install_with_frozen_policy",
                persisted["post_mutation_emergency_fpm_fallbacks"][0]["status"],
            )
            self.assertEqual("failed_dependency_rollback_required", state["status"])

    def test_post_mutation_http_gate_failure_still_invokes_rollback(self) -> None:
        state: dict[str, object] = {"dependency_mutation_started": True}
        state_path = Path("/private/deployment-state.json")
        helper = Path("/private/runtime-helper.php")
        containment = {
            "status": "site_gated_http_unverified",
            "http_verified": False,
            "rollback_may_continue_boot_independently": True,
        }
        interrupted = lambda _stage: None
        with patch.object(
            RUNNER,
            "establish_rollback_gate",
            return_value=containment,
        ) as establish, patch.object(RUNNER, "write_state"), patch.object(
            RUNNER,
            "rollback_from_state",
        ) as rollback:
            RUNNER.handle_cutover_failure(
                state,
                state_path,
                helper,
                RUNNER.FpmProbeUnavailable("post-mutation timeout"),
                failure_injector=interrupted,
            )
        establish.assert_called_once_with(
            state,
            state_path,
            "cutover_failure",
            fault_injector=interrupted,
        )
        rollback.assert_called_once_with(
            state,
            state_path,
            helper,
            failure_injector=interrupted,
        )
        self.assertEqual("failed_dependency_rollback_required", state["status"])
        self.assertTrue(state["gate_active"])
        self.assertFalse(state["gate_verified"])

    def test_missing_or_malformed_emergency_frozen_envelope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-emergency-envelope-") as directory:
            root = Path(directory)
            state_path = root / "deployment-state.json"
            valid = {
                "release_receipt_sha256": "b" * 64,
                "fpm_opcache": self.valid_fpm_opcache_envelope(),
                "dependency_mutation_started": False,
            }
            RUNNER.write_state(state_path, valid)
            with patch.object(
                RUNNER,
                "probe_fpm_opcache",
                return_value=valid["fpm_opcache"],
            ):
                RUNNER.record_fpm_opcache_before_mutation(valid, state_path)
            valid["dependency_mutation_started"] = True
            RUNNER.write_state(state_path, valid)
            self.assertIs(
                valid["fpm_opcache"],
                RUNNER.validate_post_mutation_frozen_fpm_opcache(valid, state_path),
            )
            for mutation in ("missing_envelope", "missing_checkpoint", "malformed_checkpoint"):
                with self.subTest(mutation=mutation):
                    candidate = dict(valid)
                    if mutation == "missing_envelope":
                        candidate.pop("fpm_opcache")
                    elif mutation == "missing_checkpoint":
                        candidate.pop("fpm_opcache_before_mutation")
                    else:
                        candidate["fpm_opcache_before_mutation"] = {"status": "pass"}
                    with self.assertRaises(RUNNER.DeploymentError):
                        RUNNER.validate_post_mutation_frozen_fpm_opcache(
                            candidate,
                            state_path,
                        )

    def test_rollback_failure_records_context_rejection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-rollback-context-stop-") as directory:
            state_path = Path(directory) / "deployment-state.json"
            state: dict[str, object] = {}
            with patch.object(
                RUNNER,
                "post_mutation_emergency_gate_context",
                side_effect=RUNNER.DeploymentError("injected context rejection"),
            ), patch.object(
                RUNNER.dependency_gate,
                "file_identity",
                side_effect=RUNNER.dependency_gate.GateError("identity unavailable"),
            ):
                with self.assertRaisesRegex(RUNNER.DeploymentError, "could not be established"):
                    RUNNER.contain_rollback_failure(
                        state,
                        state_path,
                        RUNNER.DeploymentError("rollback failure"),
                    )
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(
                "rollback_failed_static_gate_identity_unavailable",
                persisted["status"],
            )
            self.assertEqual(
                "unavailable",
                persisted["rollback_failure_live_front_controller"]["status"],
            )

    def test_describe_is_review_only_v4_and_preserves_scope_boundaries(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            RUNNER.describe()
        payload = json.loads(output.getvalue())
        self.assertEqual("buy-dtf-laravel-remember-cookie-dependency-review-v4", payload["artifact"])
        self.assertEqual("review-only; not staged or deployed", payload["artifact_review_status"])
        self.assertEqual("proxy", payload["composer_bin_compat"])
        self.assertEqual(178, payload["expected_route_count"])
        self.assertIn("laravel-remember-cookie-v4-releases", payload["release_root"])
        self.assertEqual(3, len(payload["static_gate_verification_routes"]))
        self.assertTrue(payload["static_gate_probe_nonce_bound_to_header_and_body"])
        self.assertEqual("monotonic", payload["fpm_opcache_policy"]["clock"])
        self.assertTrue(payload["fpm_opcache_policy"]["timestamp_validation_required"])
        self.assertEqual("/var/www/buy-dtf/public", payload["nginx_document_root_required"])
        self.assertEqual(
            "/run/php/php8.2-fpm.sock",
            payload["nginx_fpm_socket_required"],
        )
        self.assertEqual(
            "/var/www/buy-dtf/public/index.php",
            payload["nginx_script_filename_required"],
        )
        self.assertTrue(payload["nginx_php_route_identity_bound_to_release_receipt"])
        self.assertEqual(
            "current-live-exact-match-required",
            payload["pre_mutation_fpm_probe"],
        )
        emergency = payload["post_mutation_emergency_fpm_policy"]
        self.assertEqual(
            "typed-live-fpm-unavailability-only",
            emergency["fallback_trigger"],
        )
        self.assertTrue(emergency["boot_independent_rollback_continues"])
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
            release_root = operations / "laravel-remember-cookie-v4-releases"
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

    @unittest.skipUnless(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "atomic metadata-drift rehearsal requires root on a safe local tree",
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

    def test_permanent_retirements_and_retired_receipt_rejection(self) -> None:
        registry_path = ROOT / "ops/deployment/laravel_remember_cookie_retired_controls.json"
        self.assertEqual(RUNNER.RETIRED_CONTROLS_SHA256, self.sha256(registry_path))
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        indexed = {
            (item["kind"], item["sha256"])
            for item in registry["retired_controls"]
        }
        for digest in RUNNER.RETIRED_RUNNER_SHA256S:
            self.assertIn(("runner", digest), indexed)
        for digest in RUNNER.RETIRED_GATE_HELPER_SHA256S:
            self.assertIn(("static_gate_helper", digest), indexed)
        for digest in RUNNER.RETIRED_RELEASE_RECEIPT_SHA256S:
            self.assertIn(("release_receipt", digest), indexed)
            with self.assertRaisesRegex(RUNNER.DeploymentError, "permanently retired"):
                RUNNER.load_approved_release(Path("/path/that/must/not/be/read"), digest)

    def test_dependency_settle_uses_the_frozen_calculated_policy(self) -> None:
        state = {
            "fpm_opcache": {
                "policy": {
                    "artifact": "buy-dtf-php-fpm-opcache-revalidation-policy-v1",
                    "php_version": "8.2.30",
                    "sapi": "fpm-fcgi",
                    "opcache_enable": True,
                    "validate_timestamps": True,
                    "revalidate_freq_seconds": 12,
                    "file_update_protection_seconds": 3,
                    "complete_revalidation_interval_seconds": 15,
                    "second_revalidation_window_seconds": 12,
                    "minimum_wait_seconds": 28,
                    "minimum_floor_seconds": 5,
                    "safety_margin_seconds": 1,
                    "formula": (
                        "max(5, 2 * revalidate_freq + file_update_protection + 1)"
                    ),
                }
            }
        }
        self.assertEqual(28, RUNNER.dependency_cache_settle_seconds(state))

    def test_pre_gate_failure_with_untouched_original_does_not_retry_unsafe_gate_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="buy-dtf-untouched-original-") as directory:
            root = Path(directory)
            front_controller = root / "index.php"
            original = b"<?php echo 'original';\n"
            front_controller.write_bytes(original)
            os.chmod(front_controller, 0o644)
            state_path = root / "deployment-state.json"
            state = {
                **RUNNER.dependency_gate.initial_gate_state(),
                "dependency_mutation_started": False,
            }
            with patch.object(RUNNER, "FRONT_CONTROLLER", front_controller), patch.object(
                RUNNER, "EXPECTED_FRONT_CONTROLLER_SHA256", hashlib.sha256(original).hexdigest()
            ), patch.object(
                RUNNER.dependency_gate,
                "reviewed_front_controller_metadata",
                return_value={
                    "kind": "file",
                    "mode": 0o644,
                    "uid": os.getuid(),
                    "gid": os.getgid(),
                },
            ), patch.object(
                RUNNER, "health_snapshot", return_value={"status": "pass"}
            ), patch.object(
                RUNNER,
                "restore_front_controller",
                side_effect=AssertionError("untouched original must not enter gate context"),
            ):
                RUNNER.restore_pre_mutation_failure(
                    state,
                    state_path,
                    RUNNER.DeploymentError("unsafe FPM envelope"),
                )
            receipt = json.loads(
                (root / "pre-mutation-failure-restoration-receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                "untouched_original_no_transition",
                receipt["restoration"]["status"],
            )
            self.assertFalse(receipt["restoration"]["opcache_wait_required"])

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

    @staticmethod
    def valid_fpm_opcache_envelope() -> dict[str, object]:
        normalized = {
            "opcache.enable": True,
            "opcache.validate_timestamps": True,
            "opcache.revalidate_freq": 2,
            "opcache.file_update_protection": 2,
        }
        directives = {
            name: {"raw": "1" if isinstance(value, bool) else str(value), "normalized": value}
            for name, value in normalized.items()
        }
        probe = {
            "artifact": RUNNER.environment_controls.FPM_OPCACHE_ARTIFACT,
            "sapi": RUNNER.environment_controls.EXPECTED_FPM_SAPI,
            "php_version": RUNNER.EXPECTED_PHP_VERSION,
            "directives": directives,
            "opcache_configuration_directives": normalized,
        }
        policy = RUNNER.dependency_gate.derive_opcache_revalidation_policy(probe)
        return {
            "artifact": "buy-dtf-php-fpm-opcache-envelope-v4",
            "status": "pass",
            "probe_helper_sha256": RUNNER.FPM_OPCACHE_PROBE_SHA256,
            "environment_helper_sha256": RUNNER.NGINX_IDENTITY_HELPER_SHA256,
            "probe": probe,
            "policy": policy,
        }


if __name__ == "__main__":
    unittest.main()
