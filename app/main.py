import os
import logging
from app import create_app
from app.models.compatibility import migrate_from_pickle

def run_app():
    """运行应用"""
    # 配置日志级别以减少频繁的访问日志
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # 减少HTTP访问日志
    
    # 获取环境配置
    config_name = os.environ.get('FLASK_ENV', 'development')
    app = create_app(config_name)
    
    # 在应用上下文中执行初始化
    with app.app_context():
        # 尝试从旧的pickle文件迁移数据
        try:
            migrate_from_pickle()
        except Exception as e:
            app.logger.warning(f"数据迁移失败: {e}")
        
        # 程序启动时自动清除所有会话数据（可通过 CLEAR_SESSIONS_ON_STARTUP=0 跳过以加快启动）
        clear_on_startup = os.environ.get('CLEAR_SESSIONS_ON_STARTUP', '1').strip().lower() not in ('0', 'false', 'no', '')
        if clear_on_startup:
            try:
                _clear_all_sessions_data(app)
            except Exception as e:
                app.logger.warning(f"启动时清除数据失败: {e}")
        else:
            app.logger.info("已跳过启动时清除会话数据（CLEAR_SESSIONS_ON_STARTUP=0）")

        # 从磁盘固化文件自动加载全局期初库存（不依赖会话 DB）
        try:
            _load_global_opening_inventory_from_disk(app)
        except Exception as e:
            app.logger.warning(f"启动时加载固化期初库存失败: {e}")

        # 确保数据完整性
        _ensure_system_health(app)
    
    return app

def _clear_all_sessions_data(app):
    """清除所有会话的数据（等同于首页"清除数据"按钮功能）。优化：先批量删 SessionDataset 与 Redis，避免逐会话重操作。"""
    try:
        from app.models.database import db, SessionDataset
        from app.models.session_data_manager import SessionDataManagerFactory

        app.logger.info("程序启动：正在清除所有会话数据...")

        # 1. 先批量删除 SessionDataset 中所有记录（一次性清空，避免逐会话 set_data）
        try:
            deleted_count = SessionDataset.query.delete(synchronize_session=False)
            db.session.commit()
            app.logger.info(f"已清除数据库中的会话数据: {deleted_count} 条记录")
        except Exception as e:
            app.logger.warning(f"清除数据库数据失败: {e}")
            db.session.rollback()
            deleted_count = 0

        # 2. 再清除 Redis 缓存（如果有）
        try:
            if hasattr(app, 'redis') and app.redis:
                pattern = f"{app.config.get('SESSION_KEY_PREFIX', 'session:')}*"
                keys = app.redis.keys(pattern)
                if keys:
                    app.redis.delete(*keys)
                    app.logger.info(f"已清除Redis缓存: {len(keys)} 个键")
        except Exception as e:
            app.logger.warning(f"清除Redis缓存失败: {e}")

        # 3. 清空内存中的 SessionDataManager 缓存，避免旧数据被复用
        try:
            SessionDataManagerFactory._managers.clear()
        except Exception as e:
            app.logger.warning(f"清空会话管理器缓存失败: {e}")

        app.logger.info("程序启动：已清除所有会话数据，等同于首页'清除数据'按钮功能")
    except Exception as e:
        app.logger.error(f"清除所有会话数据失败: {e}")
        import traceback
        traceback.print_exc()

def _load_global_opening_inventory_from_disk(app):
    """从 data/persistent 自动加载期初库存到全局会话。"""
    from app.services.opening_inventory_store import (
        has_persistent_file,
        load_from_disk_into_memory,
    )

    if not has_persistent_file():
        app.logger.info("未找到固化期初库存文件，等待用户上传")
        return

    ok, message = load_from_disk_into_memory()
    if ok:
        app.logger.info(f"期初库存固化加载成功: {message}")
    else:
        app.logger.warning(f"期初库存固化加载失败: {message}")


def _ensure_system_health(app):
    """确保系统健康状态"""
    try:
        # 检查Redis连接
        if hasattr(app, 'redis') and app.redis:
            app.redis.ping()
            app.logger.info("Redis连接正常")
        else:
            app.logger.info("使用文件系统会话存储")
        
        # 检查数据库连接
        from app.models.database import db
        from sqlalchemy import text
        with db.engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        app.logger.info("数据库连接正常")
        
        # 记录系统启动
        app.logger.info(f"系统启动成功 - 环境: {app.config.get('DATABASE_TYPE', 'unknown')}")
        
    except Exception as e:
        app.logger.error(f"系统健康检查失败: {e}")

if __name__ == '__main__':
    app = run_app()
    
    # 生产模式配置
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    
    app.run(debug=debug_mode, host=host, port=port)
