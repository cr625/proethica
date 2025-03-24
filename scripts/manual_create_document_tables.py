#!/usr/bin/env python
"""
Script to manually create document and document_chunk tables with pgvector support.
This script should be run after installing the pgvector extension in PostgreSQL.
"""

import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, DocumentChunk

def create_tables():
    """Manually create document tables."""
    app = create_app()
    
    with app.app_context():
        # Try to enable pgvector extension
        try:
            db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        except Exception as e:
            print(f"Warning: Could not enable pgvector extension: {str(e)}")
            print("Continuing without vector similarity search support...")
        
        # Create tables
        Document.__table__.create(db.engine, checkfirst=True)
        DocumentChunk.__table__.create(db.engine, checkfirst=True)
        
        # No need to create vector similarity index since we're using JSON strings for embeddings
        
        db.session.commit()
        
        print("Document tables created successfully")

if __name__ == "__main__":
    create_tables()
