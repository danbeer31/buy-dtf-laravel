#!/usr/bin/env python3
"""Read-only production maintenance, front-controller, and lock verification."""

import fcntl
import hashlib
import json
from pathlib import Path
import stat


APP_ROOT = Path("/var/www/buy-dtf")
EXPECTED_FRONT = "eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9"
LOCKS = {
    "receiver": APP_ROOT / "storage/framework/incoming-order-v1-deployment.lock",
    "dependency": APP_ROOT / "storage/framework/dependency-deployment.lock",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


lock_state = {}
for name, path in LOCKS.items():
    if not path.is_file():
        raise SystemExit(f"required lock file is absent: {name}")
    with path.open("rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_state[name] = False
        else:
            lock_state[name] = True
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

front = APP_ROOT / "public/index.php"
metadata = front.stat()
front_identity = {
    "sha256": sha256(front),
    "bytes": metadata.st_size,
    "mode": stat.S_IMODE(metadata.st_mode),
    "uid": metadata.st_uid,
    "gid": metadata.st_gid,
}
if front_identity["sha256"] != EXPECTED_FRONT or front_identity["mode"] != 0o644:
    raise SystemExit("front-controller identity differs from baseline")
if not all(lock_state.values()):
    raise SystemExit("a deployment lock is active")
if (APP_ROOT / "storage/framework/down").exists():
    raise SystemExit("Laravel maintenance is active")

rollback_root = APP_ROOT / "storage/app/private/operations/incoming-order-v1-rollbacks"
rollback_directories = sorted(
    path.name for path in rollback_root.iterdir() if path.is_dir() and not path.is_symlink()
)

print(
    json.dumps(
        {
            "status": "pass",
            "scope": "read_only_production_lock_and_gate_state",
            "maintenance_active": False,
            "static_gate_active": False,
            "front_controller": front_identity,
            "locks_free": lock_state,
            "rollback_directories": rollback_directories,
            "filesystem_mutation": False,
        },
        indent=2,
        sort_keys=True,
    )
)
