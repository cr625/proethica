#!/usr/bin/env python
"""
Test script for temporal functionality in the RDF triple-based structure.

This script demonstrates how to use the TemporalContextService
to add temporal data to entity triples and perform temporal queries.
"""

import sys
import os
import datetime
from pprint import pprint

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService
from app.services.temporal_context_service import TemporalContextService
from app.models.scenario import Scenario
from app.models.event import Event, Action
from app.models.character import Character
from rdflib import Namespace

# Initialize Flask app
app = create_app()

# Define namespaces for testing
PROETHICA = Namespace("http://proethica.org/ontology/")
PROETHICA_INT = Namespace("http://proethica.org/ontology/intermediate#")
BFO = Namespace("http://purl.obolibrary.org/obo/")

def clear_test_data(scenario_id):
    """Clear any existing test data."""
    print(f"Clearing test data for scenario {scenario_id}...")
    
    # Delete entity triples for the scenario
    db.session.query(EntityTriple).filter_by(scenario_id=scenario_id).delete()
    
    # Delete events and actions for the scenario
    db.session.query(Event).filter_by(scenario_id=scenario_id).delete()
    db.session.query(Action).filter_by(scenario_id=scenario_id).delete()
    
    db.session.commit()
    print("Test data cleared.")

def create_test_timeline(scenario_id, character_id):
    """Create a test timeline with events, actions, and decisions."""
    print(f"Creating test timeline for scenario {scenario_id}...")
    
    # Create a sequence of actions and events
    timeline = []
    
    # Day 1: Initial actions and events
    base_time = datetime.datetime.now()
    
    # Event 1: Project Kickoff
    event1 = Event(
        scenario_id=scenario_id,
        character_id=character_id,
        event_time=base_time,
        description="Project kickoff meeting with stakeholders"
    )
    db.session.add(event1)
    db.session.flush()
    timeline.append(("event", event1, 0))
    
    # Action 1: Engineer reviews building plans
    action1 = Action(
        scenario_id=scenario_id,
        character_id=character_id,
        action_time=base_time + datetime.timedelta(hours=2),
        name="Review building plans",
        description="Engineer reviews detailed building plans"
    )
    db.session.add(action1)
    db.session.flush()
    timeline.append(("action", action1, 120))
    
    # Event 2: Potential safety issue discovered
    event2 = Event(
        scenario_id=scenario_id,
        character_id=character_id,
        event_time=base_time + datetime.timedelta(hours=5),
        description="Potential structural safety issue discovered"
    )
    db.session.add(event2)
    db.session.flush()
    timeline.append(("event", event2, 0))
    
    # Action 2: Engineer performs detailed analysis
    action2 = Action(
        scenario_id=scenario_id,
        character_id=character_id,
        action_time=base_time + datetime.timedelta(hours=8),
        name="Perform detailed analysis",
        description="Engineer performs detailed structural analysis"
    )
    db.session.add(action2)
    db.session.flush()
    timeline.append(("action", action2, 180))
    
    # Decision 1: Whether to report the issue
    decision1 = Action(
        scenario_id=scenario_id,
        character_id=character_id,
        action_time=base_time + datetime.timedelta(days=1),
        name="Decision on reporting safety issue",
        description="Engineer decides whether to report the safety issue",
        is_decision=True,
        options={
            "report": {
                "description": "Report the safety issue to authorities",
                "ethical_principles": ["integrity", "public_safety"]
            },
            "inform_client": {
                "description": "Inform the client but not authorities",
                "ethical_principles": ["confidentiality", "client_service"]
            },
            "keep_confidential": {
                "description": "Keep the issue confidential per contract",
                "ethical_principles": ["confidentiality", "contractual_obligation"]
            }
        },
        selected_option="report"
    )
    db.session.add(decision1)
    db.session.flush()
    timeline.append(("decision", decision1, 0))
    
    # Event 3: Meeting with client about the issue
    event3 = Event(
        scenario_id=scenario_id,
        character_id=character_id,
        event_time=base_time + datetime.timedelta(days=1, hours=4),
        description="Meeting with client about the safety issue"
    )
    db.session.add(event3)
    db.session.flush()
    timeline.append(("event", event3, 0))
    
    # Action 3: Engineer files report
    action3 = Action(
        scenario_id=scenario_id,
        character_id=character_id,
        action_time=base_time + datetime.timedelta(days=1, hours=6),
        name="File safety report",
        description="Engineer files official safety report with authorities"
    )
    db.session.add(action3)
    db.session.flush()
    timeline.append(("action", action3, 60))
    
    db.session.commit()
    print(f"Created {len(timeline)} timeline items.")
    return timeline

