#!/usr/bin/env python
"""
Database migration script to remove guidelines_url and guidelines_text fields from the World model.
This script should be run after migrate_guidelines_to_documents.py to ensure data is not lost.
"""

import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

def remove_guidelines_fields():
    """Remove guidelines_url and guidelines_text fields from the World model."""
    app = create_app()
    
    with app.app_context():
        print("Starting removal of guidelines fields from World model...")
        
        # Check if the fields exist by inspecting the table info
        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('worlds')
        column_names = [column['name'] for column in columns]
        
        guidelines_url_exists = 'guidelines_url' in column_names
        guidelines_text_exists = 'guidelines_text' in column_names
        
        if not guidelines_url_exists and not guidelines_text_exists:
            print("Fields do not exist in the database, nothing to do.")
            return
        
        print("Fields exist in the database, proceeding with removal...")
        
        # Drop the columns
        try:
            if guidelines_url_exists:
                db.session.execute(text("ALTER TABLE worlds DROP COLUMN IF EXISTS guidelines_url"))
                print("Dropped guidelines_url column")
            
            if guidelines_text_exists:
                db.session.execute(text("ALTER TABLE worlds DROP COLUMN IF EXISTS guidelines_text"))
                print("Dropped guidelines_text column")
            
            db.session.commit()
            print("Successfully removed guidelines fields from World model")
        except Exception as e:
            db.session.rollback()
            print(f"Error removing guidelines fields: {str(e)}")
            raise

if __name__ == "__main__":
    remove_guidelines_fields()
