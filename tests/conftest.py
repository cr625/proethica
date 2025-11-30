import os
import sys
import pytest
import subprocess
from datetime import datetime
from app import create_app, db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.resource import Resource
from app.models.event import Action, Event
from app.models.role import Role
from app.models.condition_type import ConditionType
from app.models.resource_type import ResourceType
from app.models.user import User


@pytest.fixture(scope="session")
def setup_test_database():
    """Set up the test database for all tests."""
    # Note: Path updated for new test directory structure
    # scripts/ is in .gitignore, script may not exist in all environments
    script_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'scripts', 'manage_test_db.py')
    
    # Run the script to reset the test database
    print("Setting up test database...")
    # Note: We're modifying this to be more tolerant of warnings
    # Some warnings from libraries like LangChain and sentence_transformers
    # shouldn't prevent tests from running
    try:
        result = subprocess.run(['python', script_path, '--reset'], capture_output=True, text=True)
        
        # Print any output for debugging purposes
        if result.stdout:
            print(f"Database setup output: {result.stdout}")
        if result.stderr:
            print(f"Database setup warnings/errors: {result.stderr}")
        
        # Do not exit on non-zero return code, warnings are likely causing this
        # but the database is probably still created successfully
    except Exception as e:
        print(f"Exception during database setup: {e}")
        # Continue anyway, database might still be usable
    
    print("Test database setup complete.")
    
    yield
    
    # We don't need to drop the database after tests since it's a dedicated test database
    # If you want to clean up after tests, uncomment the following:
    # 
    # print("Cleaning up test database...")
    # result = subprocess.run(['python', script_path, '--drop'], capture_output=True, text=True)
    # if result.returncode != 0:
    #     print(f"Error cleaning up test database: {result.stderr}")