def convert_timeline_to_triples(timeline, scenario_id):
    """Convert timeline items to entity triples with temporal data."""
    print("Converting timeline to entity triples...")
    
    triple_service = EntityTripleService()
    temporal_service = TemporalContextService()
    
    # Create triples for each timeline item
    for item_type, item, duration in timeline:
        if item_type == "event":
            # Create triples for the event
            triples = triple_service.event_to_triples(item)
            
            # Add temporal data
            temporal_service.enhance_event_with_temporal_data(
                event_id=item.id,
                event_time=item.event_time,
                duration_minutes=duration if duration > 0 else None
            )
        else:  # action or decision
            # Create triples for the action/decision
            triples = triple_service.action_to_triples(item)
            
            # Add temporal data
            temporal_service.enhance_action_with_temporal_data(
                action_id=item.id,
                action_time=item.action_time,
                duration_minutes=duration if duration > 0 else None,
                is_decision=item.is_decision
            )
    
    # Create temporal relationships
    for i in range(len(timeline) - 1):
        current_type, current_item, _ = timeline[i]
        next_type, next_item, _ = timeline[i + 1]
        
        # Get triples for both items
        if current_type == "event":
            current_triples = temporal_service.triple_service.find_triples(
                entity_type="event", entity_id=current_item.id
            )
        else:
            current_triples = temporal_service.triple_service.find_triples(
                entity_type="action", entity_id=current_item.id
            )
            
        if next_type == "event":
            next_triples = temporal_service.triple_service.find_triples(
                entity_type="event", entity_id=next_item.id
            )
        else:
            next_triples = temporal_service.triple_service.find_triples(
                entity_type="action", entity_id=next_item.id
            )
        
        # Create relationship between first triples of each
        if current_triples and next_triples:
            temporal_service.create_temporal_relation(
                current_triples[0].id,
                next_triples[0].id,
                "precedes"
            )
    
    triple_count = db.session.query(EntityTriple).filter_by(scenario_id=scenario_id).count()
    print(f"Created {triple_count} entity triples with temporal data.")

def test_temporal_queries(scenario_id):
    """Test various temporal queries."""
    print("Testing temporal queries...")
    
    temporal_service = TemporalContextService()
    
    # 1. Query triples in a specific timeframe
    base_time = datetime.datetime.now()
    start_time = base_time + datetime.timedelta(hours=1)
    end_time = base_time + datetime.timedelta(hours=9)
    
    print(f"\n1. Triples valid between {start_time} and {end_time}:")
    triples = temporal_service.find_triples_in_timeframe(start_time, end_time, scenario_id=scenario_id)
    print(f"Found {len(triples)} triples within timeframe.")
    
    # 2. Get temporal sequence
    print("\n2. Temporal sequence of triples:")
    sequence = temporal_service.find_temporal_sequence(scenario_id)
    print(f"Found {len(sequence)} triples in temporal sequence.")
    
    # 3. Build timeline
    print("\n3. Complete timeline:")
    timeline = temporal_service.build_timeline(scenario_id)
    print(f"Timeline has {len(timeline['events'])} events, {len(timeline['actions'])} actions, and {len(timeline['decisions'])} decisions.")
    
    # 4. Generate context for Claude
    print("\n4. Generated context for Claude:")
    context = temporal_service.get_temporal_context_for_claude(scenario_id)
    print(context)

def main():
    """Main function to run the test."""
    # Use a Flask application context for all database operations
    with app.app_context():
        # Get scenario to use for testing
        scenario = Scenario.query.first()
        if not scenario:
            print("No scenarios found in the database. Please create a scenario first.")
            return
        
        print(f"Using scenario: {scenario.id} - {scenario.name}")
        
        # Get character for testing
        character = Character.query.filter_by(scenario_id=scenario.id).first()
        if not character:
            print("No characters found for this scenario. Please create a character first.")
            return
        
        print(f"Using character: {character.id} - {character.name}")
        
        # Clean up any existing test data
        clear_test_data(scenario.id)
        
        # Create test timeline
        timeline = create_test_timeline(scenario.id, character.id)
        
        # Convert timeline to triples with temporal data
        convert_timeline_to_triples(timeline, scenario.id)
        
        # Test temporal queries
        test_temporal_queries(scenario.id)
        
        print("\nTemporal functionality test completed successfully!")

if __name__ == "__main__":
    main()
