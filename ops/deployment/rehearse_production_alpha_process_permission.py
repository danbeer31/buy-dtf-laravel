#!/usr/bin/env python3
"""Actual Linux UID 33 /proc denial and full disposable rollback/reopening.

Root creates only isolated processes/files. UID 1000 executes the real runner's
rollback and post-open path, real UID 33 FPM observes the foreign process, and
real nginx/FPM execute the reviewed gate with full seven-second waits. Database,
runtime-envelope and maintenance commands use explicit isolated doubles. The
HTTP original is a sentinel controller loading the retained Laravel 12.69.1
autoload; no application boot, customer data, accounting task or production
access occurs. Raw local HTTP evidence remains private.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import time
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rehearse_production_alpha_transparency as source
import rehearse_laravel_dependency_opcache as web

deploy = source.deploy
controls = deploy.scheduler_controls
gate = deploy.source_controls.dependency_gate
ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("legacy-unreadable-foreign", "corrected-foreign-rollback", "corrected-foreign-reopening-replay",
             "legacy-exit-before-fpm-read", "corrected-exit-before-fpm-read",
             "corrected-scoped-work", "observer-unavailable", "observer-response-mismatch")
EXIT_SCENARIOS = {"legacy-exit-before-fpm-read", "corrected-exit-before-fpm-read"}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def send_fixture_message(channel, value):
    channel.sendall(json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n")


def receive_fixture_message(channel):
    data = b""
    while not data.endswith(b"\n"):
        chunk = channel.recv(4096 - len(data))
        require(chunk and len(data) + len(chunk) < 4096, "Malformed bounded fixture IPC.")
        data += chunk
    return json.loads(data)


def owned(path, uid=1000, gid=1000, mode=0o700):
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def actor(request_path: Path):
    require(os.geteuid() == 1000, "Runner rehearsal must use actual UID 1000.")
    request = json.loads(request_path.read_text())
    app, front, state_dir = map(Path, (request["application"], request["front"], request["state_directory"]))
    rows = deploy.parse_manifest(source.MANIFEST_PATH)
    state_path = state_dir / "state.json"
    frozen = deploy.source_controls.frozen_envelope()["fpm_opcache"]
    original_sha = deploy.sha256_file(front)
    helper = Path(request["helper"])
    scope_helper = Path(request["scope_helper"])
    scope_socket = Path(request["socket"])
    scenario = request["scenario"]
    pid = request["foreign_pid"]
    pid_entry = Path("/proc") / str(pid)
    before_pid = controls._process_identity(pid_entry)
    denial = {}
    for name in ("cwd", "exe"):
        try:
            os.readlink(pid_entry / name)
            raise RuntimeError("UID 1000 unexpectedly read UID 33 process scope.")
        except PermissionError as error:
            denial[name] = {"errno": error.errno, "reader_uid": os.geteuid(), "target_uid": 33}
    observation_reader = controls.FpmProcessScopeReader(scope_helper, scope_socket,
        expected_php_version=request["local_php_version"])
    positive = observation_reader(before_pid)
    require(positive["identity"] == before_pid and positive["observer_uid"] == 33,
            "FPM did not prove target scope with actual UID 33.")
    probes = []
    commands = []
    exit_events = []

    def fresh():
        return source.runtime_snapshot()

    def runtime(_helper, directory, name):
        payload = fresh()
        path = directory / f"{name}.fixture.json"
        deploy.atomic_json(path, payload)
        return payload, {"scope": "isolated-database-runtime-double", "path": str(path), "sha256": deploy.sha256_file(path)}

    def probe(route, directory=state_dir, label="probe"):
        value = web.http_probe(port=request["origin_port"] if route == web.ORIGIN_ROUTE else request["public_port"],
            route=route, nonce=secrets.token_hex(12), evidence_directory=directory,
            label=f"{label}-{time.monotonic_ns()}")
        probes.append(web.receipt_probe(value))
        return value

    def gate_response(route, directory=state_dir, label="gate"):
        value = probe(route, directory, label)
        web.require_gate(value)
        return {"status": "pass", **web.receipt_probe(value)}

    def health():
        receipts = []
        for route in (web.ORIGIN_ROUTE, web.PUBLIC_ROUTE):
            value = probe(route, label="health")
            payload = web.require_original(value)
            require(payload["laravel_version"] == "12.69.1", "Retained Laravel changed.")
            require(not deploy.LARAVEL_MAINTENANCE_FILE.exists(), "Local maintenance marker remained active.")
            receipts.append(web.receipt_probe(value))
        return {"status": "pass", "routes": receipts, "actual_fpm_php": request["local_php_version"],
                "laravel_version": "12.69.1", "http_fixture_only": True}

    def capability(*_args):
        return {"status": 200, "receiver_enabled": False, "job_label_enabled": False,
            "retention_enabled": False, "artwork_hosts": [], "isolated_fixture": True}

    def down(_directory, name):
        commands.append(["maintenance-double", "down", name])
        deploy.atomic_write(deploy.LARAVEL_MAINTENANCE_FILE, b"isolated maintenance\n", 0o600)
        return {"status": "pass", "isolated_maintenance_double": True}

    def up(_directory, name):
        commands.append(["maintenance-double", "up", name])
        deploy.LARAVEL_MAINTENANCE_FILE.unlink(missing_ok=True)
        return {"status": "pass", "isolated_maintenance_double": True}

    real_reader_class = controls.FpmProcessScopeReader
    def exit_before_fpm_read(identity):
        # Test-only IPC asks the fixture's parent to let its own child finish
        # normally and reap it. The deployment/observer sends no process signal.
        with socket.socket(fileno=request["exit_control_fd"]) as channel:
            channel.settimeout(10)
            send_fixture_message(channel, {"action": "finish_owned_fixture", "identity": identity})
            reply = receive_fixture_message(channel)
        require(reply["pid"] == pid and reply["returncode"] == 0 and reply["reaped"] is True,
                "Fixture did not disappear before the real FPM read.")
        real_run = subprocess.run
        def record_transport(argv, **kwargs):
            value = real_run(argv, **kwargs)
            require(argv[:2] == ["/usr/bin/cgi-fcgi", "-bind"], "Unexpected exit-race transport.")
            raw = value.stdout.replace(b"\r\n", b"\n")
            headers, body = raw.split(b"\n\n", 1)
            rejected = json.loads(body)
            require(b"Status: 503 Service Unavailable" in headers and rejected["status"] == "rejected"
                and rejected["reason"] == "Process scope evidence unavailable or malformed.",
                "The real FPM helper did not reject the already-gone target.")
            path = state_dir / "exit-race-fpm-response.private"
            deploy.atomic_write(path, value.stdout, 0o600)
            exit_events.append({"identity": identity, "fpm_status": 503,
                "fpm_response_sha256": deploy.sha256_file(path), "fixture_completion": reply,
                "response_received_monotonic_ns": time.monotonic_ns()})
            return value
        try:
            with mock.patch.object(controls.subprocess, "run", side_effect=record_transport):
                observation_reader(identity)
        except controls.ProcessScopeProbeRejected as error:
            if scenario == "legacy-exit-before-fpm-read":
                raise controls.SchedulerError("Pre-correction rejected response has no fresh disappearance check.") from error
            raise
        raise RuntimeError("Exited target unexpectedly returned successful FPM scope evidence.")

    def reader_factory(*_args, **_kwargs):
        if scenario == "legacy-unreadable-foreign":
            # V5 behavior: permission denial has no UID 33 scope fallback.
            return lambda _: (_ for _ in ()).throw(controls.SchedulerError("legacy unreadable /proc cwd"))
        if scenario == "observer-unavailable":
            return real_reader_class(scope_helper, scope_socket.with_name("absent-fpm.sock"), expected_php_version=request["local_php_version"])
        if scenario == "observer-response-mismatch":
            return lambda identity: {**positive, "identity": {**identity, "start_ticks": identity["start_ticks"] + 1}}
        if scenario in EXIT_SCENARIOS:
            return exit_before_fpm_read
        return observation_reader

    baseline = fresh()
    state = {"version": 1, "target_commit": deploy.TARGET_COMMIT, "status": "fixture_post_mutation_failure",
        "source_install_started": False, "source_install_complete": False, "rollback_complete": False,
        "state_directory": str(state_dir), "front_controller_transitions": [], "created_directories": [],
        "release_receipt_sha256": "b" * 64, "fpm_opcache": frozen,
        "scheduler_policy_sha256": controls.POLICY_SHA256,
        "scheduler_identity_sha256": controls.identity_sha256(baseline), "installed_schema_baseline": baseline}
    patches = {
        "APP_ROOT": app, "FRONT_CONTROLLER": front, "FPM_SOCKET": scope_socket,
        "ROLLBACK_ROOT": state_dir.parent, "LARAVEL_MAINTENANCE_FILE": app / "storage/framework/down",
        "DEPLOYMENT_LOCK": app / "storage/framework/rehearsal.lock",
        "EXPECTED_FRONT_CONTROLLER_SHA256": original_sha,
        "runtime_probe": runtime, "health_snapshot": health, "capability_probe": capability,
        "enter_laravel_maintenance": down, "leave_laravel_maintenance": up,
        "dependency_identity": lambda: {"composer_lock_sha256": deploy.EXPECTED_COMPOSER_LOCK_SHA256,
            "vendor_manifest_sha256": deploy.EXPECTED_VENDOR_MANIFEST_SHA256, "isolated_read_only_baseline_double": True},
        "gate_origin_probe": lambda directory, name: gate_response(web.ORIGIN_ROUTE, directory, name),
        "gate_public_probe": lambda directory, name: gate_response(web.PUBLIC_ROUTE, directory, name),
    }
    with ExitStack() as stack:
        for name, value in patches.items():
            stack.enter_context(mock.patch.object(deploy, name, value))
        stack.enter_context(mock.patch.object(deploy.source_controls, "APP_ROOT", app))
        stack.enter_context(mock.patch.object(deploy.source_controls, "FRONT_CONTROLLER", front))
        stack.enter_context(mock.patch.object(deploy.source_controls, "EXPECTED_FRONT_CONTROLLER_SHA256", original_sha))
        stack.enter_context(mock.patch.object(deploy.source_controls, "probe_fpm_opcache", return_value=frozen))
        stack.enter_context(mock.patch.object(deploy.source_controls, "require_configuration_identity",
            return_value=deploy.source_controls.frozen_envelope()["configuration_sha256"]))
        stack.enter_context(mock.patch.object(controls, "FpmProcessScopeReader", side_effect=reader_factory))
        # Exact original backups are made before local source mutation.
        backup, absent = deploy.source_backup(rows, state_dir)
        state["source_backup_receipt"] = backup["path"]
        state["additions_absent_before"] = absent
        original_backup = state_dir / "front-controller-before.php"
        deploy.atomic_copy(front, original_backup)
        state["front_controller_backup"] = str(original_backup)
        state["front_controller_backup_sha256"] = original_sha
        state["front_controller_metadata"] = deploy.path_metadata(front)
        deploy.write_state(state_path, state)
        pre_health = health()
        deploy.source_controls.record_fpm_opcache_before_mutation(state, state_path)
        state["source_install_started"] = True
        deploy.write_state(state_path, state)
        deploy.install_runtime_files(Path(request["candidate"]), rows, state_dir, state=state, state_path=state_path)
        state["source_install_complete"] = True
        deploy.write_state(state_path, state)
        failure = None
        result = None
        try:
            if scenario == "corrected-foreign-reopening-replay":
                # Invoke the actual reviewed recovery entry point locally only,
                # with receipt validation isolated to this disposable fixture.
                receipt_path = Path(request["release_receipt"])
                state["release_receipt"] = str(receipt_path)
                deploy.write_state(state_path, state)
                with mock.patch.object(deploy, "validate_release_receipt", return_value=(
                        {"inputs": {"helper": {"path": str(helper)}}}, receipt_path.parent, rows)):
                    recovery_receipt = deploy.recover_state(state_path=state_path, approval_token=deploy.RECOVERY_APPROVAL_TOKEN)
                    result = json.loads(recovery_receipt.read_text())
            else:
                result = deploy.rollback_operation(state_path=state_path, state=state, rows=rows, helper=helper, automatic=True)
        except deploy.DeploymentError as error:
            failure = {"type": type(error).__name__, "message_sha256": hashlib.sha256(str(error).encode()).hexdigest()}
        final_state = json.loads(state_path.read_text())
        source_after = deploy.live_manifest_snapshot(rows, target=False)
        complete_source_after = deploy.full_source_identity(target=False)
        require(source_after["sha256"] == deploy.EXPECTED_PRE_SOURCE_CAS_SHA256, "Original scoped source was not restored.")
        expected_open = scenario in {"corrected-foreign-rollback", "corrected-foreign-reopening-replay", "corrected-exit-before-fpm-read"}
        require((failure is None) == expected_open, "Rollback outcome differs from scenario.")
        if expected_open:
            require(final_state["status"] == "rolled_back" and final_state["rollback_complete"] is True,
                "Complete rollback was not durably recorded.")
            final_health = health()
            require(deploy.sha256_file(front) == original_sha, "Exact original front was not restored.")
            require(deploy.path_metadata(front) == gate.reviewed_front_controller_metadata(), "Original metadata changed.")
            process_receipts = [json.loads(p.read_text())["process_envelope"] for p in sorted(state_dir.glob("scheduler-observation-*.json"))]
            if scenario == "corrected-exit-before-fpm-read":
                exits = [item for row in process_receipts for item in row["confirmed_process_exits"]]
                require(len(exits) == 1 and exits[0]["identity"] == before_pid
                    and exits[0]["trigger"] == "validated_fpm_target_unavailable_rejection"
                    and exits[0]["response_sha256"] == exit_events[0]["fpm_response_sha256"],
                    "Automatic rollback did not record fresh proof after the rejected FPM response.")
                require(all(check["monotonic_ns"] >= exit_events[0]["response_received_monotonic_ns"]
                    for check in exits[0]["checks"]), "Disappearance checks were not fresh after rejection.")
                require(len(process_receipts) >= 4, "Complete rollback and reopening validation did not run.")
            else:
                require(process_receipts and all(any(item["pid"] == pid and item["scope_source"] == "read_only_fpm_uid_33"
                    for item in row["verified_outside_application"]) for row in process_receipts), "Rollback and reopening did not use the real UID 33 scope proof.")
        else:
            require(final_state["status"] == "rollback_failed_site_gated", "Failure did not retain durable containment.")
            require(deploy.sha256_file(front) == deploy.EXPECTED_GATE_SHA256, "Failure did not retain exact reviewed gate.")
            final_health = gate_response(web.PUBLIC_ROUTE, label="final-contained")
            process_receipts = []
        if scenario in EXIT_SCENARIOS:
            require(len(exit_events) == 1 and not pid_entry.exists(), "Exit-race target was not normally completed and reaped.")
        else:
            require(controls._process_identity(pid_entry) == before_pid, "Foreign process was altered or terminated.")
        transitions = [json.loads(p.read_text()) for p in state_dir.glob("*opcache*wait*.json")]
        # Transition receipts carry real monotonic elapsed time. No clock doubles.
        wait_receipts = []
        for path in state_dir.glob("*.json"):
            item = json.loads(path.read_text())
            if isinstance(item, dict) and item.get("artifact") == "buy-dtf-front-controller-opcache-revalidation-wait-v1":
                wait_receipts.append(item)
        require(wait_receipts and all(item["elapsed_monotonic_ns"] >= 7_000_000_000 for item in wait_receipts),
            "Full seven-second monotonic gate waits were not recorded.")
        portable = {"scenario": scenario, "status": "pass", "actor_uid": 1000, "target_uid": 33,
            "kernel_permission_denials": denial, "fpm_scope_proven": True,
            "foreign_process_unchanged": scenario not in EXIT_SCENARIOS,
            "owned_fixture_completed_normally": scenario in EXIT_SCENARIOS, "exit_race_events": exit_events,
            "confirmed_process_exits": [item for row in process_receipts for item in row["confirmed_process_exits"]],
            "final_state_status": final_state["status"], "rollback_complete": final_state.get("rollback_complete", False),
            "source_restored_sha256": source_after["sha256"], "front_controller_sha256": deploy.sha256_file(front),
            "complete_original_source": complete_source_after,
            "front_controller_metadata": deploy.path_metadata(front), "maintenance_active": deploy.LARAVEL_MAINTENANCE_FILE.exists(),
            "failure": failure, "http_probes": probes, "process_scope_observations": len(process_receipts),
            "full_monotonic_wait_receipts": wait_receipts,
            "state_sha256": deploy.sha256_file(state_path), "database_and_runtime_envelope_simulated": True,
            "maintenance_commands_simulated": True, "local_php_fpm_version": request["local_php_version"],
            "production_php_version_unchanged": "8.2.30", "actual_autoload_laravel": "12.69.1",
            "production_accessed": False, "raw_http_evidence_private": True}
        deploy.atomic_json(state_dir / "portable-result.json", portable)


def run(private_parent: Path, output: Path, vendor: Path, original_source: Path):
    require(os.geteuid() == 0, "Disposable www-data/FPM fixture requires local Linux root.")
    os.umask(0o077)
    rows = deploy.parse_manifest(source.MANIFEST_PATH)
    complete_original = deploy.source_controls.require_source_identity(original_source, target=False)
    baseline, baseline_evidence = source.resolve_baseline_sources(list(source.DEFAULT_BASELINE_ROOTS), rows)
    private = Path(__import__('tempfile').mkdtemp(prefix="bdtf-proc-", dir=private_parent))
    os.chmod(private, 0o711)
    results = []
    local_version = subprocess.check_output(["/usr/bin/php", "-r", "echo PHP_VERSION;"], text=True).strip()
    require((vendor / "vendor/autoload.php").is_file(), "Retained local Laravel vendor unavailable.")
    for scenario in SCENARIOS:
        item = source.build_fixture(private, scenario, rows, baseline)
        root, app, front = item["root"], item["application"], item["front"]
        # Rehearse the complete frozen 326-file source, not just the changed paths.
        for relative in deploy.source_controls.SOURCE_ROOTS:
            shutil.copytree(original_source / relative, app / relative, dirs_exist_ok=True)
        for relative in deploy.source_controls.SOURCE_TOP_LEVEL_FILES:
            shutil.copyfile(original_source / relative, app / relative)
        for path in sorted(root.rglob("*")):
            if not path.is_symlink():
                os.chown(path, 1000, 1000)
                # The FPM sentinel does not boot this application. Keep copied
                # runtime configuration/source private to the local actor.
                if path != app and path.is_relative_to(app) and not path.is_relative_to(app / "public"):
                    os.chmod(path, 0o700 if path.is_dir() else 0o600)
        os.chown(root, 1000, 1000)
        state_dir = item["rollback"] / "case"
        state_dir.mkdir(mode=0o700)
        owned(state_dir)
        stack_dir = root / "stack"
        stack_dir.mkdir(mode=0o711)
        os.chmod(stack_dir, 0o711)
        socket_path = stack_dir / "fpm.sock"
        origin_port, public_port = port(), port()
        fpm_config = web.render_fpm_configuration(root=stack_dir, socket_path=socket_path,
            pid_path=stack_dir / "fpm.pid", error_log=stack_dir / "fpm-error.private.log")
        fpm_config = fpm_config.replace("listen.owner = www-data", "listen.owner = " + pwd.getpwuid(1000).pw_name)
        (stack_dir / "fpm.conf").write_text(fpm_config)
        nginx_config = web.render_nginx_configuration(root=stack_dir, public_root=app / "public", socket_path=socket_path,
            origin_port=origin_port, public_port=public_port, pid_path=stack_dir / "nginx.pid",
            error_log=stack_dir / "nginx-error.private.log", access_log=stack_dir / "nginx-access.private.log")
        (stack_dir / "nginx.conf").write_text("user www-data www-data;\n" + nginx_config)
        for path in (stack_dir / "nginx-client-temp", stack_dir / "nginx-proxy-temp"):
            path.mkdir(mode=0o700)
            owned(path, 33, 33)
        controller = web.original_front_controller().replace(b"$directives = [", (
            "require " + json.dumps(str(vendor / "vendor/autoload.php")) + ";\n$directives = [").encode())
        controller = controller.replace(b"'sapi' => PHP_SAPI,", b"'laravel_version' => \\Illuminate\\Foundation\\Application::VERSION,\n    'sapi' => PHP_SAPI,")
        front.write_bytes(controller)
        owned(front, mode=0o644)
        foreign_cwd = app if scenario == "corrected-scoped-work" else root / "unrelated-app"
        foreign_cwd.mkdir(mode=0o700, exist_ok=True)
        dummy = ['<?php echo "READY\\n"; fflush(STDOUT); fgets(STDIN);\n']
        if foreign_cwd != app:
            fake_artisan = foreign_cwd / "artisan"
            require(not fake_artisan.exists(), "Fixture would overwrite an Artisan file.")
            fake_artisan.write_text(dummy[0])
            owned(foreign_cwd, 33, 33)
            owned(fake_artisan, 33, 33, 0o600)
        scope_helper = root / "production_alpha_process_scope_probe.php"
        shutil.copyfile(ROOT / "ops/deployment/production_alpha_process_scope_probe.php", scope_helper)
        owned(scope_helper, mode=0o600)
        nginx = fpm = foreign = None
        parent_channel = actor_channel = None
        try:
            fpm = web._start_process(["/usr/sbin/php-fpm8.3", "--nodaemonize", "--fpm-config", str(stack_dir / "fpm.conf")], stack_dir / "fpm.private.log")
            web._wait_for_socket(socket_path, fpm)
            nginx = web._start_process(["/usr/sbin/nginx", "-c", str(stack_dir / "nginx.conf"), "-p", str(stack_dir), "-g", "daemon off;"], stack_dir / "nginx.private.log")
            arguments = ["/usr/bin/php8.3", "artisan", "fixture:idle"] if foreign_cwd != app else [
                "/usr/bin/php8.3", "-r", dummy[0].removeprefix("<?php "), "artisan", "fixture:idle"]
            foreign = subprocess.Popen(["/usr/bin/setpriv", "--reuid=33", "--regid=33", "--clear-groups", *arguments], cwd=foreign_cwd,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            require(foreign.stdout.readline() == b"READY\n", "UID 33 dummy process did not start.")
            time.sleep(0.25)
            request = {"scenario": scenario, "application": str(app), "front": str(front),
                "state_directory": str(state_dir), "candidate": str(item["candidate"]),
                "helper": str(item["helper"]), "scope_helper": str(scope_helper), "socket": str(socket_path),
                "release_receipt": str(item["receipt_path"]), "origin_port": origin_port,
                "public_port": public_port, "foreign_pid": foreign.pid, "local_php_version": local_version}
            if scenario in EXIT_SCENARIOS:
                parent_channel, actor_channel = socket.socketpair()
                parent_channel.settimeout(100)
                request["exit_control_fd"] = actor_channel.fileno()
            request_path = root / "actor-request.private.json"
            request_path.write_bytes(deploy.canonical_bytes(request))
            owned(request_path, mode=0o600)
            command = ["/usr/bin/setpriv", "--reuid=1000", "--regid=1000", "--clear-groups", "/usr/bin/python3",
                str(Path(__file__).resolve()), "--actor-request", str(request_path)]
            if scenario in EXIT_SCENARIOS:
                actor_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    pass_fds=(actor_channel.fileno(),))
                actor_channel.close()
                actor_channel = None
                message = receive_fixture_message(parent_channel)
                require(message["action"] == "finish_owned_fixture" and message["identity"] == controls._process_identity(Path("/proc") / str(foreign.pid)),
                    "Exit-race IPC did not bind the exact owned fixture.")
                foreign.stdin.write(b"finish fixture normally\n")
                foreign.stdin.flush()
                foreign.communicate(timeout=10)
                reply = {"pid": foreign.pid, "returncode": foreign.returncode, "reaped": True,
                    "completed_monotonic_ns": time.monotonic_ns(), "normal_fixture_ipc_only": True}
                require(foreign.returncode == 0 and not (Path("/proc") / str(foreign.pid)).exists(),
                    "Owned fixture did not disappear before the FPM request.")
                send_fixture_message(parent_channel, reply)
                stdout, stderr = actor_process.communicate(timeout=100)
                completed = subprocess.CompletedProcess(command, actor_process.returncode, stdout, stderr)
            else:
                completed = subprocess.run(command, capture_output=True, timeout=100)
            (root / "actor.stdout.private").write_bytes(completed.stdout)
            (root / "actor.stderr.private").write_bytes(completed.stderr)
            if completed.returncode:
                # Error text is local fixture only, no production/customer information.
                raise RuntimeError(f"Local actor {scenario} failed: {completed.stderr.decode(errors='replace')[-2500:]}")
            results.append(json.loads((state_dir / "portable-result.json").read_text()))
            require(foreign.returncode == 0 if scenario in EXIT_SCENARIOS else foreign.poll() is None,
                "Foreign fixture lifecycle differs from scenario.")
        finally:
            for channel in (parent_channel, actor_channel):
                if channel is not None:
                    channel.close()
            if foreign is not None and foreign.poll() is None:
                foreign.stdin.write(b"finish fixture\n")
                foreign.stdin.flush()
                foreign.communicate(timeout=10)
            web._stop_process(nginx)
            web._stop_process(fpm)
    inventory = []
    for path in sorted(private.rglob("*")):
        if path.is_file() and not path.is_symlink():
            inventory.append({"path": str(path.relative_to(private)), "sha256": deploy.sha256_file(path),
                "bytes": path.stat().st_size, "mode": stat.S_IMODE(path.stat().st_mode)})
    require(all(item["mode"] == 0o600 for item in inventory if item["path"].endswith(".headers.raw")),
        "Raw HTTP headers escaped private mode 0600.")
    manifest = private / "PRIVATE_MANIFEST.json"
    manifest.write_bytes(deploy.canonical_bytes({"entries": inventory}))
    report = {"artifact": "buy-dtf-process-permission-linux-rollback-rehearsal-v1", "status": "pass",
        "scenario_count": len(results), "scenarios": results, "baseline_source_records": baseline_evidence,
        "complete_original_source_before": complete_original,
        "runner_sha256": deploy.sha256_file(ROOT / "ops/deployment/production_alpha_transparency_deploy.py"),
        "scheduler_guard_sha256": deploy.sha256_file(ROOT / "ops/deployment/production_alpha_scheduler_guard.py"),
        "process_scope_probe_sha256": deploy.sha256_file(ROOT / "ops/deployment/production_alpha_process_scope_probe.php"),
        "rehearsal_sha256": deploy.sha256_file(Path(__file__).resolve()),
        "private_manifest_sha256": deploy.sha256_file(manifest), "private_evidence_entries": len(inventory),
        "local_php_fpm_version": local_version, "production_accessed": False,
        "no_existing_process_or_permission_changes": True, "loopback_only": True,
        "raw_http_headers_mode": "0600", "copied_runtime_configuration_private": True,
        "limits": ["Database, production runtime envelope and maintenance commands are isolated doubles.",
                   "Local FPM is PHP " + local_version + "; production PHP 8.2.30 is not accessed.",
                   "HTTP fixture loads Laravel 12.69.1 but does not boot the customer application."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(deploy.canonical_bytes(report))
    print(json.dumps({"status": "pass", "scenario_count": len(results), "private_path": str(private),
        "portable_sha256": deploy.sha256_file(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-request", type=Path)
    parser.add_argument("--private-parent", type=Path, default=Path("/tmp"))
    parser.add_argument("--portable-output", type=Path)
    parser.add_argument("--vendor-root", type=Path, default=Path("/tmp/buydtf-alpha-v3-build-a-20261004-r3"))
    parser.add_argument("--original-source-root", type=Path, default=Path("/tmp/buydtf-remember-v4-build-a/shadow"))
    args = parser.parse_args()
    if args.actor_request:
        actor(args.actor_request)
    else:
        require(args.portable_output is not None, "A local portable receipt path is required.")
        run(args.private_parent, args.portable_output, args.vendor_root, args.original_source_root)
