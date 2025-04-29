"""
WSL (Windows Subsystem for Linux) environment configuration.
This file contains settings specific to running in a WSL environment.
"""

# Database configuration
DB_HOST = "localhost"
DB_PORT = 5432  # Using WSL PostgreSQL port
DB_NAME = "ai_ethical_dm"

# MCP server configuration
MCP_SERVER_PORT = 5001
MCP_SERVER_URL = f"http://localhost:{MCP_SERVER_PORT}"
LOCK_FILE_PATH = "./tmp/enhanced_mcp_server.lock"  # Local path for WSL
LOG_DIR = "./logs"

# Feature flags
USE_MOCK_FALLBACK = False  # Use real data in WSL

# Debug settings
DEBUG = True
VERBOSE_LOGGING = True

# WSL specific settings
WSL_CHROME_PATH = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
WSL_PUPPETEER_EXECUTABLE_PATH = WSL_CHROME_PATH
