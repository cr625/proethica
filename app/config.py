import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-for-development-only')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or "postgresql://postgres:PASS@localhost/ai_ethical_dm"
    USE_CLAUDE = os.environ.get('USE_CLAUDE', 'true').lower() == 'true'
    USE_AGENT_ORCHESTRATOR = os.environ.get('USE_AGENT_ORCHESTRATOR', 'true').lower() == 'true'
    APP_NAME = os.environ.get('APP_NAME', 'R.E.A.L.M.')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = True

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or "postgresql://postgres:PASS@localhost/ai_ethical_dm_test"
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'codespace': DevelopmentConfig,  # Map Codespaces to DevelopmentConfig
    'wsl': DevelopmentConfig,  # Map WSL to DevelopmentConfig
    'default': DevelopmentConfig
}
