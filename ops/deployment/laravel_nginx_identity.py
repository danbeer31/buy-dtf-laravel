#!/usr/bin/env python3
"""Read-only PHP-FPM OPcache and effective nginx identity controls.

The module deliberately performs no service reload and changes no nginx or PHP
configuration.  Its only filesystem writes are exclusive evidence files in a
caller-provided directory.  The complete nginx dump is private mode 0600;
the separately written summary contains identities and hashes, never raw
configuration text.
"""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import subprocess
from typing import Any, Callable, Sequence


FPM_OPCACHE_ARTIFACT = "buy-dtf-php-fpm-opcache-probe-v1"
NGINX_IDENTITY_ARTIFACT = "buy-dtf-nginx-document-root-identity-v1"
EXPECTED_FPM_SAPI = "fpm-fcgi"
EXPECTED_SERVER_NAME = "buy-dtf.com"
EXPECTED_DOCUMENT_ROOT = Path("/var/www/buy-dtf/public")
RAW_CAPTURE_MODE = 0o600

BOOLEAN_DIRECTIVES = (
    "opcache.enable",
    "opcache.validate_timestamps",
)
INTEGER_DIRECTIVES = (
    "opcache.revalidate_freq",
    "opcache.file_update_protection",
)
OPCACHE_DIRECTIVES = BOOLEAN_DIRECTIVES + INTEGER_DIRECTIVES


class EnvironmentControlError(RuntimeError):
    """An environment identity is absent, ambiguous, unsafe, or malformed."""


@dataclass(frozen=True)
class NginxStatement:
    name: str
    arguments: tuple[str, ...]
    children: tuple["NginxStatement", ...] | None = None


CommandRunner = Callable[..., subprocess.CompletedProcess[bytes]]


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_boolean(name: str, raw: str | bool) -> bool:
    if raw is False:
        raise EnvironmentControlError(f"PHP-FPM did not expose required directive {name}.")
    if not isinstance(raw, str):
        raise EnvironmentControlError(f"PHP-FPM directive {name} has an invalid raw value.")
    value = raw.strip().lower()
    if value in {"1", "on", "true", "yes"}:
        return True
    if value in {"", "0", "off", "false", "no"}:
        return False
    raise EnvironmentControlError(f"PHP-FPM directive {name} is not a recognized boolean.")


def _normalize_integer(name: str, raw: str | bool) -> int:
    if raw is False:
        raise EnvironmentControlError(f"PHP-FPM did not expose required directive {name}.")
    if not isinstance(raw, str) or re.fullmatch(r"[0-9]+", raw.strip()) is None:
        raise EnvironmentControlError(
            f"PHP-FPM directive {name} is not a nonnegative integer."
        )
    return int(raw.strip())


