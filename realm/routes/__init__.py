"""
REALM Routes.

This package contains the route definitions for the REALM application.
"""

from flask import Blueprint

from realm.routes.main import main_bp
from realm.routes.api import api_bp

def register_routes(app):
    """Register all Blueprint routes with the Flask application.
    
    Args:
        app: Flask application instance
    """
    # Register blueprint routes
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register error handlers
    register_error_handlers(app)

def register_error_handlers(app):
    """Register error handlers with the Flask application.
    
    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def page_not_found(e):
        return {
            "error": "Not Found",
            "message": "The requested resource was not found"
        }, 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return {
            "error": "Internal Server Error",
            "message": "An internal server error occurred"
        }, 500
