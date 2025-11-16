import json
import pytest
from app.models.entity import Entity
from app.models.event import Event


def test_create_entity(client):
    """Test creating a new entity."""
    # Send request
    response = client.post('/entities', json={
        'name': 'Test Entity',
        'description': 'This is a test entity'
    })
    
    # Verify response
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'Entity created'
    assert data['entity']['name'] == 'Test Entity'
    
    # Verify entity was created
    entity = Entity.query.filter_by(name='Test Entity').first()
    assert entity is not None
    assert entity.description == 'This is a test entity'


def test_create_entity_missing_name(client):
    """Test creating an entity without a name."""
    # Send request without name
    response = client.post('/entities', json={
        'description': 'This is a test entity'
    })
    
    # Verify response
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_add_entity_to_event(client, create_test_world, create_test_scenario, create_test_event):
    """Test adding an entity to an event."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    event = create_test_event(scenario_id=scenario.id)
    
    # Create an entity
    entity_response = client.post('/entities', json={
        'name': 'Test Entity',
        'description': 'This is a test entity'
    })
    entity_data = json.loads(entity_response.data)
    entity_id = entity_data['entity']['id']
    
    # Add entity to event
    response = client.post(f'/events/{event.id}/entities', json={
        'entity_id': entity_id
    })
    
    # Verify response
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['message'] == 'Entity added to event'
    
    # Verify entity was added to event
    event = Event.query.get(event.id)
    assert len(event.entities) == 1
    assert event.entities[0].id == entity_id


def test_add_entity_to_nonexistent_event(client):
    """Test adding an entity to a non-existent event."""
    # Create an entity
    entity_response = client.post('/entities', json={
        'name': 'Test Entity',
        'description': 'This is a test entity'
    })
    entity_data = json.loads(entity_response.data)
    entity_id = entity_data['entity']['id']
    
    # Try to add entity to non-existent event
    response = client.post('/events/999/entities', json={
        'entity_id': entity_id
    })
    
    # Verify response
    assert response.status_code == 404


def test_add_nonexistent_entity_to_event(client, create_test_world, create_test_scenario, create_test_event):
    """Test adding a non-existent entity to an event."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    event = create_test_event(scenario_id=scenario.id)
    
    # Try to add non-existent entity to event
    response = client.post(f'/events/{event.id}/entities', json={
        'entity_id': 999
    })
    
    # Verify response
    assert response.status_code == 404


def test_add_entity_to_event_missing_entity_id(client, create_test_world, create_test_scenario, create_test_event):
    """Test adding an entity to an event without providing entity_id."""
    # Create test data
    world = create_test_world()
    scenario = create_test_scenario(world_id=world.id)
    event = create_test_event(scenario_id=scenario.id)
    
    # Try to add entity without entity_id
    response = client.post(f'/events/{event.id}/entities', json={})
    
    # Verify response
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
