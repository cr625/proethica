"""
Flask application initialization module.
"""

import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf

from app.models import db
from app.template_filters import init_app as init_filters

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

    # Expose pipeline state manager in templates
    @app.context_processor
    def inject_pipeline_state():
        """
        Inject pipeline state manager into all templates.

        Usage in templates:
            {% set state = get_pipeline_state(case_id) %}
            {% if state.can_start('step4', 'questions') %}
                <button>Extract Questions</button>
            {% endif %}
        """
        from app.services.pipeline_state_manager import get_pipeline_state, PipelineStateManager
        return dict(
            get_pipeline_state=get_pipeline_state,
            PipelineStateManager=PipelineStateManager
        )

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
    from app.routes.scenario_pipeline import interactive_scenario_bp
    from app.routes.scenario_pipeline.entity_review import bp as entity_review_bp
    from app.routes.scenario_pipeline.step4 import bp as step4_bp
    from app.routes.scenario_pipeline.step5 import bp as step5_bp
    from app.routes.characters import characters_bp
    from app.routes.events import events_bp
    from app.routes.simulation import simulation_bp
    # STUB ROUTES: Ontology functionality moved to OntServe - these redirect to OntServe
    from app.routes.ontology import ontology_bp
    from app.routes.debug import debug_bp
    from app.routes.documents import documents_bp
    from app.routes.cases import cases_bp
    from app.routes.document_structure import doc_structure_bp
    from app.routes.test_routes import test_bp
    from app.routes.experiment import experiment_bp
    from app.routes.type_management import type_management_bp
    from app.routes.debug_env import debug_env_bp
    from app.routes.wizard import wizard_bp
    from app.routes.guidelines import guidelines_bp
    from app.routes.admin import admin_bp
    from app.routes.admin_prompts import admin_prompts_bp
    from app.routes.prompt_builder import prompt_builder_bp
    from app.routes.worlds_extract_only import worlds_extract_only_bp
    from app.routes.annotations import annotations_bp
    from app.routes.agent import agent_bp
    # Enhanced intelligent annotations
    from app.routes.intelligent_annotations import intelligent_annotations_bp
    # Enhanced guideline annotations with multi-agent orchestration
    from app.routes.enhanced_annotations import bp as enhanced_annotations_bp
    # LLM-enhanced annotation routes
    from app.routes.llm_annotations import bp as llm_annotations_bp
    # Annotation review routes
    from app.routes.annotation_review import bp as annotation_review_bp
    # Annotation versioning API routes
    from app.routes.annotation_versions import annotation_versions_bp
    # Unified document annotation API routes
    from app.routes.api_document_annotations import bp as api_document_annotations_bp
    # Reasoning inspector routes
    from app.routes.reasoning import reasoning_bp
    # PROV-O provenance viewer routes
    from app.routes.provenance import provenance_bp
    # Tools routes (references, etc.)
    from app.routes.tools import tools_bp
    # Precedent discovery routes
    from app.routes.precedents import precedents_bp
    # Pipeline automation dashboard
    from app.routes.pipeline_dashboard import pipeline_bp
    # Documentation routes
    from app.routes.docs import docs_bp
    # Health check endpoints for monitoring
    from app.routes.health import health_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(worlds_bp, url_prefix='/worlds')
    app.register_blueprint(domains_bp, url_prefix='/domains')
    app.register_blueprint(roles_bp, url_prefix='/roles')
    app.register_blueprint(resources_bp, url_prefix='/resources')
    app.register_blueprint(conditions_bp, url_prefix='/conditions')
    app.register_blueprint(scenarios_bp, url_prefix='/scenarios')
    app.register_blueprint(interactive_scenario_bp)  # Uses /scenario_pipeline prefix from blueprint
    app.register_blueprint(entity_review_bp, url_prefix='/scenario_pipeline')
    app.register_blueprint(step4_bp)  # Uses /scenario_pipeline prefix from blueprint
    app.register_blueprint(step5_bp)  # Step 5: Scenario Generation
    app.register_blueprint(characters_bp, url_prefix='/characters')
    app.register_blueprint(events_bp, url_prefix='/events')
    app.register_blueprint(simulation_bp, url_prefix='/simulation')
    # STUB ROUTES: Ontology routes redirect to OntServe
    app.register_blueprint(ontology_bp, url_prefix='/ontology')
    app.register_blueprint(debug_bp, url_prefix='/debug')
    app.register_blueprint(documents_bp, url_prefix='/documents')
    app.register_blueprint(cases_bp, url_prefix='/cases')
    app.register_blueprint(doc_structure_bp)
    app.register_blueprint(experiment_bp, url_prefix='/experiment')
    app.register_blueprint(type_management_bp)
    app.register_blueprint(debug_env_bp)
    app.register_blueprint(wizard_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(guidelines_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_prompts_bp)
    app.register_blueprint(prompt_builder_bp)
    app.register_blueprint(worlds_extract_only_bp)
    app.register_blueprint(annotations_bp)
    app.register_blueprint(agent_bp)  # Register the agent blueprint
    app.register_blueprint(intelligent_annotations_bp)  # Register intelligent annotations
    app.register_blueprint(enhanced_annotations_bp)  # Register enhanced annotations with MCP integration
    app.register_blueprint(llm_annotations_bp)  # Register LLM-enhanced annotations
    app.register_blueprint(annotation_review_bp)  # Register annotation review endpoints
    app.register_blueprint(annotation_versions_bp)  # Register annotation versioning API
    app.register_blueprint(api_document_annotations_bp)  # Register unified document annotation API
    app.register_blueprint(reasoning_bp)  # Register reasoning inspector routes
    app.register_blueprint(provenance_bp)  # Register PROV-O provenance viewer routes
    app.register_blueprint(tools_bp)  # Register tools routes (references, etc.)
    app.register_blueprint(precedents_bp)  # Register precedent discovery routes
    app.register_blueprint(pipeline_bp)  # Pipeline automation dashboard
    app.register_blueprint(docs_bp)  # Documentation routes
    app.register_blueprint(health_bp)  # Health check endpoints for monitoring

    # Exempt API routes from CSRF protection
    from app.routes.api_document_annotations import init_csrf_exemption
    init_csrf_exemption(app)
    from app.routes.health import init_health_csrf_exemption
    init_health_csrf_exemption(app)
    from app.routes.scenario_pipeline.interactive_builder import init_csrf_exemption as init_scenario_csrf_exemption
    init_scenario_csrf_exemption(app)
    
    # Exempt specific case routes from CSRF protection
    from app.routes.cases import init_cases_csrf_exemption
    init_cases_csrf_exemption(app)
    
    # Initialize CSRF exemptions after registering blueprints
    from app.routes.scenario_pipeline.step1 import init_step1_csrf_exemption
    from app.routes.scenario_pipeline.step2 import init_step2_csrf_exemption
    from app.routes.scenario_pipeline.step3 import init_step3_csrf_exemption
    from app.routes.scenario_pipeline.step4 import init_step4_csrf_exemption
    from app.routes.scenario_pipeline.step5 import init_step5_csrf_exemption
    init_step1_csrf_exemption(app)
    init_step2_csrf_exemption(app)
    init_step3_csrf_exemption(app)
    init_step4_csrf_exemption(app)
    init_step5_csrf_exemption(app)

    # Exempt document structure routes from CSRF protection
    from app.routes.document_structure import init_doc_structure_csrf_exemption
    init_doc_structure_csrf_exemption(app)

    # Exempt pipeline API routes from CSRF protection
    from app.routes.pipeline_dashboard import init_pipeline_csrf_exemption
    init_pipeline_csrf_exemption(app)

    # Exempt entity review API routes from CSRF protection
    from app.routes.scenario_pipeline.entity_review import init_entity_review_csrf_exemption
    init_entity_review_csrf_exemption(app)


    # Make db accessible at app level for imports in other modules
    app.db = db
    
    @app.context_processor
    def inject_environment():
        """Add environment variables to template context."""
        return {
            'environment': app.config.get('ENVIRONMENT', 'development'),
            'app_name': 'ProEthica'
        }

    @app.context_processor
    def inject_domain_context():
        """
        Inject domain selection context for navigation.
        Provides all domains and the currently selected domain from session.
        """
        from flask import session
        from app.models.world import World

        try:
            # Get all available domains (reverse alpha so Engineering comes first)
            all_domains = World.query.order_by(World.name.desc()).all()

            # Always default to "Engineering" domain (ignore session for default)
            selected_domain = None
            if all_domains:
                selected_domain = next(
                    (d for d in all_domains if d.name == 'Engineering'),
                    all_domains[0]  # Fall back to first if not found
                )
                session['selected_domain_id'] = selected_domain.id

            return {
                'all_domains': all_domains,
                'selected_domain': selected_domain,
                'selected_domain_id': selected_domain.id if selected_domain else None
            }
        except Exception:
            return {
                'all_domains': [],
                'selected_domain': None,
                'selected_domain_id': None
            }

    @app.context_processor
    def inject_pipeline_status():
        """
        Inject pipeline_status for scenario pipeline pages.
        Only runs the query if we're on a scenario pipeline route with a case_id.
        """
        from flask import request
        result = {'pipeline_status': None}

        # Only compute for scenario_pipeline routes
        if request.endpoint and 'scenario_pipeline' in request.endpoint or \
           request.endpoint and request.endpoint.startswith('step4.') or \
           request.endpoint and request.endpoint.startswith('step5.'):
            # Try to get case_id from URL parameters
            case_id = request.view_args.get('case_id') if request.view_args else None
            if case_id:
                try:
                    from app.services.pipeline_status_service import PipelineStatusService
                    result['pipeline_status'] = PipelineStatusService.get_step_status(case_id)
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Failed to get pipeline status: {e}")

        return result
    
    # Error handlers for authentication and permissions
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors with helpful message."""
        from flask import render_template
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors with tracking and alerting."""
        from flask import render_template, request
        from flask_login import current_user
        logger = logging.getLogger(__name__)

        # Log the error
        logger.error(f"500 error on {request.path}: {error}")

        # Capture error for tracking and alerting
        try:
            from app.utils.error_tracker import capture_error
            user_id = current_user.id if current_user.is_authenticated else None
            capture_error(
                error=error,
                path=request.path,
                method=request.method,
                user_id=user_id,
                remote_addr=request.remote_addr,
                send_alert=True
            )
        except Exception as track_error:
            logger.warning(f"Failed to track error: {track_error}")

        # Check if templates exist, otherwise return JSON
        try:
            return render_template('errors/500.html'), 500
        except Exception:
            return {'error': 'Internal server error', 'status': 500}, 500

    # Initialize prompt templates on startup (after database is ready)
    with app.app_context():
        try:
            from app.utils.prompt_seeder import seed_initial_prompt_templates
            seed_initial_prompt_templates()
        except Exception as e:
            print(f"Warning: Could not seed prompt templates: {e}")

    # Activity tracking middleware
    @app.after_request
    def track_activity(response):
        """Track significant user activities for the activity log."""
        from flask import request
        from flask_login import current_user

        # Skip static files and health check endpoints
        if request.path.startswith('/static') or request.path.startswith('/health'):
            return response

        # Skip if not a successful response
        if response.status_code >= 400:
            return response

        # Determine if this is a significant action to log
        try:
            from app.utils.activity_tracker import log_activity

            path = request.path
            method = request.method
            user_id = current_user.id if current_user.is_authenticated else None
            username = current_user.username if current_user.is_authenticated else None

            # Categorize and log significant actions
            action = None
            category = None

            # Auth actions (handled separately in auth routes)
            if path.startswith('/auth/'):
                pass  # Let auth routes handle their own logging

            # Skip API/AJAX endpoints (usually internal)
            elif '/api/' in path or path.endswith('.json'):
                pass

            # Admin pages
            elif path.startswith('/admin'):
                if method == 'GET':
                    # Track admin page views
                    if path == '/admin/' or path == '/admin':
                        action = 'Viewed admin dashboard'
                    elif '/users' in path:
                        action = 'Viewed user management'
                    elif '/validation' in path:
                        action = 'Viewed validation studies'
                    elif '/data' in path:
                        action = 'Viewed data overview'
                    category = 'admin'
                elif method in ['POST', 'PUT', 'DELETE']:
                    action = f"Admin action on {path}"
                    category = 'admin'

            # Document/Case pages
            elif path.startswith('/cases/') or path.startswith('/documents/'):
                parts = path.split('/')
                if method == 'GET':
                    if path == '/cases/' or path == '/cases':
                        action = 'Viewed cases list'
                        category = 'page_view'
                    elif '/precedents' in path:
                        action = 'Viewed precedents'
                        category = 'page_view'
                    elif len(parts) >= 3 and parts[2].isdigit():
                        case_id = parts[2]
                        if '/structure' in path:
                            action = f"Viewed case {case_id} structure"
                        elif '/review' in path:
                            action = f"Viewed case {case_id} review"
                        else:
                            action = f"Viewed case {case_id}"
                        category = 'document'
                elif method in ['POST', 'PUT', 'DELETE']:
                    action = f"Modified {path}"
                    category = 'document'

            # Pipeline pages
            elif path.startswith('/scenario_pipeline/'):
                parts = path.split('/')
                if len(parts) >= 3 and parts[2].isdigit():
                    case_id = parts[2]
                    if method == 'POST':
                        action = f"Pipeline action on case {case_id}"
                        category = 'pipeline'
                    elif method == 'GET':
                        if len(parts) > 3:
                            step = parts[3]
                            action = f"Viewed pipeline {step} for case {case_id}"
                        else:
                            action = f"Viewed pipeline for case {case_id}"
                        category = 'pipeline'

            # Home page
            elif path == '/' or path == '/index':
                if method == 'GET':
                    action = 'Visited home page'
                    category = 'page_view'

            # Documentation
            elif path.startswith('/docs'):
                if method == 'GET':
                    action = 'Viewed documentation'
                    category = 'page_view'

            # Log if we identified an action
            if action and category:
                log_activity(
                    action=action,
                    category=category,
                    user_id=user_id,
                    username=username,
                    path=path,
                    method=method,
                    remote_addr=request.remote_addr
                )

        except Exception as e:
            # Don't let activity tracking break the request
            logging.getLogger(__name__).debug(f"Activity tracking error: {e}")

        return response

    return app

# Make db accessible at the module level for imports
db = db
