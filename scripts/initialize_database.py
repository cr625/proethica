#!/usr/bin/env python
import os
import sys
from flask_migrate import upgrade
from app import create_app, db

def initialize_database():
    """Initialize database schema by running all migrations."""
    print("Initializing database schema...")
    
    # Get environment from command line or use development as default
    environment = os.environ.get('ENVIRONMENT', 'development')
    print(f"Using environment: {environment}")
    
    # Create app with the specified environment
    app = create_app(environment)
    
    # Use app context to run migrations
    with app.app_context():
        # Upgrade database to the latest revision
        upgrade()
        
        # Check if database was initialized properly
        try:
            # Try to query some tables to verify they exist
            from app.models import World, User
            world_count = World.query.count()
            user_count = User.query.count()
            print(f"Database initialized successfully!")
            print(f"Found {world_count} worlds and {user_count} users in the database.")
        except Exception as e:
            print(f"Error checking database: {e}")
            return False
    
    return True

if __name__ == '__main__':
    # Set environment variable for the environment if provided as argument
    if len(sys.argv) > 1:
        os.environ['ENVIRONMENT'] = sys.argv[1]
    
    success = initialize_database()
    if not success:
        sys.exit(1)
