"""
Application configuration module.
"""

import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Debug and development settings
DEBUG = os.getenv('FLASK_ENV') == 'development'
TESTING = False
SECRET_KEY = os.getenv('SECRET_KEY', 'development-key-change-me')

# Database URL with fallback
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm')
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
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# Environment detection
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# API configuration
USE_AGENT_ORCHESTRATOR = os.getenv('USE_AGENT_ORCHESTRATOR', 'true').lower() == 'true'
USE_CLAUDE = os.getenv('USE_CLAUDE', 'true').lower() == 'true'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Model configuration - use centralized config
from config.models import ModelConfig
CLAUDE_MODEL_VERSION = ModelConfig.get_default_model()

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

# Detect Codespace environment
is_codespace = os.getenv('CODESPACES') == 'true'
if is_codespace and ENVIRONMENT != 'codespace':
    print("Detected GitHub Codespaces environment - overriding settings")
    ENVIRONMENT = 'codespace'

# Special configurations for different environments
if ENVIRONMENT == 'codespace':
    print("Using Codespace configuration")
    # Override settings specific to GitHub Codespaces
    pass
elif ENVIRONMENT == 'wsl':
    print("Using WSL configuration")
    # Override settings specific to WSL
    pass
elif ENVIRONMENT == 'production':
    print("Using Production configuration")
    DEBUG = False
    # Add additional production settings here
    pass
