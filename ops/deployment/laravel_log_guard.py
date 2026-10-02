#!/usr/bin/env python3
"""Parse Laravel log entries and identify rollback-worthy failures.

Laravel's ``<channel>.<LEVEL>`` field is metadata, not proof that an
application failed.  This guard therefore classifies complete entries,
including continuation lines, and fails only on reviewed failure signals.
The returned reports contain hashes and classifications rather than log
messages so they can be copied into deployment receipts without disclosing
customer or carrier data.
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
import re
from typing import Any, Iterable


ENTRY_HEADER = re.compile(
    r"^\[(?P<timestamp>[^\]\r\n]+)\]\s+"
    r"(?P<channel>[A-Za-z0-9_.-]+?)\."
    r"(?P<level>DEBUG|INFO|NOTICE|WARNING|ERROR|CRITICAL|ALERT|EMERGENCY):"
    r"(?:\s?(?P<message>.*))?$"
)
HEADER_LIKE = re.compile(
    r"^\[[^\]\r\n]+\]\s+[A-Za-z0-9_.-]+\.[A-Za-z]+:"
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

PRODUCTION_ALPHA_CANDIDATE_MARKERS: tuple[str, ...] = (
    "production alpha",
    "productionalphabounds",
    "productionalphathreshold",
    "productionalphapolicyidentity",
    "thresholdalphamask",
    "fully_transparent_image",
    "alpha-preserving",
    "2026_10_01_120000_add_item_meta_to_savedimages_table",
    "savedimages.item_meta",
    "savedimages item_meta",
    "app/helpers/imagehelper.php",
    "app/helpers/productionhelper.php",
    "app/http/controllers/admin/orderimagecontroller.php",
    "app/http/controllers/cartcontroller.php",
    "app/http/controllers/teamcustomizationcontroller.php",
    "app/models/dtfimage.php",
    "app/models/savedimage.php",
    "imagehelper::",
    "productionhelper::",
    "orderimagecontroller",
    "teamcustomizationcontroller",
    "savedimage",
    "compare probe failed",
    "image probe failed",
    "upload processing failed",
    "attachtoorder failed",
    "failed to prepare image for production",
)

CANDIDATE_FAILURE_WORDS = re.compile(
    r"\b(?:error|exception|fail(?:ed|ure)?|fatal|uncaught|invalid|missing|"
    r"not found|undefined|unable|cannot|could not)\b",
    re.IGNORECASE,
)

FAILURE_LEVELS = frozenset({"ERROR", "CRITICAL", "ALERT", "EMERGENCY"})
ALWAYS_FATAL_LEVELS = frozenset({"CRITICAL", "ALERT", "EMERGENCY"})
FAILURE_MESSAGE_WORDS = re.compile(
    r"\b(?:error|fail(?:ed|ure)?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LaravelLogEntry:
    """One Laravel entry, including all multiline continuation lines."""

    number: int
    timestamp: str | None
    channel: str | None
    level: str | None
    message: str
    raw: str
    orphan: bool = False

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw.encode("utf-8")).hexdigest()


class LaravelLogGuardError(RuntimeError):
    """Raised when a parsed log contains rollback-worthy failure signals."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        signals = ", ".join(sorted(report["signal_counts"]))
        super().__init__(
            "Laravel log guard found "
            f"{report['fatal_finding_count']} rollback-worthy finding"
            f"{'s' if report['fatal_finding_count'] != 1 else ''}"
            f" (signals: {signals})."
        )


def _make_entry(lines: list[str], number: int, *, orphan: bool) -> LaravelLogEntry:
    raw = "\n".join(lines)
    if orphan:
        return LaravelLogEntry(
            number=number,
            timestamp=None,
            channel=None,
            level=None,
            message=raw,
            raw=raw,
            orphan=True,
        )

    match = ENTRY_HEADER.match(lines[0])
    if match is None:  # Guarded by parse_laravel_entries.
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
    """Split a Laravel log delta into headers and their continuation lines.

    Nonempty data before the first valid header is retained as an orphan entry
    so a delta beginning in the middle of a stack trace cannot bypass checks.
    """

    entries: list[LaravelLogEntry] = []
    current: list[str] = []
    current_is_orphan = False

    def flush() -> None:
        nonlocal current, current_is_orphan
        if not current or not any(line.strip() for line in current):
            current = []
            current_is_orphan = False
            return
        entries.append(
            _make_entry(current, len(entries) + 1, orphan=current_is_orphan)
        )
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
            # A timestamp/channel/level-shaped line with an unknown or malformed
            # level is format drift, not a continuation of the prior entry.
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
    candidate_markers: Iterable[str] = PRODUCTION_ALPHA_CANDIDATE_MARKERS,
) -> tuple[str, ...]:
    """Return the reviewed rollback signals present in an entry."""

    signals = [name for name, pattern in FAILURE_PATTERNS if pattern.search(entry.raw)]
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
    return tuple(signals)


def analyze_log_bytes(
    content: bytes,
    *,
    candidate_markers: Iterable[str] = PRODUCTION_ALPHA_CANDIDATE_MARKERS,
) -> dict[str, Any]:
    """Return a JSON-safe, message-free classification report."""

    invalid_utf8 = False
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        # Decode only to finish a message-free report. Any replacement means
        # the monitor cannot reliably classify the original bytes, so the
        # global invalid_utf8 finding below fails closed.
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
                "timestamp": None,
                "channel": None,
                "level": None,
                "signals": ["invalid_utf8"],
                "entry_sha256": hashlib.sha256(content).hexdigest(),
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
                "timestamp": entry.timestamp,
                "channel": entry.channel,
                "level": entry.level,
                "signals": list(signals),
                "entry_sha256": entry.sha256,
            }
        )

    fatal_numbers = {
        finding["entry_number"]
        for finding in findings
        if finding["entry_number"] > 0
    }
    nonfatal_error_entries = sum(
        entry.level in FAILURE_LEVELS and entry.number not in fatal_numbers
        for entry in entries
    )
    report: dict[str, Any] = {
        "status": "fail" if findings else "pass",
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "entry_count": len(entries),
        "orphan_entry_count": sum(entry.orphan for entry in entries),
        "invalid_utf8": invalid_utf8,
        "decode_replacement_count": text.count("\ufffd") if invalid_utf8 else 0,
        "level_counts": dict(sorted(level_counts.items())),
        "nonfatal_error_entry_count": nonfatal_error_entries,
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
    candidate_markers: Iterable[str] = PRODUCTION_ALPHA_CANDIDATE_MARKERS,
) -> dict[str, Any]:
    """Return a safe report, or raise when a rollback signal is present."""

    report = analyze_log_bytes(content, candidate_markers=candidate_markers)
    if report["fatal_finding_count"]:
        raise LaravelLogGuardError(report)
    return report


__all__ = [
    "LaravelLogEntry",
    "LaravelLogGuardError",
    "PRODUCTION_ALPHA_CANDIDATE_MARKERS",
    "analyze_log_bytes",
    "classify_entry",
    "inspect_log_bytes",
    "parse_laravel_entries",
]
