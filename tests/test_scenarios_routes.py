import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from flask import url_for
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.resource import Resource
from app.models.event import Action, Event


def test_api_get_scenarios(client, create_test_world, create_test_scenario):
    """Test the API endpoint to get all scenarios."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get('/scenarios/api')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['data']) == 1
    assert data['data'][0]['id'] == scenario.id
    assert data['data'][0]['name'] == scenario.name


def test_api_get_scenario(client, create_test_world, create_test_scenario):
    """Test the API endpoint to get a specific scenario by ID."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/api/{scenario.id}')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['data']['id'] == scenario.id
    assert data['data']['name'] == scenario.name


def test_api_get_scenario_not_found(client):
    """Test the API endpoint to get a non-existent scenario."""
    # Send request for a non-existent scenario
    response = client.get('/scenarios/api/999')
    
    # Verify response
    assert response.status_code == 404


def test_list_scenarios(client, create_test_world, create_test_scenario):
    """Test the list_scenarios route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get('/scenarios/')
    
    # Verify response
    assert response.status_code == 200
    assert b'Test Scenario' in response.data


def test_list_scenarios_with_world_filter(client, create_test_world, create_test_scenario):
    """Test the list_scenarios route with world filter."""
    # Create test data
    world1 = create_test_world(name='World 1')
    world2 = create_test_world(name='World 2')
    scenario1 = create_test_scenario(world_id=world1.id, name='Scenario 1')
    scenario2 = create_test_scenario(world_id=world2.id, name='Scenario 2')
    
    # Send request with world filter
    response = client.get(f'/scenarios/?world_id={world1.id}')
    
    # Verify response
    assert response.status_code == 200
    assert b'Scenario 1' in response.data
    assert b'Scenario 2' not in response.data


def test_new_scenario(client, create_test_world):
    """Test the new_scenario route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.get('/scenarios/new')
    
    # Verify response
    assert response.status_code == 200
    assert b'Create New Scenario' in response.data


def test_new_scenario_with_world(client, create_test_world):
    """Test the new_scenario route with world_id parameter."""
    # Create test data
    world = create_test_world()
    
    # Send request with world_id
    response = client.get(f'/scenarios/new?world_id={world.id}')
    
    # Verify response
    assert response.status_code == 200
    assert b'Create New Scenario' in response.data
    assert str(world.id).encode() in response.data


def test_view_scenario(client, create_test_world, create_test_scenario):
    """Test the view_scenario route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}')
    
    # Verify response
    assert response.status_code == 200
    assert scenario.name.encode() in response.data
    assert scenario.description.encode() in response.data


def test_view_scenario_not_found(client):
    """Test the view_scenario route with a non-existent scenario."""
    # Send request for a non-existent scenario
    response = client.get('/scenarios/999')
    
    # Verify response
    assert response.status_code == 404


def test_edit_scenario(client, create_test_world, create_test_scenario):
    """Test the edit_scenario route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/edit')
    
    # Verify response
    assert response.status_code == 200
    assert b'Edit Scenario' in response.data
    assert scenario.name.encode() in response.data


