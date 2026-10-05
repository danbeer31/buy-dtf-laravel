"""Read-only scheduler policy for the source-only deployment.

Idle is mandatory before installation. After opening (and while verifying a
source rollback), only the pinned ten-minute QBO refresh may hold its mutex.
Expiry, status, schedule, and durable monotonic observations bound that exception;
no code in this module acquires, releases, clears, or executes scheduled work.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from zoneinfo import ZoneInfo


class SchedulerError(RuntimeError):
    pass


TASK = "qbo:refresh-admin-cache"
COMMAND_SHA256 = "5e5f803d8dcc65662d6a731cff510c28b61dece97d429bbf4f949099f7c9f5fd"
MUTEX_SHA256 = "a086c96c5fd6e5ba9e3e47ba418706400ad8928e2ea406688628a505d26b3eff"
PERIOD_SECONDS = 600
START_GRACE_SECONDS = 15
STARTUP_SECONDS = 10
STARTUP_POLL_SECONDS = 1
MAX_ACTIVITY_SECONDS = 120
MAX_OBSERVATION_GAP_SECONDS = 90
RELEASE_GRACE_SECONDS = 5
POLL_SECONDS = 5
MUTEX_TTL_SECONDS = 900
SCHEDULE_TIMEZONE = "America/Chicago"
SCHEDULE_ZONE = ZoneInfo(SCHEDULE_TIMEZONE)
POLICY = {
    "artifact": "buy-dtf-source-scheduler-policy-v2",
    "task": TASK,
    "command_sha256": COMMAND_SHA256,
    "mutex_name_sha256": MUTEX_SHA256,
    "expression": "*/10 * * * *",
    "timezone": SCHEDULE_TIMEZONE,
    "without_overlapping_minutes": 15,
    "run_in_background": True,
    "schedule_start_grace_seconds": START_GRACE_SECONDS,
    "worker_startup_seconds": STARTUP_SECONDS,
    "worker_startup_poll_seconds": STARTUP_POLL_SECONDS,
    "timestamp_policy": "explicit RFC3339 offsets normalized to UTC; no naive or unknown offsets",
    "maximum_activity_seconds": MAX_ACTIVITY_SECONDS,
    "maximum_observation_gap_seconds": MAX_OBSERVATION_GAP_SECONDS,
    "completion_release_grace_seconds": RELEASE_GRACE_SECONDS,
    "active_poll_seconds": POLL_SECONDS,
    "site_process_uids": [33, 1000],
    "php_executable": "/usr/bin/php8.2",
    "dispatcher_php_argv0_allowlist": ["/usr/bin/php8.2", "/usr/bin/php", "php8.2", "php"],
}
SOURCE_SHA256 = {
    "routes/console.php": "26aabb054889be1279c4c74c3e37c412e6de8a527864657b523fe983de03d444",
    "app/Console/Commands/RefreshQboAdminSnapshots.php": "21b014cd459b284bdedda0d8aa6d489a65b85fb84a8525798875633ea484c224",
    "app/Services/QboAdminSnapshotRefresher.php": "12c3a8bd07ec8218cb63e0b5f9d277dc8d9e7bb883d65f0ab913556509069ab2",
    "app/Services/QboAdminSnapshotStore.php": "5162053198ca8f2bbc55759d1619f9c3a3be01df67d9b689e07d7e6e66c5ba21",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


POLICY_SHA256 = digest(POLICY)


def integer(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise SchedulerError(f"Malformed scheduler {name}.")
    return value


def timestamp(value: Any, name: str, *, nullable: bool = False) -> int | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value) or value.endswith("-00:00"):
        raise SchedulerError(f"Malformed scheduler {name} timestamp.")
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())
    except (ValueError, OverflowError) as error:
        raise SchedulerError(f"Malformed scheduler {name} timestamp.") from error


def schedule_local(epoch: int | float) -> datetime:
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(SCHEDULE_ZONE)


def seconds_since_qbo_slot(epoch: int | float) -> float:
    at = schedule_local(epoch)
    return (at.minute % 10) * 60 + at.second + at.microsecond / 1e6


def due_commands(epoch: int | float) -> list[str]:
    """The frozen event inventory evaluated in the actual IANA timezone.

    Convert an absolute instant to local time, preserving both DST folds. Never
    attach Chicago to a naive wall clock or assume a fixed UTC offset.
    """
    at = schedule_local(epoch)
    due = []
    if at.minute == 0:
        due.append("stripe:sync-payouts")
    if at.hour == 1 and at.minute == 30:
        due.append("accounting:reconcile-stripe-holding")
    if at.minute % 10 == 0:
        due.append(TASK)
    return due


def expected_events() -> list[dict[str, Any]]:
    events = []
    for command, expression, background, overlaps in (
        ("stripe:sync-payouts", "0 * * * *", False, False),
        ("accounting:reconcile-stripe-holding", "30 1 * * *", False, False),
        (TASK, "*/10 * * * *", True, True),
    ):
        events.append({
            "command_sha256": hashlib.sha256(f"'/usr/bin/php8.2' 'artisan' {command}".encode()).hexdigest(),
            "expression": expression, "timezone": SCHEDULE_TIMEZONE,
            "without_overlapping": overlaps, "expires_at_minutes": 15 if overlaps else 1440,
            "run_in_background": background,
            "mutex_name_sha256": MUTEX_SHA256 if overlaps else None,
        })
    return sorted(events, key=lambda row: row["command_sha256"])


def validate_identity(payload: dict[str, Any]) -> dict[str, Any]:
    scheduler = payload.get("scheduler")
    if not isinstance(scheduler, dict) or type(scheduler.get("observer_version")) is not int or scheduler.get("observer_version") != 2:
        raise SchedulerError("Scheduler read-only observer identity is unavailable.")
    if scheduler.get("application_timezone") != SCHEDULE_TIMEZONE or scheduler.get("php_default_timezone") != SCHEDULE_TIMEZONE:
        raise SchedulerError("Application or PHP schedule timezone differs from baseline.")
    if scheduler.get("source_sha256") != SOURCE_SHA256 or not isinstance(scheduler.get("events"), list) or digest(scheduler["events"]) != digest(expected_events()):
        raise SchedulerError("Scheduled command identity, source, or schedule differs from baseline.")
    if type(scheduler.get("event_count")) is not int or scheduler["event_count"] != 3 or type(scheduler.get("stripe_payout_sync_event_count")) is not int or scheduler.get("stripe_payout_sync_event_count") != 1:
        raise SchedulerError("Scheduled event inventory differs from baseline.")
    mutexes = scheduler.get("overlap_mutexes")
    if not isinstance(mutexes, list) or len(mutexes) != 1 or not isinstance(mutexes[0], dict):
        raise SchedulerError("Unexpected scheduler overlap mutex inventory.")
    mutex = mutexes[0]
    if mutex.get("command_sha256") != COMMAND_SHA256 or mutex.get("mutex_name_sha256") != MUTEX_SHA256:
        raise SchedulerError("Unexpected scheduler overlap mutex identity.")
    if type(mutex.get("exists")) is not bool or type(scheduler.get("active_overlap_mutex_count")) is not int or scheduler["active_overlap_mutex_count"] != int(mutex["exists"]):
        raise SchedulerError("Malformed scheduler overlap mutex count.")
    if scheduler.get("read_only") is not True or not isinstance(scheduler.get("cache_driver"), str) or scheduler.get("cache_driver") not in {"file", "database"}:
        raise SchedulerError("Unsupported or mutating scheduler cache observer.")
    status = scheduler.get("refresh_status")
    if not isinstance(status, dict) or status.get("exists") is not True:
        raise SchedulerError("QBO refresh status is missing or malformed.")
    if status.get("state") != "ok" or status.get("last_error_at") is not None or status.get("last_error_present") is not False or status.get("circuit_retry_at") is not None:
        raise SchedulerError("QBO scheduled refresh is failing or deferred.")
    for key in ("linked_businesses", "updated_businesses", "invoice_count"):
        integer(status.get(key), key)
    attempt = timestamp(status.get("last_attempt_at"), "last_attempt_at")
    success = timestamp(status.get("last_success_at"), "last_success_at")
    observed = timestamp(payload.get("generated_at_utc"), "probe")
    if success > attempt or attempt > observed + 2:
        raise SchedulerError("QBO refresh status contains impossible timestamps.")
    if observed - success > PERIOD_SECONDS + START_GRACE_SECONDS + MAX_ACTIVITY_SECONDS:
        raise SchedulerError("QBO scheduled refresh status is stale.")
    if not mutex["exists"] and (mutex.get("expires_at_unix") is not None or mutex.get("owner_sha256") is not None):
        raise SchedulerError("Malformed absent scheduler mutex.")
    if mutex["exists"]:
        expiry = integer(mutex.get("expires_at_unix"), "mutex expiry")
        if not isinstance(mutex.get("owner_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", mutex["owner_sha256"]):
            raise SchedulerError("Malformed scheduler mutex owner.")
        started = expiry - MUTEX_TTL_SECONDS
        if started < 0 or started > observed + 2 or expiry <= observed:
            raise SchedulerError("Stale or malformed scheduler mutex expiry.")
    return {"scheduler": scheduler, "mutex": mutex, "attempt": attempt, "success": success, "observed": observed}


def require_idle(payload: dict[str, Any]) -> dict[str, Any]:
    row = validate_identity(payload)
    if row["mutex"]["exists"] or row["attempt"] != row["success"]:
        raise SchedulerError("Scheduled work or an overlap mutex differs from baseline: scheduler must be idle before source mutation.")
    return {"status": "pass", "policy": "idle", "policy_sha256": POLICY_SHA256, "active": False}


def identity_sha256(payload: dict[str, Any]) -> str:
    row = validate_identity(payload)["scheduler"]
    return digest({key: row[key] for key in ("observer_version", "read_only", "cache_driver", "application_timezone", "php_default_timezone", "source_sha256", "events", "event_count", "stripe_payout_sync_event_count")})


def process_envelope(payload: dict[str, Any], application_root: Path, *,
                     proc_root: Path = Path("/proc"), ticks_per_second: int | None = None,
                     wall_time: float | None = None) -> dict[str, Any]:
    """Read only command/cwd/executable/UID/start-time facts, never environments.

    Only an exact QBO worker or its exact successful finish command may remain.
    A brief schedule:run dispatcher is allowed solely when QBO is the only due
    event. Shell background wrappers with quoted commands are not executed or
    treated as workers; their exact source is pinned by the Laravel dependency
    and schedule identities. Any other scoped Artisan work fails closed.
    """
    row = validate_identity(payload)
    processes = []
    workers = 0
    hz = os.sysconf("SC_CLK_TCK") if ticks_per_second is None else ticks_per_second
    now = time.time() if wall_time is None else wall_time
    uptime = float((proc_root / "uptime").read_text().split()[0])
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) in {os.getpid(), os.getppid()}:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
            if b"artisan" not in raw:
                continue
            argv = raw.rstrip(b"\0").decode("utf-8", errors="strict").split("\0")
            if not any(value == "artisan" or value.endswith("/artisan") for value in argv):
                continue
            cwd = (entry / "cwd").resolve(strict=True)
            if cwd != application_root and str(application_root) not in " ".join(argv):
                continue
            executable = os.path.realpath(entry / "exe")
            if cwd != application_root or executable != POLICY["php_executable"] or len(argv) < 3 or argv[0] not in POLICY["dispatcher_php_argv0_allowlist"] or argv[1] != "artisan":
                raise SchedulerError("Unexpected scoped Artisan executable or working directory.")
            status = (entry / "status").read_text()
            match = re.search(r"(?m)^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", status)
            if not match or len(set(match.groups())) != 1 or int(match[1]) not in POLICY["site_process_uids"]:
                raise SchedulerError("Unexpected scheduled task process owner.")
            fields = (entry / "stat").read_text().rsplit(") ", 1)[1].split()
            age = uptime - int(fields[19]) / hz
            if age < 0 or age > MAX_ACTIVITY_SECONDS:
                raise SchedulerError("Scheduled process start time is malformed or stuck.")
            started = now - age
            role = None
            if argv[2:] == [TASK]:
                if argv[0] != POLICY["php_executable"]:
                    raise SchedulerError("QBO process is not from its reviewed schedule slot.")
                if row["mutex"]["exists"]:
                    acquired = row["mutex"]["expires_at_unix"] - MUTEX_TTL_SECONDS
                    if seconds_since_qbo_slot(acquired) > START_GRACE_SECONDS or not acquired - 2 <= started <= acquired + STARTUP_SECONDS:
                        raise SchedulerError("QBO worker launch does not match its bounded mutex startup.")
                elif seconds_since_qbo_slot(started) > START_GRACE_SECONDS + STARTUP_SECONDS:
                    raise SchedulerError("QBO finishing worker started outside its reviewed startup window.")
                if not row["mutex"]["exists"] and row["observed"] - row["success"] > RELEASE_GRACE_SECONDS:
                    raise SchedulerError("QBO process has no matching mutex or fresh completion.")
                role = "reviewed_qbo_worker"
                workers += 1
            elif len(argv) == 5 and argv[2] == "schedule:finish" and hashlib.sha256(argv[3].encode()).hexdigest() == MUTEX_SHA256 and argv[4] == "0":
                if argv[0] != POLICY["php_executable"] or age > RELEASE_GRACE_SECONDS or row["observed"] - row["success"] > RELEASE_GRACE_SECONDS:
                    raise SchedulerError("QBO finish process lacks fresh successful completion.")
                role = "reviewed_qbo_successful_finish"
            elif argv[2:] == ["schedule:run"]:
                if age > RELEASE_GRACE_SECONDS or seconds_since_qbo_slot(started) > START_GRACE_SECONDS or due_commands(started) != [TASK]:
                    raise SchedulerError("Scheduler dispatcher includes unapproved due work or is stale.")
                role = "reviewed_qbo_only_dispatcher"
            else:
                raise SchedulerError("Unexpected or failing scoped Artisan work after reopening.")
            processes.append({"pid": int(entry.name), "role": role, "uid": int(match[1]),
                "argv_sha256": hashlib.sha256(raw).hexdigest(), "executable": executable,
                "working_directory": str(cwd), "age_seconds": round(age, 6)})
        except (FileNotFoundError, ProcessLookupError):
            continue  # A process can finish during this read-only observation.
        except (UnicodeError, ValueError, IndexError, PermissionError) as error:
            raise SchedulerError("Malformed or unreadable scoped scheduler process evidence.") from error
    if workers > 1:
        raise SchedulerError("More than one QBO scheduled worker is active.")
    return {"status": "pass", "read_only": True, "processes": sorted(processes, key=lambda item: item["pid"]),
            "environments_read": False, "mutex_or_task_actions": False}


def observe(payload: dict[str, Any], previous: dict[str, Any] | None, *, phase: str,
            monotonic_ns: int | None = None, wall_time: float | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if phase not in {"post_open", "monitor", "rollback", "recovery"}:
        raise SchedulerError("Unreviewed scheduler activity phase.")
    row = validate_identity(payload)
    tick = time.monotonic_ns() if monotonic_ns is None else monotonic_ns
    now = time.time() if wall_time is None else wall_time
    if abs(now - row["observed"]) > 30:
        raise SchedulerError("Stale scheduler runtime observation.")
    if previous is None:
        previous = {"artifact": "buy-dtf-source-scheduler-state-v2", "policy_sha256": POLICY_SHA256,
                    "cache_driver": row["scheduler"]["cache_driver"],
                    "last_monotonic_ns": tick, "last_observed_unix": row["observed"],
                    "last_success_unix": row["success"], "last_attempt_unix": row["attempt"],
                    "pending": None, "sequence": 0}
    if not isinstance(previous, dict) or previous.get("artifact") != "buy-dtf-source-scheduler-state-v2" or previous.get("policy_sha256") != POLICY_SHA256:
        raise SchedulerError("Missing or malformed frozen scheduler state.")
    if previous.get("cache_driver") != row["scheduler"]["cache_driver"]:
        raise SchedulerError("Scheduler cache identity changed or is missing.")
    old_tick = integer(previous.get("last_monotonic_ns"), "monotonic state")
    old_success = integer(previous.get("last_success_unix"), "success state")
    old_attempt = integer(previous.get("last_attempt_unix"), "attempt state")
    old_observed = integer(previous.get("last_observed_unix"), "wall state")
    if tick < old_tick or row["observed"] < old_observed or row["success"] < old_success or row["attempt"] < old_attempt:
        raise SchedulerError("Scheduler clock or status regressed.")
    if abs((row["observed"] - old_observed) - (tick - old_tick) / 1e9) > 5:
        raise SchedulerError("Scheduler wall/monotonic clock continuity was lost.")
    if (tick - old_tick) / 1e9 > MAX_OBSERVATION_GAP_SECONDS:
        raise SchedulerError("Scheduler observation gap is too large to prove bounded activity.")
    pending = previous.get("pending")
    transitions = []
    if pending is not None:
        if not isinstance(pending, dict) or set(pending) != {"identity_sha256", "started_unix", "first_monotonic_ns", "startup_deadline_monotonic_ns", "stage", "attempt_recorded_unix", "completion_unix"}:
            raise SchedulerError("Malformed pending scheduler state.")
        pending_start = integer(pending["started_unix"], "pending start")
        if not isinstance(pending["identity_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", pending["identity_sha256"]):
            raise SchedulerError("Malformed pending scheduler identity.")
        first_tick = integer(pending["first_monotonic_ns"], "pending monotonic start")
        if tick < first_tick or (tick - first_tick) / 1e9 > MAX_ACTIVITY_SECONDS:
            raise SchedulerError("QBO scheduled refresh is stuck (monotonic bound).")
        deadline = integer(pending["startup_deadline_monotonic_ns"], "startup deadline")
        if not first_tick <= deadline <= first_tick + STARTUP_SECONDS * 10**9 or pending["stage"] not in {"startup", "running", "completing"}:
            raise SchedulerError("Malformed durable scheduler startup transition.")
        attempt_recorded = pending["attempt_recorded_unix"]
        completion = pending["completion_unix"]
        if attempt_recorded is not None and not pending_start <= integer(attempt_recorded, "recorded attempt") <= pending_start + STARTUP_SECONDS:
            raise SchedulerError("Malformed durable scheduler attempt transition.")
        if completion is not None and not pending_start <= integer(completion, "recorded completion") <= pending_start + MAX_ACTIVITY_SECONDS:
            raise SchedulerError("Malformed durable scheduler completion transition.")
        if ((pending["stage"] == "startup" and (attempt_recorded is not None or completion is not None))
            or (pending["stage"] == "running" and (attempt_recorded is None or completion is not None))
            or (pending["stage"] == "completing" and completion is None)):
            raise SchedulerError("Malformed durable scheduler progress state.")
    mutex = row["mutex"]
    if mutex["exists"]:
        started = mutex["expires_at_unix"] - MUTEX_TTL_SECONDS
        age = row["observed"] - started
        identity = digest({"owner": mutex["owner_sha256"], "expires": mutex["expires_at_unix"]})
        if seconds_since_qbo_slot(started) > START_GRACE_SECONDS or age > MAX_ACTIVITY_SECONDS:
            raise SchedulerError("QBO overlap mutex is unscheduled, stale, or stuck.")
        if row["success"] >= started and row["observed"] - row["success"] > RELEASE_GRACE_SECONDS:
            raise SchedulerError("QBO refresh succeeded but its mutex is stuck.")
        if pending is not None and pending["identity_sha256"] != identity:
            raise SchedulerError("QBO mutex changed before verified task completion.")
        if pending is None:
            pending = {"identity_sha256": identity, "started_unix": started, "first_monotonic_ns": tick,
                       "startup_deadline_monotonic_ns": tick + max(0, STARTUP_SECONDS - age) * 10**9,
                       "stage": None, "attempt_recorded_unix": None, "completion_unix": None}
            transitions.append("acquired")
        prior_stage = pending["stage"]
        if row["attempt"] < started:
            # Laravel acquires the mutex before the worker can call markAttempt.
            # Admit only the previous healthy completion for a fixed ten seconds
            # from that acquisition, never ten new seconds from a later sample.
            if row["attempt"] != row["success"] or prior_stage in {"running", "completing"}:
                raise SchedulerError("QBO startup has an orphaned or regressed refresh attempt.")
            if age > STARTUP_SECONDS or tick > pending["startup_deadline_monotonic_ns"]:
                raise SchedulerError("QBO startup did not record timely progress.")
            if prior_stage == "startup" and (row["attempt"] != old_attempt or row["success"] != old_success):
                raise SchedulerError("Previous QBO status changed during startup.")
            if prior_stage is None:
                transitions.append("startup")
            pending["stage"] = "startup"
        elif row["success"] >= started and row["attempt"] == row["success"]:
            if row["success"] > started + MAX_ACTIVITY_SECONDS:
                raise SchedulerError("QBO completion exceeded its activity bound.")
            if prior_stage == "startup":
                if row["success"] > started + STARTUP_SECONDS:
                    raise SchedulerError("QBO startup completed without timely observed progress.")
                pending["attempt_recorded_unix"] = row["success"]
                transitions.append("startup_progress_confirmed")
            if prior_stage == "completing" and pending["completion_unix"] != row["success"]:
                raise SchedulerError("QBO completion changed before its mutex was released.")
            if prior_stage != "completing":
                transitions.append("success_recorded")
            pending["stage"] = "completing"
            pending["completion_unix"] = row["success"]
        else:
            if row["attempt"] > started + STARTUP_SECONDS or prior_stage == "completing":
                raise SchedulerError("QBO worker did not make timely startup progress.")
            if pending["attempt_recorded_unix"] is not None and pending["attempt_recorded_unix"] != row["attempt"]:
                raise SchedulerError("QBO worker recorded an unexpected additional attempt.")
            if prior_stage == "startup":
                transitions.append("startup_progress_confirmed")
            pending["stage"] = "running"
            pending["attempt_recorded_unix"] = row["attempt"]
    else:
        if row["attempt"] != row["success"]:
            raise SchedulerError("QBO refresh attempt is orphaned or failed without a mutex.")
        if pending is not None:
            if not pending["started_unix"] <= row["success"] <= pending["started_unix"] + MAX_ACTIVITY_SECONDS:
                raise SchedulerError("QBO mutex cleared without bounded successful completion.")
            if pending["stage"] == "startup":
                if row["success"] > pending["started_unix"] + STARTUP_SECONDS:
                    raise SchedulerError("QBO startup mutex cleared without timely progress.")
                transitions.append("startup_progress_confirmed")
            if pending["completion_unix"] is not None and pending["completion_unix"] != row["success"]:
                raise SchedulerError("QBO completion changed during mutex release.")
            transitions.extend(["completed", "released"])
            pending = None
        elif row["success"] > old_success:
            if seconds_since_qbo_slot(row["success"]) > START_GRACE_SECONDS + MAX_ACTIVITY_SECONDS:
                raise SchedulerError("Unscheduled QBO refresh completion between observations.")
            transitions.append("completed_between_samples")
    current = {"artifact": previous["artifact"], "policy_sha256": POLICY_SHA256,
               "cache_driver": row["scheduler"]["cache_driver"],
               "last_monotonic_ns": tick, "last_observed_unix": row["observed"],
               "last_success_unix": row["success"], "last_attempt_unix": row["attempt"], "pending": pending,
               "sequence": integer(previous.get("sequence"), "sequence") + 1}
    receipt = {"status": "pass", "phase": phase, "policy": "bounded_reviewed_qbo_only",
               "policy_sha256": POLICY_SHA256, "task": TASK, "active": mutex["exists"],
               "observed_at_utc": payload["generated_at_utc"], "monotonic_ns": tick,
               "scheduler_snapshot_sha256": digest(row["scheduler"]),
               "transitions": transitions, "pending": pending,
               "last_success_unix": row["success"], "sequence": current["sequence"]}
    return current, receipt
