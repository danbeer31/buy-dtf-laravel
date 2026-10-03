#!/usr/bin/env python3
"""Fail-closed Laravel log-delta capture and classification.

The classifier works on complete Laravel entries rather than treating the
``.ERROR`` level as proof of an application failure.  The collector keeps the
active log inode open across rename rotations, writes newly observed bytes to
private evidence files, and rejects truncation or continuity rewrites.

Reports intentionally contain hashes, counts, levels, and signal names only.
They never copy Laravel messages or raw log bytes into a redacted receipt.
"""

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Iterable, Iterator


ENTRY_HEADER = re.compile(
    r"^\[(?P<timestamp>[^\]\r\n]+)\]\s+"
    r"(?P<channel>[A-Za-z0-9_.-]+?)\."
    r"(?P<level>DEBUG|INFO|NOTICE|WARNING|ERROR|CRITICAL|ALERT|EMERGENCY):"
    r"(?:\s?(?P<message>.*))?$"
)
HEADER_LIKE = re.compile(
    r"^\[[^\]\r\n]+\]\s+[A-Za-z0-9_.-]+\.[A-Za-z]+:"
)
HEADER_LIKE_BYTES = re.compile(
    rb"^\[[^\]\r\n]+\]\s+[A-Za-z0-9_.-]+\.[A-Za-z]+:"
)

FAILURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "exception",
        re.compile(
            r"\b(?:[A-Za-z_][A-Za-z0-9_\\]*Exception|Exception)"
            r"(?=\s*(?::|\(|\[|$))|"
            r"\bexception\s+(?:thrown|caught|during|while)\b|"
            r"\b(?:Throwable|TypeError|ValueError|ArgumentCountError|ParseError|"
            r"CompileError|AssertionError|ArithmeticError|DivisionByZeroError|"
            r"UnhandledMatchError|FiberError)\b|"
            r'["\'](?:exception_type|exception_class|throwable_type|error_type)["\']'
            r'\s*:\s*["\'][^"\']*(?:Exception|Throwable|Error)["\']|'
            r'"exception"\s*:\s*"\[object\]',
            re.IGNORECASE,
        ),
    ),
    (
        "trace",
        re.compile(
            r"(?:^|\n)\s*\[stacktrace\]\s*(?:\n|$)|"
            r"(?:^|\n)\s*stack trace\s*:|"
            r"(?:^|\n)\s*#\d+\s+(?:\S|\{main\})",
            re.IGNORECASE,
        ),
    ),
    (
        "fatal",
        re.compile(r"\b(?:PHP\s+)?fatal error\b|\buncaught\s+", re.IGNORECASE),
    ),
    ("sqlstate", re.compile(r"\bSQLSTATE\s*\[", re.IGNORECASE)),
    (
        "missing_class",
        re.compile(
            r"\b(?:class|interface|trait)\s+[\"'][^\"']+[\"']\s+not found\b|"
            r"\btarget class\s+\[[^\]]+\]\s+does not exist\b|"
            r"\bclass\s+[^\r\n]+\s+does not exist\b",
            re.IGNORECASE,
        ),
    ),
    (
        "missing_view",
        re.compile(
            r"\bview\s+\[[^\]]+\]\s+not found\b|"
            r"\bview\s+[\"'][^\"']+[\"']\s+not found\b",
            re.IGNORECASE,
        ),
    ),
)

STALE_COOKIE_HASH_EQUALS = re.compile(
    r"hash_equals\(\):\s*Argument\s+#1\s+\(\$known_string\)\s+"
    r"must be of type string,\s*null given",
    re.IGNORECASE,
)
STALE_COOKIE_SESSION_GUARD = re.compile(
    r"(?:Illuminate[\\/]Auth[\\/]SessionGuard|SessionGuard\.php|userFromRecaller)",
    re.IGNORECASE,
)

DEPENDENCY_CANDIDATE_MARKERS: tuple[str, ...] = (
    "laravel 12.69.1",
    "laravel/framework",
    "illuminate/auth/sessionguard",
    "illuminate\\auth\\sessionguard",
    "sessionguard.php",
    "userfromrecaller",
    "hash_equals",
    "remember cookie",
    "remember-cookie",
    "recaller",
    "vendor/autoload.php",
    "composer.lock",
)

FAILURE_LEVELS = frozenset({"ERROR", "CRITICAL", "ALERT", "EMERGENCY"})
ALWAYS_FATAL_LEVELS = frozenset({"CRITICAL", "ALERT", "EMERGENCY"})
CANDIDATE_FAILURE_WORDS = re.compile(
    r"\b(?:error|exception|fail(?:ed|ure)?|fatal|uncaught|invalid|missing|"
    r"not found|undefined|unable|cannot|could not)\b",
    re.IGNORECASE,
)
FAILURE_MESSAGE_WORDS = re.compile(
    r"\b(?:error|fail(?:ed|ure)?)\b",
    re.IGNORECASE,
)

