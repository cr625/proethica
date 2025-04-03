#!/usr/bin/env python
"""
Implementation script for unified entity triples approach.
This script demonstrates how to extend the RDF triple model to handle
events, actions, resources, and other entity types beyond characters.
"""

import os
import sys
import json
from datetime import datetime
from pprint import pprint
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.role import Role
from app.models.event import Event, Action
from app.models.triple import Triple
from app.services.rdf_service import RDFService, PROETHICA, ENG_ETHICS
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base

# Define additional namespaces for our RDF graph
PROETHICA_ACTION = Namespace("http://proethica.org/action/")
PROETHICA_EVENT = Namespace("http://proethica.org/event/")
PROETHICA_RESOURCE = Namespace("http://proethica.org/resource/")
NSPE = Namespace("http://proethica.org/ontology/engineering-ethics/nspe#")
IEEE = Namespace("http://proethica.org/ontology/engineering-ethics/ieee#")


class EntityTripleModel:
    """
    Unified entity triple model to replace the character-specific Triple model.
    This is not meant to be executed but to serve as a template for migration.
    """
    
    __tablename__ = 'entity_triples'
    
    id = Column(Integer, primary_key=True)
    subject = Column(String(255), nullable=False, index=True)  # Entity URI
    predicate = Column(String(255), nullable=False, index=True)  # Property URI
    object_literal = Column(Text)  # Value as string when is_literal=True
    object_uri = Column(String(255))  # Value as URI when is_literal=False
    is_literal = Column(Boolean, nullable=False)  # Whether object is a literal or URI
    graph = Column(String(255), index=True)  # Named graph (e.g., scenario ID)
    
    # Vector embeddings for semantic similarity searches
    subject_embedding = Column(ARRAY(db.Float), nullable=True)
    predicate_embedding = Column(ARRAY(db.Float), nullable=True)
    object_embedding = Column(ARRAY(db.Float), nullable=True)
    
    # Metadata and timestamps
    triple_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Polymorphic entity reference
    entity_type = Column(String(50), nullable=False, index=True)  # 'character', 'action', 'event', 'resource'
    entity_id = Column(Integer, nullable=False, index=True)  # ID in respective entity table
    scenario_id = Column(Integer, ForeignKey('scenarios.id', ondelete='CASCADE'), nullable=True)
    
    # Indexes
    # CREATE INDEX idx_entity ON entity_triples (entity_type, entity_id);
    # CREATE INDEX idx_subject ON entity_triples (subject);
    # CREATE INDEX idx_predicate ON entity_triples (predicate);


