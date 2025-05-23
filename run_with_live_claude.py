#!/usr/bin/env python3
"""
Start the Flask application with live Claude configuration.
"""

import os
import sys

# Set environment variables for live Claude
os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'false'
os.environ['FORCE_MOCK_LLM'] = 'false'
os.environ['ANTHROPIC_MODEL'] = 'claude-3-7-sonnet-20250219'

print("=== Starting Flask App with Live Claude ===")
print(f"USE_MOCK_GUIDELINE_RESPONSES: {os.environ.get('USE_MOCK_GUIDELINE_RESPONSES')}")
print(f"FORCE_MOCK_LLM: {os.environ.get('FORCE_MOCK_LLM')}")
print(f"ANTHROPIC_MODEL: {os.environ.get('ANTHROPIC_MODEL')}")
print(f"ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")

# Import and run the Flask app
from run_ui_app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
