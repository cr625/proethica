"""
GitHub Codespaces environment-specific configuration.
"""

import os

class config:
    """Codespace environment configuration."""
    
    # Override debug setting
    DEBUG = False
    
    # Database URL specific to Codespaces
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    
    # MCP Server configuration
    MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:5001')
