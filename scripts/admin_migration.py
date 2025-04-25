#!/usr/bin/env python3
"""
Add is_admin column to users table.

This script:
1. Adds is_admin column to the users table
2. Sets admin flag on the first user account (typically admin)
3. Exits with success or error
"""

import sys
import os
import logging
from sqlalchemy import Column, Boolean, text
from sqlalchemy.exc import SQLAlchemyError

# Add the parent directory to the path so we can import app correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_admin_column():
    """Add is_admin column to users table and set admin flag for first user."""
    try:
        # Configure app without unnecessary services for this script
        os.environ["USE_AGENT_ORCHESTRATOR"] = "false"
        os.environ["USE_CLAUDE"] = "false"
        os.environ["USE_MOCK_FALLBACK"] = "false"
        
        app = create_app()
        with app.app_context():
            # Check if column already exists - we'll do this with raw SQL to avoid SQLAlchemy cache issues
            connection = db.engine.connect()
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('users')
            has_admin_column = any(col['name'] == 'is_admin' for col in columns)
            
            if not has_admin_column:
                logger.info("Adding is_admin column to users table")
                # Add the column if it doesn't exist
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
                connection.commit()
                logger.info("Column added successfully")
            else:
                logger.info("is_admin column already exists")
            
            # Set the first user as admin
            from app.models.user import User
            first_user = User.query.order_by(User.id).first()
            
            if first_user:
                logger.info(f"Setting admin flag for user: {first_user.username}")
                first_user.is_admin = True
                db.session.commit()
                logger.info("Admin flag set successfully")
            else:
                logger.warning("No users found in the database")
            
            # Verify migration
            if first_user:
                # Refresh from database to ensure we see the changes
                db.session.refresh(first_user)
                logger.info(f"User {first_user.username} admin status: {first_user.is_admin}")
            
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error adding admin column: {str(e)}")
        return False

if __name__ == "__main__":
    if add_admin_column():
        logger.info("Admin column migration completed successfully")
    else:
        logger.error("Failed to complete admin column migration")
        sys.exit(1)
