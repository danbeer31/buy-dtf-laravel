#!/usr/bin/env python3
"""Regression tests for the schema-present source-only alpha runner."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "ops/deployment/production_alpha_transparency_deploy.py"
REHEARSAL_PATH = ROOT / "ops/deployment/rehearse_production_alpha_transparency.py"
LOG_GUARD_PATH = ROOT / "ops/deployment/laravel_log_guard.py"
FIXTURES = ROOT / "tests/Fixtures/Deployment/LaravelLogs"
MANIFEST_PATH = (
    ROOT
    / "ops/evidence/production-alpha-transparency-activation-v6-20261005"
    / "APPLICATION_MANIFEST.json"
)
REHEARSAL_RECEIPT_PATH = (
    ROOT / "ops/evidence/production-alpha-transparency-activation-v6-20261005/source-rehearsal/rehearsal-receipt.json"
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
    def snapshot(self) -> dict:
        return rehearsal.runtime_snapshot()

    def assert_refused(self, payload: dict, phrase: str) -> None:
        with self.assertRaises(deploy.DeploymentError) as raised:
            deploy.validate_runtime_snapshot(payload)
        self.assertIn(phrase, str(raised.exception))

    def parse_modified_manifest(self, document: dict) -> list[dict]:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "APPLICATION_MANIFEST.json"
            path.write_text(json.dumps(document) + "\n", encoding="utf-8")
            with mock.patch.object(
                deploy, "EXPECTED_MANIFEST_SHA256", deploy.sha256_file(path)
            ):
                return deploy.parse_manifest(path)

    def test_manifest_pins_eleven_source_paths_and_source_only_migration(self) -> None:
        rows = deploy.parse_manifest(MANIFEST_PATH)
        replacements = {
            row["path"]: row["expected_bytes"]
            for row in rows
            if row["action"] == "M"
        }
        self.assertEqual(
            replacements,
            {
                "app/Helpers/ImageHelper.php": 28229,
                "app/Helpers/ProductionHelper.php": 17594,
                "app/Http/Controllers/Admin/OrderImageController.php": 14948,
                "app/Http/Controllers/CartController.php": 32079,
                "app/Http/Controllers/TeamCustomizationController.php": 9957,
                "app/Models/DtfImage.php": 8990,
                "app/Models/SavedImage.php": 1043,
                "app/Http/Controllers/Checkout/CheckoutController.php": 44433,
                "app/Services/ShippoService.php": 8299,
                "app/Http/Controllers/Webhooks/ShippoWebhookController.php": 3385,
            },
        )
        additions = [row for row in rows if row["action"] == "A"]
        self.assertEqual(len(rows), 11)
        self.assertEqual(len(additions), 1)
        self.assertEqual(additions[0]["path"], deploy.MIGRATION_RELATIVE_PATH.as_posix())
        self.assertEqual(additions[0]["expected"], "ABSENT")

        document = json.loads(MANIFEST_PATH.read_text("utf-8"))
        self.assertEqual(document["artifact_status"], "frozen_review_only_non_stageable")
        self.assertEqual(document["application_target_commit"], deploy.TARGET_COMMIT)
        self.assertEqual(
            document["current_handoff"],
            {
                "name": "buy-dtf-codie-handoff-2026-10-02.md",
                "sha256": deploy.HANDOFF_SHA256,
            },
        )
        self.assertEqual(
            document["dependency_envelope"],
            {
                "status": deploy.DEPENDENCY_ENVELOPE_STATUS,
                "stageable": False,
                "deployable": False,
            },
        )
        self.assertEqual(document["expected_schema_sha256"], deploy.EXPECTED_SCHEMA_SHA256)
        self.assertEqual(
            document["expected_ledger"],
            {
                "row_count": 21,
                "sha256": deploy.EXPECTED_LEDGER_SHA256,
                "target_entry_count": 1,
            },
        )
        self.assertEqual(
            document["migration"],
            {
                "name": deploy.TARGET_MIGRATION,
                "expected_live_state": "absent",
                "installed_schema_required": True,
                "source_install_only": True,
                "migration_command_allowed": False,
                "migration_pretend_allowed": False,
                "migration_reverse_allowed": False,
                "target_sha256": deploy.EXPECTED_MIGRATION_SHA256,
            },
        )
        checkout = next(
            row
            for row in document["paths"]
            if row["path"] == "app/Http/Controllers/Checkout/CheckoutController.php"
        )
        self.assertEqual(
            checkout["expected_live_line_endings"],
            {"crlf_count": 795, "remaining_lf_count": 102},
        )

    def test_manifest_requires_target_commit_and_source_only_declaration(self) -> None:
        original = json.loads(MANIFEST_PATH.read_text("utf-8"))
        changed = copy.deepcopy(original)
        changed["application_target_commit"] = "0" * 40
        with self.assertRaisesRegex(deploy.DeploymentError, "application target"):
            self.parse_modified_manifest(changed)

        changed = copy.deepcopy(original)
        changed["migration"]["migration_command_allowed"] = True
        with self.assertRaisesRegex(deploy.DeploymentError, "migration identity"):
            self.parse_modified_manifest(changed)

        changed = copy.deepcopy(original)
        changed["current_handoff"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(deploy.DeploymentError, "handoff identity"):
            self.parse_modified_manifest(changed)

        changed = copy.deepcopy(original)
        changed["dependency_envelope"]["stageable"] = True
        with self.assertRaisesRegex(deploy.DeploymentError, "pre-freeze gate"):
            self.parse_modified_manifest(changed)

    def test_manifest_source_cas_constants_match_all_eleven_rows(self) -> None:
        rows = deploy.parse_manifest(MANIFEST_PATH)
        expected_live = []
        target = []
        for row in rows:
            if row["expected"] == "ABSENT":
                expected_live.append({"path": row["path"], "state": "absent"})
            else:
                expected_live.append(
                    {
                        "path": row["path"],
                        "state": "file",
                        "sha256": row["expected"],
                        "bytes": row["expected_bytes"],
                    }
                )
            target.append(
                {
                    "path": row["path"],
                    "state": "file",
                    "sha256": row["target"],
                    "bytes": row["target_bytes"],
                }
            )
        self.assertEqual(
            deploy.sha256_bytes(deploy.canonical_bytes(expected_live)),
            deploy.EXPECTED_PRE_SOURCE_CAS_SHA256,
        )
        self.assertEqual(
            deploy.sha256_bytes(deploy.canonical_bytes(target)),
            deploy.EXPECTED_TARGET_SOURCE_CAS_SHA256,
        )

    def test_exact_installed_schema_and_twenty_one_row_ledger_are_required(self) -> None:
        result = deploy.validate_runtime_snapshot(self.snapshot())
        self.assertEqual(result["schema_state"], deploy.SCHEMA_STATE)
        self.assertEqual(result["schema_sha256"], deploy.EXPECTED_SCHEMA_SHA256)
        self.assertEqual(result["ledger_row_count"], 21)
        self.assertEqual(result["ledger_sha256"], deploy.EXPECTED_LEDGER_SHA256)
        self.assertEqual(result["target_migration_entries"], 1)
        self.assertFalse(result["migration_command_invoked"])
        self.assertFalse(result["migration_pretend_invoked"])
        self.assertFalse(result["migration_executed_this_attempt"])

    def test_schema_and_ledger_drift_are_refused(self) -> None:
        cases = (
            (("schema", "sha256"), "0" * 64, "schema differs"),
            (("schema", "without_item_meta_sha256"), "1" * 64, "schema differs"),
            (("migration_ledger", "row_count"), 20, "ledger differs"),
            (("migration_ledger", "rows_sha256"), "2" * 64, "ledger differs"),
            (("migration_ledger", "target_entry_count"), 0, "ledger differs"),
        )
        for keys, value, phrase in cases:
            with self.subTest(field=".".join(keys)):
                payload = self.snapshot()
                payload[keys[0]][keys[1]] = value
                self.assert_refused(payload, phrase)

    def test_wrong_item_meta_definition_is_refused(self) -> None:
        for key, value in (
            ("COLUMN_TYPE", "longtext"),
            ("IS_NULLABLE", "NO"),
            ("COLUMN_DEFAULT", "{}"),
            ("EXTRA", "generated"),
        ):
            with self.subTest(key=key):
                payload = self.snapshot()
                payload["schema"]["savedimages_item_meta"]["definition"][0][key] = value
                self.assert_refused(payload, "nullable TEXT definition")


    def test_incoming_tables_ledger_and_queues_each_fail_closed(self):
        for field,value in [('incoming_order_jobs',1),('api_asset_records',1)]:
            payload=self.snapshot();payload['schema']['required_table_row_counts'][field]=value
            with self.assertRaises(deploy.DeploymentError):deploy.validate_runtime_snapshot(payload)
            payload=self.snapshot();payload['schema']['required_tables'][field]=False
            with self.assertRaises(deploy.DeploymentError):deploy.validate_runtime_snapshot(payload)
        payload=self.snapshot();payload['migration_ledger']['incoming_order_entry_count']=0
        with self.assertRaises(deploy.DeploymentError):deploy.validate_runtime_snapshot(payload)
        for field in ['jobs','failed_jobs']:
            payload=self.snapshot();payload['queue']['counts'][field]=1
            with self.assertRaises(deploy.DeploymentError):deploy.validate_runtime_snapshot(payload)

    def test_customer_metadata_can_change_without_changing_schema_identity(self) -> None:
        before = self.snapshot()
        after = self.snapshot()
        after["schema"]["savedimages_item_meta"]["nonnull_rows"] = 4
        after["schema"]["savedimages_item_meta"]["savedimages_rows"] = 12
        after["schema"]["savedimages_item_meta"]["data_sha256_without_item_meta"] = "4" * 64
        comparison = deploy.compare_installed_schema_snapshots(before, after)
        self.assertTrue(comparison["schema_and_ledger_unchanged"])
        self.assertFalse(comparison["customer_row_counts_compared"])
        self.assertFalse(comparison["customer_row_data_compared"])

    def test_item_meta_must_be_empty_pre_source_but_may_grow_after_cutover(self) -> None:
        before = self.snapshot()
        preexisting = self.snapshot()
        preexisting["schema"]["savedimages_item_meta"]["nonnull_rows"] = 1

        verified = deploy.validate_pre_source_runtime_snapshot(before)
        self.assertTrue(verified["pre_source_item_meta_empty"])
        with self.assertRaisesRegex(deploy.DeploymentError, "null for every existing row"):
            deploy.validate_pre_source_runtime_snapshot(preexisting)

        # The ordinary post-cutover and rollback validators intentionally allow
        # new uploads to populate item_meta once source installation completes.
        post = deploy.validate_runtime_snapshot(preexisting)
        self.assertEqual(post["item_meta_nonnull_rows"], 1)
        rollback = deploy.verify_rollback_schema_state(
            preexisting,
            {
                "migration_command_invoked": False,
                "migration_pretend_invoked": False,
                "migration_executed_this_attempt": False,
            },
        )
        self.assertEqual(
            rollback["verification"]["item_meta_nonnull_rows"],
            1,
        )

        source = RUNNER_PATH.read_text("utf-8")
        self.assertIn(
            "installed_verification = validate_pre_source_runtime_snapshot(before_repeat)",
            source,
        )

    def test_disabled_capabilities_and_idle_jobs_are_required(self) -> None:
        cases = (
            ("capabilities", "receiver_enabled", True, "capability or artwork host"),
            ("capabilities", "job_label_enabled", True, "capability or artwork host"),
            ("capabilities", "retention_enabled", True, "capability or artwork host"),
            ("capabilities", "allowed_host_count", 1, "capability or artwork host"),
            ("queue", "connection", "database", "queue connection"),
        )
        for section, key, value, phrase in cases:
            with self.subTest(field=f"{section}.{key}"):
                payload = self.snapshot()
                payload[section][key] = value
                self.assert_refused(payload, phrase)

    def test_rollback_preserves_exact_installed_schema_and_refuses_migration_flags(self) -> None:
        state = {
            "migration_command_invoked": False,
            "migration_pretend_invoked": False,
            "migration_executed_this_attempt": False,
        }
        result = deploy.verify_rollback_schema_state(self.snapshot(), state)
        self.assertEqual(result["observed_schema_state"], deploy.SCHEMA_STATE)
        self.assertTrue(result["additive_schema_preserved"])

        for key in state:
            with self.subTest(key=key):
                changed = dict(state)
                changed[key] = True
                with self.assertRaisesRegex(deploy.DeploymentError, "prohibited migration"):
                    deploy.verify_rollback_schema_state(self.snapshot(), changed)

    def test_only_source_install_is_the_mutation_boundary(self) -> None:
        self.assertFalse(deploy.mutation_has_started({}))
        self.assertFalse(
            deploy.mutation_has_started(
                {
                    "migration_command_invoked": True,
                    "migration_pretend_invoked": True,
                    "migration_executed_this_attempt": True,
                    "source_install_started": False,
                }
            )
        )
        self.assertTrue(deploy.mutation_has_started({"source_install_started": True}))

    def test_runner_has_no_migration_execution_or_reverse_path(self) -> None:
        source = RUNNER_PATH.read_text("utf-8")
        tree = ast.parse(source)
        definitions = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        self.assertNotIn("staged_pretend", definitions)
        self.assertNotIn("execute_single_migration", definitions)
        self.assertNotIn("verify_post_migration", definitions)
        self.assertNotIn('"--pretend"', source)
        self.assertNotIn('"migrate:rollback"', source)
        self.assertEqual(source.count('"artisan migrate"'), 1)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name != "run_artisan" or not node.args or not isinstance(node.args[0], ast.List):
                continue
            arguments = [
                element.value
                for element in node.args[0].elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
            self.assertFalse(any(argument.startswith("migrate") for argument in arguments))

    def test_runner_has_no_database_backup_or_mysqldump_path(self) -> None:
        source = RUNNER_PATH.read_text("utf-8")
        tree = ast.parse(source)
        definitions = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        self.assertNotIn("verify_gzip", definitions)
        self.assertNotIn("database_backups", definitions)
        self.assertNotIn("/usr/bin/mysqldump", source)
        self.assertNotIn("database_backup_receipt", source)

        rehearsal_source = REHEARSAL_PATH.read_text("utf-8")
        self.assertNotIn("fake_database_backups", rehearsal_source)
        self.assertNotIn("database-backup-rehearsal", rehearsal_source)

    def test_retired_runner_and_receipt_artifacts_are_permanent_no_go(self) -> None:
        self.assertIn(
            "59bbd90cafa8d1b5efd56a6c40667924193e37539f4340e4b6163c6274425cab",
            deploy.RETIRED_RUNNER_SHA256S,
        )
        self.assertIn(
            "76cfff204e86ee1119251b1d79931b1219cd19704b099f75d4e3db202ffe5b17",
            deploy.RETIRED_RUNNER_SHA256S,
        )
        retired_receipt = next(iter(deploy.RETIRED_RELEASE_RECEIPT_SHA256S))
        with self.assertRaisesRegex(deploy.DeploymentError, "permanently retired runner"):
            deploy.validate_release_receipt(Path("does-not-exist"), retired_receipt)

        retired_path = Path(next(iter(deploy.RETIRED_RELEASE_RECEIPT_PATHS)))
        with self.assertRaisesRegex(deploy.DeploymentError, "path is permanently retired"):
            deploy.validate_release_receipt(retired_path, "a" * 64)

    @mock.patch.object(deploy, "DEPENDENCY_ENVELOPE_FROZEN", False)
    @mock.patch.object(deploy, "LOCAL_CORRECTION_REVIEW_ONLY", False)
    def test_stage_and_deploy_are_disabled_without_the_live_freeze(self) -> None:
        self.assertFalse(deploy.DEPENDENCY_ENVELOPE_FROZEN)
        self.assertEqual(
            deploy.DEPENDENCY_ENVELOPE_STATUS,
            deploy.DEPENDENCY_ENVELOPE_STATUS,
        )
        with self.assertRaisesRegex(deploy.DeploymentError, "staging is disabled"):
            deploy.stage_release(
                archive=Path("missing.tar"),
                manifest=Path("missing.json"),
                helper=Path("missing.php"),
                log_guard=Path("missing.py"),
                approval_token=deploy.STAGE_APPROVAL_TOKEN,
            )
        with self.assertRaisesRegex(deploy.DeploymentError, "deployment is disabled"):
            deploy.deploy_release(
                release_receipt_path=Path("missing-receipt.json"),
                release_receipt_sha256="0" * 64,
                approval_token=deploy.DEPLOY_APPROVAL_TOKEN,
            )

    def test_log_delta_uses_guard_and_keeps_distinct_evidence(self) -> None:
        guard = deploy.load_laravel_log_guard(LOG_GUARD_PATH)
        self.assertTrue(callable(guard.inspect_log_bytes))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_bytes(
                b"[2026-10-02 00:00:00] local.INFO: pre-cutover baseline\n"
            )
            state = root / "evidence"
            state.mkdir()
            with mock.patch.object(deploy, "APP_ROOT", application):
                baseline = deploy.log_baseline()
                with log_path.open("ab") as handle:
                    handle.write(
                        (FIXTURES / "reviewed-56-error-delta.redacted.txt").read_bytes()
                    )
                post_open = deploy.log_delta(
                    baseline,
                    state,
                    LOG_GUARD_PATH,
                    evidence_label="post-open",
                )
                final = deploy.log_delta(
                    baseline,
                    state,
                    LOG_GUARD_PATH,
                    evidence_label="final",
                )
            self.assertEqual(post_open["analysis"]["status"], "pass")
            self.assertEqual(post_open["analysis"]["nonfatal_error_entry_count"], 56)
            self.assertEqual(post_open["analysis"]["fatal_entry_count"], 0)
            self.assertNotEqual(post_open["path"], final["path"])
            self.assertNotEqual(post_open["analysis_path"], final["analysis_path"])
            self.assertEqual(deploy.sha256_file(Path(post_open["path"])), post_open["sha256"])
            self.assertEqual(deploy.sha256_file(Path(final["path"])), final["sha256"])

            with mock.patch.object(deploy, "APP_ROOT", application):
                genuine_baseline = deploy.log_baseline()
                with log_path.open("ab") as handle:
                    handle.write((FIXTURES / "genuine-sqlstate.txt").read_bytes())
                with self.assertRaisesRegex(deploy.DeploymentError, "rollback-worthy"):
                    deploy.log_delta(
                        genuine_baseline,
                        state,
                        LOG_GUARD_PATH,
                        evidence_label="genuine",
                    )
            report = json.loads(
                (state / "laravel-log-genuine-analysis.json").read_text("utf-8")
            )
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["signal_counts"], {"sqlstate": 1})

    def test_log_continuity_fails_closed_on_rotation_truncation_or_rewrite(self) -> None:
        for mode in ("rotation", "truncation", "copytruncate-regrow"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                application = Path(temporary) / "application"
                log_path = application / "storage/logs/laravel.log"
                log_path.parent.mkdir(parents=True)
                log_path.write_bytes(
                    b"[2026-10-02 00:00:00] production.INFO: "
                    + b"A" * 70000
                    + b"\n"
                )
                with mock.patch.object(deploy, "APP_ROOT", application):
                    checkpoint = deploy.log_baseline()
                    with log_path.open("ab") as handle:
                        handle.write(b"\nnormal append\n")
                    advanced = deploy.verify_log_continuity(checkpoint)
                    self.assertGreater(advanced["bytes"], checkpoint["bytes"])

                    if mode == "rotation":
                        log_path.replace(log_path.with_suffix(".log.1"))
                        log_path.write_bytes(b"B" * 80000)
                    elif mode == "truncation":
                        with log_path.open("r+b") as handle:
                            handle.truncate(10)
                    else:
                        with log_path.open("wb") as handle:
                            handle.write(b"B" * 80000)

                    with self.assertRaises(deploy.DeploymentError):
                        deploy.verify_log_continuity(advanced)

        source = RUNNER_PATH.read_text("utf-8")
        self.assertIn(
            "log_checkpoint = verify_log_continuity(log_checkpoint)",
            source,
        )

    def test_log_baseline_requires_an_existing_nonempty_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application = Path(temporary) / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            with mock.patch.object(deploy, "APP_ROOT", application):
                with self.assertRaisesRegex(deploy.DeploymentError, "must exist"):
                    deploy.log_baseline()
                log_path.write_bytes(b"")
                with self.assertRaisesRegex(deploy.DeploymentError, "nonempty"):
                    deploy.log_baseline()

    def test_log_baseline_retains_context_for_a_partial_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            partial = (
                b"[2026-10-02 00:00:00] production.INFO: "
                b"entry captured in the middle"
            )
            log_path.write_bytes(partial)
            state = root / "evidence"
            state.mkdir()

            with mock.patch.object(deploy, "APP_ROOT", application):
                baseline = deploy.log_baseline()
                self.assertFalse(baseline["ends_at_line_boundary"])
                self.assertEqual(baseline["entry_start"], 0)
                self.assertEqual(baseline["boundary_context_bytes"], len(partial))
                self.assertEqual(baseline["entry_context"]["bytes"], len(partial))
                self.assertEqual(
                    baseline["entry_context"]["sha256"],
                    deploy.sha256_bytes(partial),
                )
                with log_path.open("ab") as handle:
                    handle.write(
                        b" and completed after baseline\n"
                        b"[2026-10-02 00:00:01] production.INFO: next entry\n"
                    )
                result = deploy.log_delta(
                    baseline,
                    state,
                    LOG_GUARD_PATH,
                    evidence_label="partial-boundary",
                )

            self.assertEqual(result["analysis"]["status"], "pass")
            self.assertEqual(result["analysis"]["entry_count"], 2)
            self.assertEqual(result["baseline_context_bytes"], len(partial))
            self.assertGreater(result["new_bytes"], 0)

    def test_log_baseline_rejects_partial_unparseable_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            application = Path(temporary) / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_bytes(b"partial bytes without a Laravel header")
            with mock.patch.object(deploy, "APP_ROOT", application):
                with self.assertRaisesRegex(deploy.DeploymentError, "parseable boundary"):
                    deploy.log_baseline()

    def test_log_baseline_reparses_continuation_after_trailing_lf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            first_line = (
                b"[2026-10-02 00:00:00] production.INFO: request still writing\n"
            )
            log_path.write_bytes(first_line)
            state = root / "evidence"
            state.mkdir()

            with mock.patch.object(deploy, "APP_ROOT", application):
                baseline = deploy.log_baseline()
                self.assertTrue(baseline["ends_at_line_boundary"])
                self.assertEqual(baseline["entry_start"], 0)
                self.assertEqual(baseline["boundary_context_bytes"], len(first_line))
                with log_path.open("ab") as handle:
                    handle.write(
                        b"[stacktrace]\n#0 /synthetic.php(1): call()\n"
                        b"[2026-10-02 00:00:01] production.INFO: next request\n"
                    )
                with self.assertRaisesRegex(deploy.DeploymentError, "rollback-worthy"):
                    deploy.log_delta(
                        baseline,
                        state,
                        LOG_GUARD_PATH,
                        evidence_label="lf-continuation",
                    )

            report = json.loads(
                (state / "laravel-log-lf-continuation-analysis.json").read_text(
                    "utf-8"
                )
            )
            self.assertEqual(report["entry_count"], 2)
            self.assertEqual(report["signal_counts"], {"trace": 1})

    def test_fresh_header_after_baseline_excludes_retained_old_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            historical = (
                b"[2026-10-02 00:00:00] production.CRITICAL: historical failure\n"
            )
            prefix = b"\n\r\n"
            fresh = b"[2026-10-02 00:00:01] production.INFO: new request healthy\n"
            log_path.write_bytes(historical)
            state = root / "evidence"
            state.mkdir()

            with mock.patch.object(deploy, "APP_ROOT", application):
                baseline = deploy.log_baseline()
                with log_path.open("ab") as handle:
                    handle.write(prefix + fresh)
                result = deploy.log_delta(
                    baseline,
                    state,
                    LOG_GUARD_PATH,
                    evidence_label="fresh-header",
                )

            self.assertEqual(result["analysis"]["status"], "pass")
            self.assertEqual(result["analysis"]["entry_count"], 1)
            self.assertEqual(result["baseline_context_bytes"], len(historical))
            self.assertEqual(result["new_bytes"], len(prefix + fresh))
            self.assertEqual(result["analysis_bytes"], len(fresh))

    def test_header_like_format_drift_does_not_replay_retained_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            log_path = application / "storage/logs/laravel.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_bytes(
                b"[2026-10-02 00:00:00] production.CRITICAL: historical failure\n"
            )
            state = root / "evidence"
            state.mkdir()

            with mock.patch.object(deploy, "APP_ROOT", application):
                baseline = deploy.log_baseline()
                with log_path.open("ab") as handle:
                    handle.write(
                        b"\n[2026-10-02 00:00:01] production.UNKNOWN: format drift\n"
                    )
                with self.assertRaisesRegex(deploy.DeploymentError, "rollback-worthy"):
                    deploy.log_delta(
                        baseline,
                        state,
                        LOG_GUARD_PATH,
                        evidence_label="header-drift",
                    )

            report = json.loads(
                (state / "laravel-log-header-drift-analysis.json").read_text("utf-8")
            )
            self.assertEqual(report["entry_count"], 1)
            self.assertEqual(report["signal_counts"], {"unparsed_data": 1})

    def test_monitor_completes_thirty_minutes_and_checks_log_continuity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            front = root / "index.php"
            front.write_bytes(b"front controller")
            checkpoint = {
                "path": str(root / "laravel.log"),
                "exists": True,
                "inode": 1,
                "bytes": 0,
                "anchor": {
                    "start": 0,
                    "bytes": 0,
                    "sha256": deploy.sha256_bytes(b""),
                },
            }
            runtime = self.snapshot()
            with (
                mock.patch.object(deploy, "MONITOR_SECONDS", 120),
                mock.patch.object(deploy, "MONITOR_INTERVAL_SECONDS", 60),
                mock.patch.object(deploy, "FRONT_CONTROLLER", front),
                mock.patch.object(deploy, "EXPECTED_FRONT_CONTROLLER_SHA256", deploy.sha256_file(front)),
                mock.patch.object(
                    deploy,
                    "LARAVEL_MAINTENANCE_FILE",
                    root / "maintenance",
                ),
                mock.patch.object(
                    deploy,
                    "runtime_probe",
                    return_value=(runtime, {"test": True}),
                ),
                mock.patch.object(deploy, "health_snapshot", return_value={"status": "pass"}),
                mock.patch.object(
                    deploy,
                    "live_manifest_snapshot",
                    return_value={"sha256": deploy.EXPECTED_TARGET_SOURCE_CAS_SHA256},
                ),
                mock.patch.object(
                    deploy,
                    "dependency_identity",
                    return_value={"identity": "reviewed"},
                ),
                mock.patch.object(
                    deploy,
                    "verify_log_continuity",
                    side_effect=lambda value: value,
                ) as continuity,
                mock.patch.object(deploy.time, "sleep") as sleep,
                mock.patch.object(deploy,"full_source_identity",return_value={"status":"test"}),
                mock.patch.object(deploy.source_controls,"require_configuration_identity",return_value={}),
            ):
                result = deploy.monitor_production(
                    Path("helper.php"),
                    [],
                    root,
                    checkpoint,
                )

            self.assertEqual(result["samples"], 2)
            self.assertEqual(result["completed_intervals"], 2)
            self.assertEqual(result["minimum_elapsed_seconds"], 120)
            self.assertEqual(sleep.call_args_list, [mock.call(60), mock.call(60)])
            self.assertEqual(continuity.call_count, 3)

    @unittest.skipUnless(shutil.which("php"), "PHP CLI is unavailable")
    def test_candidate_fpm_probe_source_is_valid_php(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "candidate-fpm-probe.php"
            probe.write_bytes(deploy.candidate_fpm_probe_source())
            completed = subprocess.run(
                [shutil.which("php") or "php", "-l", str(probe)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_describe_declares_schema_present_source_only_safety(self) -> None:
        description = deploy.describe()
        self.assertEqual(description["target_application_commit"], deploy.TARGET_COMMIT)
        self.assertEqual(description["migration"]["schema_state"], deploy.SCHEMA_STATE)
        self.assertFalse(description["migration"]["command_invoked"])
        self.assertFalse(description["migration"]["pretend_invoked"])
        self.assertFalse(description["migration"]["executed_this_attempt"])
        self.assertEqual(description["installed_schema_identity"]["ledger_rows"], 21)
        self.assertEqual(
            description["runtime_paths"],
            {"total": 11, "additions": 1, "replacements": 10},
        )
        self.assertTrue(
            description["safety"]["schema_preserved_during_source_deploy_and_rollback"]
        )
        self.assertFalse(description["safety"]["capability_enablement"])
        self.assertFalse(description["safety"]["retention_execution"])
        self.assertTrue(
            description["dependency_identity"]["frozen_for_stage_or_deploy"]
        )
        self.assertEqual(
            description["dependency_identity"]["freeze_status"],
            deploy.DEPENDENCY_ENVELOPE_STATUS,
        )
        self.assertEqual(
            description["approval_tokens"]["status"],
            "bindings_frozen_pending_execution_authorization",
        )
        for action, value in deploy.expected_authorization_bindings().items():
            self.assertEqual(description["approval_tokens"][action], value)
        self.assertFalse(description["approval_tokens"]["execution_authorization_granted"])
        self.assertIn(
            "c43f39f556d057c99bb01e95ee7ca68658c05232",
            description["retired_artifacts"]["artifact_commit"],
        )
        serialized = json.dumps(description, sort_keys=True)
        self.assertNotIn("database_backup", serialized)
        self.assertNotIn("mysqldump", serialized)

    def test_rehearsal_covers_success_and_every_source_only_failure_boundary(self) -> None:
        self.assertEqual(
            rehearsal.SCENARIOS,
            (
                "success",
                "pre-source-failure",
                "activation-fpm-before-gate-rejection",
                "activation-fpm-under-gate-rejection",
                "source-swap-failure",
                "candidate-check-failure",
                "post-reopen-failure",
                "genuine-log-failure",
                "schema-preserving-rollback",
                "post-source-fpm-unavailable",
                "post-source-gate-http-failure",
                "rollback-with-normal-qbo",
                "recovery-with-normal-qbo",
                "rollback-with-qbo-startup",
                "recovery-with-qbo-startup",
            ),
        )
        source = REHEARSAL_PATH.read_text("utf-8")
        self.assertNotIn("runtime_state", source)
        self.assertNotIn("pre-migration-failure", source)
        self.assertIn("reviewed-56-error-delta.redacted.txt", source)
        self.assertIn("genuine-exception.txt", source)

        receipt = json.loads(REHEARSAL_RECEIPT_PATH.read_text("utf-8"))
        self.assertEqual(receipt["status"], "pass")
        self.assertTrue(receipt["dependency_envelope_simulated"])
        self.assertFalse(receipt["post_laravel_12_69_1_live_freeze_pending"])
        self.assertFalse(receipt["production_accessed"])
        self.assertFalse(receipt["production_staged"])
        self.assertEqual(set(receipt["scenarios"]), set(rehearsal.SCENARIOS))
        for name, result in receipt["scenarios"].items():
            with self.subTest(scenario=name):
                self.assertEqual(result["schema_state"], deploy.SCHEMA_STATE)
                self.assertEqual(result["migration_command_count"], 0)
                self.assertFalse(result["migration_command_invoked"])
                self.assertFalse(result["migration_pretend_invoked"])
                self.assertFalse(result["migration_executed_this_attempt"])
                self.assertTrue(result["separate_web_identity_all_passed"])
                if name == "success":
                    self.assertEqual(result["source_expectation"], "target")
                    self.assertFalse(result["rollback_complete"])
                elif name == "activation-fpm-before-gate-rejection":
                    self.assertEqual(result["source_expectation"], "expected-live")
                    self.assertFalse(result["source_install_started"])
                    self.assertFalse(result["rollback_complete"])
                    self.assertEqual(result["separate_web_identity_probe_count"], 0)
                else:
                    self.assertEqual(result["source_expectation"], "expected-live")
                    self.assertTrue(result["rollback_complete"])
                if name == "pre-source-failure":
                    self.assertFalse(result["source_install_started"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
