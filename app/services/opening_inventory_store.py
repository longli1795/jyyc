"""
期初库存文件固化：磁盘为唯一真相源，全局会话 global_opening_inventory 承载解析后的 source_data。
"""
import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from werkzeug.utils import secure_filename

GLOBAL_OPENING_SESSION_ID = 'global_opening_inventory'
ALLOWED_EXTENSIONS = frozenset({'xlsx', 'xls', 'csv'})
META_FILENAME = 'opening_inventory_meta.json'
STORED_BASENAME = 'opening_inventory'


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_persistent_dir() -> str:
    from app.config import config
    base = getattr(config, 'OPENING_INVENTORY_DIR', None)
    if not base:
        base = os.path.join(_project_root(), 'data', 'persistent')
    os.makedirs(base, exist_ok=True)
    return base


def get_backups_dir() -> str:
    d = os.path.join(get_persistent_dir(), 'backups')
    os.makedirs(d, exist_ok=True)
    return d


def get_meta_path() -> str:
    return os.path.join(get_persistent_dir(), META_FILENAME)


def _atomic_write_json(path: str, obj: Dict[str, Any]) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def get_meta() -> Optional[Dict[str, Any]]:
    path = get_meta_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_persistent_file_path() -> Optional[str]:
    meta = get_meta()
    if meta:
        stored = meta.get('stored_filename')
        if stored:
            full = os.path.join(get_persistent_dir(), stored)
            if os.path.exists(full):
                return full
    persistent_dir = get_persistent_dir()
    for ext in ('xlsx', 'xls', 'csv'):
        candidate = os.path.join(persistent_dir, f'{STORED_BASENAME}.{ext}')
        if os.path.exists(candidate):
            return candidate
    return None


def has_persistent_file() -> bool:
    path = get_persistent_file_path()
    return path is not None and os.path.isfile(path) and os.path.getsize(path) > 0


def _backup_existing_file(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path):
        return None
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = os.path.basename(file_path)
    base, ext = os.path.splitext(name)
    dest = os.path.join(get_backups_dir(), f'{base}_backup_{ts}{ext}')
    try:
        shutil.copy2(file_path, dest)
        return dest
    except OSError:
        return None


def save_uploaded_file(file_storage, uploaded_by_user_id: Optional[int] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    将上传文件固化到 data/persistent/，覆盖前备份旧文件。
    返回 (success, message, meta_dict)
    """
    if not file_storage or not file_storage.filename:
        return False, '没有选择文件', None

    original_filename = file_storage.filename
    file_ext = original_filename.lower().split('.')[-1] if '.' in original_filename else ''
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f'不支持的文件格式: .{file_ext}，请选择 Excel(.xlsx, .xls) 或 CSV(.csv)', None

    persistent_dir = get_persistent_dir()
    stored_filename = f'{STORED_BASENAME}.{file_ext}'
    dest_path = os.path.join(persistent_dir, stored_filename)

    for old_ext in ALLOWED_EXTENSIONS:
        old_path = os.path.join(persistent_dir, f'{STORED_BASENAME}.{old_ext}')
        if os.path.exists(old_path) and os.path.abspath(old_path) != os.path.abspath(dest_path):
            _backup_existing_file(old_path)
            try:
                os.remove(old_path)
            except OSError:
                pass

    if os.path.exists(dest_path):
        _backup_existing_file(dest_path)

    tmp_path = f'{dest_path}.{os.getpid()}.tmp'
    try:
        file_storage.save(tmp_path)
        file_size = os.path.getsize(tmp_path)
        if file_size == 0:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False, '文件为空，请检查文件内容', None
        if file_size > 50 * 1024 * 1024:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False, '文件过大，请选择小于50MB的文件', None
        os.replace(tmp_path, dest_path)
    except OSError as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False, f'文件保存失败: {e}', None

    meta = {
        'original_filename': original_filename,
        'stored_filename': stored_filename,
        'file_ext': file_ext,
        'uploaded_at': datetime.now().isoformat(timespec='seconds'),
        'uploaded_by_user_id': uploaded_by_user_id,
        'file_size_bytes': file_size,
        'stored_path': dest_path,
    }
    _atomic_write_json(get_meta_path(), meta)
    return True, f'期初库存已固化: {stored_filename}', meta


def load_from_disk_into_memory() -> Tuple[bool, str]:
    """从磁盘固化文件加载到全局会话。需在 Flask app context 内调用。"""
    path = get_persistent_file_path()
    if not path:
        return False, '无期初库存固化文件'

    from app.services.data_service import DataService

    data_service = DataService(GLOBAL_OPENING_SESSION_ID)
    if not data_service.load_source_data(path):
        return False, '固化文件解析失败，请重新上传'

    if not data_service.load_mapping_data():
        return False, '映射数据加载失败'

    source_data = data_service.app_data.get_data('source_data')
    rows = len(source_data) if source_data is not None else 0
    meta = get_meta() or {}
    meta['last_loaded_at'] = datetime.now().isoformat(timespec='seconds')
    meta['row_count'] = rows
    _atomic_write_json(get_meta_path(), meta)
    return True, f'已从固化文件加载 {rows} 行期初库存数据'


def get_global_source_data():
    """从全局会话读取 source_data（供计算链路使用）。"""
    from app.models.compatibility import AppDataManager

    app_data = AppDataManager.get_instance(GLOBAL_OPENING_SESSION_ID)
    return app_data.get_data('source_data')


def get_global_source_row_count() -> int:
    data = get_global_source_data()
    if data is None:
        return 0
    try:
        return len(data) if hasattr(data, '__len__') else 0
    except TypeError:
        return 0


def get_status_fields() -> Dict[str, Any]:
    """供 StatusService 使用的固化状态字段。"""
    meta = get_meta() or {}
    has_file = has_persistent_file()
    row_count = get_global_source_row_count()
    return {
        'has_opening_inventory_file': has_file,
        'has_source_data': has_file and row_count > 0,
        'opening_inventory_meta': meta if has_file else None,
        'opening_inventory_rows': row_count,
        'can_run_calculation': has_file and row_count > 0,
    }