class ExtendedRDFService:
    """
    Extended RDF service for handling multiple entity types.
    This builds on the existing RDFService but adds support for events, actions, etc.
    """
    
    def __init__(self):
        # Initialize with base RDFService functionality
        self.base_service = RDFService()
        self.namespaces = self.base_service.get_namespaces()
        
        # Add additional namespaces
        self.namespaces['action'] = PROETHICA_ACTION
        self.namespaces['event'] = PROETHICA_EVENT
        self.namespaces['resource'] = PROETHICA_RESOURCE
        self.namespaces['nspe'] = NSPE
        self.namespaces['ieee'] = IEEE
    
    def add_entity_triple(self, subject, predicate, obj, is_literal=True, 
                         graph=None, entity_type=None, entity_id=None, 
                         scenario_id=None, embeddings=None):
        """
        Add a new triple to the store with entity information.
        This method would be implemented once the entity_triples table is created.
        """
        # In a real implementation, this would create a new EntityTriple record
        print(f"Adding triple: {subject} {predicate} {obj}")
        print(f"  Entity: {entity_type} (ID: {entity_id})")
        
        # For demo purposes, use the existing Triple model
        # In production, you would create a new EntityTriple model
        triple = Triple(
            subject=subject,
            predicate=predicate,
            object_literal=obj if is_literal else None,
            object_uri=obj if not is_literal else None,
            is_literal=is_literal,
            graph=graph,
            triple_metadata={'entity_type': entity_type, 'entity_id': entity_id},
            scenario_id=scenario_id
        )
        
        # If this is a character, set the character_id for backward compatibility
        if entity_type == 'character':
            triple.character_id = entity_id
            
        # Don't actually add to the database in this demo
        # db.session.add(triple)
        # db.session.flush()
        
        return triple
    
    def generate_event_uri(self, event):
        """Generate a unique URI for an event."""
        return f"{PROETHICA_EVENT}{event.id}"
    
    def generate_action_uri(self, action):
        """Generate a unique URI for an action."""
        return f"{PROETHICA_ACTION}{action.id}"
    
    def generate_resource_uri(self, resource):
        """Generate a unique URI for a resource."""
        return f"{PROETHICA_RESOURCE}{resource.id}"
    
    def action_to_triples(self, action):
        """
        Convert an Action object to RDF triples.
        Similar to character_to_triples but for actions.
        """
        triples = []
        
        # Generate URI for the action
        action_uri = self.generate_action_uri(action)
        action_uri_str = str(action_uri)
        
        # Graph identifier (scenario ID)
        graph = f"scenario_{action.scenario_id}"
        
        # Add basic action information
        triples.append(self.add_entity_triple(
            action_uri_str, 
            str(RDF.type), 
            str(PROETHICA.Action), 
            is_literal=False,
            graph=graph,
            entity_type='action',
            entity_id=action.id,
            scenario_id=action.scenario_id
        ))
        
        # Add name/label
        triples.append(self.add_entity_triple(
            action_uri_str,
            str(RDFS.label),
            action.name,
            is_literal=True,
            graph=graph,
            entity_type='action',
            entity_id=action.id,
            scenario_id=action.scenario_id
        ))
        
        # Add description if available
        if action.description:
            triples.append(self.add_entity_triple(
                action_uri_str,
                str(RDFS.comment),
                action.description,
                is_literal=True,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            ))
        
        # Add character relationship if available
        if action.character_id:
            character_uri = self.base_service.generate_character_uri(
                Character.query.get(action.character_id).name, 
                action.scenario_id
            )
            triples.append(self.add_entity_triple(
                action_uri_str,
                str(PROETHICA.performedBy),
                str(character_uri),
                is_literal=False,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            ))
            
            # Add the reverse relationship
            triples.append(self.add_entity_triple(
                str(character_uri),
                str(PROETHICA.performs),
                action_uri_str,
                is_literal=False,
                graph=graph,
                entity_type='character',
                entity_id=action.character_id,
                scenario_id=action.scenario_id
            ))
        
        # Add action time if available
        if action.action_time:
            triples.append(self.add_entity_triple(
                action_uri_str,
                str(PROETHICA.hasActionTime),
                action.action_time.isoformat(),
                is_literal=True,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            ))
        
        # Add parameters if available
        if action.parameters:
            for key, value in action.parameters.items():
                # Create predicate URI based on parameter name
                predicate = PROETHICA[f"hasParameter_{key}"]
                
                # Add parameter triple
                triples.append(self.add_entity_triple(
                    action_uri_str,
                    str(predicate),
                    str(value),
                    is_literal=True,
                    graph=graph,
                    entity_type='action',
                    entity_id=action.id,
                    scenario_id=action.scenario_id
                ))
        
        # For decisions, add special triples
        if action.is_decision:
            # Add decision type
            triples.append(self.add_entity_triple(
                action_uri_str,
                str(RDF.type),
                str(PROETHICA.Decision),
                is_literal=False,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            ))
            
            # Add options
            if action.options:
                for i, option in enumerate(action.options):
                    option_value = option
                    if isinstance(option, dict):
                        option_value = json.dumps(option)
                    
                    triples.append(self.add_entity_triple(
                        action_uri_str,
                        str(PROETHICA.hasOption),
                        option_value,
                        is_literal=True,
                        graph=graph,
                        entity_type='action',
                        entity_id=action.id,
                        scenario_id=action.scenario_id
                    ))
            
            # Add selected option if available
            if action.selected_option:
                triples.append(self.add_entity_triple(
                    action_uri_str,
                    str(PROETHICA.selectedOption),
                    action.selected_option,
                    is_literal=True,
                    graph=graph,
                    entity_type='action',
                    entity_id=action.id,
                    scenario_id=action.scenario_id
                ))
        
        # Add ontology connection if available
        if action.ontology_uri:
            triples.append(self.add_entity_triple(
                action_uri_str,
                str(PROETHICA.hasOntologyReference),
                action.ontology_uri,
                is_literal=False,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            ))
        
        return triples
    
    def event_to_triples(self, event):
        """
        Convert an Event object to RDF triples.
        """
        triples = []
        
        # Generate URI for the event
        event_uri = self.generate_event_uri(event)
        event_uri_str = str(event_uri)
        
        # Graph identifier (scenario ID)
        graph = f"scenario_{event.scenario_id}"
        
        # Add basic event information
        triples.append(self.add_entity_triple(
            event_uri_str, 
            str(RDF.type), 
            str(PROETHICA.Event), 
            is_literal=False,
            graph=graph,
            entity_type='event',
            entity_id=event.id,
            scenario_id=event.scenario_id
        ))
        
        # Add description as label if available
        if event.description:
            triples.append(self.add_entity_triple(
                event_uri_str,
                str(RDFS.label),
                event.description,
                is_literal=True,
                graph=graph,
                entity_type='event',
                entity_id=event.id,
                scenario_id=event.scenario_id
            ))
        
        # Add event time if available
        if event.event_time:
            triples.append(self.add_entity_triple(
                event_uri_str,
                str(PROETHICA.hasEventTime),
                event.event_time.isoformat(),
                is_literal=True,
                graph=graph,
                entity_type='event',
                entity_id=event.id,
                scenario_id=event.scenario_id
            ))
        
        # Add character relationship if available
        if event.character_id:
            character_uri = self.base_service.generate_character_uri(
                Character.query.get(event.character_id).name, 
                event.scenario_id
            )
            triples.append(self.add_entity_triple(
                event_uri_str,
                str(PROETHICA.hasCharacter),
                str(character_uri),
                is_literal=False,
                graph=graph,
                entity_type='event',
                entity_id=event.id,
                scenario_id=event.scenario_id
            ))
        
        # Add action relationship if available
        if event.action_id:
            action_uri = self.generate_action_uri(Action.query.get(event.action_id))
            
            triples.append(self.add_entity_triple(
                event_uri_str,
                str(PROETHICA.generatedBy),
                str(action_uri),
                is_literal=False,
                graph=graph,
                entity_type='event',
                entity_id=event.id,
                scenario_id=event.scenario_id
            ))
            
            # Add the reverse relationship
            triples.append(self.add_entity_triple(
                str(action_uri),
                str(PROETHICA.generates),
                event_uri_str,
                is_literal=False,
                graph=graph,
                entity_type='action',
                entity_id=event.action_id,
                scenario_id=event.scenario_id
            ))
        
        # Add parameters if available
        if event.parameters:
            for key, value in event.parameters.items():
                # Create predicate URI based on parameter name
                predicate = PROETHICA[f"hasParameter_{key}"]
                
                # Add parameter triple
                triples.append(self.add_entity_triple(
                    event_uri_str,
                    str(predicate),
                    str(value),
                    is_literal=True,
                    graph=graph,
                    entity_type='event',
                    entity_id=event.id,
                    scenario_id=event.scenario_id
                ))
        
        return triples
    
    def entity_to_triples(self, entity, entity_type):
        """
        Generic method to convert any entity to triples.
        This delegates to specific methods based on entity type.
        """
        if entity_type == 'character':
            return self.base_service.character_to_triples(entity, commit=False)
        elif entity_type == 'action':
            return self.action_to_triples(entity)
        elif entity_type == 'event':
            return self.event_to_triples(entity)
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")
    
    def find_related_entities(self, entity_id, entity_type, relationship=None, target_type=None, scenario_id=None):
        """
        Find entities related to the given entity through a specific relationship.
        
        Args:
            entity_id: ID of the source entity
            entity_type: Type of the source entity ('character', 'action', 'event', etc.)
            relationship: Optional URI of the relationship to follow (predicate)
            target_type: Optional type of target entities to filter by
            scenario_id: Optional scenario ID to filter by
            
        Returns:
            List of related entities (as dicts with subject, predicate, object)
        """
        print(f"Finding {target_type or 'all'} entities related to {entity_type} {entity_id}")
        print(f"  Relationship: {relationship or 'any'}")
        print(f"  Scenario: {scenario_id or 'any'}")
        
        # In real implementation, this would query the entity_triples table
        # using recursive CTEs or similar techniques
        
        # For demo, return a mock result
        results = []
        
        # Create some example related entities for demonstration
        if entity_type == 'character':
            # Character performs actions
            results.append({
                'subject': f"http://proethica.org/character/{entity_id}",
                'predicate': str(PROETHICA.performs),
                'object': f"http://proethica.org/action/42",
                'entity_type': 'action',
                'entity_id': 42
            })
            
        elif entity_type == 'action':
            # Action generates events
            results.append({
                'subject': f"http://proethica.org/action/{entity_id}",
                'predicate': str(PROETHICA.generates),
                'object': f"http://proethica.org/event/55",
                'entity_type': 'event',
                'entity_id': 55
            })
            
            # Action performed by character
            results.append({
                'subject': f"http://proethica.org/action/{entity_id}",
                'predicate': str(PROETHICA.performedBy),
                'object': f"http://proethica.org/character/33",
                'entity_type': 'character',
                'entity_id': 33
            })
            
        elif entity_type == 'event':
            # Event generated by action
            results.append({
                'subject': f"http://proethica.org/event/{entity_id}",
                'predicate': str(PROETHICA.generatedBy),
                'object': f"http://proethica.org/action/77",
                'entity_type': 'action',
                'entity_id': 77
            })
            
        return results
    
    def execute_graph_query(self, query):
        """
        Execute a graph query against the triple store.
        This is a simplified implementation for demonstration purposes.
        
        Args:
            query: A string containing a SPARQL-like query
            
        Returns:
            Query results as a list of dictionaries
        """
        print(f"Executing graph query: {query}")
        
        # In real implementation, this would parse the query and execute against the database
        # For demo, we'll just return mock results for specific query patterns
        
        if "professional engineer" in query.lower():
            return [{
                'character': {
                    'uri': 'http://proethica.org/character/20_jane_smith',
                    'name': 'Jane Smith',
                    'id': 33
                },
                'role': {
                    'uri': 'http://proethica.org/ontology/engineering-ethics#ProfessionalEngineer',
                    'name': 'ProfessionalEngineer',
                    'id': 5
                }
            }]
            
        elif "ethical decision" in query.lower():
            return [{
                'decision': {
                    'uri': 'http://proethica.org/action/42',
                    'label': 'Bridge Safety Reporting Decision',
                    'id': 42
                },
                'principle': {
                    'uri': 'http://proethica.org/ontology/engineering-ethics/nspe#PublicSafetyPriority',
                    'label': 'Hold paramount the safety, health, and welfare of the public',
                    'id': None
                },
                'character': {
                    'uri': 'http://proethica.org/character/20_jane_smith',
                    'name': 'Jane Smith',
                    'id': 33
                }
            }]
            
        # Default empty result
        return []


