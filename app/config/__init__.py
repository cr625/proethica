"""
Configuration package for the application.
This package contains different configuration classes for different environments.
"""

import os

# Config class for backward compatibility
# This is used by various services that import app.config.Config
class Config:
    """Main configuration class for backward compatibility."""
    # Load dynamically from environment variable
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    
    # Debug and development settings
    DEBUG = os.getenv('FLASK_ENV') == 'development'
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'development-key-change-me')

    # Database URL with fallback
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask session config
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True

    # CSRF protection
    WTF_CSRF_ENABLED = True
    SET_CSRF_TOKEN_ON_PAGE_LOAD = os.getenv('SET_CSRF_TOKEN_ON_PAGE_LOAD', 'false').lower() == 'true'

    # File uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # API configuration
    USE_AGENT_ORCHESTRATOR = os.getenv('USE_AGENT_ORCHESTRATOR', 'true').lower() == 'true'
    USE_CLAUDE = os.getenv('USE_CLAUDE', 'true').lower() == 'true'
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    CLAUDE_MODEL_VERSION = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')

    # Embedding configuration
    EMBEDDING_PROVIDER_PRIORITY = os.getenv('EMBEDDING_PROVIDER_PRIORITY', 'local')
    LOCAL_EMBEDDING_MODEL = os.getenv('LOCAL_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    CLAUDE_EMBEDDING_MODEL = os.getenv('CLAUDE_EMBEDDING_MODEL', 'claude-3-embedding-3-0')
    OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-ada-002')

    # Zotero API configuration
    ZOTERO_API_KEY = os.getenv('ZOTERO_API_KEY')
    ZOTERO_USER_ID = os.getenv('ZOTERO_USER_ID')
    ZOTERO_GROUP_ID = os.getenv('ZOTERO_GROUP_ID')

    # MCP Server configuration
    MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:5001')
    USE_MOCK_FALLBACK = os.getenv('USE_MOCK_FALLBACK', 'false').lower() == 'true'

# Simplified configs for other environments
# These are included to ensure compatibility but the focus is on Codespace
class DevelopmentConfig:
    """Simplified configuration for development environment."""
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/ai_ethical_dm')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    WTF_CSRF_ENABLED = True
    SET_CSRF_TOKEN_ON_PAGE_LOAD = True
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ENVIRONMENT = 'development'
    USE_AGENT_ORCHESTRATOR = True
    USE_CLAUDE = True
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    CLAUDE_MODEL_VERSION = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
    MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:5001')
    USE_MOCK_FALLBACK = os.getenv('USE_MOCK_FALLBACK', 'false').lower() == 'true'

class ProductionConfig:
    """Simplified configuration for production environment."""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY')
    DATABASE_URL = os.getenv('DATABASE_URL')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    WTF_CSRF_ENABLED = True
    SET_CSRF_TOKEN_ON_PAGE_LOAD = True
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ENVIRONMENT = 'production'
    USE_AGENT_ORCHESTRATOR = True
    USE_CLAUDE = True
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    CLAUDE_MODEL_VERSION = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
    MCP_SERVER_URL = os.getenv('MCP_SERVER_URL')
    USE_MOCK_FALLBACK = False
