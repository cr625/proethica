"""
Tests for the MCP API routes.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_get_world_entities():
    """Mock the get_world_entities method."""
    with patch('app.routes.mcp_api.MCPClient.get_instance') as mock_get_instance:
        mock_client = MagicMock()
        mock_get_instance.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_get_entity():
    """Mock the get_entity method."""
    with patch('app.routes.mcp_api.MCPClient.get_instance') as mock_get_instance:
        mock_client = MagicMock()
        mock_get_instance.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_search_zotero():
    """Mock the search_zotero_items method."""
    with patch('app.routes.mcp_api.MCPClient.get_instance') as mock_get_instance:
        mock_client = MagicMock()
        mock_get_instance.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_get_citation():
    """Mock the get_zotero_citation method."""
    with patch('app.routes.mcp_api.MCPClient.get_instance') as mock_get_instance:
        mock_client = MagicMock()
        mock_get_instance.return_value = mock_client
        yield mock_client

def test_get_ontology_entities(client, mock_get_world_entities):
    """Test the get_ontology_entities route."""
    # Set up mock return value
    mock_get_world_entities.get_world_entities.return_value = {
        'entities': {
            'roles': [{'id': 'role1', 'label': 'Engineer'}],
            'conditions': [{'id': 'cond1', 'label': 'Conflict of Interest'}]
        }
    }
    
    # Send request
    response = client.get('/api/ontology/world/1/entities')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'entities' in data
    assert 'roles' in data['entities']
    
    # Verify mock was called with correct arguments
    mock_get_world_entities.get_world_entities.assert_called_once_with('1')

def test_get_ontology_entities_by_type(client, mock_get_world_entities):
    """Test the get_ontology_entities_by_type route."""
    # Set up mock return value
    mock_get_world_entities.get_world_entities.return_value = {
        'entities': {
            'roles': [
                {'id': 'role1', 'label': 'Engineer'},
                {'id': 'role2', 'label': 'Manager'}
            ]
        }
    }
    
    # Send request
    response = client.get('/api/ontology/world/1/entities/roles')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'entities' in data
    assert len(data['entities']) == 2
    
    # Verify mock was called with correct arguments
    mock_get_world_entities.get_world_entities.assert_called_once_with('1', entity_type='roles')

def test_get_ontology_entity(client, mock_get_entity):
    """Test the get_ontology_entity route."""
    # Set up mock return value
    mock_get_entity.get_entity.return_value = {
        'id': 'role1',
        'label': 'Engineer',
        'description': 'Professional engineer'
    }
    
    # Send request
    response = client.get('/api/ontology/entity/role1')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['entity']['id'] == 'role1'
    assert data['entity']['label'] == 'Engineer'
    
    # Verify mock was called with correct arguments
    mock_get_entity.get_entity.assert_called_once_with('role1')

def test_get_ontology_entity_not_found(client, mock_get_entity):
    """Test the get_ontology_entity route when entity is not found."""
    # Set up mock return value
    mock_get_entity.get_entity.return_value = None
    
    # Send request
    response = client.get('/api/ontology/entity/nonexistent')
    
    # Verify response
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert 'Entity not found' in data['message']

def test_search_zotero(client, mock_search_zotero):
    """Test the search_zotero route."""
    # Set up mock return value
    mock_results = [
        {
            'data': {
                'title': 'Engineering Ethics Article',
                'creators': [{'firstName': 'John', 'lastName': 'Doe'}]
            },
            'key': 'item1'
        }
    ]
    mock_search_zotero.search_zotero_items.return_value = mock_results
    
    # Send request
    response = client.get('/api/zotero/search?query=ethics')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'results' in data
    assert len(data['results']) == 1
    assert data['results'][0]['data']['title'] == 'Engineering Ethics Article'
    
    # Verify mock was called with correct arguments
    mock_search_zotero.search_zotero_items.assert_called_once_with('ethics')

def test_get_zotero_citation(client, mock_get_citation):
    """Test the get_zotero_citation route."""
    # Set up mock return value
    mock_get_citation.get_zotero_citation.return_value = 'Doe, J. (2023). Engineering Ethics Article.'
    
    # Send request
    response = client.get('/api/zotero/items/item1/citation?style=apa')
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['citation'] == 'Doe, J. (2023). Engineering Ethics Article.'
    
    # Verify mock was called with correct arguments
    mock_get_citation.get_zotero_citation.assert_called_once_with('item1', 'apa')
