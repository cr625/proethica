"""
WSL environment-specific configuration.
"""

import os

class config:
    """WSL environment configuration."""
    
    # Database URL specific to WSL environment
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    
    # Additional WSL-specific settings can be added here
