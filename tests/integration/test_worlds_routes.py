import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from app.models.world import World
from app.models.scenario import Scenario


def test_api_get_worlds(client, create_test_world):
    """Test the API endpoint to get all worlds."""
    world = create_test_world()
    response = client.get('/worlds/api')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['data']) == 1
    assert data['data'][0]['id'] == world.id
    assert data['data'][0]['name'] == world.name


def test_api_get_world(client, create_test_world):
    """Test the API endpoint to get a specific world by ID."""
    world = create_test_world()
    response = client.get(f'/worlds/api/{world.id}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['data']['id'] == world.id
    assert data['data']['name'] == world.name


def test_api_get_world_not_found(client):
    """Test the API endpoint to get a non-existent world."""
    response = client.get('/worlds/api/999')
    assert response.status_code == 404


def test_list_worlds(client, create_test_world):
    """Test the list_worlds route."""
    world = create_test_world()
    response = client.get('/worlds/')
    assert response.status_code == 200
    assert b'Test World' in response.data


def test_new_world(client):
    """Test the new_world route renders the creation form."""
    response = client.get('/worlds/new')
    assert response.status_code == 200
    assert b'Create New Domain' in response.data


def test_create_world(app, client):
    """Test the create_world route via form POST."""
    response = client.post('/worlds/', data={
        'name': 'New World',
        'description': 'This is a new world',
        'ontology_source': 'test.ttl'
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        world = World.query.filter_by(name='New World').first()
        assert world is not None
        assert world.description == 'This is a new world'


def test_create_world_api(app, client):
    """Test the create_world API route."""
    response = client.post('/worlds/', json={
        'name': 'New World',
        'description': 'This is a new world',
        'ontology_source': 'test.ttl'
    })
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'World created successfully'
    assert data['data']['name'] == 'New World'

    with app.app_context():
        world = World.query.filter_by(name='New World').first()
        assert world is not None
        assert world.description == 'This is a new world'


def test_view_world(client, create_test_world, monkeypatch):
    """Test the view_world route."""
    world = create_test_world()

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

    response = client.get(f'/worlds/{world.id}')
    assert response.status_code == 200
    assert world.name.encode() in response.data
    assert world.description.encode() in response.data


def test_view_world_not_found(client):
    """Test the view_world route with a non-existent world."""
    response = client.get('/worlds/999')
    assert response.status_code == 404


def test_edit_world(admin_client, create_test_world):
    """Test the edit_world route (requires login + can_edit permission)."""
    world = create_test_world()
    response = admin_client.get(f'/worlds/{world.id}/edit')
    assert response.status_code == 200
    assert b'Edit' in response.data
    assert world.name.encode() in response.data


def test_update_world_form(app, admin_client, create_test_world):
    """Test the update_world_form route."""
    world = create_test_world()
    response = admin_client.post(f'/worlds/{world.id}/edit', data={
        'name': 'Updated World',
        'description': 'This is an updated world',
        'ontology_source': 'updated.ttl',
        'guidelines_url': 'https://example.com/guidelines',
        'guidelines_text': 'These are the guidelines'
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        world = World.query.get(world.id)
        assert world.name == 'Updated World'
        assert world.description == 'This is an updated world'


def test_update_world_api(app, admin_client, create_test_world):
    """Test the update_world API route (PUT requires login + can_edit)."""
    world = create_test_world()
    response = admin_client.put(f'/worlds/{world.id}', json={
        'name': 'Updated World',
        'description': 'This is an updated world',
        'ontology_source': 'updated.ttl',
        'guidelines_url': 'https://example.com/guidelines',
        'guidelines_text': 'These are the guidelines',
        'metadata': {'key': 'value'}
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'World updated successfully'
    assert data['data']['name'] == 'Updated World'

    with app.app_context():
        world = World.query.get(world.id)
        assert world.name == 'Updated World'
        assert world.description == 'This is an updated world'


def test_delete_world_confirm(app, admin_client, create_test_world):
    """Test the delete_world_confirm route (form POST, requires can_delete)."""
    world = create_test_world()
    world_id = world.id
    response = admin_client.post(f'/worlds/{world_id}/delete', follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        world = World.query.get(world_id)
        assert world is None


def test_delete_world_api(app, admin_client, create_test_world):
    """Test the delete_world API route (DELETE requires login + can_delete)."""
    world = create_test_world()
    world_id = world.id
    response = admin_client.delete(f'/worlds/{world_id}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'World deleted successfully'

    with app.app_context():
        world = World.query.get(world_id)
        assert world is None


def test_delete_world_with_scenarios(app, admin_client, create_test_world, create_test_scenario):
    """Test deleting a world that has scenarios (requires can_delete)."""
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    world_id = world.id
    scenario_id = scenario.id

    response = admin_client.post(f'/worlds/{world_id}/delete', follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        assert World.query.get(world_id) is None
        assert Scenario.query.get(scenario_id) is None


# Case management routes tests
def test_add_case(client, create_test_world):
    """Test the add_case route."""
    world = create_test_world()
    response = client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case',
        'decision': 'Test decision',
        'outcome': 'Test outcome',
        'ethical_analysis': 'Test analysis',
        'date': '2023-01-01'
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Case added successfully'
    assert data['data']['title'] == 'Test Case'

    world = World.query.get(world.id)
    assert 'cases' in world.metadata
    assert len(world.metadata['cases']) == 1
    assert world.metadata['cases'][0]['title'] == 'Test Case'
    assert world.metadata['cases'][0]['date'] == '2023-01-01'


def test_add_case_with_default_date(client, create_test_world):
    """Test the add_case route with default date."""
    world = create_test_world()
    response = client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case',
        'decision': 'Test decision',
        'outcome': 'Test outcome',
        'ethical_analysis': 'Test analysis'
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True

    world = World.query.get(world.id)
    assert 'cases' in world.metadata
    assert len(world.metadata['cases']) == 1
    assert 'date' in world.metadata['cases'][0]
    assert len(world.metadata['cases'][0]['date']) == 10


def test_delete_case(client, create_test_world):
    """Test the delete_case route."""
    world = create_test_world()
    client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case'
    })
    response = client.delete(f'/worlds/{world.id}/cases/0')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Case deleted successfully'

    world = World.query.get(world.id)
    assert 'cases' in world.metadata
    assert len(world.metadata['cases']) == 0


def test_delete_case_invalid_index(client, create_test_world):
    """Test the delete_case route with an invalid index."""
    world = create_test_world()
    client.post(f'/worlds/{world.id}/cases', json={
        'title': 'Test Case',
        'description': 'This is a test case'
    })
    response = client.delete(f'/worlds/{world.id}/cases/999')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'not found' in data['message']


# Ruleset management routes tests
def test_add_ruleset(client, create_test_world):
    """Test the add_ruleset route."""
    world = create_test_world()
    response = client.post(f'/worlds/{world.id}/rulesets', json={
        'name': 'Test Ruleset',
        'description': 'This is a test ruleset',
        'rules': [
            {'id': 1, 'text': 'Rule 1'},
            {'id': 2, 'text': 'Rule 2'}
        ]
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Ruleset added successfully'
    assert data['data']['name'] == 'Test Ruleset'

    world = World.query.get(world.id)
    assert 'rulesets' in world.metadata
    assert len(world.metadata['rulesets']) == 1
    assert world.metadata['rulesets'][0]['name'] == 'Test Ruleset'
    assert len(world.metadata['rulesets'][0]['rules']) == 2


def test_delete_ruleset(client, create_test_world):
    """Test the delete_ruleset route."""
    world = create_test_world()
    client.post(f'/worlds/{world.id}/rulesets', json={
        'name': 'Test Ruleset',
        'description': 'This is a test ruleset',
        'rules': [{'id': 1, 'text': 'Rule 1'}]
    })
    response = client.delete(f'/worlds/{world.id}/rulesets/0')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['message'] == 'Ruleset deleted successfully'

    world = World.query.get(world.id)
    assert 'rulesets' in world.metadata
    assert len(world.metadata['rulesets']) == 0


def test_delete_ruleset_invalid_index(client, create_test_world):
    """Test the delete_ruleset route with an invalid index."""
    world = create_test_world()
    client.post(f'/worlds/{world.id}/rulesets', json={
        'name': 'Test Ruleset',
        'description': 'This is a test ruleset',
        'rules': [{'id': 1, 'text': 'Rule 1'}]
    })
    response = client.delete(f'/worlds/{world.id}/rulesets/999')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'not found' in data['message']


# References routes tests
def test_world_references(client, create_test_world, monkeypatch):
    """Test the world_references route."""
    world = create_test_world()

    from app.services.mcp_client import MCPClient
    from app.services.zotero_client import ZoteroClient

    MCPClient._instance = None
    ZoteroClient._instance = None

    mock_client = MagicMock()
    mock_client.get_references_for_world.return_value = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]
    mock_client.search_zotero_items.return_value = [{'data': {'title': 'Reference 1', 'creators': [{'firstName': 'John', 'lastName': 'Doe'}]}, 'key': 'ref1'}]

    monkeypatch.setattr(MCPClient, 'get_instance', lambda: mock_client)

    import os
    os.environ['TESTING'] = 'true'

    response = client.get(f'/worlds/{world.id}/references')
    assert response.status_code == 200
    assert b'References' in response.data

    del os.environ['TESTING']


def test_world_references_with_search(client, create_test_world, monkeypatch):
    """Test the world_references route with search query."""
    world = create_test_world()

    from app.services.mcp_client import MCPClient
    from app.services.zotero_client import ZoteroClient

    MCPClient._instance = None
    ZoteroClient._instance = None

    mock_client = MagicMock()
    mock_client.search_zotero_items.return_value = [{'data': {'title': 'Search Result', 'creators': [{'firstName': 'Jane', 'lastName': 'Smith'}]}, 'key': 'ref2'}]

    monkeypatch.setattr(MCPClient, 'get_instance', lambda: mock_client)

    import os
    os.environ['TESTING'] = 'true'

    response = client.get(f'/worlds/{world.id}/references?query=ethics')
    assert response.status_code == 200
    assert b'References' in response.data

    del os.environ['TESTING']
