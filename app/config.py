import os
import tempfile

class Config:
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = tempfile.gettempdir()
    
    # 会话管理配置
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'business_forecast:'
    SESSION_REDIS = None  # 将在应用初始化时设置
    PERMANENT_SESSION_LIFETIME = 86400  # 24小时
    
    # Redis配置
    REDIS_HOST = os.environ.get('REDIS_HOST') or 'localhost'
    REDIS_PORT = int(os.environ.get('REDIS_PORT') or 6379)
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD') or None
    REDIS_DB = int(os.environ.get('REDIS_DB') or 0)
    REDIS_URL = os.environ.get('REDIS_URL') or f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    
    # 数据库配置
    DATABASE_TYPE = os.environ.get('DATABASE_TYPE') or 'sqlite'  # sqlite, mysql, postgresql
    
    # SQLite配置（默认）
    SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_storage', 'business_forecast.db')
    
    # MySQL配置
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or 3306)
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'business_forecast'
    
    # PostgreSQL配置
    POSTGRES_HOST = os.environ.get('POSTGRES_HOST') or 'localhost'
    POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT') or 5432)
    POSTGRES_USER = os.environ.get('POSTGRES_USER') or 'postgres'
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD') or ''
    POSTGRES_DATABASE = os.environ.get('POSTGRES_DATABASE') or 'business_forecast'
    
    # 动态构建数据库URL
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        if self.DATABASE_TYPE == 'mysql':
            return f'mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4'
        elif self.DATABASE_TYPE == 'postgresql':
            return f'postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}'
        else:  # sqlite
            return f'sqlite:///{self.SQLITE_DB_PATH}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # 期初库存固化目录（全系统共用一份文件）
    OPENING_INVENTORY_DIR = os.environ.get('OPENING_INVENTORY_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'persistent'
    )

    # 工作区快照存储目录（按用户分子目录）
    SNAPSHOTS_DIR = os.environ.get('SNAPSHOTS_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'snapshots'
    )

    # 同步历史存储目录（按用户分子目录）
    SYNC_HISTORY_DIR = os.environ.get('SYNC_HISTORY_DIR') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'sync_history'
    )
    SYNC_HISTORY_MAX_ENTRIES = int(os.environ.get('SYNC_HISTORY_MAX_ENTRIES') or 20)

    # 数据存储配置（向后兼容）
    DATA_STORAGE_DIR = 'data_storage'
    PERSISTENT_DATA_FILE = os.path.join(DATA_STORAGE_DIR, 'app_data.pkl')
    DATA_INFO_FILE = os.path.join(DATA_STORAGE_DIR, 'data_info.json')
    
    # 会话数据配置
    SESSION_TIMEOUT = 3600 * 24  # 24小时会话超时
    MAX_CONCURRENT_SESSIONS = 100  # 最大并发会话数
    
    # 业务配置
    DEFAULT_PER_PAGE = 50
    MAX_RECORDS_PER_PAGE = 200

    # 基础数据维护权限配置（逗号分隔用户ID，如: "1,2,3"）
    BASE_DATA_MAINTAINER_USER_IDS = os.environ.get('BASE_DATA_MAINTAINER_USER_IDS', '')
    
    # 缓存配置
    CACHE_TIMEOUT = 3600  # 1小时缓存超时
    ENABLE_REDIS_CACHE = True
    
    # AI模型配置
    AI_MODEL_BASE_URL = os.environ.get('AI_MODEL_BASE_URL') or 'http://10.30.5.32:1234'
    AI_MODEL_NAME = os.environ.get('AI_MODEL_NAME') or 'google/gemma-4-26b-a4b'  # 如果为空，将使用默认模型
    AI_REQUEST_TIMEOUT = int(os.environ.get('AI_REQUEST_TIMEOUT') or 180)  # 请求超时时间（秒），默认180秒以适应大模型处理时间
    AI_MAX_TOKENS = int(os.environ.get('AI_MAX_TOKENS') or 8192)  # 最大生成token数，默认8192（根据LM Studio上下文长度32768，设置为8192以提供更完整的分析内容）

class DevelopmentConfig(Config):
    DEBUG = True
    # 开发环境使用内存Redis（如果没有安装Redis）
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    DATABASE_TYPE = 'sqlite'  # 开发环境默认使用SQLite

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境必须配置Redis和数据库
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    DATABASE_TYPE = os.environ.get('DATABASE_TYPE') or 'postgresql'  # 生产环境推荐PostgreSQL
    
    # 生产环境安全配置（HTTP 内网部署默认 false，HTTPS 反向代理时设 SESSION_COOKIE_SECURE=true）
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_TYPE = 'sqlite'
    SQLITE_DB_PATH = ':memory:'  # 测试环境使用内存数据库
    REDIS_URL = 'redis://localhost:6379/1'  # 使用不同的Redis数据库

# 配置映射
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# 默认配置
config = config_map.get(os.environ.get('FLASK_ENV', 'default'), DevelopmentConfig)
