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

# FORCE ALL LLM SERVICES TO USE ENGINEERING ETHICS CONTENT
os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'true'
os.environ['FORCE_MOCK_LLM'] = 'true'

# Set database URL
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

# Apply comprehensive fix to eliminate military medical triage content
print("Applying comprehensive fix to eliminate military medical triage content...")
try:
    from force_mock_llm_fix import apply_comprehensive_fix
    apply_comprehensive_fix()
    print("✓ Fix applied successfully")
except Exception as e:
    print(f"⚠️  Warning: Could not apply comprehensive fix: {e}")
    print("   Application will still run but may show military content")

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
