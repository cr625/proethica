#!/usr/bin/env python3
"""
Create a test user for ProEthica authentication.
Run this script to create an admin user when auth is enabled.
"""

import os
import sys
from werkzeug.security import generate_password_hash

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def create_test_user():
    """Create a test admin user."""
    app = create_app('config')
    
    with app.app_context():
        try:
            # Import the User model
            from app.models.user import User
            
            # Check if user already exists
            existing_user = User.query.filter_by(username='admin').first()
            if existing_user:
                print("✅ Test user 'admin' already exists!")
                print(f"   Username: admin")
                print(f"   Email: {existing_user.email}")
                return
            
            # Create test user
            user = User(
                username='admin',
                email='admin@proethica.org'
            )
            user.set_password('password123')  # Simple password for development
            
            db.session.add(user)
            db.session.commit()
            
            print("✅ Test user created successfully!")
            print("   Username: admin")
            print("   Password: password123")
            print("   Email: admin@proethica.org")
            print()
            print("💡 To enable authentication:")
            print("   1. Set BYPASS_AUTH='false' in run_debug_app.py")
            print("   2. Restart the server")
            print("   3. Login with the credentials above")
            
        except ImportError:
            print("❌ User model not found.")
            print("   This is normal if you haven't created the User table yet.")
            print("   The auth bypass system will work fine without it.")
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_test_user()