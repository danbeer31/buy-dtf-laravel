#!/usr/bin/env python3
"""Reproduce front-controller OPcache staleness through disposable nginx/FPM.

This is a local rehearsal only.  It starts foreground nginx and PHP-FPM
processes with configuration, sockets, ports, logs, and a webroot rooted in a
new temporary directory.  It never invokes a service manager and never sends
traffic anywhere except 127.0.0.1.
"""

from __future__ import annotations

import argparse
from contextlib import suppress
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import grp
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable


sys.path.insert(0, str(Path(__file__).resolve().parent))
import laravel_dependency_gate as gate  # noqa: E402


ARTIFACT = "buy-dtf-laravel-dependency-opcache-rehearsal-v1"
ORIGINAL_SENTINEL = "BUYDTF_OPCACHE_REHEARSAL_ORIGINAL"
ORIGIN_ROUTE = "local_origin_nginx_fpm"
PUBLIC_ROUTE = "local_public_nginx_proxy"
ROUTE_HEADER = "X-BuyDTF-Opcache-Rehearsal-Route"
NONCE_HEADER = "X-BuyDTF-Opcache-Rehearsal-Nonce"
REVALIDATE_FREQUENCY_SECONDS = 2
FILE_UPDATE_PROTECTION_SECONDS = 2
VALIDATION_CLOCK_CONDITIONING_SECONDS = REVALIDATE_FREQUENCY_SECONDS + 1
EXPECTED_FPM_SAPI = "fpm-fcgi"
TEMPORARY_PREFIX = "buy-dtf-opcache-rehearsal-"
HTTP_TIMEOUT_SECONDS = 5
PROCESS_START_TIMEOUT_SECONDS = 15


class RehearsalError(RuntimeError):
    """The isolated OPcache rehearsal failed an invariant."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def utc_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RehearsalError(f"Expected a regular file: {path}")
    metadata = path.stat(follow_symlinks=False)
    return {
        "bytes": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "sha256": sha256_bytes(path.read_bytes()),
    }


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, content: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)
    fsync_directory(path.parent)


def atomic_install(
    path: Path,
    content: bytes,
    *,
    uid: int,
    gid: int,
    mode: int = 0o644,
) -> dict[str, Any]:
    before = file_identity(path)
    temporary = path.parent / f".{path.name}.opcache-{os.getpid()}-{secrets.token_hex(6)}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchown(descriptor, uid, gid)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        prepared = file_identity(temporary)
        if prepared["sha256"] != sha256_bytes(content):
            raise RehearsalError("Prepared front controller has unexpected bytes.")
        if (prepared["uid"], prepared["gid"], prepared["mode"]) != (uid, gid, mode):
            raise RehearsalError("Prepared front controller has unexpected metadata.")
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    installed = file_identity(path)
    if installed["sha256"] != sha256_bytes(content):
        raise RehearsalError("Atomic front-controller replacement has unexpected bytes.")
    if (installed["uid"], installed["gid"], installed["mode"]) != (uid, gid, mode):
        raise RehearsalError("Atomic front-controller replacement has unexpected metadata.")
    return {"before": before, "installed": installed}


def original_front_controller() -> bytes:
    directives = ",\n        ".join(
        f"'{name}' => ['raw' => (string) ini_get('{name}'), "
        f"'normalized' => {normalizer}]"
        for name, normalizer in (
            ("opcache.enable", "filter_var(ini_get('opcache.enable'), FILTER_VALIDATE_BOOLEAN)"),
            (
                "opcache.validate_timestamps",
                "filter_var(ini_get('opcache.validate_timestamps'), FILTER_VALIDATE_BOOLEAN)",
            ),
            (
                "opcache.revalidate_freq",
                "filter_var(ini_get('opcache.revalidate_freq'), FILTER_VALIDATE_INT)",
            ),
            (
                "opcache.file_update_protection",
                "filter_var(ini_get('opcache.file_update_protection'), FILTER_VALIDATE_INT)",
            ),
        )
    )
    return f"""<?php
declare(strict_types=1);

$directives = [
        {directives}
];
$configuration = opcache_get_configuration();
$configurationDirectives = is_array($configuration)
    && isset($configuration['directives'])
    && is_array($configuration['directives'])
        ? $configuration['directives']
        : [];
