"""
Simplified Flask configuration - standard approach.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database - use standard Flask-SQLAlchemy variable name
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI') or \
                             os.environ.get('DATABASE_URL') or \
                             'postgresql://postgres:PASS@localhost:5432/ai_ethical_dm'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # CSRF protection
    WTF_CSRF_ENABLED = True
    
    # File uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # API Keys
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    
    # LangExtract
    USE_DATABASE_LANGEXTRACT_EXAMPLES = os.environ.get('USE_DATABASE_LANGEXTRACT_EXAMPLES', 'true').lower() == 'true'
    ENABLE_ONTOLOGY_DRIVEN_LANGEXTRACT = os.environ.get('ENABLE_ONTOLOGY_DRIVEN_LANGEXTRACT', 'true').lower() == 'true'
    
    # MCP Integration - Always enabled (required for system to function)
    ENABLE_EXTERNAL_MCP_ACCESS = True  # Always true - external MCP is required
    ONTSERVE_MCP_URL = os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    ENVIRONMENT = 'development'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    ENVIRONMENT = 'production'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    ENVIRONMENT = 'testing'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}