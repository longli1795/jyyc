"""
认证蓝图 - 登录 / 登出 / 获取当前用户
"""

from datetime import datetime
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from app.models.database import db, User
from app.utils.auth_utils import login_required

auth_bp = Blueprint('auth', __name__)


def _parse_allowed_pages(user):
    """从 User 读取并规范化 allowed_pages。"""
    from app.core.page_permissions import normalize_stored_allowed_pages
    ap = getattr(user, 'allowed_pages', None)
    return normalize_stored_allowed_pages(ap)


def _resolve_post_login_redirect(user, allowed_pages, next_url=None):
    """登录成功后解析跳转目标。"""
    from app.core.page_permissions import (
        get_user_landing_path,
        user_can_access_path,
    )
    landing = get_user_landing_path(allowed_pages, user.is_admin)
    if not next_url:
        return landing

    # 仅允许站内相对路径
    parsed = urlparse(next_url)
    if parsed.netloc or not next_url.startswith('/'):
        return landing

    if user_can_access_path(allowed_pages, next_url, user.is_admin):
        return next_url
    return landing


@auth_bp.route('/login', methods=['GET'])
def login_page():
    """登录页面"""
    if session.get('user_id'):
        from app.core.page_permissions import get_user_landing_path
        user = User.query.get(session['user_id'])
        if user and user.is_active:
            allowed = session.get('allowed_pages')
            if allowed is None:
                allowed = _parse_allowed_pages(user)
            landing = get_user_landing_path(allowed, user.is_admin)
            return redirect(landing)
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
def login_action():
    """处理登录表单"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template('login.html', error='请输入用户名和密码')

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return render_template('login.html', error='用户名或密码错误', username=username)

    if not user.is_active:
        return render_template('login.html', error='该账户已被禁用，请联系管理员', username=username)

    from app.core.page_permissions import get_all_page_keys, user_can_login_with_pages

    if user.is_admin:
        allowed_pages = get_all_page_keys()
    else:
        allowed_pages = _parse_allowed_pages(user)

    if not user_can_login_with_pages(allowed_pages, user.is_admin):
        return render_template(
            'login.html',
            error='该账户未配置可访问页面，请联系管理员',
            username=username,
        )

    # 登录成功 —— 写入 session
    session['user_id'] = user.id
    session['username'] = user.username
    session['display_name'] = user.display_name or user.username
    session['is_admin'] = user.is_admin
    session['is_read_only'] = getattr(user, 'is_read_only', False)
    session['allowed_pages'] = allowed_pages

    # 关键：将数据隔离的 session_id 绑定到用户，而非随机 UUID
    session['session_id'] = f'user_{user.id}'
    session.permanent = True
    session.modified = True

    user.last_login = datetime.utcnow()
    db.session.commit()

    next_url = request.args.get('next') or request.form.get('next')
    redirect_url = _resolve_post_login_redirect(user, allowed_pages, next_url)
    return redirect(redirect_url)


@auth_bp.route('/logout')
def logout():
    """登出"""
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('display_name', None)
    session.pop('is_admin', None)
    session.pop('is_read_only', None)
    session.pop('allowed_pages', None)
    session.pop('session_id', None)
    return redirect(url_for('auth.login_page'))


@auth_bp.route('/api/auth/me')
def current_user_info():
    """获取当前登录用户信息（API）"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'logged_in': False}), 401
    user = User.query.get(user_id)
    if not user:
        return jsonify({'logged_in': False}), 401
    return jsonify({
        'logged_in': True,
        'user': user.to_dict()
    })


@auth_bp.route('/api/me/permissions')
def current_user_permissions():
    """获取当前用户可访问页面权限（供前端过滤菜单/入口）"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'allowed_pages': []}), 401
    from app.core.page_permissions import get_all_page_keys, expand_allowed_pages, normalize_stored_allowed_pages
    allowed = session.get('allowed_pages')
    if allowed is None:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'allowed_pages': []}), 401
        if user.is_admin:
            allowed = get_all_page_keys()
        else:
            allowed = normalize_stored_allowed_pages(getattr(user, 'allowed_pages', None))
    allowed = expand_allowed_pages(allowed)
    return jsonify({'success': True, 'allowed_pages': allowed})


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """当前登录用户修改密码（需验证旧密码）"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({'success': False, 'message': '账户已被禁用或不存在'}), 401

    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not old_password:
        return jsonify({'success': False, 'message': '请输入当前密码'}), 400
    if not user.check_password(old_password):
        return jsonify({'success': False, 'message': '当前密码错误'}), 400
    if not new_password or len(new_password) < 4:
        return jsonify({'success': False, 'message': '新密码不能为空且至少4位'}), 400
    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的新密码不一致'}), 400
    if user.check_password(new_password):
        return jsonify({'success': False, 'message': '新密码不能与当前密码相同'}), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify({'success': True, 'message': '密码已修改'})
