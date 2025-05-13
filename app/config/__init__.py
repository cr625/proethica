"""
Configuration package for the application.
This package contains different configuration classes for different environments.
"""

import os
from app import config as base_config
from app.config import codespace as codespace_config

class DevelopmentConfig:
    """Base configuration for development environment."""
    DEBUG = base_config.DEBUG
    TESTING = base_config.TESTING
    SECRET_KEY = base_config.SECRET_KEY
    DATABASE_URL = base_config.DATABASE_URL
    SQLALCHEMY_DATABASE_URI = base_config.SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = base_config.SQLALCHEMY_TRACK_MODIFICATIONS
    SESSION_TYPE = base_config.SESSION_TYPE
    SESSION_PERMANENT = base_config.SESSION_PERMANENT
    SESSION_USE_SIGNER = base_config.SESSION_USE_SIGNER
    WTF_CSRF_ENABLED = base_config.WTF_CSRF_ENABLED
    SET_CSRF_TOKEN_ON_PAGE_LOAD = base_config.SET_CSRF_TOKEN_ON_PAGE_LOAD
    UPLOAD_FOLDER = base_config.UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = base_config.MAX_CONTENT_LENGTH
    ENVIRONMENT = base_config.ENVIRONMENT
    USE_AGENT_ORCHESTRATOR = base_config.USE_AGENT_ORCHESTRATOR
    USE_CLAUDE = base_config.USE_CLAUDE
    OPENAI_API_KEY = base_config.OPENAI_API_KEY
    ANTHROPIC_API_KEY = base_config.ANTHROPIC_API_KEY
    CLAUDE_MODEL_VERSION = base_config.CLAUDE_MODEL_VERSION
    EMBEDDING_PROVIDER_PRIORITY = base_config.EMBEDDING_PROVIDER_PRIORITY
    LOCAL_EMBEDDING_MODEL = base_config.LOCAL_EMBEDDING_MODEL
    CLAUDE_EMBEDDING_MODEL = base_config.CLAUDE_EMBEDDING_MODEL
    OPENAI_EMBEDDING_MODEL = base_config.OPENAI_EMBEDDING_MODEL
    ZOTERO_API_KEY = base_config.ZOTERO_API_KEY
    ZOTERO_USER_ID = base_config.ZOTERO_USER_ID
    ZOTERO_GROUP_ID = base_config.ZOTERO_GROUP_ID
    MCP_SERVER_URL = base_config.MCP_SERVER_URL
    USE_MOCK_FALLBACK = base_config.USE_MOCK_FALLBACK

class CodespaceConfig:
    """Configuration for GitHub Codespaces environment."""
    DEBUG = codespace_config.DEBUG
    TESTING = codespace_config.TESTING
    SECRET_KEY = codespace_config.SECRET_KEY
    DATABASE_URL = codespace_config.DATABASE_URL
    SQLALCHEMY_DATABASE_URI = codespace_config.SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = codespace_config.SQLALCHEMY_TRACK_MODIFICATIONS
    SESSION_TYPE = codespace_config.SESSION_TYPE
    SESSION_PERMANENT = codespace_config.SESSION_PERMANENT
    SESSION_USE_SIGNER = codespace_config.SESSION_USE_SIGNER
    WTF_CSRF_ENABLED = codespace_config.WTF_CSRF_ENABLED
    SET_CSRF_TOKEN_ON_PAGE_LOAD = codespace_config.SET_CSRF_TOKEN_ON_PAGE_LOAD
    UPLOAD_FOLDER = codespace_config.UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = codespace_config.MAX_CONTENT_LENGTH
    ENVIRONMENT = codespace_config.ENVIRONMENT
    USE_AGENT_ORCHESTRATOR = codespace_config.USE_AGENT_ORCHESTRATOR
    USE_CLAUDE = codespace_config.USE_CLAUDE
    OPENAI_API_KEY = codespace_config.OPENAI_API_KEY
    ANTHROPIC_API_KEY = codespace_config.ANTHROPIC_API_KEY
    CLAUDE_MODEL_VERSION = codespace_config.CLAUDE_MODEL_VERSION
    EMBEDDING_PROVIDER_PRIORITY = codespace_config.EMBEDDING_PROVIDER_PRIORITY
    LOCAL_EMBEDDING_MODEL = codespace_config.LOCAL_EMBEDDING_MODEL
    CLAUDE_EMBEDDING_MODEL = codespace_config.CLAUDE_EMBEDDING_MODEL
    OPENAI_EMBEDDING_MODEL = codespace_config.OPENAI_EMBEDDING_MODEL
    ZOTERO_API_KEY = codespace_config.ZOTERO_API_KEY
    ZOTERO_USER_ID = codespace_config.ZOTERO_USER_ID
    ZOTERO_GROUP_ID = codespace_config.ZOTERO_GROUP_ID
    MCP_SERVER_URL = codespace_config.MCP_SERVER_URL
    USE_MOCK_FALLBACK = codespace_config.USE_MOCK_FALLBACK
    CODESPACE = codespace_config.CODESPACE
    ENABLE_LIVERELOAD = codespace_config.ENABLE_LIVERELOAD
    DB_SSL_MODE = codespace_config.DB_SSL_MODE

class ProductionConfig:
    """Configuration for production environment."""
    DEBUG = base_config.DEBUG
    TESTING = base_config.TESTING
    SECRET_KEY = base_config.SECRET_KEY
    DATABASE_URL = base_config.DATABASE_URL
    SQLALCHEMY_DATABASE_URI = base_config.SQLALCHEMY_DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = base_config.SQLALCHEMY_TRACK_MODIFICATIONS
    SESSION_TYPE = base_config.SESSION_TYPE
    SESSION_PERMANENT = base_config.SESSION_PERMANENT
    SESSION_USE_SIGNER = base_config.SESSION_USE_SIGNER
    WTF_CSRF_ENABLED = base_config.WTF_CSRF_ENABLED
    SET_CSRF_TOKEN_ON_PAGE_LOAD = base_config.SET_CSRF_TOKEN_ON_PAGE_LOAD
    UPLOAD_FOLDER = base_config.UPLOAD_FOLDER
    MAX_CONTENT_LENGTH = base_config.MAX_CONTENT_LENGTH
    ENVIRONMENT = base_config.ENVIRONMENT
    USE_AGENT_ORCHESTRATOR = base_config.USE_AGENT_ORCHESTRATOR
    USE_CLAUDE = base_config.USE_CLAUDE
    OPENAI_API_KEY = base_config.OPENAI_API_KEY
    ANTHROPIC_API_KEY = base_config.ANTHROPIC_API_KEY
    CLAUDE_MODEL_VERSION = base_config.CLAUDE_MODEL_VERSION
    EMBEDDING_PROVIDER_PRIORITY = base_config.EMBEDDING_PROVIDER_PRIORITY
    LOCAL_EMBEDDING_MODEL = base_config.LOCAL_EMBEDDING_MODEL
    CLAUDE_EMBEDDING_MODEL = base_config.CLAUDE_EMBEDDING_MODEL
    OPENAI_EMBEDDING_MODEL = base_config.OPENAI_EMBEDDING_MODEL
    ZOTERO_API_KEY = base_config.ZOTERO_API_KEY
    ZOTERO_USER_ID = base_config.ZOTERO_USER_ID
    ZOTERO_GROUP_ID = base_config.ZOTERO_GROUP_ID
    MCP_SERVER_URL = base_config.MCP_SERVER_URL
    USE_MOCK_FALLBACK = base_config.USE_MOCK_FALLBACK
    
    # Override settings for production
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
