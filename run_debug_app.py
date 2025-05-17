"""
Run the application in debug mode for GitHub Codespaces.
"""

import os
import argparse
from dotenv import load_dotenv
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
    app.run(host='0.0.0.0', port=3334, debug=True)
