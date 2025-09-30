"""
Environment-aware authentication utilities for ProEthica.

This module provides authentication decorators that behave differently in development
vs production environments. In development, authentication is optional for testing.
In production, authentication is enforced for write operations.
"""

import functools
from flask import current_app, request, abort, redirect, url_for, flash
from flask_login import current_user, login_required
from werkzeug.exceptions import Unauthorized


def is_production():
    """Check if the application is running in production mode."""
    return current_app.config.get('ENVIRONMENT') == 'production'


def is_read_only_request():
    """
    Determine if the current request is read-only.
    GET requests are typically read-only, while POST, PUT, DELETE, PATCH are write operations.
    """
    return request.method in ['GET', 'HEAD', 'OPTIONS']


def auth_required_for_write(f):
    """
    Decorator that requires authentication only for write operations (POST, PUT, DELETE, PATCH).
    In development mode, authentication is optional for all operations.
    In production mode, authentication is required for write operations but not for reads.

    This allows public viewing of content while protecting data modification.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # In development mode, bypass authentication
        if not is_production():
            return f(*args, **kwargs)

        # In production mode, check if this is a write operation
        if not is_read_only_request():
            # Write operations require authentication
            if not current_user.is_authenticated:
                # For AJAX requests, return 401
                if request.is_json or request.path.startswith('/api/'):
                    abort(401)
                # For regular requests, redirect to login
                flash('Please log in to perform this action.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

        # Read operations or authenticated users can proceed
        return f(*args, **kwargs)

    return decorated_function


def auth_required_for_llm(f):
    """
    Decorator specifically for LLM/AI operations that cost money.
    Always requires authentication in production.
    Optional in development.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # In development mode, bypass authentication
        if not is_production():
            return f(*args, **kwargs)

        # In production, always require authentication for LLM operations
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                abort(401)
            flash('Please log in to use AI features.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        return f(*args, **kwargs)

    return decorated_function


def auth_optional(f):
    """
    Decorator for routes where authentication is completely optional.
    The route will work for both authenticated and anonymous users.
    Useful for public read operations.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Simply pass through - Flask-Login's current_user will be
        # either authenticated or anonymous
        return f(*args, **kwargs)

    return decorated_function


def development_only(f):
    """
    Decorator for routes that should only be accessible in development mode.
    Useful for debug endpoints and testing tools.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if is_production():
            abort(404)  # Pretend the route doesn't exist in production
        return f(*args, **kwargs)

    return decorated_function


def admin_required_production(f):
    """
    Decorator that requires admin privileges in production but not in development.
    Useful for sensitive operations that developers need access to locally.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if is_production():
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    abort(401)
                return redirect(url_for('auth.login', next=request.url))

            if not getattr(current_user, 'is_admin', False):
                abort(403)  # Forbidden

        # In development, allow access
        return f(*args, **kwargs)

    return decorated_function


def auth_required_for_create(f):
    """
    Decorator that requires authentication for creation forms and actions.
    This includes both GET requests (forms) and POST requests (actions).
    In development mode, authentication is optional.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # In development mode, bypass authentication
        if not is_production():
            return f(*args, **kwargs)

        # In production, always require authentication
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                abort(401)
            flash('Please log in to create content.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        return f(*args, **kwargs)

    return decorated_function