LOG_CONTEXT_LIMIT = 1024 * 1024
LOG_ANCHOR_LIMIT = 64 * 1024
LOG_DELTA_LIMIT = 20 * 1024 * 1024
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
UTC_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

INDEPENDENT_REVIEW_ARTIFACT = "buy-dtf-laravel-log-independent-review-v1"
INDEPENDENT_REVIEW_CHECKS = {
    "raw_private_delta_reviewed_read_only": True,
    "parsed_delta_status_pass": True,
    "stale_remember_cookie_absent": True,
    "genuine_exceptions_absent": True,
    "critical_alert_emergency_absent": True,
    "invalid_utf8_absent": True,
    "unparsed_or_orphan_data_absent": True,
}
REVIEW_BINDING_FIELDS = frozenset(
    {
        "deployment_state_sha256",
        "release_receipt_sha256",
        "runner_sha256",
        "runtime_helper_sha256",
        "parser_sha256",
        "raw_manifest_sha256",
        "analysis_summary_sha256",
        "monitor_samples_sha256",
        "database_envelope_sha256",
    }
)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _private_directory(path: Path, *, create: bool) -> Path:
    if create:
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Private Laravel log evidence path is not a real directory.")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError("Private Laravel log evidence directory must have mode 0700.")
    return path.resolve(strict=True)


def _write_private_file(path: Path, content: bytes, *, exclusive: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600, follow_symlinks=False)
    fsync_directory(path.parent)


def _atomic_private_json(path: Path, payload: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    _write_private_file(temporary, canonical_bytes(payload), exclusive=True)
    os.replace(temporary, path)
    os.chmod(path, 0o600, follow_symlinks=False)
    fsync_directory(path.parent)


@dataclass(frozen=True)
class LaravelLogEntry:
    """One Laravel log entry, including all continuation lines."""

    number: int
    timestamp: str | None
    channel: str | None
    level: str | None
    message: str
    raw: str
    orphan: bool = False

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.raw.encode("utf-8"))