def test_update_scenario_form(client, create_test_world, create_test_scenario):
    """Test the update_scenario_form route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/edit', data={
        'name': 'Updated Scenario',
        'description': 'This is an updated scenario',
        'world_id': world.id
    }, follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Scenario updated successfully' in response.data
    assert b'Updated Scenario' in response.data


def test_update_scenario_form_invalid_world(client, create_test_world, create_test_scenario):
    """Test the update_scenario_form route with an invalid world ID."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request with invalid world ID
    response = client.post(f'/scenarios/{scenario.id}/edit', data={
        'name': 'Updated Scenario',
        'description': 'This is an updated scenario',
        'world_id': 999
    }, follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'World with ID 999 not found' in response.data


def test_create_scenario(client, create_test_world):
    """Test the create_scenario route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.post('/scenarios/', data={
        'name': 'New Scenario',
        'description': 'This is a new scenario',
        'world_id': world.id
    }, follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Scenario created successfully' in response.data
    assert b'New Scenario' in response.data


def test_create_scenario_api(client, create_test_world):
    """Test the create_scenario API route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.post('/scenarios/', json={
        'name': 'New Scenario',
        'description': 'This is a new scenario',
        'world_id': world.id
    })
    
    # Verify response
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Scenario created successfully'
    assert data['data']['name'] == 'New Scenario'


def test_create_scenario_invalid_world(client):
    """Test the create_scenario route with an invalid world ID."""
    # Send request with invalid world ID
    response = client.post('/scenarios/', data={
        'name': 'New Scenario',
        'description': 'This is a new scenario',
        'world_id': 999
    }, follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'World with ID 999 not found' in response.data


def test_delete_scenario_form(client, create_test_world, create_test_scenario):
    """Test the delete_scenario_form route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Scenario deleted successfully' in response.data
    
    # Verify scenario was deleted
    response = client.get(f'/scenarios/{scenario.id}')
    assert response.status_code == 404


def test_delete_scenario_api(client, create_test_world, create_test_scenario):
    """Test the delete_scenario API route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.delete(f'/scenarios/{scenario.id}')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Scenario deleted successfully'
    
    # Verify scenario was deleted
    response = client.get(f'/scenarios/api/{scenario.id}')
    assert response.status_code == 404


# Character routes tests
def test_new_character(client, create_test_world, create_test_scenario):
    """Test the new_character route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/characters/new')
    
    # Verify response
    assert response.status_code == 200
    assert b'Add Character' in response.data


def test_add_character(client, create_test_world, create_test_scenario, create_test_role):
    """Test the add_character route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    role = create_test_role(world_id=world.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/characters', json={
        'name': 'Test Character',
        'role_id': role.id,
        'attributes': {'strength': 10, 'intelligence': 15},
        'conditions': [
            {
                'name': 'Test Condition',
                'description': 'This is a test condition',
                'severity': 2
            }
        ]
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Character added successfully'
    assert data['data']['name'] == 'Test Character'
    
    # Verify character was added
    from app.models.character import Character
    character = Character.query.filter_by(name='Test Character').first()
    assert character is not None
    assert character.scenario_id == scenario.id
    assert character.role_id == role.id


def test_edit_character(client, create_test_world, create_test_scenario, create_test_character):
    """Test the edit_character route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/characters/{character.id}/edit')
    
    # Verify response
    assert response.status_code == 200
    assert b'Edit Character' in response.data
    assert character.name.encode() in response.data


def test_update_character(client, create_test_world, create_test_scenario, create_test_character, create_test_role):
    """Test the update_character route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    role = create_test_role(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/characters/{character.id}/update', json={
        'name': 'Updated Character',
        'role_id': role.id,
        'attributes': {'strength': 12, 'intelligence': 18},
        'conditions': []
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Character updated successfully'
    assert data['data']['name'] == 'Updated Character'
    
    # Verify character was updated
    character = Character.query.get(character.id)
    assert character.name == 'Updated Character'
    assert character.role_id == role.id


def test_delete_character(client, create_test_world, create_test_scenario, create_test_character):
    """Test the delete_character route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/characters/{character.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Character and associated actions deleted successfully' in response.data
    
    # Verify character was deleted
    character = Character.query.get(character.id)
    assert character is None


# Resource routes tests
def test_new_resource(client, create_test_world, create_test_scenario):
    """Test the new_resource route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/resources/new')
    
    # Verify response
    assert response.status_code == 200
    assert b'Add Resource' in response.data


def test_add_resource(client, create_test_world, create_test_scenario, create_test_resource_type):
    """Test the add_resource route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    resource_type = create_test_resource_type(world_id=world.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/resources', json={
        'name': 'Test Resource',
        'resource_type_id': resource_type.id,
        'quantity': 5,
        'description': 'This is a test resource'
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Resource added successfully'
    assert data['data']['name'] == 'Test Resource'
    assert data['data']['quantity'] == 5
    
    # Verify resource was added
    from app.models.resource import Resource
    resource = Resource.query.filter_by(name='Test Resource').first()
    assert resource is not None
    assert resource.scenario_id == scenario.id
    assert resource.resource_type_id == resource_type.id
    assert resource.quantity == 5


def test_edit_resource(client, create_test_world, create_test_scenario, create_test_resource):
    """Test the edit_resource route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    resource = create_test_resource(scenario_id=scenario.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/resources/{resource.id}/edit')
    
    # Verify response
    assert response.status_code == 200
    assert b'Edit Resource' in response.data
    assert resource.name.encode() in response.data


def test_update_resource(client, create_test_world, create_test_scenario, create_test_resource, create_test_resource_type):
    """Test the update_resource route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    resource_type = create_test_resource_type(world_id=world.id)
    resource = create_test_resource(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/resources/{resource.id}/update', json={
        'name': 'Updated Resource',
        'resource_type_id': resource_type.id,
        'quantity': 10,
        'description': 'This is an updated resource'
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Resource updated successfully'
    assert data['data']['name'] == 'Updated Resource'
    assert data['data']['quantity'] == 10
    
    # Verify resource was updated
    resource = Resource.query.get(resource.id)
    assert resource.name == 'Updated Resource'
    assert resource.resource_type_id == resource_type.id
    assert resource.quantity == 10


def test_delete_resource(client, create_test_world, create_test_scenario, create_test_resource):
    """Test the delete_resource route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    resource = create_test_resource(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/resources/{resource.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Resource deleted successfully' in response.data
    
    # Verify resource was deleted
    resource = Resource.query.get(resource.id)
    assert resource is None


# Action routes tests
def test_new_action(client, create_test_world, create_test_scenario):
    """Test the new_action route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/actions/new')
    
    # Verify response
    assert response.status_code == 200
    assert b'Add Action' in response.data


def test_add_action(client, create_test_world, create_test_scenario, create_test_character):
    """Test the add_action route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/actions', json={
        'name': 'Test Action',
        'description': 'This is a test action',
        'character_id': character.id,
        'action_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action_type': 'test',
        'parameters': {'param1': 'value1'},
        'is_decision': False
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Action added successfully'
    assert data['data']['name'] == 'Test Action'
    
    # Verify action was added
    action = Action.query.filter_by(name='Test Action').first()
    assert action is not None
    assert action.scenario_id == scenario.id
    assert action.character_id == character.id


def test_edit_action(client, create_test_world, create_test_scenario, create_test_action):
    """Test the edit_action route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    action = create_test_action(scenario_id=scenario.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/actions/{action.id}/edit')
    
    # Verify response
    assert response.status_code == 200
    assert b'Edit Action' in response.data
    assert action.name.encode() in response.data


def test_update_action(client, create_test_world, create_test_scenario, create_test_action, create_test_character):
    """Test the update_action route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    action = create_test_action(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/actions/{action.id}/update', json={
        'name': 'Updated Action',
        'description': 'This is an updated action',
        'character_id': character.id,
        'action_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action_type': 'updated',
        'parameters': {'param2': 'value2'},
        'is_decision': True,
        'options': ['Option 1', 'Option 2']
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Action updated successfully'
    assert data['data']['name'] == 'Updated Action'
    assert data['data']['is_decision'] is True
    
    # Verify action was updated
    action = Action.query.get(action.id)
    assert action.name == 'Updated Action'
    assert action.character_id == character.id
    assert action.is_decision is True


def test_delete_action(client, create_test_world, create_test_scenario, create_test_action):
    """Test the delete_action route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    action = create_test_action(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/actions/{action.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Action deleted successfully' in response.data
    
    # Verify action was deleted
    action = Action.query.get(action.id)
    assert action is None


# Event routes tests
def test_new_event(client, create_test_world, create_test_scenario):
    """Test the new_event route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/events/new')
    
    # Verify response
    assert response.status_code == 200
    assert b'Add Event' in response.data


def test_add_event(client, create_test_world, create_test_scenario, create_test_character):
    """Test the add_event route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/events', json={
        'description': 'This is a test event',
        'event_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'character_id': character.id,
        'metadata': {'meta1': 'value1'}
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Event added successfully'
    assert data['data']['description'] == 'This is a test event'
    
    # Verify event was added
    event = Event.query.filter_by(description='This is a test event').first()
    assert event is not None
    assert event.scenario_id == scenario.id
    assert event.character_id == character.id


def test_edit_event(client, create_test_world, create_test_scenario, create_test_event):
    """Test the edit_event route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    event = create_test_event(scenario_id=scenario.id)
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/events/{event.id}/edit')
    
    # Verify response
    assert response.status_code == 200
    assert b'Edit Event' in response.data
    assert event.description.encode() in response.data


def test_update_event(client, create_test_world, create_test_scenario, create_test_event, create_test_character):
    """Test the update_event route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    character = create_test_character(scenario_id=scenario.id)
    event = create_test_event(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/events/{event.id}/update', json={
        'description': 'This is an updated event',
        'event_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'character_id': character.id,
        'metadata': {'meta2': 'value2'}
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Event updated successfully'
    assert data['data']['description'] == 'This is an updated event'
    
    # Verify event was updated
    event = Event.query.get(event.id)
    assert event.description == 'This is an updated event'
    assert event.character_id == character.id


def test_delete_event(client, create_test_world, create_test_scenario, create_test_event):
    """Test the delete_event route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    event = create_test_event(scenario_id=scenario.id)
    
    # Send request
    response = client.post(f'/scenarios/{scenario.id}/events/{event.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'Event deleted successfully' in response.data
    
    # Verify event was deleted
    event = Event.query.get(event.id)
    assert event is None


# References routes tests
def test_scenario_references(client, create_test_world, create_test_scenario, monkeypatch):
    """Test the scenario_references route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Mock the MCPClient.get_references_for_scenario method
    from app.services.mcp_client import MCPClient
    from app.services.zotero_client import ZoteroClient
    
    # Clear the singleton instances
    MCPClient._instance = None
    ZoteroClient._instance = None
    
    # Create a mock instance
    mock_client = MagicMock()
    mock_client.get_references_for_scenario.return_value = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
    
    # Set up the mock to render the reference in the template
    mock_client.search_zotero_items.return_value = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
    
    # Replace the get_instance method
    monkeypatch.setattr(MCPClient, 'get_instance', lambda: mock_client)
    
    # Set environment variable for testing
    import os
    os.environ['TESTING'] = 'true'
    
    # Send request
    response = client.get(f'/scenarios/{scenario.id}/references')
    
    # Verify response
    assert response.status_code == 200
    assert b'References' in response.data
    
    # Clean up
    del os.environ['TESTING']


def test_scenario_references_with_search(client, create_test_world, create_test_scenario, monkeypatch):
    """Test the scenario_references route with search query."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Mock the MCPClient.search_zotero_items method
    from app.services.mcp_client import MCPClient
    from app.services.zotero_client import ZoteroClient
    
    # Clear the singleton instances
    MCPClient._instance = None
    ZoteroClient._instance = None
    
    # Create a mock instance
    mock_client = MagicMock()
    mock_client.search_zotero_items.return_value = [{'data': {'title': 'Search Result', 'creators': [{'firstName': 'Jane', 'lastName': 'Smith'}]}, 'key': 'ref2'}]
    
    # Replace the get_instance method
    monkeypatch.setattr(MCPClient, 'get_instance', lambda: mock_client)
    
    # Set environment variable for testing
    import os
    os.environ['TESTING'] = 'true'
    
    # Send request with search query
    response = client.get(f'/scenarios/{scenario.id}/references?query=ethics')
    
    # Verify response
    assert response.status_code == 200
    assert b'References' in response.data
    
    # Clean up
    del os.environ['TESTING']


def test_get_reference_citation(client, create_test_world, create_test_scenario, monkeypatch):
    """Test the get_reference_citation route."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Mock the ZoteroClient.get_citation method
    from app.services.mcp_client import MCPClient
    from app.services.zotero_client import ZoteroClient
    
    # Clear the singleton instances
    MCPClient._instance = None
    ZoteroClient._instance = None
    
    # Create a mock ZoteroClient instance
    mock_zotero_client = MagicMock()
    mock_zotero_client.get_citation.return_value = 'Doe, J. (2023). Reference Title. Journal Name, 1(1), 1-10.'
    
    # Create a mock MCPClient instance that uses the mock ZoteroClient
    mock_mcp_client = MagicMock()
    mock_mcp_client.get_zotero_citation.return_value = 'Doe, J. (2023). Reference Title. Journal Name, 1(1), 1-10.'
    
    # Replace the get_instance methods
    with patch('app.routes.scenarios.MCPClient.get_instance', return_value=mock_mcp_client):
        with patch('app.services.mcp_client.ZoteroClient.get_instance', return_value=mock_zotero_client):
            # Set environment variable for testing
            import os
            os.environ['TESTING'] = 'true'
            
            # Send request
            response = client.get(f'/scenarios/{scenario.id}/references/ref1/citation?style=apa')
            
            # Verify response
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['citation'] == 'Doe, J. (2023). Reference Title. Journal Name, 1(1), 1-10.'
            
            # Verify the mock was called correctly
            mock_mcp_client.get_zotero_citation.assert_called_once_with('ref1', 'apa')
            
            # Clean up
            del os.environ['TESTING']
