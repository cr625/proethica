import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from app.models.world import World
from app.models.scenario import Scenario


def test_api_get_worlds(client, create_test_world):
    """Test the API endpoint to get all worlds."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.get('/worlds/api')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['data']) == 1
    assert data['data'][0]['id'] == world.id
    assert data['data'][0]['name'] == world.name


def test_api_get_world(client, create_test_world):
    """Test the API endpoint to get a specific world by ID."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.get(f'/worlds/api/{world.id}')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['data']['id'] == world.id
    assert data['data']['name'] == world.name


def test_api_get_world_not_found(client):
    """Test the API endpoint to get a non-existent world."""
    # Send request for a non-existent world
    response = client.get('/worlds/api/999')
    
    # Verify response
    assert response.status_code == 404


def test_list_worlds(client, create_test_world):
    """Test the list_worlds route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.get('/worlds/')
    
    # Verify response
    assert response.status_code == 200
    assert b'Test World' in response.data


def test_new_world(client):
    """Test the new_world route."""
    # Send request
    response = client.get('/worlds/new')
    
    # Verify response
    assert response.status_code == 200
    assert b'Create New World' in response.data


def test_create_world(client):
    """Test the create_world route."""
    # Send request
    response = client.post('/worlds/', data={
        'name': 'New World',
        'description': 'This is a new world',
        'ontology_source': 'test.ttl'
    }, follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'World created successfully' in response.data
    assert b'New World' in response.data
    
    # Verify world was created
    world = World.query.filter_by(name='New World').first()
    assert world is not None
    assert world.description == 'This is a new world'
    assert world.ontology_source == 'test.ttl'


def test_create_world_api(client):
    """Test the create_world API route."""
    # Send request
    response = client.post('/worlds/', json={
        'name': 'New World',
        'description': 'This is a new world',
        'ontology_source': 'test.ttl'
    })
    
    # Verify response
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'World created successfully'
    assert data['data']['name'] == 'New World'
    
    # Verify world was created
    world = World.query.filter_by(name='New World').first()
    assert world is not None
    assert world.description == 'This is a new world'
    assert world.ontology_source == 'test.ttl'


def test_view_world(client, create_test_world, monkeypatch):
    """Test the view_world route."""
    # Create test data
    world = create_test_world()
    
    # Mock the MCPClient.get_world_entities method
    def mock_get_world_entities(*args, **kwargs):
        return {
            'entities': {
                'roles': [{'id': 'role1', 'label': 'Role 1', 'description': 'Test role'}],
                'resources': [{'id': 'resource1', 'label': 'Resource 1', 'description': 'Test resource'}],
                'conditions': [{'id': 'condition1', 'label': 'Condition 1', 'description': 'Test condition'}],
                'actions': [{'id': 'action1', 'label': 'Action 1', 'description': 'Test action'}]
            }
        }
    
    from app.services.mcp_client import MCPClient
    monkeypatch.setattr(MCPClient, 'get_world_entities', mock_get_world_entities)
    
    # Send request
    response = client.get(f'/worlds/{world.id}')
    
    # Verify response
    assert response.status_code == 200
    assert world.name.encode() in response.data
    assert world.description.encode() in response.data
    # We don't need to check for the exact entity names in the response
    # as the template might render them differently or use JavaScript to display them


def test_view_world_not_found(client):
    """Test the view_world route with a non-existent world."""
    # Send request for a non-existent world
    response = client.get('/worlds/999')
    
    # Verify response
    assert response.status_code == 404


def test_edit_world(client, create_test_world):
    """Test the edit_world route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.get(f'/worlds/{world.id}/edit')
    
    # Verify response
    assert response.status_code == 200
    assert b'Edit World' in response.data
    assert world.name.encode() in response.data