class LaravelLogDeltaError(RuntimeError):
    """A captured delta contains a fail-closed parser finding."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        analysis = report.get("summary", {}).get("analysis", report)
        signals = ", ".join(sorted(analysis.get("signal_counts", {})))
        super().__init__(
            "Laravel log delta contains "
            f"{analysis.get('fatal_finding_count', 0)} fail-closed finding(s)"
            f" (signals: {signals})."
        )


class LogContinuityError(RuntimeError):
    """The rotation-safe collector cannot prove an append-only delta."""

    def __init__(self, signal: str, details: dict[str, Any] | None = None):
        self.signal = signal
        self.details = details or {}
        super().__init__(f"Laravel log continuity failed closed: {signal}.")


class IndependentReviewError(RuntimeError):
    """An independent log-review receipt is invalid or not bound to evidence."""


def _make_entry(lines: list[str], number: int, *, orphan: bool) -> LaravelLogEntry:
    raw = "\n".join(lines)
    if orphan:
        return LaravelLogEntry(number, None, None, None, raw, raw, True)
    match = ENTRY_HEADER.match(lines[0])
    if match is None:
        raise ValueError("Laravel entry did not begin with a valid header.")
    first_message = match.group("message") or ""
    continuation = lines[1:]
    message = "\n".join([first_message, *continuation]) if continuation else first_message
    return LaravelLogEntry(
        number=number,
        timestamp=match.group("timestamp"),
        channel=match.group("channel"),
        level=match.group("level"),
        message=message,
        raw=raw,
    )


def parse_laravel_entries(text: str) -> list[LaravelLogEntry]:
    """Parse Laravel headers with all continuations; retain nonempty orphans."""

    entries: list[LaravelLogEntry] = []
    current: list[str] = []
    current_is_orphan = False

    def flush() -> None:
        nonlocal current, current_is_orphan
        if not current or not any(line.strip() for line in current):
            current = []
            current_is_orphan = False
            return
        entries.append(_make_entry(current, len(entries) + 1, orphan=current_is_orphan))
        current = []
        current_is_orphan = False

    for line in text.splitlines():
        line = line.rstrip("\r")
        if ENTRY_HEADER.match(line):
            flush()
            current = [line]
            current_is_orphan = False
            continue
        if HEADER_LIKE.match(line):
            flush()
            current = [line]
            current_is_orphan = True
            continue
        if not current:
            if not line.strip():
                continue
            current_is_orphan = True
        current.append(line)
    flush()
    return entries


def _candidate_related(entry: LaravelLogEntry, markers: Iterable[str]) -> bool:
    lowered = entry.message.lower()
    if not any(marker.lower() in lowered for marker in markers):
        return False
    return entry.level in FAILURE_LEVELS or bool(CANDIDATE_FAILURE_WORDS.search(entry.message))


def classify_entry(
    entry: LaravelLogEntry,
    *,
    candidate_markers: Iterable[str] = DEPENDENCY_CANDIDATE_MARKERS,
) -> tuple[str, ...]:
    """Return fail-closed signals present in one complete Laravel entry."""

    signals = [name for name, pattern in FAILURE_PATTERNS if pattern.search(entry.raw)]
    if STALE_COOKIE_HASH_EQUALS.search(entry.raw) and STALE_COOKIE_SESSION_GUARD.search(
        entry.raw
    ):
        signals.append("stale_remember_cookie")
    if entry.orphan:
        signals.append("unparsed_data")
    if entry.level in ALWAYS_FATAL_LEVELS:
        signals.append("severe_level")
    if _candidate_related(entry, candidate_markers):
        signals.append("candidate_error")
    if (
        entry.level in FAILURE_LEVELS
        and FAILURE_MESSAGE_WORDS.search(entry.message)
        and not {"exception", "fatal", "candidate_error"}.intersection(signals)
    ):
        signals.append("failure_message")
    return tuple(dict.fromkeys(signals))


def analyze_log_bytes(
    content: bytes,
    *,
    candidate_markers: Iterable[str] = DEPENDENCY_CANDIDATE_MARKERS,
) -> dict[str, Any]:
    """Return a message-free parser report for raw Laravel log bytes."""

    invalid_utf8 = False
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        invalid_utf8 = True
        text = content.decode("utf-8", errors="replace")
    entries = parse_laravel_entries(text)
    candidate_markers = tuple(candidate_markers)
    level_counts = Counter(entry.level or "UNPARSED" for entry in entries)
    findings: list[dict[str, Any]] = []
    signal_counts: Counter[str] = Counter()

    if invalid_utf8:
        signal_counts.update(["invalid_utf8"])
        findings.append(
            {
                "entry_number": 0,
                "level": None,
                "signals": ["invalid_utf8"],
                "entry_sha256": sha256_bytes(content),
            }
        )

    if content and not content.endswith(b"\n"):
        signal_counts.update(["incomplete_trailing_data"])
        findings.append(
            {
                "entry_number": 0,
                "level": None,
                "signals": ["incomplete_trailing_data"],
                "entry_sha256": sha256_bytes(content),
            }
        )

    for entry in entries:
        signals = classify_entry(entry, candidate_markers=candidate_markers)
        if not signals:
            continue
        signal_counts.update(signals)
        findings.append(
            {
                "entry_number": entry.number,
                "level": entry.level,
                "signals": list(signals),
                "entry_sha256": entry.sha256,
            }
        )

    fatal_numbers = {
        finding["entry_number"] for finding in findings if finding["entry_number"] > 0
    }
    report: dict[str, Any] = {
        "status": "fail" if findings else "pass",
        "bytes": len(content),
        "sha256": sha256_bytes(content),
        "entry_count": len(entries),
        "orphan_entry_count": sum(entry.orphan for entry in entries),
        "invalid_utf8": invalid_utf8,
        "decode_replacement_count": text.count("\ufffd") if invalid_utf8 else 0,
        "level_counts": dict(sorted(level_counts.items())),
        "nonfatal_error_entry_count": sum(
            entry.level in FAILURE_LEVELS and entry.number not in fatal_numbers
            for entry in entries
        ),
        "fatal_entry_count": len(fatal_numbers),
        "global_failure_count": sum(
            finding["entry_number"] == 0 for finding in findings
        ),
        "fatal_finding_count": len(findings),
        "rollback_finding_count": len(findings),
        "signal_counts": dict(sorted(signal_counts.items())),
        "fatal_findings": findings,
    }
    return report


def inspect_log_bytes(
    content: bytes,
    *,
    candidate_markers: Iterable[str] = DEPENDENCY_CANDIDATE_MARKERS,
) -> dict[str, Any]:
    report = analyze_log_bytes(content, candidate_markers=candidate_markers)
    if report["fatal_finding_count"]:
        raise LaravelLogDeltaError(report)
    return report


def _first_header_offset(content: bytes) -> int | None:
    offset = 0
    for line in content.splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        if not body.strip():
            offset += len(line)
            continue
        return offset if HEADER_LIKE_BYTES.match(body) else None
    return len(content)


def _latest_entry_context(descriptor: int, end: int) -> tuple[bytes, bool]:
    if end == 0:
        return b"", True
    read_start = max(0, end - LOG_CONTEXT_LIMIT - 1)
    window = os.pread(descriptor, end - read_start, read_start)
    if len(window) != end - read_start:
        raise LogContinuityError("baseline_context_changed")
    search_start = 0
    if read_start:
        first_newline = window.find(b"\n")
        if first_newline < 0:
            raise LogContinuityError("baseline_entry_exceeds_context_limit")
        search_start = first_newline + 1
    matches = list(re.finditer(rb"(?m)^\[[^\]\r\n]+\]\s+[A-Za-z0-9_.-]+\.[A-Za-z]+:", window[search_start:]))
    if not matches:
        raise LogContinuityError("baseline_has_no_parseable_entry_boundary")
    entry_start = search_start + matches[-1].start()
    context = window[entry_start:]
    if len(context) > LOG_CONTEXT_LIMIT:
        raise LogContinuityError("baseline_entry_exceeds_context_limit")
    return context, window.endswith(b"\n")


def _anchor(descriptor: int, cursor: int) -> dict[str, Any]:
    size = min(cursor, LOG_ANCHOR_LIMIT)
    start = cursor - size
    value = os.pread(descriptor, size, start)
    if len(value) != size:
        raise LogContinuityError("anchor_read_changed")
    return {"start": start, "bytes": size, "sha256": sha256_bytes(value)}


@dataclass
class _CapturedSegment:
    descriptor: int
    device: int
    inode: int
    segment_id: str
    discovered_name: str
    discovered_at_utc: str
    baseline: bool
    start_offset: int
    cursor: int
    observed_size: int
    observed_mtime_ns: int
    context: bytes
    ends_at_line_boundary: bool
    anchor: dict[str, Any]
    aliases: set[str] = field(default_factory=set)
    chunks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def key(self) -> tuple[int, int]:
        return self.device, self.inode


class RotationSafeLaravelLogCollector:
    """Capture an append-only delta across rename rotations.

    The collector holds every observed generation open. Rename rotation is
    therefore safe even when the rotated pathname is later removed. Any size
    regression or boundary-anchor rewrite fails closed; copy-truncate cannot be
    accepted because bytes may have disappeared between samples.
    """

    def __init__(
        self,
        log_path: Path,
        private_directory: Path,
        *,
        delta_limit: int = LOG_DELTA_LIMIT,
    ):
        if log_path.is_symlink():
            raise LogContinuityError("log_path_is_symlink")
        self.log_directory = log_path.parent.resolve(strict=True)
        self.log_path = self.log_directory / log_path.name
        if self.log_directory.is_symlink() or not self.log_directory.is_dir():
            raise LogContinuityError("log_directory_invalid")
        self.private_directory = _private_directory(private_directory, create=True)
        self.delta_limit = delta_limit
        self.state_path = self.private_directory / "capture-state.json"
        self.raw_manifest_path = self.private_directory / "raw-manifest.json"
        self.analysis_path = self.private_directory / "redacted-analysis.json"
        self._segments: dict[tuple[int, int], _CapturedSegment] = {}
        self._baseline_known: set[tuple[int, int]] = set()
        self._active_key: tuple[int, int] | None = None
        self._next_segment = 1
        self._next_chunk = 1
        self._total_bytes = 0
        self._closed = False
        self._status = "initializing"
        self._events: list[dict[str, Any]] = []
        self._started_at_utc = utc_now()
        self._rotation_pattern = self._make_rotation_pattern(self.log_path.name)
        self._open_baseline()

    @staticmethod
    def _make_rotation_pattern(name: str) -> re.Pattern[str]:
        path = Path(name)
        stem = re.escape(path.stem)
        suffix = re.escape(path.suffix)
        exact = re.escape(name)
        return re.compile(
            rf"(?:{exact}|{exact}\.\d+|{stem}-\d{{4}}-\d{{2}}-\d{{2}}{suffix})"
        )

    def __enter__(self) -> "RotationSafeLaravelLogCollector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _eligible_paths(self) -> list[Path]:
        paths: list[Path] = []
        for item in self.log_directory.iterdir():
            if self._rotation_pattern.fullmatch(item.name):
                paths.append(item)
        return sorted(paths, key=lambda item: (item.name != self.log_path.name, item.name))

    def _open_regular(self, path: Path) -> tuple[int, os.stat_result]:
        try:
            listed = path.lstat()
        except FileNotFoundError as exception:
            raise LogContinuityError("log_path_disappeared") from exception
        if not stat.S_ISREG(listed.st_mode) or stat.S_ISLNK(listed.st_mode):
            raise LogContinuityError("log_path_not_regular", {"name": path.name})
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            os.close(descriptor)
            raise LogContinuityError("log_descriptor_not_regular", {"name": path.name})
        if (listed.st_dev, listed.st_ino) != (metadata.st_dev, metadata.st_ino):
            os.close(descriptor)
            raise LogContinuityError("log_path_raced", {"name": path.name})
        return descriptor, metadata

    def _open_baseline(self) -> None:
        eligible = self._eligible_paths()
        exact = [path for path in eligible if path.name == self.log_path.name]
        if len(exact) != 1:
            raise LogContinuityError("baseline_log_missing_or_ambiguous")
        for path in eligible:
            descriptor, metadata = self._open_regular(path)
            key = (metadata.st_dev, metadata.st_ino)
            self._baseline_known.add(key)
            if path.name != self.log_path.name:
                os.close(descriptor)
                continue
            context, ends_at_line_boundary = _latest_entry_context(
                descriptor, metadata.st_size
            )
            segment = _CapturedSegment(
                descriptor=descriptor,
                device=metadata.st_dev,
                inode=metadata.st_ino,
                segment_id=f"segment-{self._next_segment:04d}",
                discovered_name=path.name,
                discovered_at_utc=self._started_at_utc,
                baseline=True,
                start_offset=metadata.st_size,
                cursor=metadata.st_size,
                observed_size=metadata.st_size,
                observed_mtime_ns=metadata.st_mtime_ns,
                context=context,
                ends_at_line_boundary=ends_at_line_boundary,
                anchor=_anchor(descriptor, metadata.st_size),
                aliases={path.name},
            )
            self._segments[key] = segment
            self._active_key = key
            self._next_segment += 1
        self._status = "capturing"
        self._events.append({"at_utc": self._started_at_utc, "event": "baseline"})
        self._write_state()

    def _discover(self) -> None:
        eligible = self._eligible_paths()
        if not any(path.name == self.log_path.name for path in eligible):
            self._fail("active_log_path_missing")
        discoveries: list[tuple[Path, int, os.stat_result]] = []
        exact_key: tuple[int, int] | None = None
        for path in eligible:
            descriptor, metadata = self._open_regular(path)
            key = (metadata.st_dev, metadata.st_ino)
            if path.name == self.log_path.name:
                exact_key = key
            if key in self._segments:
                self._segments[key].aliases.add(path.name)
                os.close(descriptor)
                continue
            if key in self._baseline_known and path.name != self.log_path.name:
                os.close(descriptor)
                continue
            discoveries.append((path, descriptor, metadata))

        discoveries.sort(key=lambda item: (item[2].st_ctime_ns, item[0].name))
        for path, descriptor, metadata in discoveries:
            key = (metadata.st_dev, metadata.st_ino)
            if key in self._segments:
                os.close(descriptor)
                continue
            segment = _CapturedSegment(
                descriptor=descriptor,
                device=metadata.st_dev,
                inode=metadata.st_ino,
                segment_id=f"segment-{self._next_segment:04d}",
                discovered_name=path.name,
                discovered_at_utc=utc_now(),
                baseline=False,
                start_offset=0,
                cursor=0,
                observed_size=0,
                observed_mtime_ns=metadata.st_mtime_ns,
                context=b"",
                ends_at_line_boundary=True,
                anchor=_anchor(descriptor, 0),
                aliases={path.name},
            )
            self._segments[key] = segment
            self._next_segment += 1
            self._events.append(
                {
                    "at_utc": segment.discovered_at_utc,
                    "event": "rotation_generation_discovered",
                    "segment_id": segment.segment_id,
                }
            )
        if exact_key is None or exact_key not in self._segments:
            self._fail("active_log_identity_untracked")
        if exact_key != self._active_key:
            previous = self._segments.get(self._active_key) if self._active_key else None
            current = self._segments[exact_key]
            self._events.append(
                {
                    "at_utc": utc_now(),
                    "event": "rename_rotation",
                    "from_segment_id": previous.segment_id if previous else None,
                    "to_segment_id": current.segment_id,
                }
            )
            self._active_key = exact_key

    def _verify_segment(self, segment: _CapturedSegment) -> os.stat_result:
        metadata = os.fstat(segment.descriptor)
        if (metadata.st_dev, metadata.st_ino) != segment.key:
            self._fail("open_descriptor_identity_changed", segment=segment)
        if metadata.st_size < segment.cursor:
            self._fail(
                "log_truncated",
                segment=segment,
                observed_size=metadata.st_size,
                expected_minimum=segment.cursor,
            )
        anchor = segment.anchor
        observed = os.pread(segment.descriptor, anchor["bytes"], anchor["start"])
        if len(observed) != anchor["bytes"] or sha256_bytes(observed) != anchor["sha256"]:
            self._fail("log_continuity_anchor_changed", segment=segment)
        if (
            metadata.st_size == segment.cursor
            and metadata.st_mtime_ns != segment.observed_mtime_ns
        ):
            self._fail("log_modified_without_append", segment=segment)
        return metadata

    def _fail(
        self,
        signal: str,
        *,
        segment: _CapturedSegment | None = None,
        **details: Any,
    ) -> None:
        safe_details = dict(details)
        if segment is not None:
            safe_details["segment_id"] = segment.segment_id
        self._status = "fail"
        self._events.append(
            {"at_utc": utc_now(), "event": "continuity_failure", "signal": signal}
        )
        self._write_state()
        raise LogContinuityError(signal, safe_details)

    def _write_state(self) -> None:
        active = self._segments.get(self._active_key) if self._active_key else None
        payload = {
            "artifact": "buy-dtf-laravel-log-capture-state-v1",
            "status": self._status,
            "started_at_utc": self._started_at_utc,
            "updated_at_utc": utc_now(),
            "log_name": self.log_path.name,
            "delta_limit": self.delta_limit,
            "captured_bytes": self._total_bytes,
            "active_segment_id": active.segment_id if active else None,
            "rotation_count": sum(
                event["event"] == "rename_rotation" for event in self._events
            ),
            "segments": [self._segment_receipt(segment) for segment in self._ordered_segments()],
            "events": self._events,
        }
        _atomic_private_json(self.state_path, payload)

    def _ordered_segments(self) -> list[_CapturedSegment]:
        return sorted(self._segments.values(), key=lambda segment: segment.segment_id)

    @staticmethod
    def _segment_receipt(segment: _CapturedSegment) -> dict[str, Any]:
        return {
            "segment_id": segment.segment_id,
            "device": segment.device,
            "inode": segment.inode,
            "baseline": segment.baseline,
            "discovered_name": segment.discovered_name,
            "discovered_at_utc": segment.discovered_at_utc,
            "aliases": sorted(segment.aliases),
            "start_offset": segment.start_offset,
            "cursor": segment.cursor,
            "observed_size": segment.observed_size,
            "observed_mtime_ns": segment.observed_mtime_ns,
            "context_bytes": len(segment.context),
            "context_sha256": sha256_bytes(segment.context),
            "ends_at_line_boundary": segment.ends_at_line_boundary,
            "anchor": segment.anchor,
            "chunks": [dict(chunk) for chunk in segment.chunks],
        }

    def capture(self) -> dict[str, Any]:
        if self._closed or self._status != "capturing":
            raise LogContinuityError("collector_not_capturing")
        self._discover()
        captured_this_sample = 0
        for segment in self._ordered_segments():
            metadata = self._verify_segment(segment)
            length = metadata.st_size - segment.cursor
            if length:
                if self._total_bytes + length > self.delta_limit:
                    self._fail("log_delta_limit_exceeded", segment=segment)
                content = os.pread(segment.descriptor, length, segment.cursor)
                if len(content) != length:
                    self._fail("log_changed_during_read", segment=segment)
                chunk_name = f"{segment.segment_id}-chunk-{self._next_chunk:04d}.bin"
                chunk_path = self.private_directory / chunk_name
                _write_private_file(chunk_path, content, exclusive=True)
                segment.chunks.append(
                    {
                        "name": chunk_name,
                        "bytes": length,
                        "sha256": sha256_bytes(content),
                        "start": segment.cursor,
                        "end": metadata.st_size,
                    }
                )
                self._next_chunk += 1
                self._total_bytes += length
                captured_this_sample += length
                segment.cursor = metadata.st_size
            segment.observed_size = metadata.st_size
            segment.observed_mtime_ns = metadata.st_mtime_ns
            segment.anchor = _anchor(segment.descriptor, segment.cursor)
        sampled_at = utc_now()
        self._events.append(
            {
                "at_utc": sampled_at,
                "event": "sample",
                "captured_bytes": captured_this_sample,
            }
        )
        self._write_state()
        return {
            "status": "pass",
            "sampled_at_utc": sampled_at,
            "captured_bytes": captured_this_sample,
            "cumulative_bytes": self._total_bytes,
            "segment_count": len(self._segments),
            "capture_state_sha256": sha256_file(self.state_path),
        }

    def _segment_delta(self, segment: _CapturedSegment) -> bytes:
        values: list[bytes] = []
        expected_start = segment.observed_size if not segment.chunks else segment.chunks[0]["start"]
        for index, chunk in enumerate(segment.chunks):
            path = self.private_directory / chunk["name"]
            if path.is_symlink() or not path.is_file():
                self._fail("private_chunk_invalid", segment=segment)
            metadata = path.stat()
            if stat.S_IMODE(metadata.st_mode) != 0o600:
                self._fail("private_chunk_mode_changed", segment=segment)
            value = path.read_bytes()
            if len(value) != chunk["bytes"] or sha256_bytes(value) != chunk["sha256"]:
                self._fail("private_chunk_identity_changed", segment=segment)
            if index == 0:
                expected_start = chunk["start"]
            if chunk["start"] != expected_start:
                self._fail("private_chunk_range_gap", segment=segment)
            expected_start = chunk["end"]
            values.append(value)
        return b"".join(values)

    def finish(self, *, raise_on_failure: bool = True) -> dict[str, Any]:
        self.capture()
        segment_reports: list[dict[str, Any]] = []
        raw_segments: list[dict[str, Any]] = []
        framed = hashlib.sha256()
        for segment in self._ordered_segments():
            delta = self._segment_delta(segment)
            analysis_delta_offset = 0
            analysis_context: dict[str, Any] | None = None
            if segment.baseline and delta:
                first_header = (
                    _first_header_offset(delta)
                    if segment.ends_at_line_boundary
                    else None
                )
                if first_header == 0:
                    inspection = delta
                else:
                    inspection = segment.context + delta
                    if segment.context:
                        context_name = f"{segment.segment_id}-analysis-context.bin"
                        context_path = self.private_directory / context_name
                        _write_private_file(
                            context_path,
                            segment.context,
                            exclusive=True,
                        )
                        analysis_context = {
                            "name": context_name,
                            "bytes": len(segment.context),
                            "sha256": sha256_bytes(segment.context),
                        }
            else:
                inspection = delta
            report = analyze_log_bytes(inspection)
            for finding in report["fatal_findings"]:
                finding["segment_id"] = segment.segment_id
            segment_reports.append(
                {
                    "segment_id": segment.segment_id,
                    "start_offset": segment.start_offset,
                    "final_offset": segment.cursor,
                    "delta_bytes": len(delta),
                    "delta_sha256": sha256_bytes(delta),
                    "analysis_bytes": len(inspection),
                    "analysis_sha256": sha256_bytes(inspection),
                    "analysis": report,
                }
            )
            raw_segments.append(
                {
                    "segment_id": segment.segment_id,
                    "device": segment.device,
                    "inode": segment.inode,
                    "baseline": segment.baseline,
                    "start_offset": segment.start_offset,
                    "final_offset": segment.cursor,
                    "delta_bytes": len(delta),
                    "delta_sha256": sha256_bytes(delta),
                    "analysis_delta_offset": analysis_delta_offset,
                    "analysis_context": analysis_context,
                    "chunks": [dict(chunk) for chunk in segment.chunks],
                }
            )
            identifier = segment.segment_id.encode("utf-8")
            framed.update(len(identifier).to_bytes(4, "big"))
            framed.update(identifier)
            framed.update(len(delta).to_bytes(8, "big"))
            framed.update(delta)

        aggregate = aggregate_reports(segment_reports)
        raw_manifest = {
            "artifact": "buy-dtf-laravel-log-private-raw-manifest-v1",
            "classification": "private-do-not-commit",
            "status": "captured",
            "started_at_utc": self._started_at_utc,
            "completed_at_utc": utc_now(),
            "framing": "uint32-id-length || id || uint64-content-length || content",
            "framed_delta_sha256": framed.hexdigest(),
            "captured_bytes": self._total_bytes,
            "rotation_history": [
                event for event in self._events if event["event"] == "rename_rotation"
            ],
            "segments": raw_segments,
        }
        _atomic_private_json(self.raw_manifest_path, raw_manifest)
        raw_manifest_sha256 = sha256_file(self.raw_manifest_path)
        summary = {
            "artifact": "buy-dtf-laravel-log-redacted-analysis-v1",
            "classification": "message-free-redacted-summary",
            "status": aggregate["status"],
            "started_at_utc": self._started_at_utc,
            "completed_at_utc": raw_manifest["completed_at_utc"],
            "captured_bytes": self._total_bytes,
            "segment_count": len(segment_reports),
            "framed_delta_sha256": framed.hexdigest(),
            "raw_manifest_sha256": raw_manifest_sha256,
            "analysis": aggregate,
            "segments": segment_reports,
        }
        _atomic_private_json(self.analysis_path, summary)
        self._status = "analysis_pass" if aggregate["status"] == "pass" else "analysis_fail"
        self._events.append(
            {
                "at_utc": utc_now(),
                "event": "analysis_complete",
                "status": aggregate["status"],
            }
        )
        self._write_state()
        result = {
            "status": aggregate["status"],
            "raw_manifest_path": str(self.raw_manifest_path),
            "raw_manifest_sha256": raw_manifest_sha256,
            "analysis_path": str(self.analysis_path),
            "analysis_sha256": sha256_file(self.analysis_path),
            "capture_state_path": str(self.state_path),
            "capture_state_sha256": sha256_file(self.state_path),
            "summary": summary,
        }
        self.close()
        if aggregate["status"] != "pass" and raise_on_failure:
            raise LaravelLogDeltaError(result)
        return result

    def close(self) -> None:
        if self._closed:
            return
        for segment in self._segments.values():
            try:
                os.close(segment.descriptor)
            except OSError:
                pass
        self._closed = True


def aggregate_reports(segment_reports: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Combine message-free segment reports without losing failure identity."""

    level_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    findings: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    invalid_utf8 = False
    segments = list(segment_reports)
    for segment in segments:
        report = segment["analysis"]
        level_counts.update(report["level_counts"])
        signal_counts.update(report["signal_counts"])
        findings.extend(report["fatal_findings"])
        invalid_utf8 = invalid_utf8 or report["invalid_utf8"]
        for key in (
            "bytes",
            "entry_count",
            "orphan_entry_count",
            "decode_replacement_count",
            "nonfatal_error_entry_count",
            "fatal_entry_count",
            "global_failure_count",
            "fatal_finding_count",
            "rollback_finding_count",
        ):
            totals[key] += int(report[key])
    return {
        "status": "fail" if findings else "pass",
        "bytes": totals["bytes"],
        "entry_count": totals["entry_count"],
        "orphan_entry_count": totals["orphan_entry_count"],
        "invalid_utf8": invalid_utf8,
        "decode_replacement_count": totals["decode_replacement_count"],
        "level_counts": dict(sorted(level_counts.items())),
        "nonfatal_error_entry_count": totals["nonfatal_error_entry_count"],
        "fatal_entry_count": totals["fatal_entry_count"],
        "global_failure_count": totals["global_failure_count"],
        "fatal_finding_count": totals["fatal_finding_count"],
        "rollback_finding_count": totals["rollback_finding_count"],
        "signal_counts": dict(sorted(signal_counts.items())),
        "fatal_findings": findings,
    }


