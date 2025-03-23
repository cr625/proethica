import os
import pytest
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


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    # Set the testing configuration
    os.environ['FLASK_ENV'] = 'testing'
    
    # Create the app with the testing configuration
    app = create_app('testing')
    
    # Create a test database
    with app.app_context():
        db.create_all()
    
    yield app
    
    # Clean up the database
    with app.app_context():
        db.session.remove()
        db.drop_all()


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
