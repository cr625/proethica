#!/usr/bin/env python
"""
Run the Flask application with agent orchestrator enabled.

This script runs the Flask application with the agent orchestrator
enabled for decision processing.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

def main():
    """Run the Flask application with agent orchestrator enabled."""
    parser = argparse.ArgumentParser(description='Run the Flask application with agent orchestrator enabled')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Set environment variable to enable agent orchestrator
    os.environ['USE_AGENT_ORCHESTRATOR'] = 'true'
    
    # Create the Flask application
    app = create_app()
    
    # Run the application
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()
