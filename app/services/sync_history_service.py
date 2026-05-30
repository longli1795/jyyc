"""
同步历史：保存/列出/应用接收到的同步数据版本（仅 SYNC_DATA_KEYS 范围）。
"""
from __future__ import annotations

import json
import os
import re
import uuid
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app

from app.models.database import db, SessionDataset, UserSession
from app.models.session_data_manager import SessionDataManager, SessionDataManagerFactory
from app.services.snapshot_service import (
    UI_SETTINGS_NAME,
    _ensure_user_session,
    _json_default,
    _load_session_from_zip,
    _write_session_dataset_to_zip,
)

MANIFEST_NAME = 'manifest.json'
SYNC_HISTORY_SCHEMA_VERSION = 1


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_sync_history_dir(user_id: int) -> str:
    from app.config import config

    base = getattr(config, 'SYNC_HISTORY_DIR', None) or os.path.join(
        _project_root(), 'data', 'sync_history'
    )
    path = os.path.join(base, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def get_max_sync_history_entries() -> int:
    from app.config import config

    try:
        return int(getattr(config, 'SYNC_HISTORY_MAX_ENTRIES', 20))
    except (TypeError, ValueError):
        return 20


def _sync_entry_path(user_id: int, sync_id: str) -> str:
    safe_id = re.sub(r'[^\w\-]', '', str(sync_id))
    if not safe_id:
        raise ValueError('sync_id 无效')
    return os.path.join(get_sync_history_dir(user_id), f'{safe_id}.zip')


def save_sync_entry(
    target_user_id: int,
    source_datasets: List[SessionDataset],
    metadata: Dict[str, Any],
) -> str:
    """将本次同步数据保存为 zip，返回 sync_id。"""
    sync_id = str(metadata.get('sync_id') or uuid.uuid4())
    synced_at = metadata.get('synced_at') or datetime.now().isoformat()
    data_keys = metadata.get('data_keys') or []
    if not isinstance(data_keys, list):
        data_keys = list(data_keys)

    key_set = set(data_keys) if data_keys else None
    datasets = [ds for ds in source_datasets if key_set is None or ds.data_key in key_set]

    ui_settings = {}
    prediction_period = metadata.get('prediction_period')
    if prediction_period is not None:
        ui_settings['prediction_period'] = prediction_period

    manifest = {
        'schema_version': SYNC_HISTORY_SCHEMA_VERSION,
        'sync_id': sync_id,
        'from_user_id': metadata.get('from_user_id'),
        'from_name': metadata.get('from_name') or '',
        'synced_at': synced_at,
        'prediction_period': prediction_period,
        'data_keys': [ds.data_key for ds in datasets],
        'session_count': len(datasets),
        'target_user_id': target_user_id,
    }

    output_path = _sync_entry_path(target_user_id, sync_id)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        if ui_settings:
            zf.writestr(
                UI_SETTINGS_NAME,
                json.dumps(ui_settings, ensure_ascii=False, default=_json_default),
            )
        for ds in datasets:
            _write_session_dataset_to_zip(zf, ds)

    prune_old_entries(target_user_id)
    return sync_id


def _read_manifest_from_path(path: str) -> Dict[str, Any]:
    with zipfile.ZipFile(path, 'r') as zf:
        if MANIFEST_NAME not in zf.namelist():
            raise ValueError('无效的同步历史文件：缺少 manifest.json')
        manifest = json.loads(zf.read(MANIFEST_NAME).decode('utf-8'))
        if manifest.get('schema_version', 0) != SYNC_HISTORY_SCHEMA_VERSION:
            raise ValueError('不支持的同步历史版本')
        return manifest


def list_sync_entries(user_id: int) -> List[Dict[str, Any]]:
    directory = get_sync_history_dir(user_id)
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(directory):
        return items

    for name in os.listdir(directory):
        if not name.lower().endswith('.zip'):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        try:
            manifest = _read_manifest_from_path(path)
            stat = os.stat(path)
            items.append({
                'sync_id': manifest.get('sync_id') or name[:-4],
                'from_user_id': manifest.get('from_user_id'),
                'from_name': manifest.get('from_name') or '',
                'synced_at': manifest.get('synced_at') or datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'prediction_period': manifest.get('prediction_period'),
                'session_count': manifest.get('session_count', 0),
                'size_bytes': stat.st_size,
            })
        except Exception:
            continue

    items.sort(key=lambda x: x.get('synced_at') or '', reverse=True)
    return items


def prune_old_entries(user_id: int, max_n: Optional[int] = None) -> None:
    max_n = max_n if max_n is not None else get_max_sync_history_entries()
    if max_n <= 0:
        return
    items = list_sync_entries(user_id)
    if len(items) <= max_n:
        return
    for item in items[max_n:]:
        sync_id = item.get('sync_id')
        if not sync_id:
            continue
        path = _sync_entry_path(user_id, sync_id)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


def _clear_session_redis_keys(session_id: str, data_keys: List[str]) -> None:
    try:
        redis_client = getattr(current_app, 'redis', None)
        if not redis_client:
            return
        prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')
        for key in data_keys:
            redis_client.delete(f'{prefix}{session_id}:{key}')
    except Exception as e:
        current_app.logger.warning(f'清除同步历史 Redis 缓存失败: {e}')


def apply_sync_entry(user_id: int, sync_id: str) -> Dict[str, Any]:
    """将指定 sync_id 的同步包写回用户会话。"""
    path = _sync_entry_path(user_id, sync_id)
    if not os.path.isfile(path):
        raise ValueError('同步记录不存在')

    session_id = f'user_{user_id}'
    _ensure_user_session(session_id)

    with zipfile.ZipFile(path, 'r') as zf:
        manifest = _read_manifest_from_path(path)
        if int(manifest.get('target_user_id') or user_id) != int(user_id):
            raise ValueError('无权应用此同步记录')

        data_keys = manifest.get('data_keys') or []
        count = _load_session_from_zip(zf, session_id)

        if UI_SETTINGS_NAME in zf.namelist():
            ui_settings = json.loads(zf.read(UI_SETTINGS_NAME).decode('utf-8'))
            if isinstance(ui_settings, dict) and ui_settings:
                SessionDataManager.upsert_user_ui_settings(session_id, ui_settings)
        elif manifest.get('prediction_period') is not None:
            SessionDataManager.upsert_user_ui_settings(
                session_id,
                {'prediction_period': manifest['prediction_period']},
            )

    db.session.flush()
    _clear_session_redis_keys(session_id, data_keys)
    SessionDataManagerFactory._managers.pop(session_id, None)
    try:
        SessionDataManager.bump_session_version(
            session_id,
            redis_client=getattr(current_app, 'redis', None),
        )
    except Exception:
        pass

    return {
        'sync_id': sync_id,
        'session_count': count,
        'data_keys': data_keys,
        'from_name': manifest.get('from_name') or '',
        'synced_at': manifest.get('synced_at') or '',
    }
