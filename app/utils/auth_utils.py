"""
Authentication utilities for ProEthica.

This module provides authentication decorators and utilities for the ProEthica system.
With the removal of the bypass system, all authentication now goes through Flask-Login.
"""

import functools
from flask_login import current_user


def admin_required(f):
    """
    Decorator that requires the current user to be an admin.
    Must be used in combination with @login_required.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # This should not happen if @login_required is used first
            from flask import abort
            abort(401)
        
        if not getattr(current_user, 'is_admin', False):
            from flask import abort
            abort(403)  # Forbidden
        
        return f(*args, **kwargs)
    
    return decorated_function


def data_owner_required(model_class, id_param='id'):
    """
    Decorator that requires the current user to be the owner of the data being accessed,
    or an admin. Must be used in combination with @login_required.
    
    Args:
        model_class: The SQLAlchemy model class to check ownership of
        id_param: The parameter name in the route that contains the item ID
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                from flask import abort
                abort(401)
            
            # Get the item ID from the route parameters
            item_id = kwargs.get(id_param)
            if item_id is None:
                from flask import abort
                abort(400)  # Bad request - missing ID
            
            # Get the item from the database
            item = model_class.query.get_or_404(item_id)
            
            # Check if user is admin or owns the data
            is_owner = getattr(item, 'created_by', None) == current_user.id
            is_admin = getattr(current_user, 'is_admin', False)
            
            if not (is_admin or is_owner):
                from flask import abort
                abort(403)  # Forbidden
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def user_required(f):
    """
    Decorator that requires any authenticated user.
    This is essentially the same as @login_required but kept for consistency.
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            from flask import abort
            abort(401)
        
        return f(*args, **kwargs)
    
    return decorated_function