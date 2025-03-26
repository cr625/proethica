from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))

def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    from app.config import config
    app.config.from_object(config[config_name])
    
    # Check if agent orchestrator is enabled
    use_agent_orchestrator = os.environ.get('USE_AGENT_ORCHESTRATOR', 'false').lower() == 'true'
    app.config['USE_AGENT_ORCHESTRATOR'] = use_agent_orchestrator
    
    if use_agent_orchestrator:
        app.logger.info("Agent Orchestrator is ENABLED")
    else:
        app.logger.info("Agent Orchestrator is DISABLED")
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.worlds import worlds_bp
    from app.routes.scenarios import scenarios_bp
    from app.routes.entities import entities_bp
    from app.routes.agent import agent_bp
    from app.routes.mcp_api import mcp_api_bp
    from app.routes.documents import documents_bp, documents_web_bp
    from app.routes.simulation import simulation_bp
    from app.routes.cases import cases_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(worlds_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(entities_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(mcp_api_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(documents_web_bp)
    app.register_blueprint(simulation_bp)
    app.register_blueprint(cases_bp)
    
    # Register template filters
    from app import template_filters
    template_filters.init_app(app)
    
    # Import MCPClient here to avoid circular imports
    from app.services import MCPClient
    
    # Get the singleton instance of MCPClient
    client = MCPClient.get_instance()
    
    # Register context processor to make agent orchestrator config available to templates
    @app.context_processor
    def inject_agent_orchestrator_config():
        return {
            'use_agent_orchestrator': app.config.get('USE_AGENT_ORCHESTRATOR', False)
        }

    # Create routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    # Redirect /cases to the cases blueprint
    @app.route('/cases')
    def cases_redirect():
        from flask import redirect, url_for
        return redirect(url_for('cases.list_cases'))
    
    @app.route('/about')
    def about():
        return render_template('about.html')

    return app
