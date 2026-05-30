import os
import redis
from flask import Flask
from flask_session import Session
from app.config import config_map
from app.models.database import db

def create_app(config_name=None):
    """创建Flask应用实例"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    config_class = config_map.get(config_name, config_map['development'])
    
    # 获取项目根目录路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_folder = os.path.join(project_root, 'templates')
    static_folder = os.path.join(project_root, 'static')
    
    app = Flask(__name__, 
                template_folder=template_folder,
                static_folder=static_folder if os.path.exists(static_folder) else None)
    app.config.from_object(config_class)
    
    # 设置数据库URI（因为是property，需要手动设置）
    app.config['SQLALCHEMY_DATABASE_URI'] = config_class().SQLALCHEMY_DATABASE_URI
    
    # 配置上传文件夹
    upload_folder = os.path.join(project_root, 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    app.config['UPLOAD_FOLDER'] = upload_folder
    
    # 确保数据存储目录存在
    data_storage_dir = os.path.join(project_root, app.config['DATA_STORAGE_DIR'])
    if not os.path.exists(data_storage_dir):
        os.makedirs(data_storage_dir)

    snapshots_dir = os.path.join(project_root, 'data', 'snapshots')
    if not os.path.exists(snapshots_dir):
        os.makedirs(snapshots_dir)
    
    # 初始化数据库
    db.init_app(app)
    
    # 初始化Redis连接
    try:
        redis_client = redis.from_url(
            app.config['REDIS_URL'],
            decode_responses=False,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        # 测试连接
        redis_client.ping()
        app.redis = redis_client
        app.config['SESSION_REDIS'] = redis_client
        app.logger.info(f"Redis连接成功: {app.config['REDIS_URL']}")
    except Exception as e:
        app.logger.warning(f"Redis连接失败，将使用文件会话存储: {e}")
        # 如果Redis不可用，回退到文件系统会话存储
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_FILE_DIR'] = os.path.join(data_storage_dir, 'sessions')
        # 禁用签名以避免bytes/string类型冲突
        app.config['SESSION_USE_SIGNER'] = False
        if not os.path.exists(app.config['SESSION_FILE_DIR']):
            os.makedirs(app.config['SESSION_FILE_DIR'])
        app.redis = None
    
    # 初始化会话管理
    Session(app)
    # Werkzeug 3+ 要求 Cookie 值为 str；flask-session 0.5 在 SESSION_USE_SIGNER 下可能传入 bytes
    if app.config.get('SESSION_TYPE') == 'redis' and app.config.get('SESSION_REDIS') is not None:
        from app.session_interface_fix import BytesSafeRedisSessionInterface
        app.session_interface = BytesSafeRedisSessionInterface(
            app.config['SESSION_REDIS'],
            app.config['SESSION_KEY_PREFIX'],
            app.config['SESSION_USE_SIGNER'],
            app.config['SESSION_PERMANENT'],
        )

    # 添加before_request钩子确保session正常工作
    @app.before_request
    def ensure_session():
        """确保session正常工作"""
        from flask import session
        # 确保session_id是字符串类型
        if 'session_id' in session:
            sid = session['session_id']
            if isinstance(sid, bytes):
                session['session_id'] = sid.decode('utf-8')
    
    # 确保session配置正确
    with app.app_context():
        # 测试session是否正常工作
        try:
            from flask import session as test_session
            app.logger.info("Flask-Session初始化成功")
        except Exception as e:
            app.logger.error(f"Flask-Session初始化失败: {e}")
    
    # 创建数据库表
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("数据库表创建成功")
            # 迁移：为已有 users 表添加 is_read_only 列（若不存在）
            try:
                from sqlalchemy import text
                if db.engine.dialect.name == 'sqlite':
                    db.session.execute(text("ALTER TABLE users ADD COLUMN is_read_only BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    app.logger.info("已添加 users.is_read_only 列")
            except Exception as mig:
                if 'duplicate column name' in str(mig).lower() or 'already exists' in str(mig).lower():
                    pass
                else:
                    app.logger.warning(f"迁移 is_read_only 列时: {mig}")
                db.session.rollback()
            # 迁移：为已有 users 表添加 allowed_pages 列（若不存在）
            try:
                from sqlalchemy import text
                if db.engine.dialect.name == 'sqlite':
                    db.session.execute(text("ALTER TABLE users ADD COLUMN allowed_pages TEXT DEFAULT NULL"))
                    db.session.commit()
                    app.logger.info("已添加 users.allowed_pages 列")
            except Exception as mig2:
                if 'duplicate column name' in str(mig2).lower() or 'already exists' in str(mig2).lower():
                    pass
                else:
                    app.logger.warning(f"迁移 allowed_pages 列时: {mig2}")
                db.session.rollback()
            # 迁移：为已有 users 表添加 is_data_maintainer 列（若不存在）
            try:
                from sqlalchemy import text
                if db.engine.dialect.name == 'sqlite':
                    db.session.execute(text("ALTER TABLE users ADD COLUMN is_data_maintainer BOOLEAN DEFAULT 0"))
                    db.session.commit()
                    app.logger.info("已添加 users.is_data_maintainer 列")
            except Exception as mig3:
                if 'duplicate column name' in str(mig3).lower() or 'already exists' in str(mig3).lower():
                    pass
                else:
                    app.logger.warning(f"迁移 is_data_maintainer 列时: {mig3}")
                db.session.rollback()
            _migrate_user_allowed_pages_home(app)
        except Exception as e:
            app.logger.error(f"数据库表创建失败: {e}")
    
    # 初始化薪酬核算基础数据（如果数据文件为空）
    with app.app_context():
        try:
            from data.base_data.salary_accounting_data import SALARY_ACCOUNTING_DATA
            if not SALARY_ACCOUNTING_DATA:
                # 如果数据为空，尝试从Excel文件读取并固化
                _init_salary_accounting_data_from_excel(project_root)
        except Exception as e:
            app.logger.warning(f"初始化薪酬核算基础数据失败: {e}")
    
    # 初始化制造费用基础数据（如果数据文件为空）
    with app.app_context():
        try:
            from data.base_data.manufacturing_cost_data import MANUFACTURING_COST_DATA
            if not MANUFACTURING_COST_DATA:
                # 如果数据为空，尝试从Excel文件读取并固化
                _init_manufacturing_cost_data_from_excel(project_root)
        except Exception as e:
            app.logger.warning(f"初始化制造费用基础数据失败: {e}")
    
    # 注册蓝图
    from app.api.main_routes import main_bp
    from app.api.calculation_api import calculation_bp
    from app.api.data_management_api import data_management_bp
    from app.api.statistics_api import statistics_bp
    from app.api.system_api import system_bp
    from app.api.cost_forecast_api import cost_forecast_bp
    from app.api.auth_api import auth_bp
    from app.api.admin_api import admin_bp
    from app.api.snapshot_api import snapshot_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(calculation_bp, url_prefix='/api')
    app.register_blueprint(data_management_bp, url_prefix='/api/data-management')
    app.register_blueprint(statistics_bp, url_prefix='/api/statistics')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    app.register_blueprint(cost_forecast_bp)
    app.register_blueprint(snapshot_bp, url_prefix='/api/snapshot')

    @app.context_processor
    def inject_allowed_pages():
        """向所有模板注入展开后的页面权限列表，供前端菜单过滤使用。"""
        from flask import session
        from app.core.page_permissions import expand_allowed_pages, get_all_page_keys
        from app.models.database import User
        user_id = session.get('user_id')
        if not user_id:
            return {'allowed_pages': []}
        user = User.query.get(user_id)
        if not user or not user.is_active:
            return {'allowed_pages': []}
        if user.is_admin:
            return {'allowed_pages': get_all_page_keys()}
        ap = session.get('allowed_pages')
        if ap is None:
            ap = getattr(user, 'allowed_pages', None) or []
        return {'allowed_pages': expand_allowed_pages(ap)}
    
    # 初始化默认分组和管理员账号
    _init_default_users_and_groups(app)
    
    # 注册定时任务（清理过期会话）
    register_scheduled_tasks(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    return app

def register_scheduled_tasks(app):
    """注册定时任务"""
    from threading import Timer
    from app.models.session_data_manager import SessionDataManagerFactory
    import atexit
    
    # 添加一个全局标志来控制定时器
    app._cleanup_running = True
    
    def cleanup_sessions():
        """定时清理过期会话"""
        # 检查是否应该继续运行
        if not getattr(app, '_cleanup_running', False):
            return
            
        with app.app_context():
            try:
                SessionDataManagerFactory.cleanup_expired_sessions()
            except Exception as e:
                app.logger.error(f"定时清理会话失败: {e}")
            
            # 重新安排下次清理（每小时执行一次）
            # 只有在应用仍在运行时才创建新定时器
            if getattr(app, '_cleanup_running', False):
                try:
                    Timer(3600, cleanup_sessions).start()
                except RuntimeError:
                    # 如果无法创建线程（如解释器关闭时），静默忽略
                    pass
    
    def stop_cleanup():
        """停止清理任务"""
        app._cleanup_running = False
    
    # 注册程序退出时的清理函数
    atexit.register(stop_cleanup)
    
    # 启动定时清理任务（延迟5分钟启动）
    try:
        Timer(300, cleanup_sessions).start()
    except RuntimeError:
        # 如果无法创建线程，静默忽略
        pass

def _init_salary_accounting_data_from_excel(project_root):
    """从Excel文件初始化薪酬核算基础数据并固化到Python文件"""
    try:
        import pandas as pd
        excel_file = os.path.join(project_root, '薪酬核算基础数据.xlsx')
        
        if not os.path.exists(excel_file):
            return False
        
        print(f"[初始化] 正在从Excel文件读取薪酬核算基础数据: {excel_file}")
        df = pd.read_excel(excel_file)
        df = df.dropna(how='all')
        
        if df.empty:
            return False
        
        print(f"[初始化] 成功读取 {len(df)} 条记录，正在固化数据...")
        
        file_content = '''# 薪酬核算基础数据 - 内置数据
# 数据来源：薪酬核算基础数据.xlsx
# 说明：此文件由 scripts/init_salary_accounting_from_excel.py 自动生成

import pandas as pd
import os

# 完整的薪酬核算基础数据
SALARY_ACCOUNTING_DATA = [
'''
        
        for index, row in df.iterrows():
            if row.isna().all():
                continue
            
            record_parts = []
            for col in df.columns:
                value = row[col]
                if pd.isna(value):
                    record_parts.append(f'"{col}": None')
                elif isinstance(value, (int, float)):
                    if pd.isna(value):
                        record_parts.append(f'"{col}": None')
                    else:
                        record_parts.append(f'"{col}": {value}')
                else:
                    str_value = str(value).replace('"', '\\"').replace('\\', '\\\\')
                    record_parts.append(f'"{col}": "{str_value}"')
            
            record_str = '{' + ', '.join(record_parts) + '}'
            file_content += f'    {record_str},\n'
        
        file_content += ''']

def get_salary_accounting_dataframe():
    """获取薪酬核算基础数据DataFrame"""
    return pd.DataFrame(SALARY_ACCOUNTING_DATA)

def filter_by_category(category):
    """根据类别筛选数据（如果有类别字段）"""
    df = get_salary_accounting_dataframe()
    if df.empty:
        return df
    if '类别' in df.columns:
        return df[df['类别'] == category]
    return df

def get_all_categories():
    """获取所有类别列表（如果有类别字段）"""
    df = get_salary_accounting_dataframe()
    if df.empty:
        return []
    if '类别' in df.columns:
        return df['类别'].unique().tolist()
    return []

def get_category_stats():
    """获取类别统计信息（如果有类别字段）"""
    df = get_salary_accounting_dataframe()
    if df.empty:
        return {}
    if '类别' in df.columns:
        return df['类别'].value_counts().to_dict()
    return {}

def get_salary_accounting_by_id(record_id):
    """根据记录ID获取薪酬核算基础数据"""
    df = get_salary_accounting_dataframe()
    if df.empty:
        return None
    if len(df) > 0:
        first_col = df.columns[0]
        if 'ID' in first_col.upper() or '代码' in first_col or '编号' in first_col:
            result = df[df[first_col].astype(str) == str(record_id)]
        else:
            try:
                idx = int(record_id)
                if 0 <= idx < len(df):
                    result = df.iloc[[idx]]
                else:
                    return None
            except (ValueError, TypeError):
                return None
        
        if len(result) > 0:
            return result.iloc[0].to_dict()
    return None
'''
        
        output_dir = os.path.join(project_root, 'data', 'base_data')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'salary_accounting_data.py')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        print(f"[初始化] ✓ 成功固化数据到: {output_file}")
        print(f"[初始化] ✓ 共固化 {len(df)} 条记录")
        
        # 重新加载模块以使用新数据
        import importlib
        import sys
        if 'data.base_data.salary_accounting_data' in sys.modules:
            importlib.reload(sys.modules['data.base_data.salary_accounting_data'])
        
        return True
        
    except Exception as e:
        print(f"[初始化] 固化薪酬核算基础数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def _init_manufacturing_cost_data_from_excel(project_root):
    """从Excel文件初始化制造费用基础数据并固化到Python文件"""
    try:
        import pandas as pd
        excel_file = os.path.join(project_root, '制造费用基础数据.xlsx')
        
        if not os.path.exists(excel_file):
            return False
        
        print(f"[初始化] 正在从Excel文件读取制造费用基础数据: {excel_file}")
        df = pd.read_excel(excel_file)
        df = df.dropna(how='all')
        
        if df.empty:
            return False
        
        print(f"[初始化] 成功读取 {len(df)} 条记录，正在固化数据...")
        
        file_content = '''# 制造费用基础数据 - 内置数据
# 数据来源：制造费用基础数据.xlsx
# 说明：此文件由 scripts/init_manufacturing_cost_from_excel.py 自动生成

import pandas as pd
import os

# 完整的制造费用基础数据
MANUFACTURING_COST_DATA = [
'''
        
        for index, row in df.iterrows():
            if row.isna().all():
                continue
            
            record_parts = []
            for col in df.columns:
                value = row[col]
                if pd.isna(value):
                    record_parts.append(f'"{col}": None')
                elif isinstance(value, (int, float)):
                    if pd.isna(value):
                        record_parts.append(f'"{col}": None')
                    else:
                        record_parts.append(f'"{col}": {value}')
                else:
                    str_value = str(value).replace('"', '\\"').replace('\\', '\\\\')
                    record_parts.append(f'"{col}": "{str_value}"')
            
            record_str = '{' + ', '.join(record_parts) + '}'
            file_content += f'    {record_str},\n'
        
        file_content += ''']

def get_manufacturing_cost_dataframe():
    """获取制造费用基础数据DataFrame"""
    return pd.DataFrame(MANUFACTURING_COST_DATA)

def filter_by_category(category):
    """根据类别筛选数据（如果有类别字段）"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return df
    if '类别' in df.columns:
        return df[df['类别'] == category]
    return df

