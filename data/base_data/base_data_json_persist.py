# -*- coding: utf-8 -*-
"""基础数据 JSON 侧车：原子写入与备份。"""
import json
import os
import shutil
from datetime import datetime
from typing import Optional


def _base_data_dir():
    return os.path.dirname(os.path.abspath(__file__))


def atomic_write_json(path: str, obj, ensure_ascii: bool = False) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=ensure_ascii, indent=2, default=str)
    os.replace(tmp, path)


def backup_json_sidecar(source_path: str, backup_prefix: str) -> Optional[str]:
    if not os.path.exists(source_path):
        return None
    backup_dir = os.path.join(os.path.dirname(_base_data_dir()), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(source_path)[1] or ".json"
    dest = os.path.join(backup_dir, f"{backup_prefix}_backup_{ts}{ext}")
    shutil.copy2(source_path, dest)
    return dest
