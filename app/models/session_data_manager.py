"""
会话隔离数据管理器
替代原有的单例AppDataManager，支持多用户并发操作
"""

import os
import json
import pickle
import time
import pandas as pd
import numpy as np
import redis
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from flask import session, request, current_app
from contextlib import contextmanager

from app.config import config
from app.models.database import db, UserSession, SessionDataset, CalculationHistory
from app.utils.data_utils import safe_json_convert


def safe_log(level, message):
    """安全的日志记录函数，可在应用上下文内外使用"""
    try:
        if level == 'info':
            current_app.logger.info(message)
        elif level == 'warning':
            current_app.logger.warning(message)
        elif level == 'error':
            current_app.logger.error(message)
        else:
            current_app.logger.debug(message)
    except RuntimeError:
        # 在应用上下文外时使用print，添加适当的前缀
        prefix = {'info': 'ℹ️', 'warning': '⚠️', 'error': '❌'}.get(level, '🔍')
        print(f"{prefix} {message}")


_CACHE_MISS = object()  # sentinel for negative caching


class SessionDataManager:
    """会话隔离的数据管理器"""
    
    def __init__(self, session_id: str = None, auto_create: bool = True):
        """
        初始化会话数据管理器
        
        Args:
            session_id: 会话ID，如果为None则自动生成或从Flask session获取
            auto_create: 是否自动创建会话
        """
        self.session_id = session_id or self._get_or_create_session_id(auto_create)
        self.redis_client = self._get_redis_client()
        self._cache = {}  # 本地缓存
        self._session_version = None  # 本地记录的会话版本，用于跨进程缓存一致性
        self._defer_db_writes = False
        self._pending_db_writes = {}
        self._pending_redis_writes = {}  # batch 模式下延迟的 Redis 写入
        
        # 确保会话存在
        if auto_create and not self._session_exists():
            self._create_session()
    
    def _get_redis_client(self) -> Optional[redis.Redis]:
        """获取Redis客户端"""
        try:
            if hasattr(current_app, 'redis'):
                return current_app.redis
            else:
                # 创建Redis连接
                redis_client = redis.from_url(
                    current_app.config['REDIS_URL'],
                    decode_responses=False,  # 保持二进制数据
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                # 测试连接
                redis_client.ping()
                return redis_client
        except Exception as e:
            safe_log("warning", f"Redis连接失败，将使用数据库存储: {e}")
            return None
    
    def _get_or_create_session_id(self, auto_create: bool = True) -> str:
        """获取或创建会话ID"""
        try:
            # 首先尝试从Flask session获取
            if hasattr(session, 'get') and session.get('session_id'):
                session_id = session.get('session_id')
                # 移除频繁的调试日志
                # 确保session被标记为已修改
                session.modified = True
                return session_id
            
            if auto_create:
                # 生成新的会话ID
                new_session_id = str(uuid.uuid4())
                session['session_id'] = new_session_id
                session.permanent = True
                session.modified = True  # 确保session被保存
                safe_log("info", f"创建新的会话ID: {new_session_id}")
                return new_session_id
            
            # 如果不自动创建，生成临时ID
            temp_session_id = str(uuid.uuid4())
            safe_log("warning", f"生成临时会话ID: {temp_session_id}")
            return temp_session_id
        except Exception as e:
            # 如果Flask session不可用，生成临时ID
            temp_session_id = str(uuid.uuid4())
            safe_log("warning", f"Flask session不可用，生成临时会话ID: {temp_session_id}, 错误: {e}")
            return temp_session_id
    
    def _session_exists(self) -> bool:
        """检查会话是否存在"""
        try:
            user_session = UserSession.query.filter_by(
                session_id=self.session_id,
                is_active=True
            ).first()
            return user_session is not None and not user_session.is_expired()
        except Exception as e:
            safe_log("error", f"检查会话存在性失败: {e}")
            return False
    
    def _create_session(self):
        """创建或复用会话：存在则更新（refresh），不存在则插入，避免 UNIQUE 冲突"""
        try:
            # 先按 session_id 查询（不限制 is_active/过期），避免已存在记录时 INSERT 触发 UNIQUE
            existing = UserSession.query.filter_by(session_id=self.session_id).first()
            if existing:
                existing.refresh()
                existing.is_active = True
                db.session.commit()
                safe_log("info", f"复用并刷新会话: {self.session_id}")
                return
            # 不存在则插入
            try:
                user_ip = request.environ.get('HTTP_X_FORWARDED_FOR') or request.environ.get('REMOTE_ADDR', '') or ''
                user_agent = (request.headers.get('User-Agent') or '')[:512]
            except RuntimeError:
                user_ip = ''
                user_agent = ''
            user_session = UserSession(
                session_id=self.session_id,
                user_ip=user_ip or '',
                user_agent=user_agent,
                expires_hours=24
            )
            db.session.add(user_session)
            db.session.commit()
            safe_log("info", f"创建新会话: {self.session_id}")
        except Exception as e:
            safe_log("error", f"创建会话失败: {e}")
            db.session.rollback()
    
    def refresh_session(self):
        """刷新会话时间"""
        try:
            user_session = UserSession.query.filter_by(session_id=self.session_id).first()
            if user_session:
                user_session.refresh()
                db.session.commit()
        except Exception as e:
            current_app.logger.error(f"刷新会话失败: {e}")
            db.session.rollback()
    
    def _get_cache_key(self, data_key: str) -> str:
        """生成缓存键"""
        return f"{current_app.config['SESSION_KEY_PREFIX']}{self.session_id}:{data_key}"

    def _get_version_key(self) -> str:
        """生成会话版本键"""
        prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')
        return f"{prefix}version:{self.session_id}"

    def _read_session_version(self):
        """读取Redis中的会话版本号（无Redis时回退为None）"""
        if not self.redis_client:
            return None
        try:
            raw = self.redis_client.get(self._get_version_key())
            if raw is None:
                return 0
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='ignore')
            return int(raw)
        except Exception as e:
            current_app.logger.warning(f"读取会话版本失败({self.session_id}): {e}")
            return None

    def _ensure_fresh_local_cache(self):
        """
        跨进程缓存一致性检查：
        若Redis版本与本地版本不同，清空本地缓存，强制后续从Redis/DB重载。
        """
        current_version = self._read_session_version()
        if current_version is None:
            return
        if self._session_version is None:
            self._session_version = current_version
            return
        if current_version != self._session_version:
            self._cache.clear()
            self._session_version = current_version

    def _bump_session_version(self):
        """写操作后提升会话版本，通知其他进程失效本地缓存"""
        if not self.redis_client:
            return
        try:
            self._session_version = self.redis_client.incr(self._get_version_key())
        except Exception as e:
            current_app.logger.warning(f"提升会话版本失败({self.session_id}): {e}")

    @classmethod
    def bump_session_version(cls, session_id: str, redis_client=None):
        """按 session_id 提升版本（供发布同步等外部流程调用）"""
        if not session_id:
            return
        client = redis_client
        if not client:
            try:
                if hasattr(current_app, 'redis'):
                    client = current_app.redis
            except RuntimeError:
                client = None
        if not client:
            return
        try:
            prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')
            client.incr(f"{prefix}version:{session_id}")
        except Exception as e:
            safe_log("warning", f"提升会话版本失败({session_id}): {e}")

    @classmethod
    def read_session_version(cls, session_id: str, redis_client=None) -> int:
        """读取指定 session_id 的数据版本号（无 Redis 时返回 0）"""
        if not session_id:
            return 0
        client = redis_client
        if not client:
            try:
                if hasattr(current_app, 'redis'):
                    client = current_app.redis
            except RuntimeError:
                client = None
        if not client:
            return 0
        try:
            prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')
            raw = client.get(f"{prefix}version:{session_id}")
            if raw is None:
                return 0
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='ignore')
            return int(raw)
        except Exception as e:
            safe_log("warning", f"读取会话版本失败({session_id}): {e}")
            return 0

    @classmethod
    def _sync_notification_key(cls, user_id: int) -> str:
        prefix = current_app.config.get('SESSION_KEY_PREFIX', 'session:')
        return f"{prefix}sync_notification:user_{user_id}"

    @classmethod
    def set_sync_notification(cls, user_id: int, payload: dict, redis_client=None, ttl_seconds: int = 86400):
        """写入同步通知（含发送者信息），供目标用户确认后刷新首页"""
        if not user_id or not payload:
            return
        client = redis_client
        if not client:
            try:
                if hasattr(current_app, 'redis'):
                    client = current_app.redis
            except RuntimeError:
                client = None
        if not client:
            return
        try:
            client.setex(cls._sync_notification_key(user_id), ttl_seconds, json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            safe_log("warning", f"设置同步通知失败(user_{user_id}): {e}")

    @classmethod
    def peek_sync_notification(cls, user_id: int, redis_client=None) -> Optional[dict]:
        """读取同步通知，不删除"""
        if not user_id:
            return None
        client = redis_client
        if not client:
            try:
                if hasattr(current_app, 'redis'):
                    client = current_app.redis
            except RuntimeError:
                client = None
        if not client:
            return None
        try:
            raw = client.get(cls._sync_notification_key(user_id))
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='ignore')
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception as e:
            safe_log("warning", f"读取同步通知失败(user_{user_id}): {e}")
            return None

    @classmethod
    def clear_sync_notification(cls, user_id: int, redis_client=None) -> bool:
        """清除同步通知"""
        if not user_id:
            return False
        client = redis_client
        if not client:
            try:
                if hasattr(current_app, 'redis'):
                    client = current_app.redis
            except RuntimeError:
                client = None
        if not client:
            return False
        try:
            return bool(client.delete(cls._sync_notification_key(user_id)))
        except Exception as e:
            safe_log("warning", f"清除同步通知失败(user_{user_id}): {e}")
            return False
    
    USER_UI_SETTINGS_KEY = 'user_ui_settings'

    @classmethod
    def _resolve_session_id(cls, user_id=None, session_id=None) -> Optional[str]:
        if session_id:
            return session_id
        if user_id:
            return f'user_{user_id}'
        return None

    @classmethod
    def get_user_ui_settings(cls, session_id: str = None, user_id: int = None) -> dict:
        """读取用户界面设置（如预测期数）"""
        sid = cls._resolve_session_id(user_id=user_id, session_id=session_id)
        if not sid:
            return {}
        try:
            row = SessionDataset.query.filter_by(
                session_id=sid, data_key=cls.USER_UI_SETTINGS_KEY
            ).first()
            if not row:
                return {}
            data = row.get_json_data()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            safe_log("warning", f"读取用户界面设置失败({sid}): {e}")
            return {}

    @classmethod
    def upsert_user_ui_settings(cls, session_id: str, updates: dict) -> dict:
        """合并写入用户界面设置"""
        if not session_id or not updates:
            return cls.get_user_ui_settings(session_id=session_id)
        try:
            if not UserSession.query.filter_by(session_id=session_id).first():
                db.session.add(UserSession(session_id=session_id, expires_hours=24))
            row = SessionDataset.query.filter_by(
                session_id=session_id, data_key=cls.USER_UI_SETTINGS_KEY
            ).first()
            if not row:
                row = SessionDataset(session_id=session_id, data_key=cls.USER_UI_SETTINGS_KEY)
                db.session.add(row)
            current = row.get_json_data()
            if not isinstance(current, dict):
                current = {}
            current.update(updates)
            row.set_json_data(current)
            db.session.flush()
            return current
        except Exception as e:
            safe_log("warning", f"写入用户界面设置失败({session_id}): {e}")
            db.session.rollback()
            return {}
    
    def get_data(self, key: str = None) -> Any:
        """
        获取数据
        
        Args:
            key: 数据键，如果为None则返回所有数据的字典
            
        Returns:
            数据值或数据字典
        """
        if key is None:
            return self._get_all_data()

        self._ensure_fresh_local_cache()
        
        # 检查本地缓存（包括否定缓存 _CACHE_MISS）
        cached = self._cache.get(key, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        
        # 尝试从Redis获取（Redis 故障冷却期内直接跳过）
        if self.redis_client and time.monotonic() >= SessionDataManager._redis_fail_until:
            try:
                cache_key = self._get_cache_key(key)
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    data = pickle.loads(cached_data)
                    self._cache[key] = data
                    return data
            except Exception as e:
                SessionDataManager._redis_fail_until = time.monotonic() + 60
                current_app.logger.warning(f"Redis获取数据失败(冷却60s): {e}")
        
        # 从数据库获取
        try:
            dataset = SessionDataset.query.filter_by(
                session_id=self.session_id,
                data_key=key
            ).first()
            
            if dataset:
                if dataset.data_type == 'dataframe':
                    data = dataset.get_dataframe_data()
                else:
                    data = dataset.get_json_data()
                
                if data is not None:
                    self._cache[key] = data
                    return data
        except Exception as e:
            current_app.logger.error(f"数据库获取数据失败: {e}")
        
        # 否定缓存：key 确实不存在时缓存 None，避免反复穿透 Redis+DB
        self._cache[key] = None
        return None
    
    def get_data_from_db(self, key: str) -> Any:
        """
        仅从数据库读取指定 key 的数据，不经过内存缓存和 Redis。
        用于同步后判断「是否有数据」等需要读到最新 DB 状态的场景。
        若从 DB 读到数据，会回填到 _cache，保证后续 get_data 一致。
        """
        try:
            dataset = SessionDataset.query.filter_by(
                session_id=self.session_id,
                data_key=key
            ).first()
            if not dataset:
                return None
            if dataset.data_type == 'dataframe':
                data = dataset.get_dataframe_data()
            else:
                data = dataset.get_json_data()
            if data is not None:
                self._cache[key] = data
            return data
        except Exception as e:
            current_app.logger.error(f"从数据库读取数据失败({key}): {e}")
            return None
    
    def set_data(self, key: str, value: Any):
        """
        设置数据
        
        Args:
            key: 数据键
            value: 数据值
        """
        self._cache[key] = value
        
        if self._defer_db_writes:
            # batch 模式：仅更新内存缓存 + 队列，跳过 Redis 写入
            self._pending_db_writes[key] = value
            self._pending_redis_writes[key] = value
        else:
            self._write_to_redis(key, value)
            self._save_to_database_async(key, value)
            self._bump_session_version()

    _redis_fail_until = 0  # 类级别：Redis 故障后的冷却时间戳

    def _write_to_redis(self, key: str, value: Any):
        """将单个 key 写入 Redis（失败不影响主流程，故障后冷却 60 秒）"""
        if not self.redis_client:
            return
        now = time.monotonic()
        if now < SessionDataManager._redis_fail_until:
            return
        try:
            cache_key = self._get_cache_key(key)
            serialized_data = pickle.dumps(value)
            self.redis_client.setex(
                cache_key,
                current_app.config['CACHE_TIMEOUT'],
                serialized_data
            )
        except Exception as e:
            SessionDataManager._redis_fail_until = now + 60
            current_app.logger.warning(f"Redis存储数据失败(冷却60s): {e}")

    @contextmanager
    def batch_update(self):
        """批量写入上下文：合并 set_data 调用，单次 commit + 批量 Redis 同步。"""
        prev_defer = self._defer_db_writes
        if not prev_defer:
            self._defer_db_writes = True
            self._pending_db_writes = {}
            self._pending_redis_writes = {}
        try:
            yield self
            if not prev_defer and self._pending_db_writes:
                # 所有 DB 写入共用一次 commit
                for key, value in self._pending_db_writes.items():
                    self._prepare_db_write(key, value)
                db.session.commit()
            if not prev_defer and self._pending_redis_writes:
                for key, value in self._pending_redis_writes.items():
                    self._write_to_redis(key, value)
            if not prev_defer and (self._pending_db_writes or self._pending_redis_writes):
                self._bump_session_version()
        except Exception:
            db.session.rollback()
            raise
        finally:
            if not prev_defer:
                self._defer_db_writes = False
                self._pending_db_writes = {}
                self._pending_redis_writes = {}
    
    def _prepare_db_write(self, key: str, value: Any):
        """准备 DB 写入（SELECT + UPDATE/INSERT），但不提交。供 batch_update 使用。"""
        dataset = SessionDataset.query.filter_by(
            session_id=self.session_id,
            data_key=key
        ).first()
        
        if not dataset:
            dataset = SessionDataset(
                session_id=self.session_id,
                data_key=key
            )
            db.session.add(dataset)
        
        if isinstance(value, pd.DataFrame):
            dataset.set_dataframe_data(value)
        else:
            dataset.set_json_data(value)

    def _save_to_database_async(self, key: str, value: Any):
        """单 key 保存到数据库（含 commit），用于非 batch 模式。"""
        try:
            self._prepare_db_write(key, value)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"数据库存储数据失败: {e}")
            db.session.rollback()
    
    def _get_all_data(self) -> Dict[str, Any]:
        """获取所有数据"""
        self._ensure_fresh_local_cache()
        all_data = {}
        
        try:
            # 从数据库获取所有数据键
            datasets = SessionDataset.query.filter_by(session_id=self.session_id).all()
            
            for dataset in datasets:
                if dataset.data_type == 'dataframe':
                    data = dataset.get_dataframe_data()
                else:
                    data = dataset.get_json_data()
                
                if data is not None:
                    all_data[dataset.data_key] = data
            
            # 合并本地缓存中的数据
            all_data.update(self._cache)
            
        except Exception as e:
            current_app.logger.error(f"获取所有数据失败: {e}")
        
        return all_data
    
    def update_status(self, status: str, progress: Optional[int] = None):
        """
        更新状态
        
        Args:
            status: 状态描述
            progress: 进度百分比
        """
        status_data = {
            'status': status,
            'progress': progress if progress is not None else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.set_data('status', status)
        if progress is not None:
            self.set_data('progress', progress)
    
    def delete_data(self, key: str):
        """删除指定数据"""
        # 从本地缓存删除
        self._cache.pop(key, None)
        
        # 从Redis删除
        if self.redis_client:
            try:
                cache_key = self._get_cache_key(key)
                self.redis_client.delete(cache_key)
            except Exception as e:
                current_app.logger.warning(f"Redis删除数据失败: {e}")
        
        # 从数据库删除
        try:
            dataset = SessionDataset.query.filter_by(
                session_id=self.session_id,
                data_key=key
            ).first()
            
            if dataset:
                db.session.delete(dataset)
                db.session.commit()
                self._bump_session_version()
        except Exception as e:
            current_app.logger.error(f"数据库删除数据失败: {e}")
            db.session.rollback()
    
    def clear_data(self, key: str):
        """清除特定数据（别名：delete_data）"""
        self.delete_data(key)
    
    def clear_all_data(self):
        """清除所有会话数据"""
        # 设置数据清除标志（防止备用会话机制恢复数据）
        self.set_data('__data_cleared__', True)
        
        # 清除本地缓存
        self._cache.clear()
        
        # 清除Redis缓存
        if self.redis_client:
            try:
                pattern = self._get_cache_key('*')
                keys = self.redis_client.keys(pattern)
                # 保留清除标志，删除其他所有数据
                keys_to_delete = [k for k in keys if not k.endswith('__data_cleared__')]
                if keys_to_delete:
                    self.redis_client.delete(*keys_to_delete)
            except Exception as e:
                current_app.logger.warning(f"Redis清除数据失败: {e}")
        
        # 清除数据库数据（保留清除标志）
        try:
            SessionDataset.query.filter(
                SessionDataset.session_id == self.session_id,
                SessionDataset.data_key != '__data_cleared__'
            ).delete()
            db.session.commit()
            self._bump_session_version()
        except Exception as e:
            current_app.logger.error(f"数据库清除数据失败: {e}")
            db.session.rollback()
    
    def record_calculation(self, calculation_type: str, status: str = 'started',
                          input_parameters: Dict = None, result_summary: Dict = None,
                          error_message: str = None, duration: float = None):
        """记录计算历史"""
        try:
            calc_history = CalculationHistory(
                session_id=self.session_id,
                calculation_type=calculation_type,
                status=status,
                input_parameters=input_parameters or {},
                result_summary=result_summary,
                error_message=error_message,
                duration=duration
            )
            
            if status in ['completed', 'failed']:
                calc_history.completed_at = datetime.utcnow()
            
            db.session.add(calc_history)
            db.session.commit()
            
            return calc_history.id
            
        except Exception as e:
            current_app.logger.error(f"记录计算历史失败: {e}")
            db.session.rollback()
            return None
    
    def get_calculation_history(self, limit: int = 10):
        """获取计算历史"""
        try:
            history = CalculationHistory.query.filter_by(
                session_id=self.session_id
            ).order_by(CalculationHistory.started_at.desc()).limit(limit).all()
            
            return [calc.to_dict() for calc in history]
        except Exception as e:
            current_app.logger.error(f"获取计算历史失败: {e}")
            return []
    
    def safe_json_convert(self, df: pd.DataFrame) -> list:
        """安全的DataFrame转JSON转换"""
        return safe_json_convert(df)
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        try:
            user_session = UserSession.query.filter_by(session_id=self.session_id).first()
            if user_session:
                return user_session.to_dict()
        except Exception as e:
            current_app.logger.error(f"获取会话信息失败: {e}")
        
        return {
            'session_id': self.session_id,
            'created_at': None,
            'last_accessed': None,
            'expires_at': None,
            'is_active': False
        }
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # 刷新会话时间
        self.refresh_session()


class SessionDataManagerFactory:
    """会话数据管理器工厂"""
    
    _managers: Dict[str, SessionDataManager] = {}
    
    @classmethod
    def get_manager(cls, session_id: str = None, auto_create: bool = True) -> SessionDataManager:
        """
        获取会话数据管理器实例
        
        Args:
            session_id: 会话ID
            auto_create: 是否自动创建会话
            
        Returns:
            SessionDataManager实例
        """
        # 移除频繁的调试日志，只在创建新会话时记录
        
        if session_id is None:
            try:
                # 从Flask session获取或创建
                if 'session_id' not in session and auto_create:
                    new_session_id = str(uuid.uuid4())
                    session['session_id'] = new_session_id
                    session.permanent = True
                    safe_log("info", f"创建新的会话ID: {new_session_id}")
                    # 立即保存session
                    session.modified = True
                session_id = session.get('session_id')
                
                # 确保session被标记为已修改，以便保存
                if session_id and 'session_id' in session:
                    session.modified = True
                    
            except Exception as e:
                safe_log("warning", f"无法访问Flask session，错误: {e}")
                if auto_create:
                    session_id = str(uuid.uuid4())
                    safe_log("info", f"生成临时session_id: {session_id}")
        
        if not session_id:
            raise ValueError("无法获取或创建会话ID")
        
        # 检查是否已有管理器实例
        if session_id not in cls._managers:
            safe_log("info", f"创建新的SessionDataManager实例: {session_id}")
            cls._managers[session_id] = SessionDataManager(session_id, auto_create)
        # 移除复用实例的日志，避免频繁输出
        
        return cls._managers[session_id]
    
    @classmethod
    def get_all_sessions(cls) -> Dict[str, SessionDataManager]:
        """获取所有活跃的会话管理器"""
        return cls._managers.copy()
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """清理过期会话"""
        try:
            # 查找过期会话
            expired_sessions = UserSession.query.filter(
                UserSession.expires_at < datetime.utcnow()
            ).all()
            
            for user_session in expired_sessions:
                # 清理Redis缓存
                try:
                    if hasattr(current_app, 'redis') and current_app.redis:
                        pattern = f"{current_app.config['SESSION_KEY_PREFIX']}{user_session.session_id}:*"
                        keys = current_app.redis.keys(pattern)
                        if keys:
                            current_app.redis.delete(*keys)
                except Exception as e:
                    current_app.logger.warning(f"清理Redis缓存失败: {e}")
                
                # 标记会话为非活跃
                user_session.is_active = False
                
                # 从工厂中移除管理器
                cls._managers.pop(user_session.session_id, None)
            
            db.session.commit()
            current_app.logger.info(f"清理了 {len(expired_sessions)} 个过期会话")
            
        except Exception as e:
            current_app.logger.error(f"清理过期会话失败: {e}")
            db.session.rollback()


# 向后兼容的获取方法
def get_session_data_manager(session_id: str = None) -> SessionDataManager:
    """获取会话数据管理器（向后兼容）"""
    return SessionDataManagerFactory.get_manager(session_id) 