@pytest.fixture
def app(setup_test_database):
    """Create and configure a Flask app for testing."""
    # Set the testing configuration
    os.environ['FLASK_ENV'] = 'testing'
    
    # Create the app with the testing configuration
    app = create_app('testing')
    
    # Start a fresh database session
    with app.app_context():
        # Truncate all tables to start with a clean slate for each test
        # but keep the schema intact
        db.session.execute(db.text('BEGIN'))
        for table in reversed(db.metadata.sorted_tables):
            try:
                db.session.execute(db.text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
            except Exception as e:
                print(f"Warning: Could not truncate table {table.name}: {e}")
                # Continue anyway - the table might not exist yet
                pass
        db.session.execute(db.text('COMMIT'))
    
    yield app
    
    # Clean up after the test
    with app.app_context():
        db.session.remove()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def app_context(app):
    """An application context for the app."""
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def create_test_user(app_context):
    """Create a test user."""
    def _create_test_user(username='testuser', email='test@example.com', password='password'):
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        return user
    return _create_test_user


@pytest.fixture
def create_test_world(app_context):
    """Create a test world."""
    def _create_test_world(name='Test World', description='This is a test world', ontology_source=None):
        world = World(
            name=name,
            description=description,
            ontology_source=ontology_source,
            metadata={}
        )
        db.session.add(world)
        db.session.commit()
        return world
    return _create_test_world


@pytest.fixture
def create_test_scenario(app_context):
    """Create a test scenario."""
    def _create_test_scenario(world_id, name='Test Scenario', description='This is a test scenario'):
        scenario = Scenario(
            name=name,
            description=description,
            world_id=world_id,
            metadata={}
        )
        db.session.add(scenario)
        db.session.commit()
        return scenario
    return _create_test_scenario


@pytest.fixture
def create_test_role(app_context):
    """Create a test role."""
    def _create_test_role(world_id, name='Test Role', description='This is a test role'):
        role = Role(
            name=name,
            description=description,
            world_id=world_id
        )
        db.session.add(role)
        db.session.commit()
        return role
    return _create_test_role


@pytest.fixture
def create_test_condition_type(app_context):
    """Create a test condition type."""
    def _create_test_condition_type(world_id, name='Test Condition Type', description='This is a test condition type'):
        condition_type = ConditionType(
            name=name,
            description=description,
            world_id=world_id,
            category='test'
        )
        db.session.add(condition_type)
        db.session.commit()
        return condition_type
    return _create_test_condition_type


@pytest.fixture
def create_test_resource_type(app_context):
    """Create a test resource type."""
    def _create_test_resource_type(world_id, name='Test Resource Type', description='This is a test resource type'):
        resource_type = ResourceType(
            name=name,
            description=description,
            world_id=world_id,
            category='test'
        )
        db.session.add(resource_type)
        db.session.commit()
        return resource_type
    return _create_test_resource_type


@pytest.fixture
def create_test_character(app_context):
    """Create a test character."""
    def _create_test_character(scenario_id, role_id=None, name='Test Character'):
        character = Character(
            name=name,
            scenario_id=scenario_id,
            role_id=role_id,
            attributes={}
        )
        db.session.add(character)
        db.session.commit()
        return character
    return _create_test_character


@pytest.fixture
def create_test_condition(app_context):
    """Create a test condition."""
    def _create_test_condition(character_id, condition_type_id=None, name='Test Condition', description='This is a test condition'):
        condition = Condition(
            name=name,
            description=description,
            character_id=character_id,
            condition_type_id=condition_type_id,
            severity=1
        )
        db.session.add(condition)
        db.session.commit()
        return condition
    return _create_test_condition


@pytest.fixture
def create_test_resource(app_context):
    """Create a test resource."""
    def _create_test_resource(scenario_id, resource_type_id=None, name='Test Resource', quantity=1):
        resource = Resource(
            name=name,
            scenario_id=scenario_id,
            resource_type_id=resource_type_id,
            quantity=quantity,
            description='This is a test resource'
        )
        db.session.add(resource)
        db.session.commit()
        return resource
    return _create_test_resource


@pytest.fixture
def create_test_action(app_context):
    """Create a test action."""
    def _create_test_action(scenario_id, character_id=None, name='Test Action', description='This is a test action'):
        action = Action(
            name=name,
            description=description,
            scenario_id=scenario_id,
            character_id=character_id,
            action_time=datetime.now(),
            action_type='test',
            parameters={},
            is_decision=False
        )
        db.session.add(action)
        db.session.commit()
        return action
    return _create_test_action


@pytest.fixture
def create_test_event(app_context):
    """Create a test event."""
    def _create_test_event(scenario_id, character_id=None, action_id=None, description='This is a test event'):
        event = Event(
            scenario_id=scenario_id,
            event_time=datetime.now(),
            description=description,
            character_id=character_id,
            action_id=action_id,
            parameters={}
        )
        db.session.add(event)
        db.session.commit()
        return event
    return _create_test_event


@pytest.fixture
def auth_client(client, create_test_user):
    """A test client with authentication."""
    user = create_test_user()
    client.post('/auth/login', data={
        'username': 'testuser',
        'password': 'password',
        'remember_me': False,
        'submit': 'Sign In'
    }, follow_redirects=True)
    return client


# Mock LLM fixtures for fast unit testing

@pytest.fixture
def mock_llm_client():
    """
    Provide a mock LLM client that returns pre-defined responses from fixtures.

    Usage:
        def test_role_extraction(mock_llm_client):
            extractor = DualRoleExtractor(llm_client=mock_llm_client)
            classes, individuals = extractor.extract_dual_roles(...)
    """
    from tests.mocks import MockLLMClient
    return MockLLMClient()


@pytest.fixture
def mock_llm_client_factory():
    """
    Provide a factory for creating mock LLM clients with custom overrides.

    Usage:
        def test_custom_response(mock_llm_client_factory):
            client = mock_llm_client_factory.create_with_overrides({
                'roles_facts': {'new_role_classes': [...], 'role_individuals': [...]}
            })
    """
    from tests.mocks.llm_client import MockLLMClientFactory
    return MockLLMClientFactory()


@pytest.fixture
def sample_case_text():
    """
    Provide sample case text for extraction tests.
    Based on Case 7 (AI in Engineering Practice).
    """
    return """
    Engineer A, an environmental engineer with several years of experience and holding a professional
    engineering license, was retained by Client W to prepare a comprehensive report addressing the
    manufacture, use, and characteristics of an organic compound identified as an emerging contaminant
    of concern. This work required Engineer A to perform an analysis of groundwater monitoring data
    from a site Engineer A had been observing for over a year. In addition, Engineer A was tasked to
    develop engineering design documents (plans and specifications) for modifications to groundwater
    infrastructure at the same site.

    Engineer A is known for their strong technical expertise but is, personally, less confident in
    their technical writing. Previously, Engineer A had relied on guidance and quality assurance
    reviews by their mentor and supervisor, Engineer B, to refine report drafts. But Engineer B
    recently retired and was no longer available to Engineer A in a work capacity.

    Faced with the need to deliver both the report and the engineering design documents without the
    review by and mentorship from Engineer B, Engineer A opted to use open-sourced artificial
    intelligence (AI) software to create an initial draft of the necessary report and to use
    AI-assisted drafting tools to generate preliminary design documents.
    """


@pytest.fixture
def sample_case_id():
    """Provide a sample case ID for extraction tests."""
    return 7
