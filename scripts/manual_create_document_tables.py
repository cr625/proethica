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
        # Enable pgvector extension
        db.session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        
        # Create tables
        Document.__table__.create(db.engine, checkfirst=True)
        DocumentChunk.__table__.create(db.engine, checkfirst=True)
        
        # Create index for similarity search
        db.session.execute(text('CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx ON document_chunks USING ivfflat (embedding vector_cosine_ops)'))
        
        db.session.commit()
        
        print("Document tables created successfully")

if __name__ == "__main__":
    create_tables()
