#!/usr/bin/env python3
"""
Script to update events in the database to set their action_id fields.
"""

import sys
import os
from flask import Flask
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Event, Action, Scenario

app = create_app()

def update_events_for_scenario(scenario_id):
    """Update events for a specific scenario to set their action_id fields."""
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            print(f"Scenario {scenario_id} not found")
            return
        
        print(f"Updating events for scenario {scenario.id}: {scenario.name}")
        
        # Get all events for this scenario
        events = Event.query.filter_by(scenario_id=scenario_id).all()
        print(f"  Found {len(events)} events")
        
        # Get all actions for this scenario
        actions = Action.query.filter_by(scenario_id=scenario_id).all()
        print(f"  Found {len(actions)} actions")
        
        # Map actions to events based on description similarity
        for event in events:
            # Find the most similar action based on description
            best_match = None
            best_match_score = 0
            
            for action in actions:
                # Simple matching based on common words
                event_words = set(event.description.lower().split())
                action_words = set(action.description.lower().split())
                common_words = event_words.intersection(action_words)
                
                # Calculate similarity score
                score = len(common_words) / max(len(event_words), len(action_words))
                
                if score > best_match_score:
                    best_match_score = score
                    best_match = action
            
            # If we found a good match, update the event
            if best_match and best_match_score > 0.3:  # Threshold for a good match
                print(f"  Updating event {event.id}: {event.description[:50]}...")
                print(f"    Matched with action {best_match.id}: {best_match.name}")
                print(f"    Similarity score: {best_match_score:.2f}")
                
                # Update the event
                event.action_id = best_match.id
                db.session.add(event)
        
        # Commit the changes
        db.session.commit()
        print(f"  Updated events for scenario {scenario.id}")

def update_events_manually():
    """Update events manually based on known relationships."""
    with app.app_context():
        # Scenario 2: Report or Not
        scenario_id = 2
        
        # Map events to actions
        event_action_map = {
            11: None,  # Project kickoff meeting
            12: 15,    # First design review meeting -> Create Initial Structural Design
            13: 16,    # Safety assessment -> Conduct Initial Safety Assessment
            14: 17,    # Ethical dilemma -> Decide Whether to Report Design Deficiency
            15: 18,    # Budget review meeting -> Decide How to Address Design Deficiency
        }
        
        for event_id, action_id in event_action_map.items():
            event = Event.query.get(event_id)
            if event:
                event.action_id = action_id
                db.session.add(event)
                print(f"Updated event {event_id} with action_id {action_id}")
        
        # Scenario 5: Mass Casualty Triage
        scenario_id = 5
        
        # Map events to actions
        event_action_map = {
            16: None,  # IED detonation
            17: 19,    # Initial treatment -> Perform Initial Triage
            18: 21,    # MEDEVAC arrival -> Determine MEDEVAC Evacuation Priority
            19: 20,    # PVT Martinez dilemma -> Allocate Limited Medical Resources
            20: 22,    # Lieutenant arrival -> Provide Continued Care to Remaining Casualties
        }
        
        for event_id, action_id in event_action_map.items():
            event = Event.query.get(event_id)
            if event:
                event.action_id = action_id
                db.session.add(event)
                print(f"Updated event {event_id} with action_id {action_id}")
        
        # Scenario 3: Conflict of Interest
        scenario_id = 3
        
        # Map events to actions
        event_action_map = {
            7: 10,    # Initial client interview -> Initial Legal Advice to Sarah Chen
            8: 11,    # Sarah provides information -> Draft Whistleblower Brief
            9: 12,    # Discovers conflict of interest -> Disclose Conflict to Partner
            10: 13,   # Michael meets with Horizon -> Consult with Managing Partner
        }
        
        for event_id, action_id in event_action_map.items():
            event = Event.query.get(event_id)
            if event:
                event.action_id = action_id
                db.session.add(event)
                print(f"Updated event {event_id} with action_id {action_id}")
        
        # Commit the changes
        db.session.commit()
        print("All events updated successfully")

if __name__ == "__main__":
    # Update events manually
    update_events_manually()
    
    # Print the updated events
    with app.app_context():
        # Get all scenarios
        scenarios = Scenario.query.all()
        
        print(f"\nUpdated events:")
        
        for scenario in scenarios:
            print(f"\nScenario {scenario.id}: {scenario.name}")
            
            # Get all events for this scenario
            events = Event.query.filter_by(scenario_id=scenario.id).all()
            print(f"  Found {len(events)} events")
            
            for event in events:
                action = Action.query.get(event.action_id) if event.action_id else None
                action_name = action.name if action else "None"
                is_decision = action.is_decision if action else False
                print(f"  Event {event.id}: action_id={event.action_id}, action_name={action_name}, is_decision={is_decision}, description={event.description[:50]}...")
