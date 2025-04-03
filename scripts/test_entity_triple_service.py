#!/usr/bin/env python
"""
Test script for the EntityTripleService.
This script demonstrates how to use the service with different entity types.
"""

import os
import sys
import json
from datetime import datetime
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.event import Event, Action
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService

def test_character_triples():
    """Test converting a character to triples and back."""
    print("\n=== Testing Character Triples ===")
    
    # Find a character to test with
    character = Character.query.first()
    if not character:
        print("No characters found for testing")
        return False
    
    print(f"Using character: {character.name} (ID: {character.id})")
    
    # Create EntityTripleService
    triple_service = EntityTripleService()
    
    # Convert character to triples
    print("\nConverting character to triples...")
    triples = triple_service.character_to_triples(character, commit=True)
    
    print(f"Created {len(triples)} triples for character")
    
    # Display the first few triples
    for i, triple in enumerate(triples[:5]):
        print(f"  {i+1}. {triple.subject} {triple.predicate} {triple.object_literal or triple.object_uri}")
        print(f"     (entity_type: {triple.entity_type}, entity_id: {triple.entity_id})")
    
    # Find triples for this character
    print("\nFinding triples for this character...")
    found_triples = triple_service.find_triples(entity_type='character', entity_id=character.id)
    
    print(f"Found {len(found_triples)} triples")
    
    return True

def test_event_triples():
    """Test converting an event to triples."""
    print("\n=== Testing Event Triples ===")
    
    # Find an event to test with
    event = Event.query.first()
    if not event:
        print("No events found for testing")
        return False
    
    print(f"Using event: '{event.description[:50]}...' (ID: {event.id})")
    
    # Create EntityTripleService
    triple_service = EntityTripleService()
    
    # Convert event to triples
    print("\nConverting event to triples...")
    triples = triple_service.event_to_triples(event, commit=True)
    
    print(f"Created {len(triples)} triples for event")
    
    # Display the first few triples
    for i, triple in enumerate(triples[:5]):
        print(f"  {i+1}. {triple.subject} {triple.predicate} {triple.object_literal or triple.object_uri}")
        print(f"     (entity_type: {triple.entity_type}, entity_id: {triple.entity_id})")
    
    # Find triples for this event
    print("\nFinding triples for this event...")
    found_triples = triple_service.find_triples(entity_type='event', entity_id=event.id)
    
    print(f"Found {len(found_triples)} triples")
    
    return True

def test_action_triples():
    """Test converting an action to triples."""
    print("\n=== Testing Action Triples ===")
    
    # Find an action to test with (preferably a decision)
    action = Action.query.filter_by(is_decision=True).first()
    if not action:
        action = Action.query.first()
    
    if not action:
        print("No actions found for testing")
        return False
    
    print(f"Using action: '{action.name or action.description[:50]}...' (ID: {action.id})")
    print(f"Is decision: {action.is_decision}")
    
    # Create EntityTripleService
    triple_service = EntityTripleService()
    
    # Convert action to triples
    print("\nConverting action to triples...")
    triples = triple_service.action_to_triples(action, commit=True)
    
    print(f"Created {len(triples)} triples for action")
    
    # Display the first few triples
    for i, triple in enumerate(triples[:5]):
        print(f"  {i+1}. {triple.subject} {triple.predicate} {triple.object_literal or triple.object_uri}")
        print(f"     (entity_type: {triple.entity_type}, entity_id: {triple.entity_id})")
    
    # Find triples for this action
    print("\nFinding triples for this action...")
    found_triples = triple_service.find_triples(entity_type='action', entity_id=action.id)
    
    print(f"Found {len(found_triples)} triples")
    
    return True

def test_sparql_like_queries():
    """Test SPARQL-like queries."""
    print("\n=== Testing SPARQL-like Queries ===")
    
    # Create EntityTripleService
    triple_service = EntityTripleService()
    
    # Test query: Find all characters that are professional engineers
    print("\n1. Finding professional engineers:")
    query = "?character <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://proethica.org/ontology/engineering-ethics#ProfessionalEngineer>"
    results = triple_service.sparql_like_query(query)
    
    print(f"Found {len(results)} results")
    for i, result in enumerate(results[:3]):
        print(f"  {i+1}. Subject: {result['subject']}")
        print(f"     Entity type: {result['entity_type']}, Entity ID: {result['entity_id']}")
    
    # Test query: Find all decisions
    print("\n2. Finding all decisions:")
    query = "?decision <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://proethica.org/ontology/Decision>"
    results = triple_service.sparql_like_query(query)
    
    print(f"Found {len(results)} results")
    for i, result in enumerate(results[:3]):
        print(f"  {i+1}. Subject: {result['subject']}")
        print(f"     Entity type: {result['entity_type']}, Entity ID: {result['entity_id']}")
    
    return True

def test_sync_entity():
    """Test synchronizing an entity with the triple store."""
    print("\n=== Testing Entity Synchronization ===")
    
    # Find a character to test with
    character = Character.query.first()
    if not character:
        print("No characters found for testing")
        return False
    
    print(f"Using character: {character.name} (ID: {character.id})")
    
    # Create EntityTripleService
    triple_service = EntityTripleService()
    
    # Count existing triples for this character
    existing_count = db.session.query(EntityTriple).filter_by(
        entity_type='character', 
        entity_id=character.id
    ).count()
    
    print(f"Character has {existing_count} existing triples")
    
    # Modify the character (simulate an update)
    if not character.attributes:
        character.attributes = {}
    
    test_value = f"test_value_{datetime.now().strftime('%H%M%S')}"
    character.attributes['test_attribute'] = test_value
    db.session.commit()
    
    print(f"Added test attribute to character: test_attribute = {test_value}")
    
    # Synchronize the character
    print("\nSynchronizing character with triple store...")
    triples = triple_service.sync_entity('character', character, commit=True)
    
    print(f"Created {len(triples)} triples for character")
    
    # Check if the new attribute was added as a triple
    print("\nChecking for the new attribute triple...")
    found_triples = triple_service.find_triples(
        entity_type='character', 
        entity_id=character.id,
        predicate=str(triple_service.namespaces['proethica']['test_attribute'])
    )
    
    if found_triples:
        print(f"✓ Found the new attribute triple: {found_triples[0].subject} {found_triples[0].predicate} {found_triples[0].object_literal}")
        return True
    else:
        print("✗ New attribute triple not found")
        return False

def main():
    """Run all tests."""
    app = create_app()
    
    with app.app_context():
        print("\n=== EntityTripleService Tests ===")
        
        # Run tests
        character_test = test_character_triples()
        event_test = test_event_triples()
        action_test = test_action_triples()
        query_test = test_sparql_like_queries()
        sync_test = test_sync_entity()
        
        # Print summary
        print("\n=== Test Results ===")
        print(f"Character triples test: {'✓ Passed' if character_test else '✗ Failed'}")
        print(f"Event triples test: {'✓ Passed' if event_test else '✗ Failed'}")
        print(f"Action triples test: {'✓ Passed' if action_test else '✗ Failed'}")
        print(f"SPARQL-like queries test: {'✓ Passed' if query_test else '✗ Failed'}")
        print(f"Entity synchronization test: {'✓ Passed' if sync_test else '✗ Failed'}")
        
        if character_test and event_test and action_test and query_test and sync_test:
            print("\n✓ All tests passed!")
        else:
            print("\n⚠ Some tests failed")

if __name__ == "__main__":
    main()
