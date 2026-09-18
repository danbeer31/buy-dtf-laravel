#!/usr/bin/env python3
"""Fail-closed runner for the single Stripe payout notes migration.

This artifact deliberately has no general migration mode. Production execution
requires an exact approval token and exact hashes for both the migration and its
Laravel runtime helper.
"""

from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Any


APP_ROOT = Path("/var/www/buy-dtf")
MIGRATION_RELATIVE_PATH = Path(
    "database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php"
)
MIGRATION_NAME = "2026_09_18_120000_add_notes_to_stripe_payout_entries_table"
MIGRATION_SHA256 = "6bdd43d63d2427af19a2fb65afd1b295b12759ac916d2803d245de2c6f7c1e0c"
RUNTIME_HELPER_SHA256 = "04918419f9b085fcbe0eb35294fc6ec58ca1eaacbfd95bb8a8a9e73aa8f60cae"
APPROVAL_TOKEN = "APPLY-STRIPE-PAYOUT-NOTES-6bdd43d63d2427af"
RUN_ROOT_RELATIVE_PATH = Path("storage/app/private/operations/payout-notes")
LOCK_RELATIVE_PATH = Path("storage/framework/payout-notes-correction.lock")

HEALTH_CHECKS = (
    ("https://buy-dtf.com/", {200}),
    ("https://buy-dtf.com/up", {200}),
    ("https://buy-dtf.com/login", {200}),
    ("https://buy-dtf.com/admin", {302}),
    ("https://buy-dtf.com/checkout", {302}),
)


