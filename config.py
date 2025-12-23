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

    # OntServe Web Interface URL - for navigation links
    ONTSERVE_WEB_URL = os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')

    # Mock LLM mode - when enabled, extractors use mock responses instead of real LLM calls
    # Set MOCK_LLM_ENABLED=true in .env to enable mock mode for UI testing
    MOCK_LLM_ENABLED = os.environ.get('MOCK_LLM_ENABLED', 'false').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    ENVIRONMENT = 'development'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    ENVIRONMENT = 'production'
    # Override OntServe Web URL for production
    ONTSERVE_WEB_URL = os.environ.get('ONTSERVE_WEB_URL', 'https://ontserve.ontorealm.net')


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    ENVIRONMENT = 'testing'
    # Use PostgreSQL test database instead of SQLite for schema compatibility
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
                              'postgresql://postgres:PASS@localhost:5432/ai_ethical_dm_test'
    WTF_CSRF_ENABLED = False  # Disable CSRF for easier testing


class ProductionSimulationConfig(Config):
    """Production simulation configuration for local testing.

    This configuration mimics production authentication behavior
    while running locally. Use this to test authentication requirements
    before deploying to production.
    """
    DEBUG = True  # Keep debug on for local development
    ENVIRONMENT = 'production'  # Mimics production auth behavior
    # Can add a visual indicator that we're in simulation mode
    PRODUCTION_SIMULATION = True


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'production-simulation': ProductionSimulationConfig,
    'default': DevelopmentConfig
}