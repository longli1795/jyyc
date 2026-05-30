"""Cleanup accumulated temporary and scheduled backups."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def log_line(log_file: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def cleanup_snapshot_preload(root: Path, keep_count: int, log_file: Path) -> int:
    backups_dir = root / "data" / "backups"
    if not backups_dir.exists():
        return 0

    entries: List[Path] = sorted(
        [
            path
            for path in backups_dir.iterdir()
            if path.is_dir() and path.name.startswith("snapshot_pre_load_")
        ],
        key=lambda path: path.name,
        reverse=True,
    )
    removed = 0
    for path in entries[keep_count:]:
        shutil.rmtree(path, ignore_errors=True)
        log_line(log_file, f"PRUNE: removed snapshot pre-load backup {path.name}")
        removed += 1
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup old temporary backups")
    parser.add_argument(
        "--keep-snapshot-preload",
        type=int,
        default=int(os.environ.get("SNAPSHOT_PRELOAD_RETENTION", "10")),
        help="Number of snapshot_pre_load_* directories to keep",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    log_file = root / "logs" / "backup.log"

    try:
        log_line(log_file, "START: cleanup old temporary backups")
        removed = cleanup_snapshot_preload(root, args.keep_snapshot_preload, log_file)
        log_line(log_file, f"DONE: removed {removed} snapshot_pre_load backup(s)")
        return 0
    except Exception as exc:
        log_line(log_file, f"ERROR: cleanup failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
