
'''
Temporary config file created by debug_run.py to fix SQLAlchemy URL issues.
'''

class config:
    '''Debug configuration.'''
    # Set debug mode
    DEBUG = True
    
    # Properly formatted database URL
    DATABASE_URL = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    
    # Other required configuration
    SECRET_KEY = 'debug_secret_key'
    
    # MCP Server configuration
    MCP_SERVER_URL = 'http://localhost:5001'
