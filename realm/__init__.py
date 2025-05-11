"""
REALM - Resource for Engineering And Learning Materials.

This package provides integration with the Materials Science Engineering Ontology (MSEO)
through a Model Context Protocol (MCP) server.
"""

import os
import logging
from flask import Flask

__version__ = '0.1.0'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(test_config=None):
    """Create and configure the REALM Flask application.
    
    Args:
        test_config: Test configuration to use instead of the default
        
    Returns:
        Flask application instance
    """
    # Create Flask app
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder='static',
        template_folder='templates'
    )
    
    # Set default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-for-realm-app'),
        MSEO_SERVER_URL=os.environ.get('MSEO_SERVER_URL', 'http://localhost:8078'),
        MSEO_SERVER_NAME='mseo-mcp-server',
        DEBUG=os.environ.get('DEBUG', 'false').lower() == 'true',
    )
    
    # Load instance config if it exists
    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.update(test_config)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Initialize database
    from realm.database import init_db, shutdown_db
    
    # Configure services
    from realm.services import mseo_service
    
    # Import and register blueprints
    from realm.routes import register_routes
    register_routes(app)
    
    # Create a simple home page
    @app.route('/ping')
    def ping():
        return 'pong'
    
    # Initialize database
    with app.app_context():
        init_db()
    
    # Register teardown handler
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        shutdown_db()
    
    logger.info(f"REALM application initialized (v{__version__})")
    
    return app
