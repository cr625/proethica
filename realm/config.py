"""
REALM Configuration.

This module defines configuration variables for the REALM application.
"""

import os
import logging
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Cache directory
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Templates directory
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Static files directory
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Default MCP server configuration
DEFAULT_MSEO_SERVER_URL = "http://localhost:8078"
DEFAULT_MSEO_SERVER_NAME = "mseo-mcp-server"

# LLM configuration (for chat functionality)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")  # Options: anthropic, openai
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-3-opus-20240229")  # Or: gpt-4, etc.

# Materials Science Ontology configuration
MSEO_ONTOLOGY_URL = "https://matportal.org/ontologies/MSEO"
MSEO_DATA_DIR = os.path.join(BASE_DIR, "data", "mseo")

# Logging configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)

# Application settings
APP_NAME = "REALM"
APP_DESCRIPTION = "Resource for Engineering And Learning Materials"
APP_VERSION = "0.1.0"
APP_AUTHOR = "REALM Team"
APP_URL = "https://github.com/realm-materials-science"

# Create necessary directories
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MSEO_DATA_DIR, exist_ok=True)
