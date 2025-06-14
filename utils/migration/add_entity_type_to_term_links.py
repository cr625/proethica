#!/usr/bin/env python3
"""
Add entity_type column to section_term_links table
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

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

from app import create_app, db
from sqlalchemy import text

def main():
    """Add entity_type column to section_term_links table."""
    app = create_app('config')
    
    with app.app_context():
        print("Adding entity_type column to section_term_links table...")
        
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'section_term_links' 
                AND column_name = 'entity_type'
            """))
            
            if result.fetchone():
                print("✅ entity_type column already exists!")
                return
            
            # Add the column
            db.session.execute(text("""
                ALTER TABLE section_term_links 
                ADD COLUMN entity_type VARCHAR(100)
            """))
            
            # Set default value for existing rows
            db.session.execute(text("""
                UPDATE section_term_links 
                SET entity_type = 'unknown' 
                WHERE entity_type IS NULL
            """))
            
            db.session.commit()
            print("✅ Successfully added entity_type column!")
            
            # Show statistics
            result = db.session.execute(text("""
                SELECT COUNT(*) as total_links,
                       COUNT(CASE WHEN entity_type = 'unknown' THEN 1 END) as unknown_count
                FROM section_term_links
            """))
            
            row = result.fetchone()
            print(f"📊 Total term links: {row[0]}")
            print(f"📊 Links with 'unknown' entity type: {row[1]}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {str(e)}")
            raise

if __name__ == '__main__':
    main()