def validate_fpm_opcache_payload(
    payload: Any,
    *,
    require_timestamp_validation: bool = True,
) -> dict[str, Any]:
    """Validate and independently normalize the hash-pinned FPM probe output."""

    if not isinstance(payload, dict):
        raise EnvironmentControlError("PHP-FPM OPcache probe did not return an object.")
    if set(payload) != {
        "artifact",
        "sapi",
        "php_version",
        "directives",
        "opcache_configuration_directives",
    }:
        raise EnvironmentControlError("PHP-FPM OPcache probe has an unexpected shape.")
    if payload.get("artifact") != FPM_OPCACHE_ARTIFACT:
        raise EnvironmentControlError("PHP-FPM OPcache probe artifact identity differs.")
    if payload.get("sapi") != EXPECTED_FPM_SAPI:
        raise EnvironmentControlError("OPcache settings were not read through PHP-FPM.")
    php_version = payload.get("php_version")
    if not isinstance(php_version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", php_version):
        raise EnvironmentControlError("PHP-FPM probe returned an invalid PHP version.")

    directives = payload.get("directives")
    normalized_summary = payload.get("opcache_configuration_directives")
    if not isinstance(directives, dict) or set(directives) != set(OPCACHE_DIRECTIVES):
        raise EnvironmentControlError("PHP-FPM probe directive set differs from policy.")
    if not isinstance(normalized_summary, dict) or set(normalized_summary) != set(
        OPCACHE_DIRECTIVES
    ):
        raise EnvironmentControlError("PHP-FPM normalized directive set differs from policy.")

    independently_normalized: dict[str, bool | int] = {}
    for name in OPCACHE_DIRECTIVES:
        item = directives.get(name)
        if not isinstance(item, dict) or set(item) != {"raw", "normalized"}:
            raise EnvironmentControlError(f"PHP-FPM directive {name} has an invalid shape.")
        raw = item.get("raw")
        if not isinstance(raw, (str, bool)) or raw is True:
            raise EnvironmentControlError(f"PHP-FPM directive {name} has an invalid raw type.")
        if name in BOOLEAN_DIRECTIVES:
            normalized: bool | int = _normalize_boolean(name, raw)
            if not isinstance(item.get("normalized"), bool):
                raise EnvironmentControlError(
                    f"PHP-FPM directive {name} normalized type is not boolean."
                )
        else:
            normalized = _normalize_integer(name, raw)
            recorded = item.get("normalized")
            if isinstance(recorded, bool) or not isinstance(recorded, int):
                raise EnvironmentControlError(
                    f"PHP-FPM directive {name} normalized type is not integer."
                )
        if item.get("normalized") != normalized:
            raise EnvironmentControlError(
                f"PHP-FPM directive {name} does not match independent normalization."
            )
        if normalized_summary.get(name) != normalized:
            raise EnvironmentControlError(
                f"PHP-FPM directive {name} differs between normalized views."
            )
        independently_normalized[name] = normalized

    if (
        require_timestamp_validation
        and independently_normalized["opcache.validate_timestamps"] is not True
    ):
        raise EnvironmentControlError(
            "PHP-FPM opcache.validate_timestamps must be enabled before gate installation."
        )
    return {
        "artifact": FPM_OPCACHE_ARTIFACT,
        "sapi": EXPECTED_FPM_SAPI,
        "php_version": php_version,
        "directives": directives,
        "opcache_configuration_directives": independently_normalized,
    }


def _tokenize_nginx(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0

    def finish() -> None:
        if current:
            tokens.append("".join(current))
            current.clear()

    while index < len(text):
        character = text[index]
        if quote is not None:
            if escaped:
                current.append(character)
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            else:
                current.append(character)
            index += 1
            continue
        if escaped:
            current.append(character)
            escaped = False
            index += 1
            continue
        if character == "\\":
            escaped = True
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
            index += 1
            continue
        if character == "#":
            finish()
            newline = text.find("\n", index)
            index = len(text) if newline == -1 else newline + 1
            continue
        if character.isspace():
            finish()
            index += 1
            continue
        if character in {"{", "}", ";"}:
            finish()
            tokens.append(character)
            index += 1
            continue
        current.append(character)
        index += 1
    if quote is not None or escaped:
        raise EnvironmentControlError("Effective nginx configuration has an unterminated token.")
    finish()
    return tokens


def _parse_statements(tokens: Sequence[str], start: int = 0, *, nested: bool = False) -> tuple[tuple[NginxStatement, ...], int]:
    statements: list[NginxStatement] = []
    header: list[str] = []
    index = start
    while index < len(tokens):
        token = tokens[index]
        if token == ";":
            if not header:
                raise EnvironmentControlError("Effective nginx configuration has an empty directive.")
            statements.append(NginxStatement(header[0], tuple(header[1:])))
            header = []
            index += 1
            continue
        if token == "{":
            if not header:
                raise EnvironmentControlError("Effective nginx configuration has an anonymous block.")
            children, index = _parse_statements(tokens, index + 1, nested=True)
            statements.append(NginxStatement(header[0], tuple(header[1:]), children))
            header = []
            continue
        if token == "}":
            if not nested or header:
                raise EnvironmentControlError("Effective nginx configuration has unmatched syntax.")
            return tuple(statements), index + 1
        header.append(token)
        index += 1
    if nested or header:
        raise EnvironmentControlError("Effective nginx configuration is incomplete.")
    return tuple(statements), index


def parse_nginx_config(text: str) -> tuple[NginxStatement, ...]:
    tokens = _tokenize_nginx(text)
    statements, end = _parse_statements(tokens)
    if end != len(tokens):
        raise EnvironmentControlError("Effective nginx configuration has trailing syntax.")
    return statements


NGINX_DUMP_SECTION = re.compile(
    r"(?m)^# configuration file (?P<path>/[^\r\n:]+):[ \t]*\r?$"
)


def _expand_nginx_dump(text: str) -> tuple[NginxStatement, ...]:
    """Parse nginx -T sections and expand each include in its lexical context."""

    markers = list(NGINX_DUMP_SECTION.finditer(text))
    if not markers:
        return parse_nginx_config(text)
    if text[: markers[0].start()].strip():
        raise EnvironmentControlError("Effective nginx dump has data before its first section.")

    sections: dict[str, tuple[NginxStatement, ...]] = {}
    for index, marker in enumerate(markers):
        path = posixpath.normpath(marker.group("path"))
        if not path.startswith("/"):
            raise EnvironmentControlError("Effective nginx dump has an invalid section identity.")
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        parsed = parse_nginx_config(text[marker.end() : end])
        if path in sections and sections[path] != parsed:
            raise EnvironmentControlError(
                "Effective nginx dump repeats one section with different content."
            )
        sections[path] = parsed

    main_path = "/etc/nginx/nginx.conf"
    if main_path not in sections:
        raise EnvironmentControlError("Effective nginx dump omits /etc/nginx/nginx.conf.")
    prefix = posixpath.dirname(main_path)

    def expand(
        statements: Sequence[NginxStatement],
        stack: tuple[str, ...],
    ) -> tuple[NginxStatement, ...]:
        expanded: list[NginxStatement] = []
        for statement in statements:
            if statement.children is None and statement.name.lower() == "include":
                if len(statement.arguments) != 1 or "$" in statement.arguments[0]:
                    raise EnvironmentControlError(
                        "Effective nginx dump has a dynamic or malformed include."
                    )
                pattern = statement.arguments[0]
                absolute_pattern = posixpath.normpath(
                    pattern if pattern.startswith("/") else posixpath.join(prefix, pattern)
                )
                matches = sorted(
                    path for path in sections if fnmatch.fnmatchcase(path, absolute_pattern)
                )
                has_wildcard = any(character in absolute_pattern for character in "*?[")
                if not matches and not has_wildcard:
                    raise EnvironmentControlError(
                        "Effective nginx dump omits a referenced include section."
                    )
                for included_path in matches:
                    if included_path in stack:
                        raise EnvironmentControlError("Effective nginx dump has an include cycle.")
                    expanded.extend(
                        expand(sections[included_path], (*stack, included_path))
                    )
                continue
            if statement.children is not None:
                statement = NginxStatement(
                    name=statement.name,
                    arguments=statement.arguments,
                    children=expand(statement.children, stack),
                )
            expanded.append(statement)
        return tuple(expanded)

    return expand(sections[main_path], (main_path,))


def _walk_blocks(statements: Sequence[NginxStatement]) -> list[NginxStatement]:
    blocks: list[NginxStatement] = []
    for statement in statements:
        if statement.children is not None:
            blocks.append(statement)
            blocks.extend(_walk_blocks(statement.children))
    return blocks


def _directives(block: NginxStatement, name: str) -> list[NginxStatement]:
    if block.children is None:
        return []
    return [
        statement
        for statement in block.children
        if statement.children is None and statement.name.lower() == name.lower()
    ]


def _listen_uses_port_443(arguments: Sequence[str]) -> bool:
    if not arguments:
        return False
    endpoint = arguments[0].lower()
    if endpoint == "443":
        return True
    if endpoint.startswith("unix:"):
        return False
    return endpoint.endswith(":443")


def _is_tls_server(block: NginxStatement) -> bool:
    listens = _directives(block, "listen")
    return any(
        _listen_uses_port_443(item.arguments)
        and "ssl" in {argument.lower() for argument in item.arguments[1:]}
        for item in listens
    )


def _listen_serves_ipv4_loopback_443(arguments: Sequence[str]) -> bool:
    if not _listen_uses_port_443(arguments):
        return False
    if "ssl" not in {argument.lower() for argument in arguments[1:]}:
        return False
    endpoint = arguments[0].lower()
    return endpoint in {"443", "*:443", "0.0.0.0:443", "127.0.0.1:443"}


def _leaf_directives(statements: Sequence[NginxStatement]) -> list[NginxStatement]:
    result: list[NginxStatement] = []
    for child in statements:
        if child.children is None:
            result.append(child)
        else:
            result.extend(_leaf_directives(child.children))
    return result


def _statement_identity(statement: NginxStatement) -> dict[str, Any]:
    return {
        "name": statement.name,
        "arguments": list(statement.arguments),
        "children": (
            [_statement_identity(child) for child in statement.children]
            if statement.children is not None
            else None
        ),
    }


def identify_nginx_document_root(
    config_text: str,
    *,
    expected_server_name: str = EXPECTED_SERVER_NAME,
    expected_document_root: Path = EXPECTED_DOCUMENT_ROOT,
) -> dict[str, Any]:
    """Require one exact TLS virtual host and its exact resolved document root."""

    statements = _expand_nginx_dump(config_text)
    expected_name = expected_server_name.rstrip(".").lower()
    matches: list[NginxStatement] = []
    for block in _walk_blocks(statements):
        if block.name.lower() != "server" or not _is_tls_server(block):
            continue
        names = {
            argument.rstrip(".").lower()
            for directive in _directives(block, "server_name")
            for argument in directive.arguments
        }
        if expected_name in names:
            matches.append(block)
    if len(matches) != 1:
        raise EnvironmentControlError(
            "Effective nginx configuration must contain exactly one matching TLS server."
        )

    match = matches[0]
    all_direct = list(match.children or ())
    nested = [
        item
        for child in all_direct
        if child.children is not None
        for item in _leaf_directives(child.children)
    ]
    forbidden = [
        statement
        for statement in (*all_direct, *nested)
        if statement.children is None
        and statement.name.lower() in {"alias", "include"}
    ]
    nested_roots = [
        statement for statement in nested if statement.name.lower() == "root"
    ]
    if forbidden or nested_roots:
        raise EnvironmentControlError(
            "Matching nginx TLS server has an included, aliased, or nested document-root override."
        )
    roots = _directives(match, "root")
    if len(roots) != 1 or len(roots[0].arguments) != 1:
        raise EnvironmentControlError(
            "Matching nginx TLS server must declare exactly one document root."
        )
    root_text = roots[0].arguments[0]
    root = Path(root_text)
    if not root.is_absolute() or "$" in root_text:
        raise EnvironmentControlError("Matching nginx document root is not a fixed absolute path.")
    try:
        resolved_root = root.resolve(strict=True)
        resolved_expected = expected_document_root.resolve(strict=True)
    except OSError as exception:
        raise EnvironmentControlError(
            "Matching nginx document root or reviewed root cannot be resolved."
        ) from exception
    if not resolved_root.is_dir() or resolved_root != resolved_expected:
        raise EnvironmentControlError("Effective nginx document root differs from review.")

    listens = sorted(
        " ".join(item.arguments) for item in _directives(match, "listen")
    )
    if not any(
        _listen_serves_ipv4_loopback_443(item.arguments)
        for item in _directives(match, "listen")
    ):
        raise EnvironmentControlError(
            "Matching nginx TLS server cannot serve the reviewed IPv4 loopback origin probe."
        )
    return {
        "server_name": expected_name,
        "matching_tls_server_count": 1,
        "tls": True,
        "origin_probe_address": "127.0.0.1:443",
        "origin_loopback_compatible": True,
        "listen_directives": listens,
        "document_root": root_text,
        "resolved_document_root": str(resolved_root),
        "server_block_sha256": sha256_bytes(canonical_bytes(_statement_identity(match))),
    }


def _require_private_directory(path: Path) -> Path:
    metadata = os.lstat(path)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise EnvironmentControlError("Nginx evidence directory is missing or symbolic.")
    return path.resolve(strict=True)


def _write_exclusive(path: Path, content: bytes, mode: int) -> None:
    parent = _require_private_directory(path.parent)
    if path.parent.resolve(strict=True) != parent:
        raise EnvironmentControlError("Nginx evidence path has an unexpected parent.")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    directory_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _regular_file_identity(path: Path) -> dict[str, Any]:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise EnvironmentControlError(f"Evidence path is not a regular file: {path}")
    return {
        "path": str(path.resolve(strict=True)),
        "sha256": sha256_bytes(path.read_bytes()),
        "bytes": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def capture_nginx_identity(
    evidence_directory: Path,
    *,
    sudo_executable: Path = Path("/usr/bin/sudo"),
    nginx_executable: Path = Path("/usr/sbin/nginx"),
    raw_filename: str = "nginx-effective-config.private.txt",
    summary_filename: str = "nginx-document-root-summary.json",
    expected_server_name: str = EXPECTED_SERVER_NAME,
    expected_document_root: Path = EXPECTED_DOCUMENT_ROOT,
    expected_executable_uid: int = 0,
    expected_executable_gid: int = 0,
    command_runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Capture `nginx -T`, retain it privately, and emit a safe identity summary."""

    directory = _require_private_directory(evidence_directory)
    if Path(raw_filename).name != raw_filename or Path(summary_filename).name != summary_filename:
        raise EnvironmentControlError("Nginx evidence filenames must be simple basenames.")
    raw_path = directory / raw_filename
    summary_path = directory / summary_filename
    if raw_path == summary_path:
        raise EnvironmentControlError("Nginx raw and summary evidence paths must differ.")
    for label, candidate in (("sudo", sudo_executable), ("nginx", nginx_executable)):
        try:
            executable_metadata = os.lstat(candidate)
        except FileNotFoundError as exception:
            raise EnvironmentControlError(
                f"Reviewed {label} executable is unavailable."
            ) from exception
        if stat.S_ISLNK(executable_metadata.st_mode) or not stat.S_ISREG(
            executable_metadata.st_mode
        ):
            raise EnvironmentControlError(
                f"Reviewed {label} executable is symbolic or not regular."
            )
        if not os.access(candidate, os.X_OK):
            raise EnvironmentControlError(f"Reviewed {label} executable is not executable.")
    sudo = sudo_executable.resolve(strict=True)
    executable = nginx_executable.resolve(strict=True)
    sudo_before = _regular_file_identity(sudo)
    executable_before = _regular_file_identity(executable)
    for label, identity in (("sudo", sudo_before), ("nginx", executable_before)):
        if (
            identity["uid"] != expected_executable_uid
            or identity["gid"] != expected_executable_gid
            or identity["mode"] & 0o022
        ):
            raise EnvironmentControlError(
                f"Reviewed {label} executable ownership or mode is unsafe."
            )
    version_command = [str(executable), "-V"]
    command_environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    }
    try:
        version_completed = command_runner(
            version_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
            env=command_environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exception:
        raise EnvironmentControlError(
            "Reviewed nginx version/build probe could not execute."
        ) from exception
    if (
        not isinstance(version_completed.stdout, bytes)
        or not isinstance(version_completed.stderr, bytes)
        or version_completed.returncode != 0
    ):
        raise EnvironmentControlError("Reviewed nginx version/build probe failed.")
    version_bytes = version_completed.stdout + version_completed.stderr
    try:
        version_text = version_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise EnvironmentControlError("Nginx version/build identity is not valid UTF-8.") from exception
    version_match = re.search(r"(?:^|\n)nginx version: nginx/([^\s]+)", version_text)
    if version_match is None:
        raise EnvironmentControlError("Nginx version/build identity is malformed.")
    # nginx -T must parse certificate and log directives that are deliberately
    # unreadable to the unprivileged deployment account.  Use only the exact,
    # noninteractive, reviewable sudo command; the parent runner itself remains
    # non-root and no service or configuration mutation is performed.
    command = [str(sudo), "-n", "--", str(executable), "-T"]
    try:
        completed = command_runner(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
            env=command_environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exception:
        raise EnvironmentControlError(
            "Read-only nginx effective-config capture could not execute."
        ) from exception
    if not isinstance(completed.stdout, bytes) or not isinstance(completed.stderr, bytes):
        raise EnvironmentControlError("Nginx command did not return byte-preserving output.")
    _write_exclusive(raw_path, completed.stdout, RAW_CAPTURE_MODE)
    raw_identity = _regular_file_identity(raw_path)
    if raw_identity["mode"] != RAW_CAPTURE_MODE:
        raise EnvironmentControlError("Raw nginx evidence is not mode 0600.")
    if completed.returncode != 0:
        raise EnvironmentControlError("Read-only nginx effective-config capture failed.")
    sudo_after = _regular_file_identity(sudo)
    executable_after = _regular_file_identity(executable)
    if sudo_after != sudo_before:
        raise EnvironmentControlError("Sudo executable identity changed during capture.")
    if executable_after != executable_before:
        raise EnvironmentControlError("Nginx executable identity changed during capture.")
    try:
        config_text = completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise EnvironmentControlError("Effective nginx configuration is not valid UTF-8.") from exception
    document_root = identify_nginx_document_root(
        config_text,
        expected_server_name=expected_server_name,
        expected_document_root=expected_document_root,
    )
    summary = {
        "artifact": NGINX_IDENTITY_ARTIFACT,
        "status": "pass",
        "read_only": True,
        "privilege_boundary": "sudo-noninteractive-exact-nginx-T",
        "sudo_executable": str(sudo),
        "sudo_executable_sha256": sudo_before["sha256"],
        "sudo_executable_identity": sudo_before,
        "nginx_executable": str(executable),
        "nginx_executable_sha256": executable_before["sha256"],
        "nginx_executable_identity": executable_before,
        "nginx_version": version_match.group(1),
        "nginx_version_argv_sha256": sha256_bytes("\0".join(version_command).encode("utf-8")),
        "nginx_version_output_sha256": sha256_bytes(version_bytes),
        "command_argv_sha256": sha256_bytes("\0".join(command).encode("utf-8")),
        "command_exit_status": completed.returncode,
        "stderr_sha256": sha256_bytes(completed.stderr),
        "effective_config_sha256": sha256_bytes(completed.stdout),
        "raw_capture": {
            "classification": "private-do-not-commit",
            **raw_identity,
        },
        "document_root_identity": document_root,
        "configuration_changed": False,
        "service_reloaded_or_restarted": False,
    }
    _write_exclusive(summary_path, canonical_bytes(summary), RAW_CAPTURE_MODE)
    summary_identity = _regular_file_identity(summary_path)
    return {
        **summary,
        "summary_capture": {
            "classification": "review-safe",
            **summary_identity,
        },
    }


def describe() -> dict[str, Any]:
    return {
        "artifact": "buy-dtf-environment-controls-v1",
        "fpm_probe_artifact": FPM_OPCACHE_ARTIFACT,
        "fpm_sapi": EXPECTED_FPM_SAPI,
        "opcache_directives": list(OPCACHE_DIRECTIVES),
        "timestamp_validation_required": True,
        "nginx_identity_artifact": NGINX_IDENTITY_ARTIFACT,
        "nginx_server_name": EXPECTED_SERVER_NAME,
        "nginx_document_root": str(EXPECTED_DOCUMENT_ROOT),
        "nginx_capture_privilege_boundary": "sudo-noninteractive-exact-nginx-T",
        "raw_capture_mode": oct(RAW_CAPTURE_MODE),
    }
