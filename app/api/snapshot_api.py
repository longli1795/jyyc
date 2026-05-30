"""
工作区快照 API：保存/加载/列出/下载/删除全量快照。
"""
import io
import os
import tempfile
import traceback

from flask import Blueprint, jsonify, request, session, send_file

from app.models.database import db
from app.utils.auth_utils import login_required, require_can_edit, get_current_user
from app.services.snapshot_service import (
    export_snapshot,
    import_snapshot,
    list_server_snapshots,
    delete_server_snapshot,
    get_server_snapshot_path,
    sanitize_snapshot_filename,
    get_snapshots_dir,
)

snapshot_bp = Blueprint('snapshot', __name__)


def _user_session_id() -> str:
    user_id = session.get('user_id')
    return session.get('session_id') or (f'user_{user_id}' if user_id else '')


@snapshot_bp.route('/save', methods=['POST'])
@login_required
@require_can_edit
def save_snapshot():
    """保存全量快照到服务器，可选同时返回下载。"""
    try:
        user = get_current_user()
        user_id = user.id
        data = request.get_json(silent=True) or {}
        filename = data.get('filename') or data.get('name') or ''
        save_to_server = data.get('save_to_server', True)
        also_download = data.get('also_download', False)

        safe_name = sanitize_snapshot_filename(filename)
        session_id = _user_session_id()
        if not session_id:
            return jsonify({'success': False, 'message': '无法确定用户会话'}), 400

        display = filename or safe_name
        saved_by = user.display_name or user.username or ''

        if save_to_server:
            output_path = os.path.join(get_snapshots_dir(user_id), safe_name)
            manifest = export_snapshot(
                session_id,
                output_path,
                saved_by_user_id=user_id,
                saved_by_name=saved_by,
                display_name=display,
            )
            if also_download:
                return send_file(
                    output_path,
                    as_attachment=True,
                    download_name=safe_name,
                    mimetype='application/zip',
                )
            return jsonify({
                'success': True,
                'message': f'快照已保存: {safe_name}',
                'data': {'filename': safe_name, 'manifest': manifest},
            })

        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            tmp_path = tmp.name
        try:
            manifest = export_snapshot(
                session_id,
                tmp_path,
                saved_by_user_id=user_id,
                saved_by_name=saved_by,
                display_name=display,
            )
            return send_file(
                tmp_path,
                as_attachment=True,
                download_name=safe_name,
                mimetype='application/zip',
            )
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@snapshot_bp.route('/list', methods=['GET'])
@login_required
def list_snapshots():
    try:
        user_id = session.get('user_id')
        items = list_server_snapshots(user_id)
        return jsonify({'success': True, 'data': items})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@snapshot_bp.route('/download/<path:filename>', methods=['GET'])
@login_required
def download_snapshot(filename):
    try:
        user_id = session.get('user_id')
        path = get_server_snapshot_path(user_id, filename)
        safe = sanitize_snapshot_filename(filename)
        return send_file(path, as_attachment=True, download_name=safe, mimetype='application/zip')
    except FileNotFoundError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@snapshot_bp.route('/load', methods=['POST'])
@login_required
def load_snapshot():
    """加载快照：source=server 或 upload。"""
    try:
        user_id = session.get('user_id')
        session_id = _user_session_id()
        if not session_id:
            return jsonify({'success': False, 'message': '无法确定用户会话'}), 400

        source = request.form.get('source') or (request.get_json(silent=True) or {}).get('source', 'upload')

        if source == 'server':
            data = request.get_json(silent=True) or {}
            filename = data.get('filename') or request.form.get('filename')
            if not filename:
                return jsonify({'success': False, 'message': '请指定快照文件名'}), 400
            path = get_server_snapshot_path(user_id, filename)
            result = import_snapshot(session_id, path, user_id=user_id)
        else:
            upload = request.files.get('file')
            if not upload or not upload.filename:
                return jsonify({'success': False, 'message': '请上传快照 zip 文件'}), 400
            if not upload.filename.lower().endswith('.zip'):
                return jsonify({'success': False, 'message': '仅支持 .zip 快照文件'}), 400
            buf = io.BytesIO(upload.read())
            result = import_snapshot(session_id, buf, user_id=user_id)

        ui = result.get('ui_settings') or {}
        pp = ui.get('prediction_period')
        return jsonify({
            'success': True,
            'message': '快照加载成功，页面将刷新以显示复盘数据',
            'data': {
                'session_keys_restored': result.get('session_keys_restored', 0),
                'backup_dir': result.get('backup_dir'),
                'opening_inventory': result.get('opening_inventory'),
                'prediction_period': pp,
                'saved_at': (result.get('manifest') or {}).get('saved_at'),
                'display_name': (result.get('manifest') or {}).get('display_name'),
            },
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({'success': False, 'message': str(e)}), 404
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@snapshot_bp.route('/delete/<path:filename>', methods=['DELETE'])
@login_required
@require_can_edit
def remove_snapshot(filename):
    try:
        user_id = session.get('user_id')
        if delete_server_snapshot(user_id, filename):
            return jsonify({'success': True, 'message': '快照已删除'})
        return jsonify({'success': False, 'message': '快照不存在'}), 404
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
