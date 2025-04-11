#!/usr/bin/env python3
import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action

def update_scenario1_timeline():
    """Update the timeline for scenario 1 to better align with NSPE case 89-7-1."""
    
    app = create_app()
    with app.app_context():
        # Get scenario 1
        scenario = Scenario.query.get(1)
        if not scenario:
            print("Scenario 1 not found")
            return
        
        print(f"Updating timeline for Scenario 1: {scenario.name}")
        
        # Get Engineer Smith character
        engineer = Character.query.filter_by(scenario_id=1, name="Engineer Smith").first()
        if not engineer:
            print("Engineer Smith character not found")
            return
            
        # 1. Find and update the "Potential structural safety issue discovered" event
        structural_event = Event.query.filter_by(
            scenario_id=1, 
            description="Potential structural safety issue discovered"
        ).first()
        
        if structural_event:
            # Update the event description
            print(f"Updating event: {structural_event.description} -> Engineer determines building is structurally sound")
            structural_event.description = "Engineer determines building is structurally sound"
            db.session.commit()
        else:
            print("Structural safety event not found")
        
        # 2. Add a new event for client revealing code violations
        # Base the event_time on the structural_event time plus an hour
        event_time = None
        if structural_event:
            event_time = structural_event.event_time + timedelta(hours=1)
        else:
            # If structural_event not found, set a default time
            datetime_base = datetime(2025, 4, 5, 16, 50)  # Based on existing timeline
            event_time = datetime_base
        
        # Check if this event already exists
        existing_event = Event.query.filter_by(
            scenario_id=1,
            description="Client reveals electrical and mechanical code violations to engineer"
        ).first()
        
        if not existing_event:
            # Create the new event
            new_event = Event(
                scenario_id=1,
                character_id=engineer.id,
                event_time=event_time,
                description="Client reveals electrical and mechanical code violations to engineer",
                parameters={}
            )
            
            print(f"Adding new event: {new_event.description} at {new_event.event_time}")
            db.session.add(new_event)
            db.session.commit()
        else:
            print(f"Event already exists: {existing_event.description}")
        
        # 3. Update the decision point description
        decision_action = Action.query.filter_by(
            scenario_id=1, 
            name="Decision on reporting safety issue"
        ).first()
        
        if decision_action:
            # Update the action description
            old_description = decision_action.description
            new_description = "Engineer decides whether to report the electrical and mechanical code violations"
            
            print(f"Updating decision: {old_description} -> {new_description}")
            decision_action.description = new_description
            db.session.commit()
        else:
            print("Decision action not found")
        
        print("Timeline update completed")

if __name__ == "__main__":
    update_scenario1_timeline()
