"""
Custom template filters for the application.
"""

import os
from flask import current_app

def init_app(app):
    """Initialize template filters for the application."""
    
    @app.template_filter('basename')
    def basename_filter(path):
        """Return the basename of a file path."""
        return os.path.basename(path) if path else ''
