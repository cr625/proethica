#!/usr/bin/env python3
"""
Debug wrapper for run.py that fixes the SQLAlchemy URL parsing issue.
This script properly formats the database URL before calling run.py.
"""

import os
import sys
import argparse
import re

def fix_database_url_in_environment():
    """Fix the database URL by setting an environment variable."""
    # Set the environment variable directly
    os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    
    print("Fixed database URL using environment variables")
    return True

def create_temp_config_override():
    """Create a temporary config file that properly sets the database URL."""
    # Create a temporary file that will override the config
    temp_config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_config')
    os.makedirs(temp_config_dir, exist_ok=True)
    
    # Create __init__.py to make it a package
    with open(os.path.join(temp_config_dir, '__init__.py'), 'w') as f:
        f.write('"""Temporary config package."""\n')
    
    # Create a config file with the proper database URL
    config_content = """
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
"""
    
    with open(os.path.join(temp_config_dir, 'config.py'), 'w') as f:
        f.write(config_content)
    
    print(f"Created temporary config override at {temp_config_dir}")
    return temp_config_dir

def main():
    """Main entry point."""
    # Parse arguments to pass through to run.py
    parser = argparse.ArgumentParser(description="Debug wrapper for run.py")
    parser.add_argument('--port', type=int, default=3333, help='Port to run the app on')
    parser.add_argument('--mcp-port', type=int, default=5001, help='Port where MCP server is running')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args, unknown = parser.parse_known_args()
    
    # Set environment
    if 'ENVIRONMENT' not in os.environ:
        print("Setting ENVIRONMENT to 'codespace'")
        os.environ['ENVIRONMENT'] = 'codespace'
    
    # Fix the database URL in environment and create a config override 
    fix_database_url_in_environment()
    temp_config_dir = create_temp_config_override()
    
    # Add the temporary config directory to the Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Set MCP server URL
    os.environ['MCP_SERVER_URL'] = f'http://localhost:{args.mcp_port}'
    os.environ['MCP_SERVER_ALREADY_RUNNING'] = 'true'
    
    # Pass control to run.py with all arguments
    run_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run.py')
    
    # Add the config module directory to PYTHONPATH via environment variable
    os.environ['PYTHONPATH'] = f"{temp_config_dir}:{os.environ.get('PYTHONPATH', '')}"
    
    # Set additional environment variables that Flask will use
    os.environ['FLASK_APP'] = 'app.create_app("temp_config")'
    
    # Reconstruct command line arguments - only use supported ones
    cmd_args = [
        sys.executable,
        run_script,
        f'--port={args.port}',
        f'--mcp-port={args.mcp_port}'
    ]
    
    if args.debug:
        cmd_args.append('--debug')
    
    # Add any unknown args
    cmd_args.extend(unknown)
    
    print(f"Running: {' '.join(cmd_args)}")
    
    # Replace current process with run.py
    os.execv(sys.executable, cmd_args)

if __name__ == "__main__":
    main()
