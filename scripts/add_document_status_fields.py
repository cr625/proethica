#!/usr/bin/env python
"""
Add processing status fields to Document model.
"""

import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

def add_document_status_fields():
    """Add processing status fields to Document model."""
    app = create_app()
    
    with app.app_context():
        print("Adding processing status fields to Document model...")
        
        # Add processing_status column
        db.session.execute(text("""
            ALTER TABLE documents 
            ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) DEFAULT 'pending'
        """))
        
        # Add processing_error column
        db.session.execute(text("""
            ALTER TABLE documents 
            ADD COLUMN IF NOT EXISTS processing_error TEXT
        """))
        
        # Update existing documents to 'completed' status
        db.session.execute(text("""
            UPDATE documents 
            SET processing_status = 'completed' 
            WHERE processing_status = 'pending'
        """))
        
        db.session.commit()
        print("Successfully added processing status fields to Document model")

if __name__ == "__main__":
    add_document_status_fields()
