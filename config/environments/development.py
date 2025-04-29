"""
Development environment configuration.
This file contains settings specific to the development environment.
"""

# Database configuration
DB_HOST = "localhost"
DB_PORT = 5432  # Standard PostgreSQL port for local development
DB_NAME = "ai_ethical_dm"

# MCP server configuration
MCP_SERVER_PORT = 5001
MCP_SERVER_URL = f"http://localhost:{MCP_SERVER_PORT}"
LOCK_FILE_PATH = "./tmp/enhanced_mcp_server.lock"  # Local path for development
LOG_DIR = "./logs"

# Feature flags
USE_MOCK_FALLBACK = False  # Default to real data in development

# Debug settings
DEBUG = True
VERBOSE_LOGGING = True
