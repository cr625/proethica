"""
Flask application initialization module.
"""

import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf

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
    
    # Initialize logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Verify required NLTK resources
    try:
        from app.utils.nltk_verification import verify_nltk_resources
        verify_nltk_resources()
    except Exception as e:
        logging.critical(f"NLTK resource verification failed: {str(e)}")
        print(f"\nERROR: {str(e)}\n")
    
    # Configure the app based on config_module
    if config_module == 'config':
        # Using our enhanced configuration system
        from config import app_config
        # Update app.config with our dictionary values
        for key, value in app_config.items():
            app.config[key] = value
        # Only show config details in debug mode
        if os.environ.get('DEBUG', '').lower() == 'true':
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
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user from the database for Flask-Login."""
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Simply test database connection without schema verification
    with app.app_context():
        try:
            from sqlalchemy import create_engine
            
            # Create engine from app config
            engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
            
            # Test connection only
            connection = engine.connect()
            connection.close()
            
            if os.environ.get('DEBUG', '').lower() == 'true':
                print("Database connection successful.")
        except Exception as e:
            print(f"Warning: Database connection error: {str(e)}")
            print("The application may not function correctly without database access.")
    
    # Register template filters
    init_filters(app)
    
    # Register template helpers for permissions and ownership
    from app.utils.template_helpers import register_template_helpers
    register_template_helpers(app)
    
    # Enable CSRF protection for forms and API (reads X-CSRFToken header for AJAX)
    try:
        csrf = CSRFProtect()
        csrf.init_app(app)
    except Exception as e:
        logging.getLogger(__name__).warning(f"CSRFProtect initialization failed: {e}")

    # Expose csrf_token() helper in templates
    @app.context_processor
    def inject_csrf_token():
        try:
            return dict(csrf_token=generate_csrf)
        except Exception:
            # In case CSRF not fully configured, avoid breaking templates
            return {}

    # Register blueprints
    from app.routes.index import index_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
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
    from app.routes.cases import cases_bp
    # from app.routes.cases_structure_update import cases_structure_bp  # Functionality consolidated into main cases_bp
    from app.routes.document_structure import doc_structure_bp
    from app.routes.test_routes import test_bp
    from app.routes.experiment import experiment_bp
    from app.routes.type_management import type_management_bp
    from app.routes.debug_env import debug_env_bp
    from app.routes.wizard import wizard_bp
    from app.routes.guidelines import guidelines_bp
    from app.routes.admin import admin_bp
    from app.routes.worlds_extract_only import worlds_extract_only_bp
    from ontology_editor import create_ontology_editor_blueprint
    
    app.register_blueprint(index_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
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
    app.register_blueprint(cases_bp, url_prefix='/cases')
    # app.register_blueprint(cases_structure_bp, url_prefix='/cases_enhanced')  # Functionality consolidated into main cases_bp
    app.register_blueprint(doc_structure_bp)
    app.register_blueprint(experiment_bp, url_prefix='/experiment')
    app.register_blueprint(type_management_bp)
    app.register_blueprint(debug_env_bp)
    app.register_blueprint(wizard_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(guidelines_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(worlds_extract_only_bp)
    
    # Create and register the ontology editor blueprint
    ontology_editor_bp = create_ontology_editor_blueprint(
        config={
            'require_auth': True,   # Enable authentication
            'admin_only': False     # Allow all authenticated users to access
        }
    )
    app.register_blueprint(ontology_editor_bp)
    
    # Make db accessible at app level for imports in other modules
    app.db = db
    
    @app.context_processor
    def inject_environment():
        """Add environment variables to template context."""
        return {
            'environment': app.config.get('ENVIRONMENT', 'development'),
            'app_name': 'ProEthica'
        }
    
    # Error handlers for authentication and permissions
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors with helpful message."""
        from flask import render_template
        return render_template('errors/403.html'), 403
    
    return app

# Make db accessible at the module level for imports
db = db
