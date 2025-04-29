"""
Production environment configuration.
This file contains settings specific to the production environment.
"""

# Database configuration
DB_HOST = "localhost"
DB_PORT = 5433  # Modified port for Docker on production
DB_NAME = "ai_ethical_dm"

# MCP server configuration
MCP_SERVER_PORT = 5001
MCP_SERVER_URL = f"http://localhost:{MCP_SERVER_PORT}"
LOCK_FILE_PATH = "/tmp/enhanced_mcp_server.lock"  # System path for production
LOG_DIR = "/var/log/proethica"

# Feature flags
USE_MOCK_FALLBACK = False  # Must use real data in production

# Debug settings
DEBUG = False
VERBOSE_LOGGING = False
