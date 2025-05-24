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
    
    @app.template_filter('slice')
    def slice_filter(iterable, start, end=None):
        """Slice an iterable and return a list."""
        if not iterable:
            return []
        if end is None:
            return list(iterable)[start:]
        return list(iterable)[start:end]
    
    @app.template_filter('hash')
    def hash_filter(value):
        """Generate a hash value for the input."""
        if not value:
            return 0
        return hash(str(value))
    
    @app.template_filter('hash_participant_id')
    def hash_participant_id_filter(value):
        """Generate a participant ID based on hash of the input."""
        if not value:
            return "P0000"
        hash_value = abs(hash(str(value))) % 10000
        return f"P{hash_value:04d}"
