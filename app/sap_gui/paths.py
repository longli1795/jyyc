# -*- coding: utf-8 -*-
"""SAP 取数相关路径：项目根、导出目录、日志、凭据文件。"""
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore


def last_month_period(now: datetime = None) -> str:
    """北京时间当前月的上个月，格式 YYYY.MM（SAP ctxtP_MONTH）。"""
    if now is None:
        if ZoneInfo is not None:
            now = datetime.now(ZoneInfo("Asia/Shanghai"))
        else:
            now = datetime.now()
    if now.month == 1:
        return "{}.12".format(now.year - 1)
    return "{}.{:02d}".format(now.year, now.month - 1)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def project_root() -> str:
    return os.path.dirname(os.path.dirname(_THIS_DIR))


def exports_dir() -> str:
    d = os.path.join(project_root(), "data", "sap_exports")
    os.makedirs(d, exist_ok=True)
    return d


def logs_dir() -> str:
    d = os.path.join(project_root(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def secrets_path() -> str:
    return os.path.join(project_root(), "secrets.ini")


def job_status_path() -> str:
    return os.path.join(exports_dir(), "job_status.json")


def log(msg: str, logfile: str = "sap_export.log") -> None:
    print(msg)
    path = os.path.join(logs_dir(), logfile)
    with open(path, "a", encoding="utf-8") as f:
        f.write("{} {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def read_job_status() -> Dict[str, Any]:
    path = job_status_path()
    if not os.path.isfile(path):
        return {"running": False, "phase": "idle", "message": ""}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"running": False, "phase": "idle"}
    except (OSError, json.JSONDecodeError):
        return {"running": False, "phase": "idle", "message": ""}


def write_job_status(updates: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    current = read_job_status()
    if updates:
        current.update(updates)
    if kwargs:
        current.update(kwargs)
    path = job_status_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)
    return current
