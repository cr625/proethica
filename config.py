"""
Configuration for the AI Ethical DM application.
This file is used when create_app('config') is called.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build configuration dictionary
app_config = {
    'DEBUG': os.getenv('FLASK_ENV') == 'development',
    'TESTING': False,
    'SECRET_KEY': os.getenv('SECRET_KEY', 'development-key-change-me'),
    'SQLALCHEMY_DATABASE_URI': os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'),
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SESSION_TYPE': 'filesystem',
    'SESSION_PERMANENT': False,
    'SESSION_USE_SIGNER': True,
    'WTF_CSRF_ENABLED': True,
    'SET_CSRF_TOKEN_ON_PAGE_LOAD': os.getenv('SET_CSRF_TOKEN_ON_PAGE_LOAD', 'false').lower() == 'true',
    'UPLOAD_FOLDER': os.path.join(os.path.dirname(__file__), 'app', 'uploads'),
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16 MB
    'ENVIRONMENT': os.getenv('ENVIRONMENT', 'development'),
    'USE_AGENT_ORCHESTRATOR': os.getenv('USE_AGENT_ORCHESTRATOR', 'true').lower() == 'true',
    'USE_CLAUDE': os.getenv('USE_CLAUDE', 'true').lower() == 'true',
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
    'CLAUDE_MODEL_VERSION': os.getenv('CLAUDE_MODEL_VERSION'),  # Will be handled by ModelConfig
    'EMBEDDING_PROVIDER_PRIORITY': os.getenv('EMBEDDING_PROVIDER_PRIORITY', 'local'),
    'LOCAL_EMBEDDING_MODEL': os.getenv('LOCAL_EMBEDDING_MODEL', 'all-MiniLM-L6-v2'),
    'CLAUDE_EMBEDDING_MODEL': os.getenv('CLAUDE_EMBEDDING_MODEL', 'claude-3-embedding-3-0'),
    'OPENAI_EMBEDDING_MODEL': os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-ada-002'),
    'ZOTERO_API_KEY': os.getenv('ZOTERO_API_KEY'),
    'ZOTERO_USER_ID': os.getenv('ZOTERO_USER_ID'),
    'ZOTERO_GROUP_ID': os.getenv('ZOTERO_GROUP_ID'),
    'MCP_SERVER_URL': os.getenv('MCP_SERVER_URL', 'http://localhost:5001'),
    'USE_MOCK_FALLBACK': os.getenv('USE_MOCK_FALLBACK', 'false').lower() == 'true',
}