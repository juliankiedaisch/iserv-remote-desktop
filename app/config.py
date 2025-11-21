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

class DevelopmentConfig(Config):
    DEBUG = True
    # Supports both SQLite and PostgreSQL
    # SQLite: sqlite:///path/to/db/main.db
    # PostgreSQL: postgresql://user:password@host:port/dbname
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or f'sqlite:///{os.path.join(os.getcwd(), "db/main.db")}'
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
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or f'sqlite:///{os.path.join(os.getcwd(), "db/main.db")}'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 40,
        'isolation_level': 'REPEATABLE READ'  # For PostgreSQL
    }