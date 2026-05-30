"""
管理后台蓝图 - 分组管理 + 用户管理 + 页面权限配置
"""

from flask import Blueprint, render_template, request, jsonify
from app.models.database import db, User, Group
from app.utils.auth_utils import admin_required
from app.core.page_permissions import get_page_permissions_for_admin, get_all_page_keys

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ──────────── 页面路由 ────────────

@admin_bp.route('/users')
@admin_required
def users_page():
    """用户管理页面"""
    return render_template('admin_users.html')


@admin_bp.route('/groups')
@admin_required
def groups_page():
    """分组管理页面"""
    return render_template('admin_groups.html')


# ──────────── 分组 API ────────────

@admin_bp.route('/api/groups', methods=['GET'])
@admin_required
def list_groups():
    """获取所有分组"""
    groups = Group.query.order_by(Group.id).all()
    return jsonify({'success': True, 'data': [g.to_dict() for g in groups]})


@admin_bp.route('/api/groups', methods=['POST'])
@admin_required
def create_group():
    """新建分组"""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()

    if not name:
        return jsonify({'success': False, 'message': '分组名称不能为空'}), 400

    if Group.query.filter_by(name=name).first():
        return jsonify({'success': False, 'message': f'分组「{name}」已存在'}), 400

    group = Group(name=name, description=description)
    db.session.add(group)
    db.session.commit()
    return jsonify({'success': True, 'message': '分组创建成功', 'data': group.to_dict()})


@admin_bp.route('/api/groups/<int:group_id>', methods=['PUT'])
@admin_required
def update_group(group_id):
    """编辑分组"""
    group = Group.query.get(group_id)
    if not group:
        return jsonify({'success': False, 'message': '分组不存在'}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    description = data.get('description')

    if name and name != group.name:
        if Group.query.filter_by(name=name).first():
            return jsonify({'success': False, 'message': f'分组「{name}」已存在'}), 400
        group.name = name
    if description is not None:
        group.description = description.strip()

    db.session.commit()
    return jsonify({'success': True, 'message': '分组更新成功', 'data': group.to_dict()})


@admin_bp.route('/api/groups/<int:group_id>', methods=['DELETE'])
@admin_required
def delete_group(group_id):
    """删除分组"""
    group = Group.query.get(group_id)
    if not group:
        return jsonify({'success': False, 'message': '分组不存在'}), 404

    # 检查是否有关联用户
    user_count = group.users.count()
    if user_count > 0:
        return jsonify({
            'success': False,
            'message': f'该分组下还有 {user_count} 个用户，请先移除或转移用户后再删除'
        }), 400

    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True, 'message': '分组已删除'})


# ──────────── 页面权限配置 API ────────────

@admin_bp.route('/api/page-permissions', methods=['GET'])
@admin_required
def list_page_permissions():
    """获取所有可配置的页面权限（供后台用户编辑时多选）"""
    return jsonify({'success': True, 'data': get_page_permissions_for_admin()})


# ──────────── 用户 API ────────────

@admin_bp.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    """获取所有用户"""
    users = User.query.order_by(User.id).all()
    return jsonify({'success': True, 'data': [u.to_dict() for u in users]})


@admin_bp.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """新建用户"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    display_name = (data.get('display_name') or '').strip()
    group_id = data.get('group_id')
    is_admin = bool(data.get('is_admin', False))
    is_read_only = bool(data.get('is_read_only', False))
    is_data_maintainer = bool(data.get('is_data_maintainer', False))
    allowed_pages = data.get('allowed_pages')
    if allowed_pages is not None and not isinstance(allowed_pages, list):
        allowed_pages = []
    if allowed_pages is not None:
        valid_keys = set(get_all_page_keys())
        allowed_pages = [k for k in allowed_pages if k in valid_keys]

    if not username:
        return jsonify({'success': False, 'message': '用户名不能为空'}), 400
    if not password or len(password) < 4:
        return jsonify({'success': False, 'message': '密码不能为空且至少4位'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': f'用户名「{username}」已存在'}), 400

    # 校验分组
    if group_id:
        group_id = int(group_id)
        if not Group.query.get(group_id):
            return jsonify({'success': False, 'message': '所选分组不存在'}), 400

    user = User(
        username=username,
        display_name=display_name or username,
        group_id=group_id if group_id else None,
        is_admin=is_admin,
        is_read_only=is_read_only,
        is_data_maintainer=is_data_maintainer,
        allowed_pages=allowed_pages if allowed_pages is not None else None,
        password_hash=''  # 下面设置
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '用户创建成功', 'data': user.to_dict()})


@admin_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """编辑用户"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    data = request.get_json(silent=True) or {}

    # 更新显示名
    display_name = data.get('display_name')
    if display_name is not None:
        user.display_name = display_name.strip()

    # 更新分组
    if 'group_id' in data:
        gid = data['group_id']
        if gid:
            gid = int(gid)
            if not Group.query.get(gid):
                return jsonify({'success': False, 'message': '所选分组不存在'}), 400
            user.group_id = gid
        else:
            user.group_id = None

    # 更新管理员状态
    if 'is_admin' in data:
        user.is_admin = bool(data['is_admin'])

    # 更新活跃状态
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])

    # 更新只读状态
    if 'is_read_only' in data:
        user.is_read_only = bool(data['is_read_only'])

    # 更新基础数据维护员状态
    if 'is_data_maintainer' in data:
        user.is_data_maintainer = bool(data['is_data_maintainer'])

    # 更新可访问页面
    if 'allowed_pages' in data:
        ap = data['allowed_pages']
        if not isinstance(ap, list):
            ap = []
        valid_keys = set(get_all_page_keys())
        user.allowed_pages = [k for k in ap if k in valid_keys]

    db.session.commit()
    return jsonify({'success': True, 'message': '用户信息已更新', 'data': user.to_dict()})


@admin_bp.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """重置用户密码"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    data = request.get_json(silent=True) or {}
    new_password = data.get('password', '')
    if not new_password or len(new_password) < 4:
        return jsonify({'success': False, 'message': '新密码不能为空且至少4位'}), 400

    user.set_password(new_password)
    db.session.commit()
    return jsonify({'success': True, 'message': '密码已重置'})


@admin_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """删除用户"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    # 不允许删除自己
    from flask import session
    if session.get('user_id') == user_id:
        return jsonify({'success': False, 'message': '不能删除当前登录的用户'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '用户已删除'})
