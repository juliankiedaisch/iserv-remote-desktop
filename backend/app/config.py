import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OAuth Configuration
    OAUTH_CLIENT_ID = os.environ.get('OAUTH_CLIENT_ID')
    OAUTH_CLIENT_SECRET = os.environ.get('OAUTH_CLIENT_SECRET')
    OAUTH_AUTHORIZE_URL = os.environ.get('OAUTH_AUTHORIZE_URL')
    OAUTH_TOKEN_URL = os.environ.get('OAUTH_TOKEN_URL')
    OAUTH_USERINFO_URL = os.environ.get('OAUTH_USERINFO_URL')
    OAUTH_JWKS_URI = os.environ.get('OAUTH_JWKS_URI')
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI')
    
    # Frontend URL for redirects after auth
    FRONTEND_URL = os.environ.get('FRONTEND_URL')

    #Rolemanagement
    ROLE_TEACHER = os.environ.get('ROLE_TEACHER')
    ROLE_ADMIN = os.environ.get('ROLE_ADMIN')
    
    # File management - UID/GID for container files (kasm user is typically 1000)
    CONTAINER_USER_ID = int(os.environ.get('CONTAINER_USER_ID', 1000))
    CONTAINER_GROUP_ID = int(os.environ.get('CONTAINER_GROUP_ID', 1000))
    
    # Data directory paths
    USER_DATA_BASE_DIR = os.environ.get('USER_DATA_BASE_DIR', '/data/users')
    SHARED_PUBLIC_DIR = os.environ.get('SHARED_PUBLIC_DIR', '/data/shared/public')
    
    # Container idle timeout (in hours) - containers inactive for this duration will be stopped
    CONTAINER_IDLE_TIMEOUT_HOURS = int(os.environ.get('CONTAINER_IDLE_TIMEOUT_HOURS', 6))

    POSTGRES_USER = os.environ.get('POSTGRES_USER')
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    POSTGRES_SERVER_NAME = os.environ.get('POSTGRES_SERVER_NAME')
    POSTGRES_DB = os.environ.get('POSTGRES_DB')

class DevelopmentConfig(Config):
    DEBUG = True
    # Supports both SQLite and PostgreSQL
    # SQLite: sqlite:///path/to/db/main.db
    # PostgreSQL: postgresql://user:password@host:port/dbname
    SQLALCHEMY_DATABASE_URI = f"postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_SERVER_NAME}:5432/{Config.POSTGRES_DB}?client_encoding=utf8"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 40
    }

class ProductionConfig(Config):
    DEBUG = False
    # Supports both SQLite and PostgreSQL
    # SQLite: sqlite:///path/to/db/main.db
    # PostgreSQL: postgresql://user:password@host:port/dbname
    SQLALCHEMY_DATABASE_URI = f"postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_SERVER_NAME}:5432/{Config.POSTGRES_DB}?client_encoding=utf8"
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 40,
        'isolation_level': 'REPEATABLE READ'  # For PostgreSQL
    }