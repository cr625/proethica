#!/usr/bin/env python3
"""
Script to add the ontology_id column to the worlds table.

This is necessary before running the migration script that
moves ontologies from files to the database.
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def add_ontology_id_column():
    """Add ontology_id column to worlds table if it doesn't exist."""
    app = create_app()
    
    with app.app_context():
        # Check if the column exists
        check_sql = text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='worlds' AND column_name='ontology_id'
            );
        """)
        
        result = db.session.execute(check_sql).scalar()
        
        if result:
            print("Column 'ontology_id' already exists in the 'worlds' table.")
            return
        
        print("Adding 'ontology_id' column to the 'worlds' table...")
        
        # Add the column
        add_column_sql = text("""
            ALTER TABLE worlds 
            ADD COLUMN ontology_id INTEGER REFERENCES ontologies(id);
        """)
        
        db.session.execute(add_column_sql)
        db.session.commit()
        
        print("Column added successfully!")
        
if __name__ == "__main__":
    add_ontology_id_column()
