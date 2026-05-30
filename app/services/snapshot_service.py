"""
工作区全量快照：导出/导入用户会话、基础数据、期初库存。
"""
from __future__ import annotations

import copy
import importlib
import io
import json
import os
import pickle
import re
import shutil
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from flask import current_app

from app.models.database import db, SessionDataset, UserSession
from app.models.session_data_manager import SessionDataManager, SessionDataManagerFactory

SCHEMA_VERSION = 1
MANIFEST_NAME = 'manifest.json'
UI_SETTINGS_NAME = 'ui_settings.json'


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_snapshots_dir(user_id: int) -> str:
    from app.config import config
    base = getattr(config, 'SNAPSHOTS_DIR', None) or os.path.join(_project_root(), 'data', 'snapshots')
    path = os.path.join(base, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def sanitize_snapshot_filename(name: str) -> str:
    """保留中文、字母数字、点、横线、下划线。"""
    if not name or not str(name).strip():
        raise ValueError('文件名不能为空')
    raw = str(name).strip()
    if raw.lower().endswith('.zip'):
        raw = raw[:-4]
    cleaned = re.sub(r'[^\w\u4e00-\u9fff.\-]', '_', raw, flags=re.UNICODE)
    cleaned = cleaned.strip('._-')
    if not cleaned:
        raise ValueError('文件名无效')
    if '..' in cleaned or '/' in cleaned or '\\' in cleaned:
        raise ValueError('文件名包含非法字符')
    return f'{cleaned}.zip'


def _safe_data_key_path(data_key: str) -> str:
    return re.sub(r'[^\w\-.]', '_', data_key)


def _json_default(obj):
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if pd.isna(obj):
        return None
    return str(obj)


def _collect_base_data() -> Dict[str, Any]:
    from data.base_data.mapping_data import get_mapping_dataframe, MAPPING_TABLE_DATA
    from data.base_data.deduction_data import DEDUCTION_CODES
    from data.base_data.product_data import reload_product_disassembly_json_if_stale
    import data.base_data.deep_processing_data as dpd
    from data.base_data.price_data import load_price_data, PRICE_FILE_PATH
    from data.base_data.subsidy_data import load_subsidy_data, SUBSIDY_FILE_PATH

    root = _project_root()
    reload_product_disassembly_json_if_stale()
    dpd.reload_deep_processing_json_if_stale()

    mapping_df = get_mapping_dataframe()
    labor_df = None
    salary_df = None
    manufacturing_df = None
    period_df = None
    try:
        from data.base_data.labor_cost_data import get_labor_cost_dataframe
        labor_df = get_labor_cost_dataframe()
    except Exception:
        pass
    try:
        from data.base_data.salary_accounting_data import get_salary_accounting_dataframe
        salary_df = get_salary_accounting_dataframe()
    except Exception:
        pass
    try:
        from data.base_data.manufacturing_cost_data import get_manufacturing_cost_dataframe
        manufacturing_df = get_manufacturing_cost_dataframe()
    except Exception:
        pass
    try:
        from data.base_data.period_cost_data import get_period_cost_dataframe
        period_df = get_period_cost_dataframe()
    except Exception:
        pass

    price_df = None
    subsidy_df = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            price_df = load_price_data()
    except Exception:
        price_df = None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            subsidy_df = load_subsidy_data()
    except Exception:
        subsidy_df = None

    price_path = PRICE_FILE_PATH if os.path.isabs(PRICE_FILE_PATH) else os.path.join(root, PRICE_FILE_PATH)
    subsidy_path = SUBSIDY_FILE_PATH if os.path.isabs(SUBSIDY_FILE_PATH) else os.path.join(root, SUBSIDY_FILE_PATH)
    prod_json = os.path.join(root, 'data', 'base_data', 'product_disassembly.json')
    deep_json = os.path.join(root, 'data', 'base_data', 'deep_processing_coefficients.json')

    return {
        'mapping': mapping_df.to_dict('records') if mapping_df is not None and not mapping_df.empty else list(MAPPING_TABLE_DATA),
        'deduction': dict(DEDUCTION_CODES),
        'product_disassembly_json': prod_json if os.path.exists(prod_json) else None,
        'deep_processing_json': deep_json if os.path.exists(deep_json) else None,
        'price_records': price_df.to_dict('records') if price_df is not None and not price_df.empty else [],
        'price_file': price_path if os.path.exists(price_path) else None,
        'subsidy_records': subsidy_df.to_dict('records') if subsidy_df is not None and not subsidy_df.empty else [],
        'subsidy_file': subsidy_path if os.path.exists(subsidy_path) else None,
        'labor_cost': labor_df.to_dict('records') if labor_df is not None and not labor_df.empty else [],
        'salary_accounting': salary_df.to_dict('records') if salary_df is not None and not salary_df.empty else [],
        'manufacturing_cost': manufacturing_df.to_dict('records') if manufacturing_df is not None and not manufacturing_df.empty else [],
        'period_cost': period_df.to_dict('records') if period_df is not None and not period_df.empty else [],
    }


def _collect_opening_inventory() -> Optional[Dict[str, Any]]:
    from app.services.opening_inventory_store import get_persistent_file_path, get_meta
    path = get_persistent_file_path()
    if not path or not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        content = f.read()
    meta = get_meta() or {}
    return {
        'filename': os.path.basename(path),
        'content': content,
        'meta': meta,
    }


def _write_session_dataset_to_zip(zf: zipfile.ZipFile, dataset: SessionDataset) -> None:
    prefix = f'session/{_safe_data_key_path(dataset.data_key)}'
    meta = {
        'data_key': dataset.data_key,
        'data_type': dataset.data_type,
        'row_count': dataset.row_count,
        'column_count': dataset.column_count,
    }
    zf.writestr(f'{prefix}.meta.json', json.dumps(meta, ensure_ascii=False))

    if dataset.data_type == 'dataframe':
        df = dataset.get_dataframe_data()
        if df is not None and not df.empty:
            try:
                json_bytes = df.to_json(orient='records', date_format='iso').encode('utf-8')
                if len(json_bytes) < 1024 * 1024:
                    zf.writestr(f'{prefix}.json', json_bytes)
                    return
            except Exception:
                pass
            zf.writestr(f'{prefix}.pkl', pickle.dumps(df))
        return

    raw = dataset.get_json_data()
    if raw is not None:
        zf.writestr(
            f'{prefix}.json',
            json.dumps(raw, ensure_ascii=False, default=_json_default).encode('utf-8'),
        )


def export_snapshot(
    session_id: str,
    output_path: str,
    *,
    saved_by_user_id: Optional[int] = None,
    saved_by_name: str = '',
    display_name: str = '',
) -> Dict[str, Any]:
    """导出全量快照到 zip 文件。"""
    datasets = SessionDataset.query.filter_by(session_id=session_id).all()
    ui_settings = SessionDataManager.get_user_ui_settings(session_id=session_id)
    base_data = _collect_base_data()
    opening = _collect_opening_inventory()

    session_keys = [d.data_key for d in datasets]
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'saved_at': datetime.utcnow().isoformat(),
        'saved_by_user_id': saved_by_user_id,
        'saved_by_name': saved_by_name,
        'display_name': display_name or os.path.basename(output_path),
        'session_id': session_id,
        'session_keys': session_keys,
        'session_count': len(session_keys),
        'has_opening_inventory': opening is not None,
        'base_data_files': list(base_data.keys()),
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(
            UI_SETTINGS_NAME,
            json.dumps(ui_settings or {}, ensure_ascii=False, default=_json_default),
        )
        for ds in datasets:
            _write_session_dataset_to_zip(zf, ds)

        skip_json_keys = {
            'price_file', 'subsidy_file', 'price_records', 'subsidy_records',
            'product_disassembly_json', 'deep_processing_json',
        }
        for key, value in base_data.items():
            if key in skip_json_keys:
                continue
            zf.writestr(
                f'base_data/{key}.json',
                json.dumps(value, ensure_ascii=False, default=_json_default).encode('utf-8'),
            )

        if base_data.get('product_disassembly_json'):
            zf.write(base_data['product_disassembly_json'], 'base_data/product_disassembly.json')
        elif 'base_data/product_disassembly.json' not in zf.namelist():
            from data.base_data.product_data import PRODUCT_DISASSEMBLY_DATA
            zf.writestr(
                'base_data/product_disassembly.json',
                json.dumps(PRODUCT_DISASSEMBLY_DATA, ensure_ascii=False, default=_json_default).encode('utf-8'),
            )

        if base_data.get('deep_processing_json'):
            zf.write(base_data['deep_processing_json'], 'base_data/deep_processing_coefficients.json')
        elif 'base_data/deep_processing_coefficients.json' not in zf.namelist():
            import data.base_data.deep_processing_data as dpd_mod
            zf.writestr(
                'base_data/deep_processing_coefficients.json',
                json.dumps(dpd_mod.DEEP_PROCESSING_DATA, ensure_ascii=False, default=_json_default).encode('utf-8'),
            )

        if base_data.get('price_file') and os.path.exists(base_data['price_file']):
            zf.write(base_data['price_file'], 'base_data/price.xlsx')
        elif base_data.get('price_records'):
            zf.writestr(
                'base_data/price_records.json',
                json.dumps(base_data['price_records'], ensure_ascii=False, default=_json_default).encode('utf-8'),
            )

        if base_data.get('subsidy_file') and os.path.exists(base_data['subsidy_file']):
            zf.write(base_data['subsidy_file'], 'base_data/subsidy.xlsx')
        elif base_data.get('subsidy_records'):
            zf.writestr(
                'base_data/subsidy_records.json',
                json.dumps(base_data['subsidy_records'], ensure_ascii=False, default=_json_default).encode('utf-8'),
            )

        if opening:
            zf.writestr(f'opening_inventory/{opening["filename"]}', opening['content'])
            zf.writestr(
                'opening_inventory/meta.json',
                json.dumps(opening['meta'], ensure_ascii=False, default=_json_default).encode('utf-8'),
            )

    file_size = os.path.getsize(output_path)
    manifest['file_size'] = file_size
    manifest['output_path'] = output_path
    return manifest


def _read_manifest(zf: zipfile.ZipFile) -> Dict[str, Any]:
    if MANIFEST_NAME not in zf.namelist():
        raise ValueError('无效的快照文件：缺少 manifest.json')
    manifest = json.loads(zf.read(MANIFEST_NAME).decode('utf-8'))
    version = manifest.get('schema_version', 0)
    if version != SCHEMA_VERSION:
        raise ValueError(f'不支持的快照版本: {version}')
    return manifest


def _backup_before_import() -> str:
    root = _project_root()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(root, 'data', 'backups', f'snapshot_pre_load_{ts}')
    os.makedirs(backup_dir, exist_ok=True)

    paths_to_backup = [
        'data/base_data/mapping_data.py',
        'data/base_data/deduction_data.py',
        'data/base_data/labor_cost_data.py',
        'data/base_data/salary_accounting_data.py',
        'data/base_data/manufacturing_cost_data.py',
        'data/base_data/period_cost_data.py',
        'data/base_data/product_disassembly.json',
        'data/base_data/deep_processing_coefficients.json',
    ]
    for rel in paths_to_backup:
        src = os.path.join(root, rel)
        if os.path.exists(src):
            dest = os.path.join(backup_dir, os.path.basename(rel))
            shutil.copy2(src, dest)

    for fname in ('销售价格.xlsx', '基金补贴单价.xlsx'):
        src = os.path.join(root, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(backup_dir, fname))

    from app.services.opening_inventory_store import get_persistent_file_path, get_meta_path
    oi_path = get_persistent_file_path()
    if oi_path and os.path.exists(oi_path):
        shutil.copy2(oi_path, os.path.join(backup_dir, os.path.basename(oi_path)))
    meta_path = get_meta_path()
    if os.path.exists(meta_path):
        shutil.copy2(meta_path, os.path.join(backup_dir, 'opening_inventory_meta.json'))

    return backup_dir


def _ensure_user_session(session_id: str) -> None:
    row = UserSession.query.filter_by(session_id=session_id).first()
    if not row:
        row = UserSession(session_id=session_id, user_ip=None, user_agent=None, expires_hours=24)
        db.session.add(row)
        db.session.flush()


def _clear_session_redis(session_id: str) -> None:
    try:
        redis_client = getattr(current_app, 'redis', None)
        if not redis_client:
            return
        prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')
        pattern = f'{prefix}{session_id}:*'
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        current_app.logger.warning(f'清除 Redis 会话缓存失败: {e}')


def _clear_user_session_data(session_id: str) -> None:
    _clear_session_redis(session_id)
    SessionDataset.query.filter_by(session_id=session_id).delete()
    db.session.flush()
    SessionDataManagerFactory._managers.pop(session_id, None)


def _load_session_from_zip(zf: zipfile.ZipFile, session_id: str) -> int:
    count = 0
    session_files = [n for n in zf.namelist() if n.startswith('session/') and n.endswith('.meta.json')]
    for meta_path in session_files:
        meta = json.loads(zf.read(meta_path).decode('utf-8'))
        data_key = meta['data_key']
        base = meta_path[:-len('.meta.json')]
        json_path = f'{base}.json'
        pkl_path = f'{base}.pkl'

        dest = SessionDataset.query.filter_by(session_id=session_id, data_key=data_key).first()
        if not dest:
            dest = SessionDataset(session_id=session_id, data_key=data_key)
            db.session.add(dest)

        if pkl_path in zf.namelist():
            df = pickle.loads(zf.read(pkl_path))
            dest.set_dataframe_data(df)
        elif json_path in zf.namelist():
            raw = json.loads(zf.read(json_path).decode('utf-8'))
            if meta.get('data_type') == 'dataframe':
                if raw:
                    dest.set_dataframe_data(pd.DataFrame(raw))
                else:
                    dest.set_dataframe_data(pd.DataFrame())
            else:
                dest.set_json_data(raw)
        count += 1
    return count


def _write_deduction_py(deduction: dict) -> None:
    root = _project_root()
    path = os.path.join(root, 'data', 'base_data', 'deduction_data.py')
    footer = ''
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        idx = content.find('\ndef get_deduction_codes')
        if idx >= 0:
            footer = content[idx:]

    lines = [
        '# -*- coding: utf-8 -*-',
        '"""',
        '减扣规则数据',
        '用于存储需要从计算结果中减扣的编码规则',
        '"""',
        '',
        'DEDUCTION_CODES = {',
    ]
    for code, info in deduction.items():
        desc = str(info.get('说明', '')).replace('"', '\\"').replace("'", "\\'")
        category = str(info.get('处置类别', '')).replace('"', '\\"').replace("'", "\\'")
        source = str(info.get('来源', '')).replace('"', '\\"').replace("'", "\\'")
        lines.append(f"    '{code}': {{")
        lines.append(f"        '说明': '{desc}',")
        lines.append(f"        '处置类别': '{category}',")
        lines.append(f"        '来源': '{source}'")
        lines.append('    },')
    lines.append('}')
    if not footer:
        footer = '''

def get_deduction_codes():
    """获取所有减扣规则"""
    return DEDUCTION_CODES
'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + footer)


def _format_record_for_py(record: dict) -> str:
    parts = []
    for key, value in record.items():
        if value is None or (isinstance(value, float) and pd.isna(value)):
            parts.append(f'"{key}": None')
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            parts.append(f'"{key}": {value}')
        else:
            str_value = str(value).replace('"', '\\"').replace('\\', '\\\\')
            parts.append(f'"{key}": "{str_value}"')
    return '{' + ', '.join(parts) + '}'


def _write_list_data_py(rel_path: str, var_name: str, header_lines: List[str], records: List[dict], footer: str) -> None:
    root = _project_root()
    path = os.path.join(root, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = '\n'.join(header_lines) + f'\n{var_name} = [\n'
    for record in records:
        content += f'    {_format_record_for_py(record)},\n'
    content += ']\n' + footer
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _restore_base_data_from_zip(zf: zipfile.ZipFile) -> None:
    from app.api.data_management_api import import_mapping_data_to_file, import_labor_cost_data_to_file
    from data.base_data.product_data import apply_product_disassembly_snapshot
    import data.base_data.deep_processing_data as dpd

    def _read_json(name: str):
        path = f'base_data/{name}.json'
        if path not in zf.namelist():
            return None
        return json.loads(zf.read(path).decode('utf-8'))

    def _quiet_call(fn, *args, **kwargs):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return fn(*args, **kwargs)

    mapping = _read_json('mapping')
    if mapping is not None:
        _quiet_call(import_mapping_data_to_file, mapping, mode='replace')

    deduction = _read_json('deduction')
    if deduction is not None:
        _write_deduction_py(deduction)

    prod = None
    if 'base_data/product_disassembly.json' in zf.namelist():
        prod = json.loads(zf.read('base_data/product_disassembly.json').decode('utf-8'))
    else:
        prod = _read_json('product_disassembly')
    if prod is not None:
        _quiet_call(apply_product_disassembly_snapshot, copy.deepcopy(prod))

    deep = None
    if 'base_data/deep_processing_coefficients.json' in zf.namelist():
        deep = json.loads(zf.read('base_data/deep_processing_coefficients.json').decode('utf-8'))
    else:
        deep = _read_json('deep_processing_coefficients')
    if deep is not None:
        _quiet_call(dpd.apply_deep_processing_snapshot, copy.deepcopy(deep))

    labor = _read_json('labor_cost')
    if labor is not None:
        _quiet_call(import_labor_cost_data_to_file, labor, mode='replace')

    salary = _read_json('salary_accounting')
    if salary is not None:
        _write_list_data_py(
            'data/base_data/salary_accounting_data.py',
            'SALARY_ACCOUNTING_DATA',
            [
                '# 薪酬核算基础数据 - 内置数据',
                '# 数据来源：快照恢复',
                '',
                'import pandas as pd',
                'import os',
                '',
                '# 完整的薪酬核算基础数据',
            ],
            salary,
            '''

def get_salary_accounting_dataframe():
    """获取薪酬核算基础数据DataFrame"""
    return pd.DataFrame(SALARY_ACCOUNTING_DATA)
''',
        )

    manufacturing = _read_json('manufacturing_cost')
    if manufacturing is not None:
        _write_list_data_py(
            'data/base_data/manufacturing_cost_data.py',
            'MANUFACTURING_COST_DATA',
            [
                '# 制造费用基础数据 - 内置数据',
                '# 数据来源：快照恢复',
                '',
                'import pandas as pd',
                'import os',
                '',
                '# 完整的制造费用基础数据',
            ],
            manufacturing,
            '''

def get_manufacturing_cost_dataframe():
    """获取制造费用基础数据DataFrame"""
    return pd.DataFrame(MANUFACTURING_COST_DATA)
''',
        )

    period = _read_json('period_cost')
    if period is not None:
        _write_list_data_py(
            'data/base_data/period_cost_data.py',
            'PERIOD_COST_DATA',
            [
                '# 期间费用基础数据 - 内置数据',
                '# 数据来源：快照恢复',
                '',
                'import pandas as pd',
                'import os',
                '',
                '# 完整的期间费用基础数据',
            ],
            period,
            '''

def get_period_cost_dataframe():
    """获取期间费用基础数据DataFrame"""
    return pd.DataFrame(PERIOD_COST_DATA)
''',
        )

    root = _project_root()
    if 'base_data/price.xlsx' in zf.namelist():
        dest = os.path.join(root, '销售价格.xlsx')
        with open(dest, 'wb') as f:
            f.write(zf.read('base_data/price.xlsx'))
    else:
        price_records = _read_json('price_records')
        if price_records:
            df = pd.DataFrame(price_records)
            dest = os.path.join(root, '销售价格.xlsx')
            df.to_excel(dest, index=False)

    if 'base_data/subsidy.xlsx' in zf.namelist():
        dest = os.path.join(root, '基金补贴单价.xlsx')
        with open(dest, 'wb') as f:
            f.write(zf.read('base_data/subsidy.xlsx'))
    else:
        subsidy_records = _read_json('subsidy_records')
        if subsidy_records:
            df = pd.DataFrame(subsidy_records)
            dest = os.path.join(root, '基金补贴单价.xlsx')
            df.to_excel(dest, index=False)

    _reload_base_data_modules()


def _reload_base_data_modules() -> None:
    modules = [
        'data.base_data.mapping_data',
        'data.base_data.deduction_data',
        'data.base_data.labor_cost_data',
        'data.base_data.salary_accounting_data',
        'data.base_data.manufacturing_cost_data',
        'data.base_data.period_cost_data',
        'data.base_data.product_data',
        'data.base_data.deep_processing_data',
        'data.base_data.price_data',
        'data.base_data.subsidy_data',
    ]
    for mod_name in modules:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
        else:
            importlib.import_module(mod_name)

    # 清除价格/补贴内存缓存
    try:
        import data.base_data.price_data as price_data
        if hasattr(price_data, '_price_data_cache'):
            price_data._price_data_cache = None
        if hasattr(price_data, 'refresh_price_data'):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                price_data.refresh_price_data()
    except Exception:
        pass
    try:
        import data.base_data.subsidy_data as subsidy_data
        if hasattr(subsidy_data, '_subsidy_data_cache'):
            subsidy_data._subsidy_data_cache = None
        if hasattr(subsidy_data, '_subsidy_mapping_cache'):
            subsidy_data._subsidy_mapping_cache = None
        if hasattr(subsidy_data, 'refresh_subsidy_data'):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                subsidy_data.refresh_subsidy_data()
    except Exception:
        pass


def _restore_opening_inventory_from_zip(zf: zipfile.ZipFile) -> Tuple[bool, str]:
    from app.services.opening_inventory_store import (
        get_persistent_dir,
        get_meta_path,
        GLOBAL_OPENING_SESSION_ID,
        _atomic_write_json,
    )

    oi_files = [n for n in zf.namelist() if n.startswith('opening_inventory/') and not n.endswith('meta.json') and n != 'opening_inventory/']
    if not oi_files:
        return False, '快照中无期初库存'

    oi_file = oi_files[0]
    filename = os.path.basename(oi_file)
    content = zf.read(oi_file)
    persistent_dir = get_persistent_dir()
    dest_path = os.path.join(persistent_dir, filename)

    for old in os.listdir(persistent_dir):
        if old.startswith('opening_inventory.') and old != filename:
            try:
                os.remove(os.path.join(persistent_dir, old))
            except OSError:
                pass

    with open(dest_path, 'wb') as f:
        f.write(content)

    meta = {}
    if 'opening_inventory/meta.json' in zf.namelist():
        meta = json.loads(zf.read('opening_inventory/meta.json').decode('utf-8'))
    meta['stored_filename'] = filename
    meta['restored_at'] = datetime.now().isoformat(timespec='seconds')
    meta['file_size_bytes'] = len(content)
    _atomic_write_json(get_meta_path(), meta)

    from app.services.opening_inventory_store import load_from_disk_into_memory
    ok, msg = load_from_disk_into_memory()
    return ok, msg


def import_snapshot(
    session_id: str,
    zip_source: Union[str, io.BytesIO],
    *,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """从 zip 导入全量快照，覆盖当前用户会话及全局基础数据/期初库存。"""
    backup_dir = _backup_before_import()

    if isinstance(zip_source, str):
        zf_ctx = zipfile.ZipFile(zip_source, 'r')
    else:
        zf_ctx = zipfile.ZipFile(zip_source, 'r')

    with zf_ctx as zf:
        manifest = _read_manifest(zf)

        _ensure_user_session(session_id)
        _clear_user_session_data(session_id)
        session_count = _load_session_from_zip(zf, session_id)

        ui_settings = {}
        if UI_SETTINGS_NAME in zf.namelist():
            ui_settings = json.loads(zf.read(UI_SETTINGS_NAME).decode('utf-8'))
            if ui_settings:
                SessionDataManager.upsert_user_ui_settings(session_id, ui_settings)

        _restore_base_data_from_zip(zf)
        oi_ok, oi_msg = _restore_opening_inventory_from_zip(zf)

        db.session.commit()

        SessionDataManagerFactory._managers.pop(session_id, None)
        redis_client = getattr(current_app, 'redis', None)
        SessionDataManager.bump_session_version(session_id, redis_client=redis_client)
        _clear_session_redis(session_id)

    return {
        'success': True,
        'manifest': manifest,
        'session_keys_restored': session_count,
        'backup_dir': backup_dir,
        'opening_inventory': {'success': oi_ok, 'message': oi_msg},
        'ui_settings': ui_settings,
    }


def list_server_snapshots(user_id: int) -> List[Dict[str, Any]]:
    directory = get_snapshots_dir(user_id)
    items = []
    for name in os.listdir(directory):
        if not name.lower().endswith('.zip'):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        stat = os.stat(path)
        manifest_summary = {}
        try:
            with zipfile.ZipFile(path, 'r') as zf:
                if MANIFEST_NAME in zf.namelist():
                    manifest_summary = json.loads(zf.read(MANIFEST_NAME).decode('utf-8'))
        except Exception:
            pass
        items.append({
            'filename': name,
            'size_bytes': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'saved_at': manifest_summary.get('saved_at'),
            'display_name': manifest_summary.get('display_name') or name,
            'session_count': manifest_summary.get('session_count', 0),
        })
    items.sort(key=lambda x: x.get('saved_at') or x['modified_at'], reverse=True)
    return items


def delete_server_snapshot(user_id: int, filename: str) -> bool:
    safe = sanitize_snapshot_filename(filename)
    path = os.path.join(get_snapshots_dir(user_id), safe)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def get_server_snapshot_path(user_id: int, filename: str) -> str:
    safe = sanitize_snapshot_filename(filename)
    path = os.path.join(get_snapshots_dir(user_id), safe)
    if not os.path.isfile(path):
        raise FileNotFoundError(f'快照不存在: {safe}')
    return path
