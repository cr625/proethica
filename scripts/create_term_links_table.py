#!/usr/bin/env python3
"""
Create the section_term_links table in the database.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import os
from config.environment import get_config

# Set environment for development
os.environ['FLASK_ENV'] = 'development'

from app import create_app, db

def create_table():
    """Create the section_term_links table."""
    
    # Load config
    config = get_config()
    
    app = create_app(config)
    
    with app.app_context():
        try:
            # Read the SQL file
            sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', 'create_section_term_links_table.sql')
            with open(sql_file, 'r') as f:
                sql_commands = f.read()
            
            # Execute the SQL
            db.session.execute(db.text(sql_commands))
            db.session.commit()
            
            print("✅ Section term links table created successfully")
            
            # Verify the table was created
            result = db.session.execute(db.text("SELECT COUNT(*) FROM section_term_links"))
            print(f"✅ Table verified - current row count: {result.scalar()}")
            
        except Exception as e:
            print(f"❌ Error creating table: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_table()