#!/usr/bin/env python3
"""Run the actual post-open/monitor validators with deterministic local inputs.

Every external application/HTTP/database check is a local double. Scheduler
validation, durable evidence, 30 monitoring intervals, log continuity calls,
failure handling, and lock-state transitions use real reviewed runner code.
No network, cron, accounting command, cache mutation, or production is used.
"""
from datetime import datetime, timezone
import argparse
import copy
import json
from pathlib import Path
import tempfile
from unittest import mock

import production_alpha_transparency_deploy as deploy
import rehearse_production_alpha_transparency as source_rehearsal


SCENARIOS = ("sample-19-normal-completion", "post-open-normal-completion", "monitor-close-normal-completion", "unexpected-mutex", "stuck-task", "task-failure",
             "orphaned-completion", "malformed-status", "unscheduled-task", "health-failure",
             "queue-failure", "schema-drift", "source-drift", "dependency-drift", "log-continuity-loss",
             "monitor-startup-normal", "post-open-startup", "monitor-close-startup", "winter-monitor-startup",
             "startup-never-progress", "startup-late-progress", "startup-orphaned", "startup-failure")
SUCCESSFUL = {"sample-19-normal-completion", "post-open-normal-completion", "monitor-close-normal-completion",
              "monitor-startup-normal", "post-open-startup", "monitor-close-startup", "winter-monitor-startup"}
BASE = int(datetime(2026, 10, 5, 0, 2, 8, tzinfo=timezone.utc).timestamp())


