#!/usr/bin/env python3
"""
Create a new user account.

Usage:
    python scripts/create_user.py <username> <email> <password> [--admin]

Examples:
    python scripts/create_user.py reviewer reviewer@example.com SecurePass123
    python scripts/create_user.py admin admin@example.com AdminPass123 --admin
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.user import User


def create_user(username: str, email: str, password: str, is_admin: bool = False):
    """Create a new user account."""
    app = create_app()

    with app.app_context():
        # Check if user already exists
        existing = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing:
            if existing.username == username:
                print(f"Error: Username '{username}' already exists")
            else:
                print(f"Error: Email '{email}' already exists")
            return False

        # Create new user
        user = User(
            username=username,
            email=email,
            password=password,
            is_admin=is_admin
        )

        db.session.add(user)
        db.session.commit()

        role = 'admin' if is_admin else 'test_user'
        print(f"Created user: {username} ({email})")
        print(f"  Role: {role}")
        print(f"  Admin: {is_admin}")
        return True


def list_users():
    """List all users."""
    app = create_app()

    with app.app_context():
        users = User.query.order_by(User.created_at.desc()).all()

        if not users:
            print("No users found")
            return

        print(f"\n{'Username':<20} {'Email':<30} {'Admin':<6} {'Role':<12} {'Logins'}")
        print("-" * 80)
        for user in users:
            admin = 'Yes' if user.is_admin else 'No'
            logins = user.login_count or 0
            print(f"{user.username:<20} {user.email:<30} {admin:<6} {user.role:<12} {logins}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCurrent users:")
        list_users()
        sys.exit(1)

    if sys.argv[1] == '--list':
        list_users()
        sys.exit(0)

    if len(sys.argv) < 4:
        print("Error: Required arguments: <username> <email> <password>")
        print("Usage: python scripts/create_user.py <username> <email> <password> [--admin]")
        sys.exit(1)

    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]
    is_admin = '--admin' in sys.argv

    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    success = create_user(username, email, password, is_admin)
    sys.exit(0 if success else 1)