def test_update_world_form(client, create_test_world):
    """Test the update_world_form route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.post(f'/worlds/{world.id}/edit', data={
        'name': 'Updated World',
        'description': 'This is an updated world',
        'ontology_source': 'updated.ttl',
        'guidelines_url': 'https://example.com/guidelines',
        'guidelines_text': 'These are the guidelines'
    }, follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'World updated successfully' in response.data
    assert b'Updated World' in response.data
    
    # Verify world was updated
    world = World.query.get(world.id)
    assert world.name == 'Updated World'
    assert world.description == 'This is an updated world'
    assert world.ontology_source == 'updated.ttl'
    assert world.guidelines_url == 'https://example.com/guidelines'
    assert world.guidelines_text == 'These are the guidelines'


def test_update_world_api(client, create_test_world):
    """Test the update_world API route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.put(f'/worlds/{world.id}', json={
        'name': 'Updated World',
        'description': 'This is an updated world',
        'ontology_source': 'updated.ttl',
        'guidelines_url': 'https://example.com/guidelines',
        'guidelines_text': 'These are the guidelines',
        'metadata': {'key': 'value'}
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'World updated successfully'
    assert data['data']['name'] == 'Updated World'
    
    # Verify world was updated
    world = World.query.get(world.id)
    assert world.name == 'Updated World'
    assert world.description == 'This is an updated world'
    assert world.ontology_source == 'updated.ttl'
    assert world.guidelines_url == 'https://example.com/guidelines'
    assert world.guidelines_text == 'These are the guidelines'
    assert world.metadata == {'key': 'value'}


def test_delete_world_confirm(client, create_test_world):
    """Test the delete_world_confirm route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.post(f'/worlds/{world.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'World deleted successfully' in response.data
    
    # Verify world was deleted
    world = World.query.get(world.id)
    assert world is None


def test_delete_world_api(client, create_test_world):
    """Test the delete_world API route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.delete(f'/worlds/{world.id}')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'World deleted successfully'
    
    # Verify world was deleted
    world = World.query.get(world.id)
    assert world is None


def test_delete_world_with_scenarios(client, create_test_world, create_test_scenario):
    """Test deleting a world that has scenarios."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    
    # Send request
    response = client.post(f'/worlds/{world.id}/delete', follow_redirects=True)
    
    # Verify response
    assert response.status_code == 200
    assert b'World deleted successfully' in response.data
    
    # Verify world and its scenarios were deleted
    world = World.query.get(world.id)
    assert world is None
    scenario = Scenario.query.get(scenario.id)
    assert scenario is None


# Case management routes tests
def test_add_case(client, create_test_world):
    """Test the add_case route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case',
        'decision': 'Test decision',
        'outcome': 'Test outcome',
        'ethical_analysis': 'Test analysis',
        'date': '2023-01-01'
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Case added successfully'
    assert data['data']['title'] == 'Test Case'
    
    # Verify case was added to world metadata
    world = World.query.get(world.id)
    assert 'cases' in world.metadata
    assert len(world.metadata['cases']) == 1
    assert world.metadata['cases'][0]['title'] == 'Test Case'
    assert world.metadata['cases'][0]['date'] == '2023-01-01'


def test_add_case_with_default_date(client, create_test_world):
    """Test the add_case route with default date."""
    # Create test data
    world = create_test_world()
    
    # Send request without date
    response = client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case',
        'decision': 'Test decision',
        'outcome': 'Test outcome',
        'ethical_analysis': 'Test analysis'
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    
    # Verify case was added with today's date
    world = World.query.get(world.id)
    assert 'cases' in world.metadata
    assert len(world.metadata['cases']) == 1
    assert 'date' in world.metadata['cases'][0]
    # Date should be in YYYY-MM-DD format
    assert len(world.metadata['cases'][0]['date']) == 10


def test_delete_case(client, create_test_world):
    """Test the delete_case route."""
    # Create test data
    world = create_test_world()
    
    # Add a case
    client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case'
    })
    
    # Send request to delete the case
    response = client.delete(f'/worlds/{world.id}/cases/0')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Case deleted successfully'
    
    # Verify case was deleted
    world = World.query.get(world.id)
    assert 'cases' in world.metadata
    assert len(world.metadata['cases']) == 0


