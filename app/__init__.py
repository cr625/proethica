"""
Flask application initialization module.
"""

import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf

from app.blueprints import (
    ADMIN_BLUEPRINTS,
    ANNOTATION_BLUEPRINTS,
    CORE_BLUEPRINTS,
    SCENARIO_BLUEPRINTS,
)
from app.models import db
from app.template_filters import init_app as init_filters
from app.utils.app_init import init_csrf_exemptions, smoke_test_db_connection


def create_app(config_name=None):
    """
    Create and configure the Flask application.
    
    Args:
        config_name (str): Name of configuration to use ('development', 'production', 'testing').
                          If None, uses FLASK_ENV environment variable or defaults to 'development'.
        
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
        print(f"\nNLTK Setup Required: {str(e)}\n")
        raise
    
    # Configure the app using standard Flask configuration
    from config import config
    
    # Determine which configuration to use
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Apply the configuration
    app.config.from_object(config[config_name])
    
    # Log configuration info in development mode
    if config_name == 'development' or os.environ.get('DEBUG', '').lower() == 'true':
        print(f"Using '{config_name}' configuration")
        print(f"Database URL: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not Set')}")
    
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
    
    smoke_test_db_connection(app)
    
    # Register template filters
    init_filters(app)
    
    # Register template helpers for permissions and ownership
    from app.utils.template_helpers import register_template_helpers
    register_template_helpers(app)
    
    # Enable CSRF protection for forms and API (reads X-CSRFToken header for AJAX)
    try:
        csrf = CSRFProtect()
        csrf.init_app(app)
        app.csrf = csrf  # Make csrf accessible at app level
    except Exception as e:
        logging.getLogger(__name__).warning(f"CSRFProtect initialization failed: {e}")
        csrf = None
        app.csrf = None

    # Expose csrf_token() helper in templates
    @app.context_processor
    def inject_csrf_token():
        try:
            return dict(csrf_token=generate_csrf)
        except Exception:
            # In case CSRF not fully configured, avoid breaking templates
            return {}

    def register_blueprints(blueprint_groups):
        for blueprint, options in blueprint_groups:
            app.register_blueprint(blueprint, **options)

    register_blueprints(CORE_BLUEPRINTS)
    register_blueprints(SCENARIO_BLUEPRINTS)
    register_blueprints(ANNOTATION_BLUEPRINTS)
    register_blueprints(ADMIN_BLUEPRINTS)
    
    init_csrf_exemptions(app)
    
    
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
    
    # Initialize prompt templates on startup (after database is ready)
    with app.app_context():
        try:
            from app.utils.prompt_seeder import seed_initial_prompt_templates
            seed_initial_prompt_templates()
        except Exception as e:
            print(f"Warning: Could not seed prompt templates: {e}")
    
    return app

# Make db accessible at the module level for imports
db = db