def demo_action_to_triples():
    """Demonstrate converting actions to triples."""
    print("\n=== Demonstrating Action to Triples Conversion ===")
    
    # Create a mock action object
    class MockAction:
        def __init__(self):
            self.id = 42
            self.name = "Bridge Safety Reporting Decision"
            self.description = "Decision on whether to report safety concerns about the bridge foundation"
            self.scenario_id = 20
            self.character_id = 33
            self.action_time = datetime.now()
            self.parameters = {
                "importance": "high",
                "impact": "public safety",
                "urgency": "immediate"
            }
            self.is_decision = True
            self.options = [
                {"id": "option1", "text": "Report safety concerns immediately"},
                {"id": "option2", "text": "Conduct further tests before reporting"},
                {"id": "option3", "text": "Discuss with supervisor first"}
            ]
            self.selected_option = "option1"
            self.ontology_uri = "http://proethica.org/ontology/engineering-ethics/nspe#PublicSafetyPriority"
    
    # Create service and convert action to triples
    service = ExtendedRDFService()
    action = MockAction()
    triples = service.action_to_triples(action)
    
    print(f"Generated {len(triples)} triples for action")
    
    # Future database migration would be:
    """
    -- Create entity_triples table
    CREATE TABLE entity_triples (
        id SERIAL PRIMARY KEY,
        subject VARCHAR(255) NOT NULL,
        predicate VARCHAR(255) NOT NULL,
        object_literal TEXT,
        object_uri VARCHAR(255),
        is_literal BOOLEAN NOT NULL,
        graph VARCHAR(255),
        subject_embedding VECTOR(384),
        predicate_embedding VECTOR(384),
        object_embedding VECTOR(384),
        triple_metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        entity_type VARCHAR(50) NOT NULL,
        entity_id INTEGER NOT NULL,
        scenario_id INTEGER REFERENCES scenarios(id) ON DELETE CASCADE,
        INDEX idx_entity (entity_type, entity_id),
        INDEX idx_subject (subject),
        INDEX idx_predicate (predicate),
        INDEX idx_graph (graph)
    );
    
    -- Migrate existing character triples
    INSERT INTO entity_triples (
        subject, predicate, object_literal, object_uri, is_literal,
        graph, subject_embedding, predicate_embedding, object_embedding,
        triple_metadata, created_at, updated_at, entity_type, entity_id, scenario_id
    )
    SELECT
        subject, predicate, object_literal, object_uri, is_literal,
        graph, subject_embedding, predicate_embedding, object_embedding,
        triple_metadata, created_at, updated_at, 'character', character_id, scenario_id
    FROM character_triples
    WHERE character_id IS NOT NULL;
    """