def build_independent_review_binding(**identities: str) -> dict[str, str]:
    """Build the exact evidence binding an independent receipt must repeat."""

    if set(identities) != REVIEW_BINDING_FIELDS:
        missing = sorted(REVIEW_BINDING_FIELDS - set(identities))
        extra = sorted(set(identities) - REVIEW_BINDING_FIELDS)
        raise IndependentReviewError(
            f"Independent review binding fields differ (missing={missing}, extra={extra})."
        )
    for name, value in identities.items():
        if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
            raise IndependentReviewError(f"Independent review binding {name} is not SHA-256.")
    return dict(sorted(identities.items()))


def validate_independent_review_receipt(
    receipt_path: Path,
    *,
    expected_sha256: str,
    expected_binding: dict[str, str],
) -> dict[str, Any]:
    """Validate an externally created, evidence-bound read-only review receipt."""

    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise IndependentReviewError("Independent review receipt is not a regular file.")
    if SHA256_PATTERN.fullmatch(expected_sha256) is None:
        raise IndependentReviewError("Expected independent review receipt hash is invalid.")
    if sha256_file(receipt_path) != expected_sha256:
        raise IndependentReviewError("Independent review receipt hash differs.")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise IndependentReviewError("Independent review receipt is invalid JSON.") from exception
    required_keys = {
        "artifact",
        "status",
        "decision",
        "review_mode",
        "reviewed_at_utc",
        "reviewer_id",
        "evidence_binding",
        "checks",
    }
    if not isinstance(receipt, dict) or set(receipt) != required_keys:
        raise IndependentReviewError("Independent review receipt shape differs.")
    if receipt["artifact"] != INDEPENDENT_REVIEW_ARTIFACT:
        raise IndependentReviewError("Independent review artifact differs.")
    if receipt["status"] != "pass" or receipt["decision"] != "accept":
        raise IndependentReviewError("Independent log review did not pass.")
    if receipt["review_mode"] != "independent_read_only":
        raise IndependentReviewError("Independent log review mode differs.")
    if not isinstance(receipt["reviewer_id"], str) or not receipt["reviewer_id"].strip():
        raise IndependentReviewError("Independent log review has no reviewer identity.")
    if not isinstance(receipt["reviewed_at_utc"], str) or UTC_PATTERN.fullmatch(
        receipt["reviewed_at_utc"]
    ) is None:
        raise IndependentReviewError("Independent log review timestamp is invalid.")
    validated_binding = build_independent_review_binding(**expected_binding)
    if receipt["evidence_binding"] != validated_binding:
        raise IndependentReviewError("Independent log review evidence binding differs.")
    if receipt["checks"] != INDEPENDENT_REVIEW_CHECKS:
        raise IndependentReviewError("Independent log review checks differ or are incomplete.")
    return receipt


__all__ = [
    "DEPENDENCY_CANDIDATE_MARKERS",
    "INDEPENDENT_REVIEW_ARTIFACT",
    "INDEPENDENT_REVIEW_CHECKS",
    "IndependentReviewError",
    "LaravelLogDeltaError",
    "LaravelLogEntry",
    "LogContinuityError",
    "RotationSafeLaravelLogCollector",
    "aggregate_reports",
    "analyze_log_bytes",
    "build_independent_review_binding",
    "classify_entry",
    "inspect_log_bytes",
    "parse_laravel_entries",
    "sha256_bytes",
    "sha256_file",
    "validate_independent_review_receipt",
]
