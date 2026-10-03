#!/usr/bin/env python3
"""Compare the retained reviewed vendor tree with the failed production shadow."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def content_signature(record: dict[str, object]) -> tuple[object, object, object]:
    return record.get("kind"), record.get("bytes"), record.get("sha256")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: analyze_vendor_mismatch.py EXPECTED_INVENTORY "
            "ACTUAL_INVENTORY EXPECTED_VENDOR_ROOT OUTPUT"
        )

    expected_document = load(Path(sys.argv[1]))
    actual_document = load(Path(sys.argv[2]))
    expected = expected_document["records"]
    actual = actual_document["records"]
    expected_root = Path(sys.argv[3])

    expected_paths = set(expected)
    actual_paths = set(actual)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    shared = sorted(expected_paths & actual_paths)

    content_changes = []
    mode_transitions: Counter[str] = Counter()
    expected_modes: Counter[str] = Counter(
        f"{record['kind']}:{record['mode']}" for record in expected.values()
    )
    actual_modes: Counter[str] = Counter(
        f"{record['kind']}:{record['mode']}" for record in actual.values()
    )
    for path in shared:
        expected_record = expected[path]
        actual_record = actual[path]
        if content_signature(expected_record) != content_signature(actual_record):
            content_changes.append(
                {
                    "actual": actual_record,
                    "expected": expected_record,
                    "path": path,
                }
            )
        if expected_record["mode"] != actual_record["mode"]:
            mode_transitions[
                f"{expected_record['kind']}:{expected_record['mode']}->{actual_record['mode']}"
            ] += 1

    autoload_proof = {}
    removed_app_bytes = 0
    for name in ("composer/autoload_classmap.php", "composer/autoload_static.php"):
        raw = (expected_root / name).read_bytes()
        lines = raw.splitlines(keepends=True)
        app_lines = [line for line in lines if b"/app/" in line]
        filtered = b"".join(line for line in lines if b"/app/" not in line)
        filtered_hash = hashlib.sha256(filtered).hexdigest()
        removed = len(raw) - len(filtered)
        removed_app_bytes += removed
        actual_record = actual[name]
        autoload_proof[name] = {
            "actual_shadow": actual_record,
            "app_lines_removed": len(app_lines),
            "expected_reviewed": expected[name],
            "filtered_bytes": len(filtered),
            "filtered_sha256": filtered_hash,
            "filtered_matches_actual": (
                len(filtered) == actual_record["bytes"]
                and filtered_hash == actual_record["sha256"]
            ),
            "removed_bytes": removed,
        }

    expected_manifest = expected_document["manifest"]
    actual_bytes = sum(
        record.get("bytes", 0)
        for record in actual.values()
        if record["kind"] == "file"
    )
    missing_bytes = sum(expected[path].get("bytes", 0) for path in missing)
    total_delta = expected_manifest["bytes"] - actual_bytes

    result = {
        "artifact": "buy-dtf-laravel-remember-cookie-vendor-mismatch-analysis-v1",
        "autoload_source_context_proof": autoload_proof,
        "byte_accounting": {
            "actual_shadow_bytes": actual_bytes,
            "accounted_delta_bytes": missing_bytes + removed_app_bytes,
            "app_classmap_bytes_absent": removed_app_bytes,
            "expected_reviewed_bytes": expected_manifest["bytes"],
            "missing_proxy_bytes": missing_bytes,
            "total_delta_bytes": total_delta,
            "fully_accounted": total_delta == missing_bytes + removed_app_bytes,
        },
        "content_changes": content_changes,
        "extra_in_shadow": extra,
        "missing_from_shadow": [
            {"path": path, **expected[path]} for path in missing
        ],
        "mode_counts": {
            "actual_shadow": dict(sorted(actual_modes.items())),
            "expected_reviewed": dict(sorted(expected_modes.items())),
        },
        "mode_transitions": dict(sorted(mode_transitions.items())),
        "record_counts": {
            "actual_shadow": len(actual),
            "content_differences": len(content_changes),
            "expected_reviewed": len(expected),
            "extra_in_shadow": len(extra),
            "missing_from_shadow": len(missing),
            "mode_differences": sum(mode_transitions.values()),
            "shared": len(shared),
        },
        "result": {
            "all_other_shared_content_identical": {
                change["path"] for change in content_changes
            }
            == {"composer/autoload_classmap.php", "composer/autoload_static.php"},
            "existing_reviewed_runner_can_reproduce_expected_identity": False,
            "failed_closed": True,
            "reason": (
                "The reviewed runner optimizes Composer autoload files before app/ is copied; "
                "the production build also differs in Composer proxy generation and modes."
            ),
            "retry_requires_revised_runner_identity_and_independent_review": True,
        },
    }
    Path(sys.argv[4]).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
