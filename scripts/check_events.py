#!/usr/bin/env python3
"""
Script to check events in the database and their action_id values.
"""

import sys
import os
from flask import Flask

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Event, Action, Scenario

app = create_app()

with app.app_context():
    # Get all scenarios
    scenarios = Scenario.query.all()
    
    print(f"Found {len(scenarios)} scenarios")
    
    for scenario in scenarios:
        print(f"\nScenario {scenario.id}: {scenario.name}")
        
        # Get all events for this scenario
        events = Event.query.filter_by(scenario_id=scenario.id).all()
        print(f"  Found {len(events)} events")
        
        for event in events:
            action = Action.query.get(event.action_id) if event.action_id else None
            action_name = action.name if action else "None"
            print(f"  Event {event.id}: action_id={event.action_id}, action_name={action_name}, description={event.description}")
        
        # Get all actions for this scenario
        actions = Action.query.filter_by(scenario_id=scenario.id).all()
        print(f"  Found {len(actions)} actions")
        
        for action in actions:
            print(f"  Action {action.id}: name={action.name}, is_decision={action.is_decision}, description={action.description}")
