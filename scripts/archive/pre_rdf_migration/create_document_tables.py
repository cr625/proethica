#!/usr/bin/env python
"""
Script to create a migration for document and document_chunk tables with pgvector support.
This script should be run after installing the pgvector extension in PostgreSQL.
"""

import os
import sys
from flask import Flask
from flask_migrate import Migrate

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, DocumentChunk

def create_migration():
    """Create a migration for document tables."""
    app = create_app()
    
    with app.app_context():
        # Create a migration
        migrate = Migrate(app, db)
        
        # Print instructions
        print("To create the migration, run:")
        print("flask db migrate -m \"Add document and document_chunk tables with pgvector support\"")
        print("\nTo apply the migration, run:")
        print("flask db upgrade")
        
        print("\nMake sure to enable the pgvector extension in your database:")
        print("CREATE EXTENSION IF NOT EXISTS vector;")

if __name__ == "__main__":
    create_migration()