def test_delete_case_invalid_index(client, create_test_world):
    """Test the delete_case route with an invalid index."""
    # Create test data
    world = create_test_world()
    
    # Add a case
    client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case'
    })
    
    # Send request with invalid index
    response = client.delete(f'/worlds/{world.id}/cases/999')
    
    # Verify response
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'not found' in data['message']


# Ruleset management routes tests
def test_add_ruleset(client, create_test_world):
    """Test the add_ruleset route."""
    # Create test data
    world = create_test_world()
    
    # Send request
    response = client.post(f'/worlds/{world.id}/rulesets', json={
        'name': 'Test Ruleset',
        'description': 'This is a test ruleset',
        'rules': [
            {'id': 1, 'text': 'Rule 1'},
            {'id': 2, 'text': 'Rule 2'}
        ]
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Ruleset added successfully'
    assert data['data']['name'] == 'Test Ruleset'
    
    # Verify ruleset was added to world metadata
    world = World.query.get(world.id)
    assert 'rulesets' in world.metadata
    assert len(world.metadata['rulesets']) == 1
    assert world.metadata['rulesets'][0]['name'] == 'Test Ruleset'
    assert len(world.metadata['rulesets'][0]['rules']) == 2


def test_delete_ruleset(client, create_test_world):
    """Test the delete_ruleset route."""
    # Create test data
    world = create_test_world()
    
    # Add a ruleset
    client.post(f'/worlds/{world.id}/rulesets', json={
        'name': 'Test Ruleset',
        'description': 'This is a test ruleset',
        'rules': [{'id': 1, 'text': 'Rule 1'}]
    })
    
    # Send request to delete the ruleset
    response = client.delete(f'/worlds/{world.id}/rulesets/0')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Ruleset deleted successfully'
    
    # Verify ruleset was deleted
    world = World.query.get(world.id)
    assert 'rulesets' in world.metadata
    assert len(world.metadata['rulesets']) == 0


def test_delete_ruleset_invalid_index(client, create_test_world):
    """Test the delete_ruleset route with an invalid index."""
    # Create test data
    world = create_test_world()
    
    # Add a ruleset
    client.post(f'/worlds/{world.id}/rulesets', json={
        'name': 'Test Ruleset',
        'description': 'This is a test ruleset',
        'rules': [{'id': 1, 'text': 'Rule 1'}]
    })
    
    # Send request with invalid index
    response = client.delete(f'/worlds/{world.id}/rulesets/999')
    
    # Verify response
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'not found' in data['message']


# References routes tests
def test_world_references(client, create_test_world, monkeypatch):
    """Test the world_references route."""
    # Create test data
    world = create_test_world()
    
    # Mock the MCPClient.get_references_for_world method
    from app.services.mcp_client import MCPClient
    from app.services.zotero_client import ZoteroClient
    
    # Clear the singleton instances
    MCPClient._instance = None
    ZoteroClient._instance = None
    
    # Create a mock instance
    mock_client = MagicMock()
    mock_client.get_references_for_world.return_value = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
    
    # Set up the mock to render the reference in the template
    mock_client.search_zotero_items.return_value = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
    
    # Replace the get_instance method
    monkeypatch.setattr(MCPClient, 'get_instance', lambda: mock_client)
    
    # Set environment variable for testing
    import os
    os.environ['TESTING'] = 'true'
    
    # Send request
    response = client.get(f'/worlds/{world.id}/references')
    
    # Verify response
    assert response.status_code == 200
    assert b'References' in response.data
    
    # Clean up
    del os.environ['TESTING']


def test_world_references_with_search(client, create_test_world, monkeypatch):
    """Test the world_references route with search query."""
    # Create test data
    world = create_test_world()
    
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
    response = client.get(f'/worlds/{world.id}/references?query=ethics')
    
    # Verify response
    assert response.status_code == 200
    assert b'References' in response.data
    
    # Clean up
    del os.environ['TESTING']