class CorrectionError(RuntimeError):
    """Expected fail-closed stop."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(path: Path, expected_sha256: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise CorrectionError(f"Required artifact is not a regular file: {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise CorrectionError(
            f"Artifact checksum mismatch for {path.name}: expected {expected_sha256}, got {actual}"
        )


def run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise CorrectionError(
            f"Command failed at {Path(command[0]).name} (exit {completed.returncode})."
        )
    return completed


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write(path, encoded)


def sanitize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(snapshot)
    sanitized.pop("database_name", None)
    return sanitized


def runtime_snapshot(helper: Path, app_root: Path) -> dict[str, Any]:
    completed = run(
        ["/usr/bin/php", str(helper), str(app_root), "snapshot"],
        cwd=app_root,
        timeout=45,
    )
    try:
        snapshot = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise CorrectionError("The Laravel runtime helper returned invalid JSON.") from exception
    if not isinstance(snapshot, dict):
        raise CorrectionError("The Laravel runtime helper returned an invalid snapshot.")
    return snapshot


def write_mysql_defaults(helper: Path, app_root: Path, output: Path) -> dict[str, Any]:
    completed = run(
        ["/usr/bin/php", str(helper), str(app_root), "write-defaults", str(output)],
        cwd=app_root,
        timeout=45,
    )
    try:
        snapshot = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise CorrectionError("Unable to decode the database-backup configuration snapshot.") from exception
    if not output.is_file() or output.is_symlink() or (output.stat().st_mode & 0o777) != 0o600:
        raise CorrectionError("The temporary MySQL defaults file is absent or has unsafe permissions.")
    return snapshot


def validate_before_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("php_version") != "8.2.30":
        raise CorrectionError("PHP CLI differs from the reviewed 8.2.30 baseline.")
    if snapshot.get("fuel_connection") != "fuelmysql":
        raise CorrectionError("The runtime helper did not select fuelmysql.")
    if snapshot.get("configured_fuel_connection") != "fuelmysql":
        raise CorrectionError("database.fuel_connection is not fuelmysql.")
    if snapshot.get("driver") != "mysql":
        raise CorrectionError("fuelmysql is not a MySQL connection.")
    if not str(snapshot.get("server_version", "")).startswith("8.0."):
        raise CorrectionError("The database server is not the audited MySQL 8.0 family.")
    if snapshot.get("stripe_payout_entries_exists") is not True:
        raise CorrectionError("stripe_payout_entries is missing.")
    if snapshot.get("notes_column") is not None:
        raise CorrectionError("The notes column already exists; no correction is required.")
    if snapshot.get("migration_ledger_count") != 0:
        raise CorrectionError("The exact migration is already recorded in the Fuel ledger.")
    if not isinstance(snapshot.get("stripe_payout_entries_count"), int):
        raise CorrectionError("The payout-entry row count could not be read.")
    if not isinstance(snapshot.get("stripe_payouts_count"), int):
        raise CorrectionError("The payout row count could not be read.")


def validate_after_snapshot(before: dict[str, Any], after: dict[str, Any]) -> None:
    column = after.get("notes_column")
    if not isinstance(column, dict):
        raise CorrectionError("The notes column is absent after migration.")
    if column.get("data_type") != "text" or column.get("is_nullable") != "YES":
        raise CorrectionError("The notes column type/nullability does not match the approved schema.")
    if after.get("migration_ledger_count") != 1:
        raise CorrectionError("The Fuel migration ledger does not contain exactly one correction entry.")
    for field in ("stripe_payout_entries_count", "stripe_payouts_count"):
        if after.get(field) != before.get(field):
            raise CorrectionError(f"Row count changed unexpectedly for {field}.")


def payout_processes() -> list[str]:
    matches: list[str] = []
    own_ancestry = {os.getpid(), os.getppid()}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in own_ancestry:
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if "artisan stripe:sync-payouts" in command or "ProcessStripePayoutWebhook" in command:
            matches.append(f"pid={entry.name}")
    return sorted(matches)


def health_snapshot() -> dict[str, int]:
    statuses: dict[str, int] = {}
    for url, allowed in HEALTH_CHECKS:
        completed = run(
            [
                "/usr/bin/curl",
                "--silent",
                "--show-error",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                "--connect-timeout",
                "5",
                "--max-time",
                "10",
                "--max-redirs",
                "0",
                url,
            ],
            cwd=APP_ROOT,
            timeout=15,
        )
        try:
            status = int(completed.stdout)
        except ValueError as exception:
            raise CorrectionError(f"Health probe returned an invalid status for {url}.") from exception
        if status not in allowed:
            raise CorrectionError(f"Health probe failed for {url} with HTTP {status}.")
        statuses[url] = status
    return statuses


def validate_toolchain() -> None:
    for executable in ("/usr/bin/curl", "/usr/bin/mysqldump", "/usr/bin/php"):
        if not Path(executable).is_file() or not os.access(executable, os.X_OK):
            raise CorrectionError(f"Required reviewed executable is unavailable: {executable}")
    if sys.version_info[:3] != (3, 10, 12):
        raise CorrectionError("Python runtime differs from the reviewed 3.10.12 baseline.")
    mysqldump = run(
        ["/usr/bin/mysqldump", "--version"],
        cwd=APP_ROOT,
        timeout=15,
    )
    if "Ver 8.0.46" not in mysqldump.stdout:
        raise CorrectionError("mysqldump differs from the reviewed 8.0.46 baseline.")


def create_backup(
    *, helper: Path, app_root: Path, run_directory: Path
) -> tuple[Path, str, dict[str, Any]]:
    defaults_file = run_directory / ".mysql-client.cnf"
    raw_dump = run_directory / ".payout-tables-before.sql"
    final_dump = run_directory / "payout-tables-before.sql.gz"
    configuration = write_mysql_defaults(helper, app_root, defaults_file)
    database_name = configuration.get("database_name")
    if not isinstance(database_name, str) or not re.fullmatch(
        r"[A-Za-z0-9_$][A-Za-z0-9_$-]*", database_name
    ):
        raise CorrectionError("The resolved database name is not safe for a positional dump argument.")

    try:
        with raw_dump.open("xb") as output:
            os.chmod(raw_dump, 0o600)
            process = subprocess.run(
                [
                    "/usr/bin/mysqldump",
                    f"--defaults-extra-file={defaults_file}",
                    "--single-transaction",
                    "--quick",
                    "--skip-lock-tables",
                    "--hex-blob",
                    "--set-gtid-purged=OFF",
                    "--no-tablespaces",
                    "--column-statistics=0",
                    database_name,
                    "stripe_payouts",
                    "stripe_payout_entries",
                ],
                cwd=app_root,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=180,
                check=False,
            )
            output.flush()
            os.fsync(output.fileno())
        if process.returncode != 0:
            raise CorrectionError(f"mysqldump failed with exit {process.returncode}.")

        seen_payouts = False
        seen_entries = False
        seen_completion = False
        trailing = b""
        with raw_dump.open("rb") as source, gzip.open(final_dump, "xb", compresslevel=9) as target:
            os.chmod(final_dump, 0o600)
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                scan = trailing + chunk
                seen_payouts = seen_payouts or b"CREATE TABLE `stripe_payouts`" in scan
                seen_entries = seen_entries or b"CREATE TABLE `stripe_payout_entries`" in scan
                seen_completion = seen_completion or b"-- Dump completed on" in scan
                trailing = scan[-256:]
                target.write(chunk)
        if not (seen_payouts and seen_entries and seen_completion):
            raise CorrectionError("The payout backup is incomplete or missing required table markers.")
        if final_dump.stat().st_size == 0:
            raise CorrectionError("The payout backup is empty.")

        with gzip.open(final_dump, "rb") as verification:
            while verification.read(1024 * 1024):
                pass
        descriptor = os.open(final_dump, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory_descriptor = os.open(run_directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)

        return final_dump, sha256_file(final_dump), configuration
    finally:
        defaults_file.unlink(missing_ok=True)
        raw_dump.unlink(missing_ok=True)


def validate_pretend(output: str) -> None:
    lowered = output.lower()
    normalized = re.sub(r"\s+", " ", lowered)
    if MIGRATION_NAME not in lowered:
        raise CorrectionError("Pretend output does not identify the approved migration.")
    if len(re.findall(r"\balter\s+table\b", normalized)) != 1:
        raise CorrectionError("Pretend output does not contain exactly one ALTER TABLE statement.")
    if not re.search(
        r"alter\s+table\s+[`\"]?stripe_payout_entries[`\"]?.*add(?:\s+column)?\s+[`\"]?notes[`\"]?\s+text",
        normalized,
    ):
        raise CorrectionError("Pretend output is not the approved nullable notes-column alteration.")
    prohibited = ("drop table", "drop column", "truncate", "delete from", "update ", "insert into", "rename table")
    if any(token in normalized for token in prohibited):
        raise CorrectionError("Pretend output contains prohibited SQL.")


def describe() -> None:
    print(
        json.dumps(
            {
                "application_root": str(APP_ROOT),
                "migration": str(MIGRATION_RELATIVE_PATH),
                "migration_sha256": MIGRATION_SHA256,
                "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
                "execution_scope": "single-migration-only",
                "general_migrate_supported": False,
                "rollback_strategy": "retain nullable notes column and roll back application code only",
            },
            indent=2,
            sort_keys=True,
        )
    )


def self_check(repo_root: Path) -> None:
    root = repo_root.resolve(strict=True)
    migration = root / MIGRATION_RELATIVE_PATH
    helper = Path(__file__).resolve().with_name("payout_notes_runtime.php")
    require_regular_file(migration, MIGRATION_SHA256)
    require_regular_file(helper, RUNTIME_HELPER_SHA256)
    print("payout-notes artifact self-check: PASS")


def preflight() -> None:
    if str(APP_ROOT.resolve(strict=True)) != str(APP_ROOT) or APP_ROOT.is_symlink():
        raise CorrectionError("The fixed production application root is invalid or symbolic.")
    migration = APP_ROOT / MIGRATION_RELATIVE_PATH
    helper = Path(__file__).resolve().with_name("payout_notes_runtime.php")
    validate_toolchain()
    require_regular_file(migration, MIGRATION_SHA256)
    require_regular_file(helper, RUNTIME_HELPER_SHA256)
    if conflicts := payout_processes():
        raise CorrectionError(f"A payout process is active ({', '.join(conflicts)}).")
    snapshot = runtime_snapshot(helper, APP_ROOT)
    validate_before_snapshot(snapshot)
    payload = {
        "artifact": "buy-dtf-stripe-payout-notes-preflight-v1",
        "status": "pass",
        "migration_sha256": MIGRATION_SHA256,
        "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
        "snapshot": sanitize_snapshot(snapshot),
        "health": health_snapshot(),
        "general_migrate_supported": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def execute(approval_token: str) -> None:
    if approval_token != APPROVAL_TOKEN:
        raise CorrectionError("The exact reviewed execution approval token was not supplied.")
    if os.geteuid() == 0:
        raise CorrectionError("Refusing to run the application-scoped correction as root.")
    if str(APP_ROOT.resolve(strict=True)) != str(APP_ROOT) or APP_ROOT.is_symlink():
        raise CorrectionError("The fixed production application root is invalid or symbolic.")
    validate_toolchain()

    migration = APP_ROOT / MIGRATION_RELATIVE_PATH
    helper = Path(__file__).resolve().with_name("payout_notes_runtime.php")
    require_regular_file(migration, MIGRATION_SHA256)
    require_regular_file(helper, RUNTIME_HELPER_SHA256)
    for executable in ("/usr/bin/php", "/usr/bin/curl", "/usr/bin/mysqldump"):
        if not Path(executable).is_file():
            raise CorrectionError(f"Required executable is unavailable: {executable}")

    lock_path = APP_ROOT / LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(mode=0o775, parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        run_root = APP_ROOT / RUN_ROOT_RELATIVE_PATH
        run_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(run_root, 0o700)
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        run_directory = run_root / timestamp
        run_directory.mkdir(mode=0o700)

        receipt: dict[str, Any] = {
            "artifact": "buy-dtf-stripe-payout-notes-correction-v1",
            "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "running",
            "stage": "initializing",
            "application_root": str(APP_ROOT),
            "migration_relative_path": str(MIGRATION_RELATIVE_PATH),
            "migration_sha256": MIGRATION_SHA256,
            "runtime_helper_sha256": RUNTIME_HELPER_SHA256,
            "general_migrate_used": False,
        }
        receipt_path = run_directory / "execution-receipt.json"
        rollback_path = run_directory / "rollback-receipt.json"
        backup_path: Path | None = None
        backup_sha256: str | None = None
        atomic_json(receipt_path, receipt)

        try:
            receipt["stage"] = "precheck"
            if conflicts := payout_processes():
                raise CorrectionError(f"A payout process is active ({', '.join(conflicts)}).")
            before = runtime_snapshot(helper, APP_ROOT)
            validate_before_snapshot(before)
            before_health = health_snapshot()
            receipt["before"] = sanitize_snapshot(before)
            receipt["health_before"] = before_health
            atomic_json(receipt_path, receipt)

            receipt["stage"] = "backup"
            backup_path, backup_sha256, backup_configuration = create_backup(
                helper=helper,
                app_root=APP_ROOT,
                run_directory=run_directory,
            )
            if backup_configuration.get("database_name_sha256") != before.get("database_name_sha256"):
                raise CorrectionError("Backup connection identity differs from the precheck connection.")
            receipt["backup"] = {
                "relative_path": backup_path.name,
                "sha256": backup_sha256,
                "bytes": backup_path.stat().st_size,
                "mode": oct(backup_path.stat().st_mode & 0o777),
                "tables": ["stripe_payouts", "stripe_payout_entries"],
                "gzip_verified": True,
            }
            atomic_json(receipt_path, receipt)

            receipt["stage"] = "pretend"
            pretend = run(
                [
                    "/usr/bin/php",
                    "artisan",
                    "migrate",
                    "--database=fuelmysql",
                    f"--path={MIGRATION_RELATIVE_PATH.as_posix()}",
                    "--pretend",
                    "--force",
                    "--no-interaction",
                    "--no-ansi",
                ],
                cwd=APP_ROOT,
                timeout=90,
            )
            validate_pretend(pretend.stdout)
            pretend_path = run_directory / "pretend-output.txt"
            atomic_write(pretend_path, pretend.stdout.encode("utf-8"))
            receipt["pretend"] = {
                "sha256": sha256_file(pretend_path),
                "validated_single_additive_alter": True,
            }
            atomic_json(receipt_path, receipt)

            if payout_processes():
                raise CorrectionError("A payout process started after precheck; stopping before migration.")
            repeat = runtime_snapshot(helper, APP_ROOT)
            validate_before_snapshot(repeat)
            if sanitize_snapshot(repeat) != sanitize_snapshot(before):
                raise CorrectionError("The payout schema/ledger/count snapshot changed before execution.")

            receipt["stage"] = "migration"
            migration_run = run(
                [
                    "/usr/bin/php",
                    "artisan",
                    "migrate",
                    "--database=fuelmysql",
                    f"--path={MIGRATION_RELATIVE_PATH.as_posix()}",
                    "--force",
                    "--no-interaction",
                    "--no-ansi",
                ],
                cwd=APP_ROOT,
                timeout=120,
            )
            migration_output_path = run_directory / "migration-output.txt"
            atomic_write(migration_output_path, migration_run.stdout.encode("utf-8"))
            receipt["migration_output_sha256"] = sha256_file(migration_output_path)
            atomic_json(receipt_path, receipt)

            receipt["stage"] = "verification"
            after = runtime_snapshot(helper, APP_ROOT)
            validate_after_snapshot(before, after)
            after_health = health_snapshot()
            receipt["after"] = sanitize_snapshot(after)
            receipt["health_after"] = after_health
            receipt["stage"] = "complete"
            receipt["status"] = "success"
            receipt["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            rollback = {
                "artifact": "buy-dtf-stripe-payout-notes-rollback-receipt-v1",
                "execution_receipt": receipt_path.name,
                "backup_relative_path": backup_path.name,
                "backup_sha256": backup_sha256,
                "automatic_database_restore": False,
                "approved_schema_rollback": "retain_nullable_notes_column",
                "application_code_rollback_safe": True,
                "reason": (
                    "Dropping the additive nullable column or restoring both payout tables could destroy "
                    "post-correction payout data. Keep the column on code rollback. Any table restore "
                    "requires a separate incident review, stopped payout writes, and this verified backup."
                ),
            }
            atomic_json(rollback_path, rollback)
            receipt["rollback_receipt_sha256"] = sha256_file(rollback_path)
            atomic_json(receipt_path, receipt)
            print(f"Correction complete. Receipt: {receipt_path}")
        except BaseException as exception:
            receipt["status"] = "failed"
            receipt["failed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            receipt["failure_class"] = type(exception).__name__
            receipt["failure_message"] = str(exception)
            rollback = {
                "artifact": "buy-dtf-stripe-payout-notes-rollback-receipt-v1",
                "execution_receipt": receipt_path.name,
                "backup_relative_path": backup_path.name if backup_path is not None else None,
                "backup_sha256": backup_sha256,
                "automatic_database_restore": False,
                "approved_schema_rollback": "retain_nullable_notes_column_if_present",
                "application_code_rollback_safe": True,
                "requires_operator_review": True,
                "reason": (
                    "The run did not complete verification. Do not drop the additive column or restore "
                    "live payout tables automatically; inspect the ledger/schema and reconcile any "
                    "post-backup activity first."
                ),
            }
            atomic_json(rollback_path, rollback)
            receipt["rollback_receipt_sha256"] = sha256_file(rollback_path)
            atomic_json(receipt_path, receipt)
            raise


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--describe", action="store_true")
    action.add_argument("--self-check", action="store_true")
    action.add_argument("--preflight", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--approval-token")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        if arguments.describe:
            describe()
        elif arguments.self_check:
            if arguments.repo_root is None:
                raise CorrectionError("--self-check requires --repo-root.")
            self_check(arguments.repo_root)
        elif arguments.preflight:
            preflight()
        else:
            if arguments.approval_token is None:
                raise CorrectionError("--execute requires --approval-token.")
            execute(arguments.approval_token)
    except (CorrectionError, BlockingIOError, subprocess.TimeoutExpired) as exception:
        print(f"STOP: {exception}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    def interrupted(signum: int, _frame: object) -> None:
        raise CorrectionError(f"Interrupted by signal {signum}; no schema rollback was attempted.")

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
