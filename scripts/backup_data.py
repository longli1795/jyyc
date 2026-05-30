"""Scheduled backup for Business Forecast System.

Daily: SQLite online backup + critical data directories/files.
Weekly: daily scope + user snapshot archives.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_sqlite_path(root: Path) -> Path:
    env_path = os.environ.get("SQLITE_DB_PATH")
    if env_path:
        return Path(env_path)
    return root / "data_storage" / "business_forecast.db"


def log_line(log_file: Path, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def backup_sqlite(source_db: Path, target_db: Path, log_file: Path) -> None:
    if not source_db.exists():
        log_line(log_file, f"WARN: SQLite database not found, skip DB backup: {source_db}")
        return

    target_db.parent.mkdir(parents=True, exist_ok=True)
    if target_db.exists():
        target_db.unlink()

    uri = f"file:{source_db.as_posix()}?mode=ro"
    source_conn = sqlite3.connect(uri, uri=True, timeout=30)
    target_conn = sqlite3.connect(str(target_db))
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()

    log_line(log_file, f"OK: SQLite backup -> {target_db}")


def copy_tree(source: Path, target: Path, log_file: Path) -> None:
    if not source.exists():
        log_line(log_file, f"WARN: source missing, skip copy: {source}")
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    log_line(log_file, f"OK: copied {source} -> {target}")


def copy_file(source: Path, target: Path, log_file: Path) -> None:
    if not source.exists():
        log_line(log_file, f"WARN: file missing, skip copy: {source}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    log_line(log_file, f"OK: copied {source.name} -> {target}")


def root_excel_files(root: Path) -> Iterable[Path]:
    for name in ("销售价格.xlsx", "基金补贴单价.xlsx"):
        path = root / name
        if path.exists():
            yield path


def create_backup(mode: str, backup_root: Path, log_file: Path) -> Path:
    root = project_root()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / mode / f"{mode}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    log_line(log_file, f"START: {mode} backup -> {backup_dir}")

    db_source = default_sqlite_path(root)
    backup_sqlite(db_source, backup_dir / "data_storage" / "business_forecast.db", log_file)

    copy_tree(root / "data" / "persistent", backup_dir / "data" / "persistent", log_file)
    copy_tree(root / "data" / "base_data", backup_dir / "data" / "base_data", log_file)

    excel_dir = backup_dir / "excel"
    excel_files: List[str] = []
    for excel_path in root_excel_files(root):
        copy_file(excel_path, excel_dir / excel_path.name, log_file)
        excel_files.append(excel_path.name)

    included_snapshots = False
    if mode == "weekly":
        copy_tree(root / "data" / "snapshots", backup_dir / "data" / "snapshots", log_file)
        included_snapshots = True

    manifest = {
        "schema_version": 1,
        "mode": mode,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(root),
        "sqlite_source": str(db_source),
        "included_snapshots": included_snapshots,
        "excel_files": excel_files,
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log_line(log_file, f"OK: manifest -> {manifest_path}")
    log_line(log_file, f"DONE: {mode} backup completed")
    return backup_dir


def prune_backups(backup_root: Path, mode: str, retention_days: int, retention_weeks: int, log_file: Path) -> None:
    mode_dir = backup_root / mode
    if not mode_dir.exists():
        return

    entries = sorted(
        [path for path in mode_dir.iterdir() if path.is_dir() and path.name.startswith(f"{mode}_")],
        key=lambda path: path.name,
        reverse=True,
    )
    if not entries:
        return

    if mode == "daily":
        cutoff = datetime.now().timestamp() - retention_days * 86400
        keep = [path for path in entries if path.stat().st_mtime >= cutoff]
        remove = [path for path in entries if path not in keep]
    else:
        keep = entries[:retention_weeks]
        remove = entries[retention_weeks:]

    for path in remove:
        shutil.rmtree(path, ignore_errors=True)
        log_line(log_file, f"PRUNE: removed old {mode} backup {path.name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup Business Forecast System data")
    parser.add_argument(
        "--mode",
        choices=("daily", "weekly"),
        default="daily",
        help="daily: core data; weekly: core data + snapshots",
    )
    parser.add_argument(
        "--backup-root",
        default=os.environ.get("BACKUP_ROOT") or r"D:\BusinessForecastBackups",
        help="Root directory for scheduled backups",
    )
    parser.add_argument(
        "--daily-retention-days",
        type=int,
        default=int(os.environ.get("BACKUP_DAILY_RETENTION_DAYS", "14")),
    )
    parser.add_argument(
        "--weekly-retention-weeks",
        type=int,
        default=int(os.environ.get("BACKUP_WEEKLY_RETENTION_WEEKS", "8")),
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Skip retention cleanup after backup",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backup_root = Path(args.backup_root)
    log_file = project_root() / "logs" / "backup.log"

    try:
        create_backup(args.mode, backup_root, log_file)
        if not args.no_prune:
            prune_backups(
                backup_root,
                args.mode,
                args.daily_retention_days,
                args.weekly_retention_weeks,
                log_file,
            )
        return 0
    except Exception as exc:
        log_line(log_file, f"ERROR: {args.mode} backup failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