def get_all_categories():
    """获取所有类别列表（如果有类别字段）"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return []
    if '类别' in df.columns:
        return df['类别'].unique().tolist()
    return []

def get_category_stats():
    """获取类别统计信息（如果有类别字段）"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return {}
    if '类别' in df.columns:
        return df['类别'].value_counts().to_dict()
    return {}

def get_manufacturing_cost_by_id(record_id):
    """根据记录ID获取制造费用基础数据"""
    df = get_manufacturing_cost_dataframe()
    if df.empty:
        return None
    # 使用"费用名称"作为主键
    if len(df) > 0:
        if '费用名称' in df.columns:
            result = df[df['费用名称'].astype(str) == str(record_id)]
            if len(result) > 0:
                return result.iloc[0].to_dict()
        # 如果找不到费用名称字段，尝试使用第一列
        first_col = df.columns[0]
        if 'ID' in first_col.upper() or '代码' in first_col or '编号' in first_col:
            result = df[df[first_col].astype(str) == str(record_id)]
        else:
            try:
                idx = int(record_id)
                if 0 <= idx < len(df):
                    result = df.iloc[[idx]]
                else:
                    return None
            except (ValueError, TypeError):
                return None
        
        if len(result) > 0:
            return result.iloc[0].to_dict()
    return None
