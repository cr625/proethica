#!/usr/bin/env python3
"""
Database Initialization Script for ProEthica.

This script creates all necessary database tables for the ProEthica application.
Run this script after setting up the PostgreSQL container to ensure the database schema is properly initialized.
"""

import os
import sys
import time

# Add the parent directory to sys.path to allow imports from the app package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set the database URL directly to avoid parsing issues
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

# Import Flask app and models
from app import create_app, db
from app.models.user import User
from app.models.world import World
from app.models.scenario import Scenario
from app.models.entity import Entity
from app.models.character import Character
from app.models.document import Document
from app.models.ontology import Ontology
from app.models.triple import Triple

def initialize_database():
    """Initialize the database by creating all tables."""
    print("Initializing ProEthica database...")
    
    # Create the app with a test configuration that uses our environment variable
    app = create_app('config')
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully.")
        
        # Check if tables exist
        engine = db.engine
        inspector = db.inspect(engine)
        tables = inspector.get_table_names()
        
        print("\nVerifying database tables:")
        expected_tables = [
            'users', 'worlds', 'scenarios', 'entities', 
            'characters', 'documents', 'ontologies', 'entity_triples'
        ]
        
        for table in expected_tables:
            if table in tables:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' is missing")
        
        print("\nDatabase initialization complete.")

if __name__ == "__main__":
    initialize_database()
