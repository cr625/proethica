import pytest
from flask import Flask, session, url_for
from flask_login import LoginManager, login_user
from unittest.mock import MagicMock, patch

from app.models.user import User
from app.agent_module import (
    create_agent_blueprint, 
    SourceInterface, 
    ContextProviderInterface,
    LLMInterface,
    FlaskLoginAuthAdapter,
    DefaultAuthProvider,
    FlaskSessionManager
)

# Mock render_template to avoid template issues in tests
def mock_render_template(*args, **kwargs):
    return "Rendered template: " + args[0]


# Mock implementations for testing
class MockSourceInterface(SourceInterface):
    """Mock source interface for testing."""
    
    def get_all_sources(self):
        return [{'id': 1, 'name': 'Test World'}]
    
    def get_source_by_id(self, source_id):
        if source_id == 1:
            return {'id': 1, 'name': 'Test World'}
        return None


class MockContextProvider(ContextProviderInterface):
    """Mock context provider for testing."""
    
    def get_context(self, source_id, query=None, additional_params=None):
        return {'content': 'Test context'}
    
    def format_context(self, context, max_tokens=None):
        return "Formatted test context"
    
    def get_guidelines(self, source_id):
        return "Test guidelines"


class MockLLMInterface(LLMInterface):
    """Mock LLM interface for testing."""
    
    def send_message(self, message, conversation, context=None, source_id=None):
        return {
            'content': f"Response to: {message}",
            'role': 'assistant',
            'timestamp': 1619000000.0
        }
    
    def get_suggestions(self, conversation, source_id=None):
        return [
            {'id': 1, 'text': 'Suggested prompt 1'},
            {'id': 2, 'text': 'Suggested prompt 2'}
        ]


class TestUser(User):
    """A test user for authentication testing."""
    def __init__(self, id=1, username='test', email='test@example.com'):
        self.id = id
        self.username = username
        self.email = email
        self.is_active = True
        self.password_hash = 'not-a-real-hash'
    
    def get_id(self):
        """Get the user ID."""
        return str(self.id)
    
    def is_authenticated(self):
        """Whether the user is authenticated."""
        return True
    
    def is_active(self):
        """Whether the user is active."""
        return True
    
    def is_anonymous(self):
        """Whether the user is anonymous."""
        return False


@pytest.fixture
def auth():
    """Create a login_required decorator for testing."""
    return FlaskLoginAuthAdapter()


@pytest.fixture
def app():
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-key'
    
    # Set up login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return TestUser(id=int(user_id))
    
    # Register agent blueprint with mocks
    source = MockSourceInterface()
    context = MockContextProvider()
    llm = MockLLMInterface()
    auth = FlaskLoginAuthAdapter()
    session = FlaskSessionManager()
    
    agent_bp = create_agent_blueprint(
        source_interface=source,
        context_provider=context,
        llm_interface=llm,
        auth_interface=auth,
        session_interface=session,
        require_auth=True,
        url_prefix='/agent'
    )
    
    app.register_blueprint(agent_bp)
    
    # Create a route for testing without auth
    @app.route('/no-auth')
    def no_auth():
        return 'No auth required'
    
    return app


def test_agent_routes_require_auth(app):
    """Test that agent routes require authentication."""
    with app.test_client() as client:
        # Test the agent window route
        response = client.get('/agent/')
        assert response.status_code == 401  # Unauthorized
        
        # Test the agent API route
        response = client.post('/agent/api/message', json={'message': 'test'})
        assert response.status_code == 401  # Unauthorized
        
        # Test suggestions route
        response = client.get('/agent/api/suggestions')
        assert response.status_code == 401  # Unauthorized
        
        # Test reset route
        response = client.post('/agent/api/reset')
        assert response.status_code == 401  # Unauthorized
        
        # Test a non-auth route
        response = client.get('/no-auth')
        assert response.status_code == 200  # OK


@patch('app.agent_module.blueprints.agent.render_template', mock_render_template)
def test_agent_routes_with_auth(app):
    """Test that agent routes work with authentication."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Create a test user and log them in
            user = TestUser()
            login_user(user)
            
            # Set user_id in session
            sess['user_id'] = user.get_id()
            sess['_fresh'] = True
        
        # Test the agent window route
        response = client.get('/agent/')
        assert response.status_code == 200  # OK
        assert "Rendered template: agent_window.html" in response.data.decode()
        
        # Test current user route
        response = client.get('/agent/api/current-user')
        assert response.status_code == 200  # OK
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['user']['username'] == 'test'


@patch('app.agent_module.blueprints.agent.render_template', mock_render_template)
def test_disable_auth_config(app):
    """Test that auth can be disabled via config."""
    # Create a new app with auth disabled
    app2 = Flask(__name__)
    app2.config['TESTING'] = True
    app2.config['SECRET_KEY'] = 'test-key'
    
    # Register agent blueprint with auth disabled
    source = MockSourceInterface()
    context = MockContextProvider()
    llm = MockLLMInterface()
    auth = DefaultAuthProvider()  # No auth
    session = FlaskSessionManager()
    
    agent_bp = create_agent_blueprint(
        source_interface=source,
        context_provider=context,
        llm_interface=llm,
        auth_interface=auth,
        session_interface=session,
        require_auth=False,
        url_prefix='/agent'
    )
    
    app2.register_blueprint(agent_bp)
    
    with app2.test_client() as client:
        # Test the agent window route
        response = client.get('/agent/')
        assert response.status_code == 200  # OK
        assert "Rendered template: agent_window.html" in response.data.decode()
        
        # Test current user route
        response = client.get('/agent/api/current-user')
        assert response.status_code == 200  # OK
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['user'] is None  # No user when auth is disabled
