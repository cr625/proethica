"""
REALM Database Configuration.

This module configures the SQLAlchemy database connection for the REALM application.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

# Get database URI from environment or use default
DATABASE_URI = os.environ.get(
    'REALM_DATABASE_URL',
    'postgresql://postgres:PASS@localhost:5433/realm'
)

# Create engine
engine = create_engine(DATABASE_URI)

# Create session factory
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create thread-scoped session
db_session = scoped_session(session_factory)

# Create declarative base
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    """Initialize the database and create all tables."""
    # Import all modules here that define models
    from realm.models import material
    
    # Create tables
    Base.metadata.create_all(bind=engine)

def shutdown_db():
    """Close the database session."""
    db_session.remove()
