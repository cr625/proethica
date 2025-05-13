"""
Custom template filters for the application.
"""

import os
import re
import markdown
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
    
    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown text to HTML."""
        if not text:
            return ''
        text = str(text)
        # Convert markdown to HTML using the Python-Markdown library
        md = markdown.Markdown(extensions=['extra', 'codehilite', 'fenced_code'])
        return Markup(md.convert(text))
