"""
Authentication services for agent module.
"""

from typing import Callable, Optional, Any
from functools import wraps
from flask_login import login_required as flask_login_required
from flask_login import current_user

from app.agent_module.interfaces.base import AuthInterface


class FlaskLoginAuthAdapter(AuthInterface):
    """
    Authentication adapter using Flask-Login.
    """
    
    def login_required(self, func: Callable) -> Callable:
        """
        Decorator to require login for a route.
        
        This method simply delegates to Flask-Login's login_required decorator.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        return flask_login_required(func)
    
    def get_current_user(self) -> Any:
        """
        Get the current user.
        
        This method simply returns Flask-Login's current_user object.
        
        Returns:
            Current user object or None if not authenticated
        """
        return current_user


class DefaultAuthProvider(AuthInterface):
    """
    Default authentication provider that doesn't require authentication.
    
    This can be used for applications that don't need authentication or
    for testing purposes.
    """
    
    def login_required(self, func: Callable) -> Callable:
        """
        Decorator that doesn't enforce login requirements.
        
        Args:
            func: Function to decorate
            
        Returns:
            Unmodified function
        """
        @wraps(func)
        def decorated_view(*args, **kwargs):
            return func(*args, **kwargs)
        
        return decorated_view
    
    def get_current_user(self) -> Optional[Any]:
        """
        Get the current user.
        
        In this implementation, there is no user.
        
        Returns:
            None
        """
        return None


class ConfigurableAuthProvider(AuthInterface):
    """
    Configurable authentication provider that can be toggled on or off.
    """
    
    def __init__(self, require_auth: bool = True, auth_provider: Optional[AuthInterface] = None):
        """
        Initialize the configurable authentication provider.
        
        Args:
            require_auth: Whether to require authentication
            auth_provider: Authentication provider to use when auth is required
        """
        self.require_auth = require_auth
        self.auth_provider = auth_provider or FlaskLoginAuthAdapter()
        self.no_auth_provider = DefaultAuthProvider()
    
    def login_required(self, func: Callable) -> Callable:
        """
        Decorator to require login for a route when authentication is enabled.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        if self.require_auth:
            return self.auth_provider.login_required(func)
        else:
            return self.no_auth_provider.login_required(func)
    
    def get_current_user(self) -> Any:
        """
        Get the current user when authentication is enabled.
        
        Returns:
            Current user object or None if not authenticated or auth is disabled
        """
        if self.require_auth:
            return self.auth_provider.get_current_user()
        else:
            return self.no_auth_provider.get_current_user()
