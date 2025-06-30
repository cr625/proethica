#!/usr/bin/env python3
"""
Create the section_term_links table in the database.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment for development
os.environ.setdefault('ENVIRONMENT', 'development')

# Set database URL if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

from app.models.section_term_link import SectionTermLink
from app import create_app, db

def create_table():
    """Create the section_term_links table."""
    
    app = create_app('config')
    
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            
            print("✅ All tables created successfully")
            
            # Verify the section_term_links table exists
            result = db.session.execute(db.text("SELECT COUNT(*) FROM section_term_links"))
            print(f"✅ section_term_links table verified - current row count: {result.scalar()}")
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")

if __name__ == '__main__':
    create_table()