'''
        
        output_dir = os.path.join(project_root, 'data', 'base_data')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'manufacturing_cost_data.py')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        print(f"[初始化] ✓ 成功固化数据到: {output_file}")
        print(f"[初始化] ✓ 共固化 {len(df)} 条记录")
        
        # 重新加载模块以使用新数据
        import importlib
        import sys
        if 'data.base_data.manufacturing_cost_data' in sys.modules:
            importlib.reload(sys.modules['data.base_data.manufacturing_cost_data'])
        
        return True
        
    except Exception as e:
        print(f"[初始化] 固化制造费用基础数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def _migrate_user_allowed_pages_home(app):
    """一次性迁移：旧 cost/revenue 权限合并为 home；历史空权限视为仅首页。"""
    from app.models.database import User
    from app.core.page_permissions import normalize_stored_allowed_pages, _coerce_pages_list

    with app.app_context():
        try:
            changed = 0
            for user in User.query.all():
                if user.is_admin:
                    continue
                stored = getattr(user, 'allowed_pages', None)
                coerced = _coerce_pages_list(stored)
                new_ap = ['home'] if not coerced else normalize_stored_allowed_pages(stored)
                if new_ap != coerced:
                    user.allowed_pages = new_ap
                    changed += 1
            if changed:
                db.session.commit()
                app.logger.info(f"已迁移 {changed} 个用户的 allowed_pages 至首页权限模型")
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"迁移 allowed_pages 至 home 时: {e}")


def _init_default_users_and_groups(app):
    """初始化默认分组和管理员账号（仅首次运行时创建）"""
    from app.models.database import User, Group

    with app.app_context():
        try:
            # 默认分组
            default_groups = [
                {'name': '管理员', 'description': '系统管理员组'},
                {'name': '领导', 'description': '公司领导层'},
                {'name': '财务部', 'description': '财务部门'},
                {'name': '电废事业部', 'description': '电废事业部门'},
            ]
            for ginfo in default_groups:
                if not Group.query.filter_by(name=ginfo['name']).first():
                    db.session.add(Group(**ginfo))

            db.session.commit()

            # 默认管理员账号
            if not User.query.filter_by(username='admin').first():
                admin_group = Group.query.filter_by(name='管理员').first()
                admin_user = User(
                    username='admin',
                    display_name='系统管理员',
                    group_id=admin_group.id if admin_group else None,
                    is_admin=True,
                    password_hash=''
                )
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                db.session.commit()
                app.logger.info("默认管理员账号已创建 (admin / admin123)")

        except Exception as e:
            app.logger.warning(f"初始化默认用户和分组失败: {e}")


def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return {'error': '页面未找到', 'code': 404}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': '服务器内部错误', 'code': 500}, 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return {'error': '上传文件过大', 'code': 413}, 413
