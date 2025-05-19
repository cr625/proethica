"""
Run the application in debug mode for GitHub Codespaces.
"""

import os
import argparse
from dotenv import load_dotenv
from app import create_app
import tempfile
from flask.sessions import SecureCookieSessionInterface
from flask import Flask

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment variables for debugging
os.environ['ENVIRONMENT'] = 'development'
os.environ['MCP_SERVER_PORT'] = '5001'
os.environ['MCP_SERVER_URL'] = 'http://localhost:5001'

# Set database URL
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

# Create app instance with proper configuration
app = create_app('config')
app.config['DEBUG'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Keep debug features but disable auto-reloader
if __name__ == '__main__':
    print(f"Starting Flask debug server on port 3333...")
    print(f"Debug mode enabled, but auto-reloader disabled to prevent restart cycle")
    
    # Run with debug=True for enhanced error pages but use_reloader=False to prevent restarts
    app.run(host='0.0.0.0', port=3333, debug=True, use_reloader=False)
