"""
Flask application initialization module.
"""

import os
from flask import Flask

from app.models import db
from app.template_filters import init_app as init_filters

def create_app(config_object='app.config'):
    """
    Create and configure the Flask application.
    
    Args:
        config_object (str): Module path to the configuration object.
        
    Returns:
        Flask: The configured Flask application
    """
    app = Flask(__name__)
    
    # Configure the app
    app.config.from_object(config_object)
    
    # Configure database
    db.init_app(app)
    
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