$selectedConfiguration = [];
foreach (array_keys($directives) as $name) {{
    $selectedConfiguration[$name] = $configurationDirectives[$name] ?? null;
}}
http_response_code(200);
header('Content-Type: application/json; charset=UTF-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
echo json_encode([
    'artifact' => 'buy-dtf-php-fpm-opcache-probe-v1',
    'sentinel' => '{ORIGINAL_SENTINEL}',
    'sapi' => PHP_SAPI,
    'php_version' => PHP_VERSION,
    'directives' => $directives,
    'opcache_configuration_directives' => $selectedConfiguration,
], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
""".encode("utf-8")


def discover_binary(explicit: Path | None, names: tuple[str, ...]) -> Path | None:
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None
    for name in names:
        value = shutil.which(name)
        if value:
            candidate = Path(value).resolve()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
    return None


def prerequisite_report(
    *,
    nginx_path: Path | None = None,
    php_fpm_path: Path | None = None,
) -> dict[str, Any]:
    nginx = discover_binary(nginx_path, ("nginx",))
    php_fpm = discover_binary(
        php_fpm_path,
        ("php-fpm8.2", "php-fpm8.3", "php-fpm"),
    )
    missing: list[str] = []
    if os.name != "posix":
        missing.append("POSIX operating system")
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        missing.append("effective UID 0")
    if nginx is None:
        missing.append("nginx executable")
    if php_fpm is None:
        missing.append("PHP-FPM executable")
    try:
        web_user = pwd.getpwuid(gate.EXPECTED_WEB_UID)
        web_group = grp.getgrgid(gate.EXPECTED_WEB_GID)
    except KeyError:
        web_user = None
        web_group = None
        missing.append(
            f"web identity UID/GID {gate.EXPECTED_WEB_UID}:{gate.EXPECTED_WEB_GID}"
        )
    try:
        pwd.getpwuid(gate.EXPECTED_APP_UID)
        grp.getgrgid(gate.EXPECTED_APP_GID)
    except KeyError:
        missing.append(
            f"application identity UID/GID {gate.EXPECTED_APP_UID}:{gate.EXPECTED_APP_GID}"
        )
    return {
        "artifact": f"{ARTIFACT}-prerequisites",
        "status": "ready" if not missing else "unavailable",
        "local_only": True,
        "missing": missing,
        "nginx": str(nginx) if nginx else None,
        "php_fpm": str(php_fpm) if php_fpm else None,
        "effective_uid": os.geteuid() if hasattr(os, "geteuid") else None,
        "web_identity": {
            "uid": gate.EXPECTED_WEB_UID,
            "gid": gate.EXPECTED_WEB_GID,
            "user": web_user.pw_name if web_user else None,
            "group": web_group.gr_name if web_group else None,
        },
    }


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def render_fpm_configuration(
    *,
    root: Path,
    socket_path: Path,
    pid_path: Path,
    error_log: Path,
) -> str:
    web_user = pwd.getpwuid(gate.EXPECTED_WEB_UID).pw_name
    web_group = grp.getgrgid(gate.EXPECTED_WEB_GID).gr_name
    return f"""[global]
pid = {pid_path}
error_log = {error_log}
daemonize = no
log_level = notice

[opcache_rehearsal]
prefix = {root}
user = {web_user}
group = {web_group}
listen = {socket_path}
listen.owner = {web_user}
listen.group = {web_group}
listen.mode = 0660
pm = static
pm.max_children = 1
pm.max_requests = 100
clear_env = yes
catch_workers_output = yes
decorate_workers_output = no
security.limit_extensions = .php
php_admin_flag[log_errors] = on
php_admin_value[opcache.enable] = 1
php_admin_value[opcache.validate_timestamps] = 1
php_admin_value[opcache.revalidate_freq] = {REVALIDATE_FREQUENCY_SECONDS}
php_admin_value[opcache.file_update_protection] = {FILE_UPDATE_PROTECTION_SECONDS}
"""


def render_nginx_configuration(
    *,
    root: Path,
    public_root: Path,
    socket_path: Path,
    origin_port: int,
    public_port: int,
    pid_path: Path,
    error_log: Path,
    access_log: Path,
) -> str:
    client_temp = root / "nginx-client-temp"
    proxy_temp = root / "nginx-proxy-temp"
    return f"""worker_processes 1;
pid {pid_path};
error_log {error_log} notice;

events {{
    worker_connections 128;
}}

http {{
    access_log {access_log};
    default_type text/plain;
    client_body_temp_path {client_temp};
    proxy_temp_path {proxy_temp};
    sendfile off;

    server {{
        listen 127.0.0.1:{origin_port};
        server_name origin.opcache.invalid;
        root {public_root};

        location / {{
            add_header {ROUTE_HEADER} origin always;
            add_header {NONCE_HEADER} $arg_ops_gate always;
            fastcgi_param QUERY_STRING $query_string;
            fastcgi_param REQUEST_METHOD $request_method;
            fastcgi_param CONTENT_TYPE $content_type;
            fastcgi_param CONTENT_LENGTH $content_length;
            fastcgi_param SCRIPT_FILENAME $document_root/index.php;
            fastcgi_param SCRIPT_NAME /index.php;
            fastcgi_param REQUEST_URI $request_uri;
            fastcgi_param DOCUMENT_URI /index.php;
            fastcgi_param DOCUMENT_ROOT $document_root;
            fastcgi_param SERVER_PROTOCOL $server_protocol;
            fastcgi_param REQUEST_SCHEME $scheme;
            fastcgi_param GATEWAY_INTERFACE CGI/1.1;
            fastcgi_param SERVER_SOFTWARE nginx/$nginx_version;
            fastcgi_param REMOTE_ADDR $remote_addr;
            fastcgi_param REMOTE_PORT $remote_port;
            fastcgi_param SERVER_ADDR $server_addr;
            fastcgi_param SERVER_PORT $server_port;
            fastcgi_param SERVER_NAME $server_name;
            fastcgi_param REDIRECT_STATUS 200;
            fastcgi_pass unix:{socket_path};
        }}
    }}

    server {{
        listen 127.0.0.1:{public_port};
        server_name public.opcache.invalid;

        location / {{
            proxy_http_version 1.1;
            proxy_set_header Host origin.opcache.invalid;
            proxy_set_header Connection "";
            proxy_set_header Cache-Control "no-cache, no-store, max-age=0";
            proxy_set_header Pragma "no-cache";
            proxy_buffering off;
            proxy_hide_header {ROUTE_HEADER};
            proxy_hide_header {NONCE_HEADER};
            add_header {ROUTE_HEADER} public always;
            add_header {NONCE_HEADER} $arg_ops_gate always;
            proxy_pass http://127.0.0.1:{origin_port};
        }}
    }}
}}
"""


def _header_values(headers: list[tuple[str, str]], name: str) -> list[str]:
    lowered = name.lower()
    return [value for key, value in headers if key.lower() == lowered]


def http_probe(
    *,
    port: int,
    route: str,
    nonce: str,
    evidence_directory: Path,
    label: str,
) -> dict[str, Any]:
    if route not in {ORIGIN_ROUTE, PUBLIC_ROUTE}:
        raise RehearsalError("Unknown local rehearsal route.")
    if len(nonce) != 24 or any(character not in "0123456789abcdef" for character in nonce):
        raise RehearsalError("Rehearsal cache buster is invalid.")
    host = "origin.opcache.invalid" if route == ORIGIN_ROUTE else "public.opcache.invalid"
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=HTTP_TIMEOUT_SECONDS)
    try:
        connection.request(
            "GET",
            f"/?ops_gate={nonce}",
            headers={
                "Host": host,
                "Cache-Control": "no-cache, no-store, max-age=0",
                "Pragma": "no-cache",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        body = response.read()
        headers = response.getheaders()
    finally:
        connection.close()

    raw_headers = (
        f"HTTP/1.1 {response.status} {response.reason}\r\n"
        + "".join(f"{name}: {value}\r\n" for name, value in headers)
        + "\r\n"
    ).encode("utf-8")
    raw_path = evidence_directory / f"{label}.headers.raw"
    body_path = evidence_directory / f"{label}.body.raw"
    write_exclusive(raw_path, raw_headers, 0o600)
    write_exclusive(body_path, body, 0o600)

    expected_route_value = "origin" if route == ORIGIN_ROUTE else "public"
    route_values = _header_values(headers, ROUTE_HEADER)
    nonce_values = _header_values(headers, NONCE_HEADER)
    return {
        "label": label,
        "route": route,
        "status": response.status,
        "route_bound": route_values == [expected_route_value],
        "nonce_bound": nonce_values == [nonce],
        "nonce_sha256": sha256_bytes(nonce.encode("ascii")),
        "header_names": sorted({name.lower() for name, _value in headers}),
        "headers_sha256": sha256_bytes(raw_headers),
        "body_sha256": sha256_bytes(body),
        "body_bytes": len(body),
        "gate_header_verified": _header_values(
            headers, gate.MAINTENANCE_GATE_HEADER_NAME
        )
        == [gate.MAINTENANCE_GATE_HEADER_VALUE],
        "gate_probe_header_verified": _header_values(
            headers, gate.MAINTENANCE_GATE_PROBE_HEADER_NAME
        )
        == [nonce],
        "gate_sentinel_verified": gate.MAINTENANCE_GATE_SENTINEL.encode("utf-8")
        in body,
        "original_sentinel_verified": ORIGINAL_SENTINEL.encode("utf-8") in body,
        "body": body,
    }


def receipt_probe(probe: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in probe.items() if key != "body"}


def require_original(probe: dict[str, Any]) -> dict[str, Any]:
    if probe["status"] != 200:
        raise RehearsalError("Original application did not return HTTP 200.")
    if not probe["route_bound"] or not probe["nonce_bound"]:
        raise RehearsalError("Original response is not bound to its route and cache buster.")
    if not probe["original_sentinel_verified"] or probe["gate_sentinel_verified"]:
        raise RehearsalError("Original application response identity is invalid.")
    try:
        payload = json.loads(probe["body"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise RehearsalError("Original application response is not valid JSON.") from exception
    if payload.get("sentinel") != ORIGINAL_SENTINEL:
        raise RehearsalError("Original application JSON sentinel is invalid.")
    if payload.get("sapi") != EXPECTED_FPM_SAPI:
        raise RehearsalError("Original application was not executed by PHP-FPM.")
    return payload


def require_gate(probe: dict[str, Any]) -> None:
    if probe["status"] != 503:
        raise RehearsalError("Reviewed gate did not return HTTP 503.")
    if not probe["route_bound"] or not probe["nonce_bound"]:
        raise RehearsalError("Gate response is not bound to its route and cache buster.")
    if not all(
        (
            probe["gate_header_verified"],
            probe["gate_probe_header_verified"],
            probe["gate_sentinel_verified"],
        )
    ):
        raise RehearsalError("Reviewed gate header, probe binding, or sentinel is absent.")
    if probe["original_sentinel_verified"]:
        raise RehearsalError("Gate response unexpectedly contains the original sentinel.")


def revalidation_wait(
    *,
    minimum_wait_seconds: int,
    path: Path,
    expected_sha256: str,
    monotonic_ns: Callable[[], int] | None = None,
    wall_time: Callable[[], float] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    if type(minimum_wait_seconds) is not int or minimum_wait_seconds < 5:
        raise RehearsalError("Revalidation wait is shorter than the five-second floor.")
    monotonic = monotonic_ns or time.monotonic_ns
    wall = wall_time or time.time
    sleep = sleeper or time.sleep
    before = file_identity(path)
    if before["sha256"] != expected_sha256:
        raise RehearsalError("Front-controller identity is wrong before revalidation wait.")
    start_monotonic_ns = monotonic()
    start_wall = wall()
    deadline_ns = start_monotonic_ns + minimum_wait_seconds * 1_000_000_000
    while True:
        remaining_ns = deadline_ns - monotonic()
        if remaining_ns <= 0:
            break
        sleep(remaining_ns / 1_000_000_000)
    end_monotonic_ns = monotonic()
    end_wall = wall()
    elapsed_ns = end_monotonic_ns - start_monotonic_ns
    if elapsed_ns < minimum_wait_seconds * 1_000_000_000:
        raise RehearsalError("Monotonic revalidation wait ended before its deadline.")
    after = file_identity(path)
    if after != before:
        raise RehearsalError("Front-controller identity changed during revalidation wait.")
    return {
        "configured_wait_seconds": minimum_wait_seconds,
        "started_at_utc": utc_from_epoch(start_wall),
        "ended_at_utc": utc_from_epoch(end_wall),
        "earliest_probe_at_utc": utc_from_epoch(start_wall + minimum_wait_seconds),
        "start_monotonic_ns": start_monotonic_ns,
        "end_monotonic_ns": end_monotonic_ns,
        "elapsed_monotonic_ns": elapsed_ns,
        "elapsed_seconds": elapsed_ns / 1_000_000_000,
        "identity_before": before,
        "identity_after": after,
    }


def _run_checked(command: list[str], *, timeout: int = 20) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    result = {
        "argv_sha256": sha256_bytes("\0".join(command).encode("utf-8")),
        "exit_status": completed.returncode,
        "stdout_sha256": sha256_bytes(completed.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(completed.stderr.encode("utf-8")),
    }
    if completed.returncode != 0:
        raise RehearsalError(f"Local daemon configuration check failed: {result}")
    return result


def _start_process(command: list[str], log_path: Path) -> subprocess.Popen[bytes]:
    handle = log_path.open("xb")
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        handle.close()
    os.chmod(log_path, 0o600)
    return process


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _wait_for_socket(path: Path, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + PROCESS_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RehearsalError("PHP-FPM exited before creating its disposable socket.")
        if path.exists() and stat.S_ISSOCK(path.stat().st_mode):
            return
        time.sleep(0.05)
    raise RehearsalError("PHP-FPM did not create its disposable socket in time.")


def _next_nonce(used: set[str]) -> str:
    while True:
        nonce = secrets.token_hex(12)
        if nonce not in used:
            used.add(nonce)
            return nonce


def _log_manifest(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and not path.is_symlink():
            metadata = path.stat()
            records.append(
                {
                    "name": path.name,
                    "bytes": metadata.st_size,
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "sha256": sha256_bytes(path.read_bytes()),
                }
            )
    return records


def run_rehearsal(
    parent: Path,
    *,
    nginx_path: Path | None = None,
    php_fpm_path: Path | None = None,
) -> dict[str, Any]:
    prerequisites = prerequisite_report(
        nginx_path=nginx_path,
        php_fpm_path=php_fpm_path,
    )
    if prerequisites["status"] != "ready":
        raise RehearsalError(
            "Local nginx/PHP-FPM prerequisites are unavailable: "
            + ", ".join(prerequisites["missing"])
        )
    resolved_parent = parent.resolve(strict=True)
    if resolved_parent.is_symlink() or not resolved_parent.is_dir():
        raise RehearsalError("Rehearsal parent must be a real directory.")

    # TemporaryDirectory is a second cleanup guard for failures that happen
    # while rendering or validating daemon configuration, before child
    # processes exist and the explicit cleanup block below is entered.
    temporary_root = tempfile.TemporaryDirectory(
        prefix=TEMPORARY_PREFIX,
        dir=resolved_parent,
    )
    root = Path(temporary_root.name)
    os.chmod(root, 0o755)
    application = root / "application"
    public_root = application / "public"
    private = root / "private-evidence"
    runtime = root / "runtime"
    for directory, mode in (
        (application, 0o755),
        (public_root, 0o755),
        (private, 0o700),
        (runtime, 0o755),
        (root / "nginx-client-temp", 0o770),
        (root / "nginx-proxy-temp", 0o770),
    ):
        directory.mkdir(mode=mode)
        os.chmod(directory, mode)
    for directory in (root / "nginx-client-temp", root / "nginx-proxy-temp"):
        os.chown(directory, gate.EXPECTED_WEB_UID, gate.EXPECTED_WEB_GID)

    front_controller = public_root / "index.php"
    original_bytes = original_front_controller()
    front_controller.write_bytes(original_bytes)
    os.chown(front_controller, gate.EXPECTED_APP_UID, gate.EXPECTED_APP_GID)
    os.chmod(front_controller, 0o644)
    old_timestamp = time.time() - 60
    os.utime(front_controller, (old_timestamp, old_timestamp))
    original_identity = file_identity(front_controller)
    original_backup = private / "index.original.php"
    write_exclusive(original_backup, original_bytes, 0o600)

    fpm_socket = runtime / "php-fpm.sock"
    fpm_config = private / "php-fpm.conf"
    nginx_config = private / "nginx.conf"
    fpm_error_log = private / "php-fpm-error.log"
    nginx_error_log = private / "nginx-error.log"
    nginx_access_log = private / "nginx-access.log"
    fpm_process_log = private / "php-fpm-process.log"
    nginx_process_log = private / "nginx-process.log"
    origin_port = reserve_local_port()
    public_port = reserve_local_port()
    while public_port == origin_port:
        public_port = reserve_local_port()

    fpm_text = render_fpm_configuration(
        root=root,
        socket_path=fpm_socket,
        pid_path=runtime / "php-fpm.pid",
        error_log=fpm_error_log,
    )
    nginx_text = render_nginx_configuration(
        root=root,
        public_root=public_root,
        socket_path=fpm_socket,
        origin_port=origin_port,
        public_port=public_port,
        pid_path=runtime / "nginx.pid",
        error_log=nginx_error_log,
        access_log=nginx_access_log,
    )
    write_exclusive(fpm_config, fpm_text.encode("utf-8"), 0o600)
    write_exclusive(nginx_config, nginx_text.encode("utf-8"), 0o600)

    nginx = Path(str(prerequisites["nginx"]))
    php_fpm = Path(str(prerequisites["php_fpm"]))
    try:
        fpm_check = _run_checked(
            [str(php_fpm), "--test", "--fpm-config", str(fpm_config)]
        )
        nginx_check = _run_checked(
            [str(nginx), "-t", "-c", str(nginx_config), "-p", f"{root}/"]
        )
    except BaseException:
        temporary_root.cleanup()
        raise

    fpm_process: subprocess.Popen[bytes] | None = None
    nginx_process: subprocess.Popen[bytes] | None = None
    used_nonces: set[str] = set()
    probes: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    try:
        fpm_process = _start_process(
            [str(php_fpm), "--nodaemonize", "--fpm-config", str(fpm_config)],
            fpm_process_log,
        )
        _wait_for_socket(fpm_socket, fpm_process)
        nginx_process = _start_process(
            [
                str(nginx),
                "-c",
                str(nginx_config),
                "-p",
                f"{root}/",
                "-g",
                "daemon off; master_process off;",
            ],
            nginx_process_log,
        )

        ready_deadline = time.monotonic() + PROCESS_START_TIMEOUT_SECONDS
        warm_payload: dict[str, Any] | None = None
        while time.monotonic() < ready_deadline:
            if nginx_process.poll() is not None:
                raise RehearsalError("nginx exited before the local origin became ready.")
            try:
                ready = http_probe(
                    port=origin_port,
                    route=ORIGIN_ROUTE,
                    nonce=_next_nonce(used_nonces),
                    evidence_directory=private,
                    label=f"probe-{len(probes) + 1:02d}-ready",
                )
                probes.append(ready)
                warm_payload = require_original(ready)
                break
            except (ConnectionError, OSError, RehearsalError):
                time.sleep(0.05)
        if warm_payload is None:
            raise RehearsalError("Disposable nginx/PHP-FPM did not become ready.")

        # The first compile does not provide a portable next-validation clock
        # boundary across supported OPcache builds.  Cross one full frequency,
        # then issue the final warm request immediately before replacement so
        # the stale-response reproduction is deterministic.
        time.sleep(VALIDATION_CLOCK_CONDITIONING_SECONDS)
        warm = http_probe(
            port=origin_port,
            route=ORIGIN_ROUTE,
            nonce=_next_nonce(used_nonces),
            evidence_directory=private,
            label=f"probe-{len(probes) + 1:02d}-warm-original",
        )
        probes.append(warm)
        warm_payload = require_original(warm)
        policy = gate.derive_opcache_revalidation_policy(warm_payload)
        if policy["revalidate_freq_seconds"] != REVALIDATE_FREQUENCY_SECONDS:
            raise RehearsalError("PHP-FPM did not apply the nonzero rehearsal frequency.")
        if policy["file_update_protection_seconds"] != FILE_UPDATE_PROTECTION_SECONDS:
            raise RehearsalError("PHP-FPM did not apply file-update protection.")

        gate_install = atomic_install(
            front_controller,
            gate.MAINTENANCE_GATE_BYTES,
            uid=gate.EXPECTED_APP_UID,
            gid=gate.EXPECTED_APP_GID,
        )
        immediate_original = http_probe(
            port=origin_port,
            route=ORIGIN_ROUTE,
            nonce=_next_nonce(used_nonces),
            evidence_directory=private,
            label=f"probe-{len(probes) + 1:02d}-immediate-after-gate",
        )
        probes.append(immediate_original)
        require_original(immediate_original)

        gate_wait = revalidation_wait(
            minimum_wait_seconds=policy["minimum_wait_seconds"],
            path=front_controller,
            expected_sha256=gate.EXPECTED_GATE_SHA256,
        )
        gate_probes: list[dict[str, Any]] = []
        for label, route, port in (
            ("origin-1", ORIGIN_ROUTE, origin_port),
            ("origin-2", ORIGIN_ROUTE, origin_port),
            ("public", PUBLIC_ROUTE, public_port),
        ):
            probe = http_probe(
                port=port,
                route=route,
                nonce=_next_nonce(used_nonces),
                evidence_directory=private,
                label=f"probe-{len(probes) + 1:02d}-gate-{label}",
            )
            probes.append(probe)
            require_gate(probe)
            gate_probes.append(probe)

        original_restore = atomic_install(
            front_controller,
            original_backup.read_bytes(),
            uid=gate.EXPECTED_APP_UID,
            gid=gate.EXPECTED_APP_GID,
        )
        immediate_gate = http_probe(
            port=origin_port,
            route=ORIGIN_ROUTE,
            nonce=_next_nonce(used_nonces),
            evidence_directory=private,
            label=f"probe-{len(probes) + 1:02d}-immediate-after-original",
        )
        probes.append(immediate_gate)
        require_gate(immediate_gate)

        original_wait = revalidation_wait(
            minimum_wait_seconds=policy["minimum_wait_seconds"],
            path=front_controller,
            expected_sha256=original_identity["sha256"],
        )
        final_probes: list[dict[str, Any]] = []
        for label, route, port in (
            ("origin", ORIGIN_ROUTE, origin_port),
            ("public", PUBLIC_ROUTE, public_port),
        ):
            probe = http_probe(
                port=port,
                route=route,
                nonce=_next_nonce(used_nonces),
                evidence_directory=private,
                label=f"probe-{len(probes) + 1:02d}-final-{label}",
            )
            probes.append(probe)
            final_payload = require_original(probe)
            if gate.derive_opcache_revalidation_policy(final_payload) != policy:
                raise RehearsalError("PHP-FPM OPcache policy drifted during restoration.")
            final_probes.append(probe)

        nonce_hashes = [probe["nonce_sha256"] for probe in probes]
        if len(nonce_hashes) != len(set(nonce_hashes)):
            raise RehearsalError("A local HTTP probe reused a cache buster.")
        if file_identity(front_controller) != original_identity:
            # mtime/inode are deliberately absent from file_identity; exact bytes and
            # reviewed metadata must return to the original identity.
            raise RehearsalError("Final front controller differs from the original identity.")

        result = {
            "artifact": ARTIFACT,
            "status": "pass",
            "generated_at_utc": utc_now(),
            "script_sha256": file_identity(Path(__file__).resolve())["sha256"],
            "gate_helper_sha256": file_identity(
                Path(str(gate.__file__)).resolve()
            )["sha256"],
            "scope": "local-disposable-nginx-php-fpm-no-service-manager",
            "loopback_only": True,
            "production_accessed": False,
            "system_services_changed": False,
            "prerequisites": prerequisites,
            "local_executables": {
                "nginx": file_identity(nginx),
                "php_fpm": file_identity(php_fpm),
            },
            "gate": {
                "sha256": gate.EXPECTED_GATE_SHA256,
                "header_name": gate.MAINTENANCE_GATE_HEADER_NAME,
                "header_value": gate.MAINTENANCE_GATE_HEADER_VALUE,
                "probe_header_name": gate.MAINTENANCE_GATE_PROBE_HEADER_NAME,
                "sentinel": gate.MAINTENANCE_GATE_SENTINEL,
            },
            "original_identity": original_identity,
            "opcache_policy": policy,
            "daemon_configuration": {
                "fpm_config_sha256": sha256_bytes(fpm_text.encode("utf-8")),
                "nginx_config_sha256": sha256_bytes(nginx_text.encode("utf-8")),
                "fpm_configuration_check": fpm_check,
                "nginx_configuration_check": nginx_check,
                "origin_and_public_ports_distinct": origin_port != public_port,
                "socket_is_disposable": str(fpm_socket).startswith(str(root)),
                "validation_clock_conditioning_seconds": (
                    VALIDATION_CLOCK_CONDITIONING_SECONDS
                ),
            },
            "sequence": {
                "warm_original": receipt_probe(warm),
                "gate_install": gate_install,
                "immediate_stale_original_after_gate_install": receipt_probe(
                    immediate_original
                ),
                "gate_revalidation_wait": gate_wait,
                "gate_probes": [receipt_probe(probe) for probe in gate_probes],
                "original_restore": original_restore,
                "immediate_stale_gate_after_original_restore": receipt_probe(immediate_gate),
                "original_revalidation_wait": original_wait,
                "final_original_probes": [
                    receipt_probe(probe) for probe in final_probes
                ],
            },
            "cache_busters": {
                "count": len(nonce_hashes),
                "unique": True,
                "sha256_values": nonce_hashes,
            },
        }
    finally:
        _stop_process(nginx_process)
        _stop_process(fpm_process)
        for path in private.iterdir():
            if path.is_file() and not path.is_symlink():
                os.chmod(path, 0o600)
        if result is not None:
            result["private_evidence_manifest"] = _log_manifest(private)
        resolved_root = root.resolve(strict=True)
        if resolved_root.parent != resolved_parent or not root.name.startswith(TEMPORARY_PREFIX):
            raise RehearsalError("Refusing to remove an unrecognized rehearsal directory.")
        temporary_root.cleanup()

    assert result is not None
    result["canonical_sha256"] = sha256_bytes(canonical_bytes(result))
    return result


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, default=Path("/tmp"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--nginx", type=Path)
    parser.add_argument("--php-fpm", type=Path)
    parser.add_argument("--check-prerequisites", action="store_true")
    return parser.parse_args()


def emit(payload: dict[str, Any], output: Path | None) -> None:
    value = canonical_bytes(payload)
    if output is None:
        sys.stdout.buffer.write(value)
        return
    parent = output.parent.resolve(strict=True)
    if output.exists() or output.is_symlink():
        raise RehearsalError("Refusing to overwrite an existing rehearsal receipt.")
    write_exclusive(parent / output.name, value, 0o600)


def main() -> int:
    arguments = parse_arguments()
    prerequisites = prerequisite_report(
        nginx_path=arguments.nginx,
        php_fpm_path=arguments.php_fpm,
    )
    if arguments.check_prerequisites:
        emit(prerequisites, arguments.output)
        return 0
    if prerequisites["status"] != "ready":
        emit(prerequisites, arguments.output)
        return 2
    result = run_rehearsal(
        arguments.parent,
        nginx_path=arguments.nginx,
        php_fpm_path=arguments.php_fpm,
    )
    emit(result, arguments.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RehearsalError as exception:
        failure = {
            "artifact": ARTIFACT,
            "status": "fail",
            "generated_at_utc": utc_now(),
            "failure_type": type(exception).__name__,
            "failure_message_sha256": sha256_bytes(str(exception).encode("utf-8")),
            "production_accessed": False,
            "system_services_changed": False,
        }
        sys.stderr.buffer.write(canonical_bytes(failure))
        raise SystemExit(1)
