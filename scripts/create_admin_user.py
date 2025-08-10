#!/usr/bin/env python3
"""
Script to create an admin user for the AI Ethical DM application.
Run this script to create a user with the provided username, email, and password.
"""

import os
import sys
import argparse
from flask import Flask
from werkzeug.security import generate_password_hash
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db

def create_user(username, email, password):
    """Create a new user with the given credentials."""
    # Create a minimal Flask app to work with the database
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or "postgresql://postgres:PASS@localhost/ai_ethical_dm"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the app with the database
    db.init_app(app)
    
    with app.app_context():
        # Import User model inside app context to avoid circular imports
        from app.models.user import User
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                print(f"Error: Username '{username}' is already taken.")
            else:
                print(f"Error: Email '{email}' is already registered.")
            return False
        
        # Create password hash directly
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        
        # Execute SQL directly to avoid potential ORM issues
        db.session.execute(
            text("""
            INSERT INTO users (username, email, password_hash, created_at, is_active, is_admin)
            VALUES (:username, :email, :password_hash, NOW(), TRUE, TRUE)
            """),
            {
                'username': username,
                'email': email,
                'password_hash': password_hash
            }
        )
        db.session.commit()
        
        print(f"User '{username}' created successfully!")
        return True

def main():
    """Main function to parse arguments and create a user."""
    parser = argparse.ArgumentParser(description='Create a user for the AI Ethical DM application.')
    parser.add_argument('--username', '-u', required=True, help='Username for the new user')
    parser.add_argument('--email', '-e', required=True, help='Email for the new user')
    parser.add_argument('--password', '-p', required=True, help='Password for the new user')
    
    args = parser.parse_args()
    
    create_user(args.username, args.email, args.password)

if __name__ == '__main__':
    main()
