"""
Index route for the application.
"""

from flask import Blueprint, render_template, current_app, redirect, url_for

# Create a blueprint for the index routes
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    """
    Render the index page.
    
    Returns:
        Rendered index template or redirect to worlds
    """
    # If the application uses an index template
    try:
        return render_template('index.html')
    except:
        # Fallback to redirecting to worlds page if index template doesn't exist
        return redirect(url_for('worlds.list_worlds'))

@index_bp.route('/about')
def about():
    """
    Render the about page.
    
    Returns:
        Rendered about template
    """
    return render_template('about.html')

@index_bp.route('/health')
def health():
    """
    Health check endpoint.
    
    Returns:
        Simple health check response
    """
    return {
        "status": "healthy",
        "environment": current_app.config.get('ENVIRONMENT', 'unknown'),
        "app_name": "ProEthica"
    }
