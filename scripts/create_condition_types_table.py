"""
Script to create the condition_types table and update the conditions table.
This script will:
1. Check if the condition_types table exists
2. Create the table if it doesn't exist
3. Add the condition_type_id column to the conditions table if it doesn't exist
"""

import sys
import os
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text, inspect
from sqlalchemy.dialects.postgresql import JSON

def check_table_exists(table_name):
    """Check if a table exists in the database."""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns

def create_condition_types_table():
    """Create the condition_types table if it doesn't exist."""
    if check_table_exists('condition_types'):
        print("condition_types table already exists.")
        return True
    
    print("Creating condition_types table...")
    try:
        # Create the table
        db.engine.execute(text("""
            CREATE TABLE condition_types (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                world_id INTEGER NOT NULL REFERENCES worlds(id),
                category VARCHAR(100),
                severity_range JSON,
                ontology_uri VARCHAR(255),
                created_at TIMESTAMP WITHOUT TIME ZONE,
                updated_at TIMESTAMP WITHOUT TIME ZONE,
                condition_type_metadata JSON
            )
        """))
        print("condition_types table created successfully.")
        return True
    except Exception as e:
        print(f"Error creating condition_types table: {str(e)}")
        return False

def add_condition_type_id_column():
    """Add the condition_type_id column to the conditions table if it doesn't exist."""
    if not check_table_exists('conditions'):
        print("conditions table doesn't exist.")
        return False
    
    if check_column_exists('conditions', 'condition_type_id'):
        print("condition_type_id column already exists in conditions table.")
        return True
    
    print("Adding condition_type_id column to conditions table...")
    try:
        # Add the column
        db.engine.execute(text("""
            ALTER TABLE conditions
            ADD COLUMN condition_type_id INTEGER REFERENCES condition_types(id)
        """))
        print("condition_type_id column added successfully.")
        return True
    except Exception as e:
        print(f"Error adding condition_type_id column: {str(e)}")
        return False

def setup_condition_types():
    """Set up condition types for the application."""
    # Create the condition_types table
    if not create_condition_types_table():
        print("Failed to create condition_types table. Aborting setup.")
        return False
    
    # Add the condition_type_id column to the conditions table
    if not add_condition_type_id_column():
        print("Failed to add condition_type_id column. Aborting setup.")
        return False
    
    print("Condition types setup completed successfully.")
    return True

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        setup_condition_types()
