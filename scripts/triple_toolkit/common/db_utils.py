#!/usr/bin/env python3
"""
Database utilities for the Triple Toolkit.
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

def load_environment():
    """Load environment variables from .env file."""
    load_dotenv()
    # Ensure DATABASE_URL is set
    if 'DATABASE_URL' not in os.environ:
        # Try to use a fallback if not in environment
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        print("WARNING: Using default DATABASE_URL. Set this in .env for production use.")
    return os.environ.get('DATABASE_URL')

def get_db_engine():
    """Get a SQLAlchemy engine connected to the database."""
    db_url = load_environment()
    try:
        engine = create_engine(db_url)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

def get_db_session():
    """Get a SQLAlchemy session."""
    engine = get_db_engine()
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    return Session()

def close_db_session(session):
    """Close the database session."""
    if session:
        session.close()

def execute_query(query, params=None):
    """Execute a raw SQL query and return results."""
    engine = get_db_engine()
    try:
        # Execute with parameters if provided
        with engine.connect() as conn:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))
            return result.fetchall()
    except Exception as e:
        print(f"ERROR: Query execution failed: {e}")
        print(f"Query: {query}")
        print(f"Params: {params}")
        return []

def execute_query_with_columns(query, params=None):
    """Execute a raw SQL query and return results with column names."""
    engine = get_db_engine()
    try:
        # Execute with parameters if provided
        with engine.connect() as conn:
            if params:
                result = conn.execute(text(query), params)
            else:
                result = conn.execute(text(query))
            columns = result.keys()
            rows = result.fetchall()
            return columns, rows
    except Exception as e:
        print(f"ERROR: Query execution failed: {e}")
        print(f"Query: {query}")
        print(f"Params: {params}")
        return [], []

# Add the application path to sys.path
def add_app_to_path():
    """Add the application root directory to the Python path."""
    # Get the current script directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up three levels to get to the app root
    app_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
    
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    
    return app_root

def get_app_context():
    """Get the Flask app context for ORM operations."""
    add_app_to_path()
    try:
        from flask import Flask
        from app import create_app
        
        # Get database URL
        db_url = load_environment()
        
        # Use a direct approach with a Flask app that has just what we need
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize SQLAlchemy with this simple app
        from app.models import db
        db.init_app(app)
        
        return app.app_context()
    except ImportError as e:
        print(f"ERROR: Could not import Flask or required modules: {e}")
        sys.exit(1)
