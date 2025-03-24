#!/usr/bin/env python
"""
Script to migrate document_chunks table to use pgvector.
This script drops and recreates the document_chunks table with the vector type.
"""

import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, DocumentChunk

def migrate_to_pgvector():
    """Migrate document_chunks table to use pgvector."""
    app = create_app()
    
    with app.app_context():
        # Try to enable pgvector extension
        try:
            db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            print("pgvector extension enabled successfully")
        except Exception as e:
            print(f"Error: Could not enable pgvector extension: {str(e)}")
            print("Aborting migration...")
            return
        
        # Drop the document_chunks table
        try:
            db.session.execute(text('DROP TABLE IF EXISTS document_chunks CASCADE'))
            db.session.commit()
            print("Dropped document_chunks table")
        except Exception as e:
            print(f"Error dropping document_chunks table: {str(e)}")
            return
        
        # Create the document_chunks table with the vector type
        try:
            DocumentChunk.__table__.create(db.engine)
            print("Created document_chunks table with vector type")
        except Exception as e:
            print(f"Error creating document_chunks table: {str(e)}")
            return
        
        # Create vector similarity index
        try:
            db.session.execute(text('CREATE INDEX document_chunks_embedding_idx ON document_chunks USING ivfflat (embedding vector_cosine_ops)'))
            db.session.commit()
            print("Created vector similarity index")
        except Exception as e:
            print(f"Warning: Could not create vector similarity index: {str(e)}")
            print("Continuing without vector similarity index...")
        
        print("Migration completed successfully")

if __name__ == "__main__":
    migrate_to_pgvector()
