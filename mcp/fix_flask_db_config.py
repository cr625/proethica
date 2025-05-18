#!/usr/bin/env python3
"""
Helper module to fix Flask database configuration.
This provides a simple way to set up database configuration for
Flask applications when running as part of an MCP server.
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import URL

def fix_flask_database_config():
    """
    Set up Flask database configuration environment variables
    to ensure proper database connectivity for any Flask app instances.
    
    This should be called before importing app.create_app
    """
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    
    # Set SQLALCHEMY_DATABASE_URI environment variable for Flask
    os.environ['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"Set SQLALCHEMY_DATABASE_URI = {database_url}", file=sys.stderr)
    
    # Return a direct SQLAlchemy session for use if needed
    try:
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        return session
    except Exception as e:
        print(f"Warning: Direct database connection failed: {str(e)}", file=sys.stderr)
        return None

def get_flask_app():
    """
    Create and configure a Flask app with correct database settings.
    
    Returns:
        Flask app or None if failed
    """
    # Fix database config first
    fix_flask_database_config()
    
    try:
        # This is safer than direct import at the module level
        # as it ensures environment variables are set first
        from app import create_app
        flask_app = create_app()
        return flask_app
    except Exception as e:
        print(f"Failed to create Flask app: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None
        
def get_sqlalchemy_session():
    """
    Get a direct SQLAlchemy session without Flask context.
    Useful for database operations outside of Flask.
    
    Returns:
        SQLAlchemy session or None if failed
    """
    database_url = os.environ.get('SQLALCHEMY_DATABASE_URI') or os.environ.get('DATABASE_URL')
    if not database_url:
        print("No database URL found in environment", file=sys.stderr)
        return None
        
    try:
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        print(f"Failed to create SQLAlchemy session: {str(e)}", file=sys.stderr)
        return None