def run_case(scenario: str, directory: Path) -> dict:
    directory.mkdir(mode=0o700)
    clock = [0]
    base = int(datetime(2026, 10, 5, 0, 20, 8, tzinfo=timezone.utc).timestamp()) if scenario == "post-open-normal-completion" else int(datetime(2026, 10, 5, 0, 9, 57, tzinfo=timezone.utc).timestamp()) if scenario == "monitor-close-normal-completion" else BASE
    startup_case = "startup" in scenario
    if startup_case:
        base = int(datetime(2026, 10, 5, 0, 20, 0, tzinfo=timezone.utc).timestamp()) if scenario == "post-open-startup" else int(datetime(2026, 10, 5, 0, 9, 57, tzinfo=timezone.utc).timestamp()) if scenario == "monitor-close-startup" else int(datetime(2026, 12, 10, 7, 2, 0, tzinfo=timezone.utc).timestamp()) if scenario == "winter-monitor-startup" else int(datetime(2026, 10, 5, 0, 2, 0, tzinfo=timezone.utc).timestamp())
    probes = []
    phases = {"monitor": False}
    checks = {key: 0 for key in ("health", "capability", "source", "configuration", "dependency", "continuity")}
    front = directory / "index.php"
    front.write_bytes(b"local original front controller\n")
    front.chmod(0o644)
    checkpoint = {"inode": 1, "bytes": 0, "anchor": {"sha256": deploy.sha256_bytes(b"")}}
    stamp = lambda epoch: datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def runtime(_helper, _directory, name):
        now = base + clock[0] // 10**9
        payload = source_rehearsal.runtime_snapshot()
        payload["generated_at_utc"] = stamp(now)
        start = base - 8 if scenario == "post-open-normal-completion" else base + 3 + 1800 if scenario == "monitor-close-normal-completion" else base + 18 * 60 - 8
        if startup_case:
            start = base if scenario == "post-open-startup" else base + 3 + 1800 if scenario == "monitor-close-startup" else base + 18 * 60
        observed_active = (phases["monitor"] or scenario in {"post-open-normal-completion", "post-open-startup"}) and start <= now < start + 16
        if scenario == "stuck-task" and phases["monitor"] and now >= start:
            observed_active = True
        if scenario == "startup-never-progress" and phases["monitor"] and now >= start:
            observed_active = True
        if scenario == "startup-orphaned" and now >= start + 8:
            observed_active = False
        success = start + 12 if now >= start + 16 and observed_active is False else None
        payload["scheduler"] = source_rehearsal.scheduler_snapshot(stamp(now), active=observed_active,
            started_at=stamp(start) if observed_active else None,
            success_at=stamp(success) if success is not None and now < start + 600 else None)
        if startup_case and observed_active:
            progress_at = start + (11 if scenario == "startup-late-progress" else 5)
            awaiting = now < progress_at or scenario == "startup-never-progress"
            payload["scheduler"] = source_rehearsal.scheduler_snapshot(stamp(now), active=True,
                started_at=stamp(start), startup=awaiting, attempt_at=None if awaiting else stamp(progress_at))
            if now >= start + 12 and scenario not in {"startup-never-progress", "startup-late-progress"}:
                payload["scheduler"]["refresh_status"].update(last_attempt_at=stamp(start + 12), last_success_at=stamp(start + 12))
        if scenario == "startup-orphaned" and phases["monitor"] and now >= start + 8:
            payload["scheduler"]["refresh_status"].update(last_attempt_at=stamp(start - 588), last_success_at=stamp(start - 588))
        if scenario == "startup-failure" and phases["monitor"] and now >= start + 5:
            payload["scheduler"]["refresh_status"].update(state="error", last_error_present=True)
        if phases["monitor"] and now >= start:
            scheduler = payload["scheduler"]
            if scenario == "unexpected-mutex": scheduler["overlap_mutexes"][0]["mutex_name_sha256"] = "0" * 64
            if scenario == "task-failure": scheduler["refresh_status"].update(state="error", last_error_present=True)
            if scenario == "orphaned-completion" and now >= start + 16:
                scheduler["refresh_status"].update(last_attempt_at=stamp(start - 600 + 12), last_success_at=stamp(start - 600 + 12))
            if scenario == "malformed-status": scheduler["refresh_status"]["last_attempt_at"] = "malformed"
            if scenario == "unscheduled-task" and observed_active: scheduler["overlap_mutexes"][0]["expires_at_unix"] += 20
            if scenario == "queue-failure": payload["queue"]["counts"]["jobs"] = 1
            if scenario == "schema-drift": payload["schema"]["sha256"] = "0" * 64
        probes.append({"name": name, "generated_at_utc": payload["generated_at_utc"], "active": observed_active})
        return payload, {"local_double": True, "name": name}

    def check(key, result):
        checks[key] += 1
        now = base + clock[0] // 10**9
        bad = {"health": "health-failure", "source": "source-drift", "dependency": "dependency-drift", "continuity": "log-continuity-loss"}.get(key)
        if phases["monitor"] and now >= base + 3 + 18 * 60 and scenario == bad:
            raise deploy.DeploymentError(f"Rehearsed {key} failure")
        return copy.deepcopy(result)

    patches = [
        mock.patch.object(deploy, "FRONT_CONTROLLER", front),
        mock.patch.object(deploy, "EXPECTED_FRONT_CONTROLLER_SHA256", deploy.sha256_file(front)),
        mock.patch.object(deploy, "LARAVEL_MAINTENANCE_FILE", directory / "down"),
        mock.patch.object(deploy, "runtime_probe", side_effect=runtime),
        mock.patch.object(deploy, "health_snapshot", side_effect=lambda: check("health", {"status": "pass"})),
        mock.patch.object(deploy, "capability_probe", side_effect=lambda *_: check("capability", {"disabled": True})),
        mock.patch.object(deploy, "full_source_identity", side_effect=lambda **_: check("source", {"sha256": deploy.source_controls.frozen_envelope()["target_source"]["sha256"]})),
        mock.patch.object(deploy, "live_manifest_snapshot", return_value={"sha256": deploy.EXPECTED_TARGET_SOURCE_CAS_SHA256}),
        mock.patch.object(deploy.source_controls, "require_configuration_identity", side_effect=lambda: check("configuration", {"frozen": True})),
        mock.patch.object(deploy, "dependency_identity", side_effect=lambda: check("dependency", {"frozen": True})),
        mock.patch.object(deploy, "verify_log_continuity", side_effect=lambda value: check("continuity", value)),
        mock.patch.object(deploy.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + round(seconds * 10**9))),
        mock.patch.object(deploy.time, "time", side_effect=lambda: base + clock[0] / 10**9),
        mock.patch.object(deploy.time, "monotonic_ns", side_effect=lambda: clock[0]),
    ]
    from contextlib import ExitStack
    result = None
    failure = None
    with ExitStack() as stack:
        for patch in patches: stack.enter_context(patch)
        # Run the actual post-open validator first. Reset neither time nor state.
        post_open = deploy.post_open_health(Path("local-helper.php"), directory, "post-open")
        phases["monitor"] = True
        try:
            result = deploy.monitor_production(Path("local-helper.php"), [], directory, checkpoint)
        except deploy.DeploymentError as error:
            failure = {"type": type(error).__name__, "reason": str(error)}
    successful = scenario in SUCCESSFUL
    if successful != (result is not None):
        raise RuntimeError(f"Unexpected rehearsal outcome for {scenario}: {failure}")
    observations = [json.loads(path.read_text()) for path in sorted(directory.glob("scheduler-observation-*.json"))]
    transitions = [value for row in observations for value in row["transitions"]]
    if successful:
        assert result["samples"] == 30 and result["minimum_elapsed_seconds"] == 1800
        assert "acquired" in transitions and "completed" in transitions and "released" in transitions
        assert clock[0] >= 1800 * 10**9
        assert observations[-1]["active"] is False
        if startup_case:
            assert "startup" in transitions and "startup_progress_confirmed" in transitions
            startup_observations = [row for row in observations if row["pending"] and row["pending"]["stage"] == "startup"]
            assert len(startup_observations) >= 2
            assert any((later["monotonic_ns"] - earlier["monotonic_ns"]) == 10**9 for earlier, later in zip(startup_observations, startup_observations[1:]))
    return {"status": "pass", "scenario": scenario, "expected_failure": not successful,
        "failure": failure, "post_open_verified": bool(post_open["runtime_verification"]),
        "samples_completed": result["samples"] if result else len(json.loads((directory / "monitoring-samples.json").read_text())) if (directory / "monitoring-samples.json").exists() else 0,
        "elapsed_virtual_seconds": clock[0] / 10**9, "clock_model": "deterministic monotonic and UTC clocks; no real monitor or production execution",
        "policy_sha256": deploy.scheduler_controls.POLICY_SHA256, "transitions": transitions,
        "checks": checks, "probes": probes, "scheduler_observations": observations,
        "scheduler_state_sha256": deploy.sha256_file(directory / "scheduler-activity-state.json"),
        "raw_log_or_customer_data": False, "production_accessed": False}


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix="buydtf-scheduler-rehearsal-") as temporary:
        for name in SCENARIOS:
            results[name] = run_case(name, Path(temporary) / name)
    receipt = {"status": "pass", "artifact": "buy-dtf-source-scheduler-rehearsal-v1",
        "scenario_count": len(results), "runner_sha256": deploy.sha256_file(Path(deploy.__file__)),
        "control_sha256": deploy.sha256_file(Path(deploy.scheduler_controls.__file__)),
        "policy": deploy.scheduler_controls.POLICY, "scenarios": results,
        "production_accessed": False, "accounting_tasks_executed": False}
    deploy.atomic_json(output / "scheduler-rehearsal-receipt.json", receipt)
    return {"status": "pass", "scenarios": len(results), "receipt_sha256": deploy.sha256_file(output / "scheduler-rehearsal-receipt.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
