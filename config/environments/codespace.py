"""
Codespace environment configuration.
This file contains settings specific to GitHub Codespaces environment.
"""

# Database configuration
DB_HOST = "localhost"
DB_PORT = 5433  # Using Docker PostgreSQL on port 5433 as specified
DB_NAME = "ai_ethical_dm"

# MCP server configuration
MCP_SERVER_PORT = 5001
MCP_SERVER_URL = f"http://localhost:{MCP_SERVER_PORT}"
LOCK_FILE_PATH = "/workspaces/ai-ethical-dm/tmp/enhanced_mcp_server.lock"  # Codespace path
LOG_DIR = "/workspaces/ai-ethical-dm/logs"

# Feature flags
USE_MOCK_FALLBACK = False  # Use real data in codespace

# Debug settings
DEBUG = True
VERBOSE_LOGGING = True
