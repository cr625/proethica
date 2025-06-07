"""
Run the ProEthica application in debug mode.
"""

import os
import logging
from dotenv import load_dotenv
from app import create_app

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment for development
os.environ.setdefault('ENVIRONMENT', 'development')

# Set database URL if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

# Use local MCP server instead of production for debugging
os.environ['MCP_SERVER_URL'] = 'http://localhost:5001'

# Configure logging to reduce noise
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Show startup configuration
print("🚀 Starting ProEthica Debug Server")
print("=" * 40)
print(f"Environment: {os.environ.get('ENVIRONMENT', 'development')}")
print(f"MCP Server: {os.environ.get('MCP_SERVER_URL', 'Not configured')}")
print(f"Database: {os.environ.get('DATABASE_URL', 'Default local')}")
print("=" * 40)

# Create app instance with proper configuration
app = create_app('config')
app.config['DEBUG'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Run the application
if __name__ == '__main__':
    print("🌐 Server starting on http://localhost:3333")
    print("✨ Debug mode enabled with auto-reload")
    print("Press Ctrl+C to stop the server")
    print()
    
    # Run with debug features enabled
    app.run(host='0.0.0.0', port=3333, debug=True, use_reloader=True)
