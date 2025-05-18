"""
Run the application in debug mode for GitHub Codespaces.
"""

import os
import argparse
import tempfile
from dotenv import load_dotenv
from werkzeug.serving import run_simple
from app import create_app

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

if __name__ == '__main__':
    print(f"Starting Flask debug server on port 3334...")
    
    # Get the Flask session directory (default is in tempfile.gettempdir() + '/flask_session')
    session_dir = app.config.get('SESSION_FILE_DIR', os.path.join(tempfile.gettempdir(), 'flask_session'))
    print(f"Configuring reloader to ignore session directory: {session_dir}")
    
    # Use run_simple instead of app.run to configure exclude_patterns
    run_simple('0.0.0.0', 3334, app,
              use_reloader=True,
              use_debugger=True,
              exclude_patterns=[f"{session_dir}/*"])
