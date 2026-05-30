"""
数据库模型定义
支持用户会话隔离和数据持久化
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json
import pandas as pd
from io import StringIO
import warnings

db = SQLAlchemy()
Base = declarative_base()


class Group(db.Model):
    """分组/部门表"""
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(String(256), default='')
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联用户
    users = relationship("User", back_populates="group", lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_count': self.users.count()
        }


class User(db.Model):
    """用户表"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(64), default='')
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_read_only = Column(Boolean, default=False)  # 只读用户：仅可查看，不可上传/计算
    is_data_maintainer = Column(Boolean, default=False)  # 基础数据维护员：可编辑基础数据并发布同步
    allowed_pages = Column(JSON, default=None)  # 可访问页面权限键列表；home=首页，无 home 时登录进入基础数据管理
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # 关联分组
    group = relationship("Group", back_populates="users")

    def set_password(self, password):
        """设置密码（哈希存储）"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """校验密码"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        ap = getattr(self, 'allowed_pages', None)
        if ap is None:
            ap = []
        if isinstance(ap, (str, bytes)):
            try:
                ap = json.loads(ap) if ap else []
            except (TypeError, ValueError):
                ap = []
        if hasattr(ap, '__iter__') and not isinstance(ap, (str, bytes)):
            ap = list(ap)
        else:
            ap = []
        from app.core.page_permissions import normalize_stored_allowed_pages
        ap = normalize_stored_allowed_pages(ap)
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name or '',
            'group_id': self.group_id,
            'group_name': self.group.name if self.group else '',
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'is_read_only': getattr(self, 'is_read_only', False),
            'is_data_maintainer': getattr(self, 'is_data_maintainer', False),
            'allowed_pages': ap,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class UserSession(db.Model):
    """用户会话表"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_ip = Column(String(45))  # 支持IPv6
    user_agent = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # 会话元数据
    session_metadata = Column(JSON)
    
    # 关联的数据集
    datasets = relationship("SessionDataset", back_populates="session", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_session_active', 'session_id', 'is_active'),
        Index('idx_session_expires', 'expires_at'),
    )
    
    def __init__(self, session_id, user_ip=None, user_agent=None, expires_hours=24):
        self.session_id = session_id
        self.user_ip = user_ip
        self.user_agent = user_agent
        self.expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        self.session_metadata = {}
    
    def is_expired(self):
        """检查会话是否过期"""
        return datetime.utcnow() > self.expires_at
    
    def refresh(self):
        """刷新会话时间"""
        self.last_accessed = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(hours=24)
    
    def to_dict(self):
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'metadata': self.session_metadata
        }

class SessionDataset(db.Model):
    """会话数据集表 - 存储每个会话的计算数据"""
    __tablename__ = 'session_datasets'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), ForeignKey('user_sessions.session_id'), nullable=False, index=True)
    data_key = Column(String(64), nullable=False)  # 数据键名
    data_type = Column(String(32))  # 数据类型: dataframe, dict, list, string, number
    
    # 数据存储
    data_json = Column(Text)  # JSON格式的数据
    data_binary = Column(db.LargeBinary)  # 二进制数据（用于大型DataFrame）
    
    # 元信息
    data_size = Column(Integer)  # 数据大小（字节）
    row_count = Column(Integer)  # DataFrame行数
    column_count = Column(Integer)  # DataFrame列数
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联
    session = relationship("UserSession", back_populates="datasets")
    
    # 索引
    __table_args__ = (
        Index('idx_session_data', 'session_id', 'data_key'),
    )
    
    def set_dataframe_data(self, df):
        """存储DataFrame数据"""
        if df is not None and not df.empty:
            self.data_type = 'dataframe'
            self.row_count = len(df)
            self.column_count = len(df.columns)
            
            try:
                json_data = df.to_json(orient='records', date_format='iso')
                if len(json_data) < 1024 * 1024:
                    self.data_json = json_data
                    self.data_binary = None  # 清理互斥字段
                    self.data_size = len(json_data)
                else:
                    import pickle
                    binary_data = pickle.dumps(df)
                    self.data_binary = binary_data
                    self.data_json = None  # 清理互斥字段
                    self.data_size = len(binary_data)
            except Exception as e:
                import pickle
                binary_data = pickle.dumps(df)
                self.data_binary = binary_data
                self.data_json = None
                self.data_size = len(binary_data)
    
    def get_dataframe_data(self):
        """获取DataFrame数据"""
        if self.data_type != 'dataframe':
            return None
            
        try:
            if self.data_json:
                # 使用StringIO包装JSON字符串以避免FutureWarning
                return pd.read_json(StringIO(self.data_json), orient='records')
            elif self.data_binary:
                import pickle
                return pickle.loads(self.data_binary)
        except Exception as e:
            print(f"获取DataFrame数据失败: {e}")
            return None
    
    def set_json_data(self, data):
        """存储JSON数据"""
        self.data_type = type(data).__name__
        self.data_json = json.dumps(data, ensure_ascii=False, default=str)
        self.data_binary = None  # 清理互斥字段
        self.data_size = len(self.data_json)
    
    def get_json_data(self):
        """获取JSON数据"""
        if self.data_json:
            return json.loads(self.data_json)
        return None

class CalculationHistory(db.Model):
    """计算历史记录表"""
    __tablename__ = 'calculation_history'
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), ForeignKey('user_sessions.session_id'), nullable=False, index=True)
    
    # 计算信息
    calculation_type = Column(String(64))  # 计算类型：auto_process, extract_data, calculate_disassembly等
    status = Column(String(32))  # 状态：started, completed, failed
    
    # 时间信息
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration = Column(Float)  # 计算耗时（秒）
    
    # 结果信息
    result_summary = Column(JSON)  # 计算结果摘要
    error_message = Column(Text)  # 错误信息
    
    # 输入参数
    input_parameters = Column(JSON)
    
    # 索引
    __table_args__ = (
        Index('idx_calc_session_type', 'session_id', 'calculation_type'),
        Index('idx_calc_status', 'status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'calculation_type': self.calculation_type,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'result_summary': self.result_summary,
            'error_message': self.error_message
        }

class SystemMetrics(db.Model):
    """系统性能指标表"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 会话统计
    active_sessions = Column(Integer, default=0)
    total_sessions = Column(Integer, default=0)
    
    # 计算统计
    calculations_per_hour = Column(Integer, default=0)
    avg_calculation_time = Column(Float, default=0.0)
    
    # 资源使用
    memory_usage_mb = Column(Float, default=0.0)
    cpu_usage_percent = Column(Float, default=0.0)
    
    # 数据库统计
    total_datasets = Column(Integer, default=0)
    total_data_size_mb = Column(Float, default=0.0)
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'active_sessions': self.active_sessions,
            'total_sessions': self.total_sessions,
            'calculations_per_hour': self.calculations_per_hour,
            'avg_calculation_time': self.avg_calculation_time,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'total_datasets': self.total_datasets,
            'total_data_size_mb': self.total_data_size_mb
        } 