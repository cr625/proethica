"""
Authentication utilities for ProEthica.
"""

import os
import functools
from flask_login import current_user, login_required as flask_login_required
from flask import redirect, url_for, request


class MockUser:
    """Mock user for development mode when auth is bypassed."""
    
    def __init__(self, user_id=1):
        self.id = user_id
        self.username = "dev_user"
        self.email = "dev@proethica.org"
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<MockUser {self.username}>'


def get_mock_user(user_id=1):
    """Get a mock user for bypass mode."""
    return MockUser(user_id)


def login_required(f):
    """
    Custom login_required decorator that respects the BYPASS_AUTH environment variable.
    
    If BYPASS_AUTH is 'true', this decorator does nothing (allows access).
    If BYPASS_AUTH is 'false' or not set, this uses Flask-Login's normal behavior.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if auth is bypassed
        if os.environ.get('BYPASS_AUTH', 'false').lower() == 'true':
            # Auth is bypassed - allow access without checking login
            return f(*args, **kwargs)
        else:
            # Normal auth behavior - use Flask-Login's login_required
            return flask_login_required(f)(*args, **kwargs)
    
    return decorated_function


def get_current_user():
    """
    Get the current user, handling both real auth and bypass mode.
    """
    if os.environ.get('BYPASS_AUTH', 'false').lower() == 'true':
        # Return mock user in bypass mode
        return get_mock_user()
    else:
        # Return real current user
        return current_user


def is_authenticated():
    """
    Check if user is authenticated, handling both real auth and bypass mode.
    """
    if os.environ.get('BYPASS_AUTH', 'false').lower() == 'true':
        # Always authenticated in bypass mode
        return True
    else:
        # Check real authentication status
        return current_user.is_authenticated