"""
Custom template filters for the application.
"""

import os
import re
from flask import current_app
from markupsafe import Markup

def init_app(app):
    """Initialize template filters for the application."""
    
    @app.template_filter('basename')
    def basename_filter(path):
        """Return the basename of a file path."""
        return os.path.basename(path) if path else ''
    
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """Convert newlines to HTML line breaks."""
        if not text:
            return ''
        text = str(text)
        return Markup(text.replace('\n', '<br>\n'))