def demo_event_to_triples():
    """Demonstrate converting events to triples."""
    print("\n=== Demonstrating Event to Triples Conversion ===")
    
    # Create a mock event object
    class MockEvent:
        def __init__(self):
            self.id = 55
            self.scenario_id = 20
            self.character_id = 33
            self.action_id = 42
            self.event_time = datetime.now()
            self.description = "Bridge foundation safety concerns reported to authorities"
            self.parameters = {
                "location": "north pier",
                "severity": "critical",
                "response_time": "4 hours"
            }
    
    # Create service and convert event to triples
    service = ExtendedRDFService()
    event = MockEvent()
    triples = service.event_to_triples(event)
    
    print(f"Generated {len(triples)} triples for event")


def demo_graph_queries():
    """Demonstrate graph queries across entity types."""
    print("\n=== Demonstrating Cross-Entity Graph Queries ===")
    
    service = ExtendedRDFService()
    
    # Find actions performed by a character
    print("\n1. Finding actions performed by character ID 33:")
    results = service.find_related_entities(
        entity_id=33, 
        entity_type='character',
        relationship=str(PROETHICA.performs),
        target_type='action'
    )
    for result in results:
        print(f"  {result['subject']} {result['predicate']} {result['object']}")
    
    # Find events generated by an action
    print("\n2. Finding events generated by action ID 42:")
    results = service.find_related_entities(
        entity_id=42, 
        entity_type='action',
        relationship=str(PROETHICA.generates),
        target_type='event'
    )
    for result in results:
        print(f"  {result['subject']} {result['predicate']} {result['object']}")
    
    # Execute a SPARQL-like query
    print("\n3. Finding ethical decisions made by professional engineers:")
    query = """
    ?decision rdf:type proethica:Decision ;
             proethica:invokes ?principle ;
             proethica:performedBy ?character .
    ?character proethica:hasRole eng:ProfessionalEngineer .
    """
    results = service.execute_graph_query(query)
    for result in results:
        print(f"  Decision: {result['decision']['label']}")
        print(f"  Character: {result['character']['name']}")
        print(f"  Principle: {result['principle']['label']}")


def main():
    """Run the entity triples implementation demo."""
    print("=== Entity Triples Implementation Demo ===")
    print("""
This script demonstrates how to implement a unified entity triples approach
for representing characters, actions, events, and other entities as RDF triples.

The key components are:
1. EntityTripleModel - A unified model for all entity types
2. ExtendedRDFService - Service that handles conversion of different entity types

Implementation steps:
1. Create the entity_triples table in the database
2. Migrate existing character triples to the new table
3. Implement conversion methods for each entity type
4. Update the query methods to work with the unified table
""")
    
    # Demo the action to triples conversion
    demo_action_to_triples()
    
    # Demo the event to triples conversion
    demo_event_to_triples()
    
    # Demo graph queries
    demo_graph_queries()
    
    print("\n=== Implementation Demo Completed ===")
    print("""
To implement this in the actual application:

1. Create a migration script to create the entity_triples table
2. Extend RDFService with the demonstrated methods
3. Update the entity models to include triple conversion methods
4. Create an EntityGraphService for complex graph queries

This implementation maintains the pgvector capabilities while adding
comprehensive graph support for all entity types.
""")


if __name__ == "__main__":
    main()
