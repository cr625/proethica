#!/usr/bin/env python3
"""
Run script for the ProEthica experiment interface.

This script sets up the necessary environment variables and runs the Flask
application with the experiment interface enabled.
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_server(host='127.0.0.1', port=5000):
    """Run Flask development server for the experiment interface."""
    try:
        # Set up environment variables
        os.environ['ENVIRONMENT'] = 'codespace'
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        os.environ['FLASK_DEBUG'] = '1'

        # Load environment variables from .env file if it exists
        if os.path.exists('.env'):
            load_dotenv()
            logger.info("Loaded environment variables from .env file")

        # Apply SQLAlchemy URL fix if available
        try:
            import patch_sqlalchemy_url
            patch_sqlalchemy_url.patch_create_app()
            logger.info("Applied SQLAlchemy URL fix")
        except Exception as e:
            logger.warning(f"Failed to apply SQLAlchemy URL fix: {str(e)}")

        # Import after environment variables are set
        from app import create_app
        
        logger.info(f"Starting experiment interface at http://{host}:{port}/experiment/")
        logger.info("Press CTRL+C to stop the server")
        
        # Create app with specific config module
        app = create_app('config')
        app.run(host=host, port=port, debug=True)
        
    except Exception as e:
        logger.exception(f"Error running server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run the ProEthica experiment interface')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)
