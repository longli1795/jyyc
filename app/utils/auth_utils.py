"""
认证工具模块
提供 login_required、admin_required、page_permission_required 装饰器
"""

import os
from functools import wraps
from flask import session, redirect, url_for, request, jsonify


def get_current_user():
    """获取当前登录用户，未登录返回 None"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    from app.models.database import User
    return User.query.get(user_id)


def login_required(f):
    """要求用户已登录的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            # API 请求返回 JSON
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            # 页面请求重定向到登录页
            return redirect(url_for('auth.login_page', next=request.url))
        # 检查用户是否存在且活跃
        from app.models.database import User
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.pop('user_id', None)
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '账户已被禁用或不存在'}), 401
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """要求用户为管理员的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login_page', next=request.url))
        from app.models.database import User
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.pop('user_id', None)
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '账户已被禁用或不存在'}), 401
            return redirect(url_for('auth.login_page'))
        if not user.is_admin:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '需要管理员权限'}), 403
            return redirect(url_for('main.main_index'))
        return f(*args, **kwargs)
    return decorated_function


def require_can_edit(f):
    """要求用户具备编辑权限（非只读），用于上传、计算等写操作"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login_page', next=request.url))
        from app.models.database import User
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.pop('user_id', None)
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '账户已被禁用或不存在'}), 401
            return redirect(url_for('auth.login_page'))
        if getattr(user, 'is_read_only', False):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '只读用户无上传或计算权限'}), 403
            return redirect(url_for('main.main_index'))
        return f(*args, **kwargs)
    return decorated_function


def is_base_data_maintainer(user):
    """是否为基础数据维护员（管理员或维护员白名单）"""
    if not user:
        return False
    if getattr(user, 'is_admin', False):
        return True
    if getattr(user, 'is_data_maintainer', False):
        return True

    # 向后兼容：保留环境变量白名单能力
    raw_ids = os.environ.get('BASE_DATA_MAINTAINER_USER_IDS', '') or ''
    allowed_ids = set()
    for part in raw_ids.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            allowed_ids.add(int(part))
        except ValueError:
            continue
    return getattr(user, 'id', None) in allowed_ids


def require_base_data_maintainer(f):
    """要求用户具备基础数据维护权限（管理员或维护员白名单）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login_page', next=request.url))
        from app.models.database import User
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.pop('user_id', None)
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '账户已被禁用或不存在'}), 401
            return redirect(url_for('auth.login_page'))
        if getattr(user, 'is_read_only', False):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '只读用户无维护权限'}), 403
            return redirect(url_for('main.main_index'))
        if not is_base_data_maintainer(user):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '仅管理员或指定维护员可编辑基础数据'}), 403
            return redirect(url_for('main.main_index'))
        return f(*args, **kwargs)
    return decorated_function


def _normalize_allowed_pages(user):
    """从 User 取出 allowed_pages 并规范为 list。"""
    from app.core.page_permissions import normalize_stored_allowed_pages
    ap = getattr(user, 'allowed_pages', None)
    return normalize_stored_allowed_pages(ap)


def _permission_denied_redirect(user, allowed):
    """无页面权限时的重定向目标，避免落到无权限首页造成循环。"""
    from app.core.page_permissions import get_user_landing_path
    landing = get_user_landing_path(allowed, user.is_admin)
    current = request.path.rstrip('/') or '/'
    landing_norm = landing.rstrip('/') or '/'
    if current == landing_norm:
        return None
    return redirect(landing + ('?permission_denied=1' if '?' not in landing else '&permission_denied=1'))


def page_permission_required(f):
    """要求用户已登录且对当前页面有访问权限。与 login_required 同时使用时放在外侧（先校验登录再校验页面）。"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            return redirect(url_for('auth.login_page', next=request.url))
        from app.models.database import User
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.pop('user_id', None)
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '账户已被禁用或不存在'}), 401
            return redirect(url_for('auth.login_page'))
        # 管理员拥有所有页面权限
        if user.is_admin:
            return f(*args, **kwargs)
        from app.core.page_permissions import path_to_page_key, user_has_page_access
        page_key = path_to_page_key(request.path)
        if page_key is None:
            return f(*args, **kwargs)
        allowed = _normalize_allowed_pages(user)
        if not user_has_page_access(allowed, page_key):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'message': '您没有访问该页面的权限'}), 403
            denied = _permission_denied_redirect(user, allowed)
            if denied is not None:
                return denied
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function
