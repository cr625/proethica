"""
Flask application initialization module.
"""

import os
from flask import Flask

from app.models import db
from app.template_filters import init_app as init_filters

def create_app(config_module='app.config'):
    """
    Create and configure the Flask application.
    
    Args:
        config_module (str): Module path to the configuration object.
        
    Returns:
        Flask: The configured Flask application
    """
    app = Flask(__name__)
    
    # Configure the app based on config_module
    if config_module == 'config':
        # Using our enhanced configuration system
        from config import app_config
        # Update app.config with our dictionary values
        for key, value in app_config.items():
            app.config[key] = value
        print(f"Using enhanced config: Database URL = {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not Set')}")
    else:
        # Using original configuration approach
        app.config.from_object(config_module)
    
    # Configure database
    # SQLAlchemy URL fix

    if app.config.get('SQLALCHEMY_DATABASE_URI') and '\\x3a' in app.config['SQLALCHEMY_DATABASE_URI']:

        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('\\x3a', ':')

        print(f"Fixed escaped database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")

    db.init_app(app)
    
    # Ensure database schema is properly setup (especially for models added after initial setup)
    with app.app_context():
        try:
            from scripts.ensure_schema import ensure_guidelines_table, ensure_entity_triples_columns
            
            # Ensure guidelines table exists
            ensure_guidelines_table()
            
            # Ensure required columns exist in entity_triples
            ensure_entity_triples_columns()
            
            print("Database schema verification completed successfully.")
        except Exception as e:
            print(f"Warning: Schema verification encountered an error: {str(e)}")
            print("The application will continue, but some features may not work correctly.")
    
    # Register template filters
    init_filters(app)
    
    # Register blueprints
    from app.routes.index import index_bp
    from app.routes.worlds import worlds_bp
    from app.routes.domains import domains_bp
    from app.routes.roles import roles_bp
    from app.routes.resources import resources_bp
    from app.routes.conditions import conditions_bp
    from app.routes.scenarios import scenarios_bp
    from app.routes.characters import characters_bp
    from app.routes.events import events_bp
    from app.routes.simulation import simulation_bp
    from app.routes.ontology import ontology_bp
    from app.routes.debug import debug_bp
    from app.routes.documents import documents_bp
    
    app.register_blueprint(index_bp)
    app.register_blueprint(worlds_bp, url_prefix='/worlds')
    app.register_blueprint(domains_bp, url_prefix='/domains')
    app.register_blueprint(roles_bp, url_prefix='/roles')
    app.register_blueprint(resources_bp, url_prefix='/resources')
    app.register_blueprint(conditions_bp, url_prefix='/conditions')
    app.register_blueprint(scenarios_bp, url_prefix='/scenarios')
    app.register_blueprint(characters_bp, url_prefix='/characters')
    app.register_blueprint(events_bp, url_prefix='/events')
    app.register_blueprint(simulation_bp, url_prefix='/simulation')
    app.register_blueprint(ontology_bp, url_prefix='/ontology')
    app.register_blueprint(debug_bp, url_prefix='/debug')
    app.register_blueprint(documents_bp, url_prefix='/documents')
    
    # Make db accessible at app level for imports in other modules
    app.db = db
    
    @app.context_processor
    def inject_environment():
        """Add environment variables to template context."""
        return {
            'environment': app.config.get('ENVIRONMENT', 'development'),
            'app_name': 'ProEthica'
        }
    
    return app

# Make db accessible at the module level for imports
db = db
