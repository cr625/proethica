"""
Codespace environment configuration.
This module contains settings specific to the GitHub Codespaces environment.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Debug and development settings
DEBUG = True
TESTING = False
SECRET_KEY = os.getenv('SECRET_KEY', 'codespace-development-key')

# Database URL specific to Codespaces - note the port is 5433
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm')
SQLALCHEMY_DATABASE_URI = DATABASE_URL
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Flask session config
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = False
SESSION_USE_SIGNER = True

# CSRF protection
WTF_CSRF_ENABLED = True
SET_CSRF_TOKEN_ON_PAGE_LOAD = True

# File uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# Environment
ENVIRONMENT = 'codespace'

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

# MCP Server configuration - ensure it's using localhost
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:5001')
USE_MOCK_FALLBACK = os.getenv('USE_MOCK_FALLBACK', 'false').lower() == 'true'

# Codespace specific settings
CODESPACE = True
ENABLE_LIVERELOAD = True

# Database SSL mode
# Set to 'require' for secure connections or 'disable' for local dev
DB_SSL_MODE = os.getenv('DB_SSL_MODE', 'disable')
