#!/usr/bin/env python3
"""
Script to manually create a specific migration revision.
This will create the exact revision ID that your application is looking for.
"""
import os
import sys
from flask import Flask
from alembic.config import Config
from alembic import command

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import db

def create_specific_revision():
    """Create a specific migration revision."""
    # The specific revision ID your app is looking for
    REVISION_ID = 'd9c222ce7986'
    
    # Create a minimal Flask app to work with the database
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or "postgresql://postgres:PASS@localhost/ai_ethical_dm"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the app with the database
    db.init_app(app)
    
    with app.app_context():
        # Get the path to the migrations directory
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')
        
        # Create versions directory if it doesn't exist
        versions_dir = os.path.join(migrations_dir, 'versions')
        os.makedirs(versions_dir, exist_ok=True)
        
        # Create the migration file path
        migration_path = os.path.join(versions_dir, f'{REVISION_ID}_manual_revision.py')
        
        # Write the migration file with the exact revision ID
        with open(migration_path, 'w') as f:
            f.write(f"""\"\"\"manual revision

Revision ID: {REVISION_ID}
Revises: 
Create Date: 2025-03-20 00:00:00.000000

\"\"\"

# revision identifiers, used by Alembic.
revision = '{REVISION_ID}'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This is a placeholder migration that represents the current state of your database
    pass


def downgrade():
    # This is a placeholder migration that represents the current state of your database
    pass
""")
        
        print(f"Created migration revision {REVISION_ID} at {migration_path}")
        
        # Now stamp the database with this revision
        config = Config(os.path.join(migrations_dir, 'alembic.ini'))
        config.set_main_option('script_location', migrations_dir)
        
        # Stamp the database with this revision
        command.stamp(config, REVISION_ID)
        
        print(f"Database stamped with revision {REVISION_ID}")

if __name__ == '__main__':
    create_specific_revision()