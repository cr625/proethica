#!/usr/bin/env python3
"""
Script template for adding timeline items (actions and events) to scenarios in the 
AI Ethical Decision-Making Simulator.

This template can be customized for different scenarios and timeline items.

Usage:
1. Modify the SCENARIO_ID and timeline item definitions as needed
2. Run the script: python -m prompts.add_timeline_script_template
"""

import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action

# Configuration
SCENARIO_ID = 3  # Replace with the ID of your target scenario

def add_timeline_to_scenario():
    """Add timeline items to the specified scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        print(f'Adding timeline to scenario: {scenario.name} (ID: {scenario.id})')
        
        # Get characters
        characters = {}
        for character in scenario.characters:
            characters[character.name] = character
        
        if len(characters) == 0:
            print("Warning: No characters found. Please add characters to the scenario first.")
            return
        
        # Base date for the timeline (2 weeks ago)
        base_date = datetime.now() - timedelta(days=14)
        
        # Timeline items (in chronological order)
        # Format for events: [type, event_time, description, character_name, event_type, parameters]
        # Format for actions: [type, action_time, name, description, character_name, action_type, parameters, is_decision, options]
        timeline_items = [
            # Example Event
            [
                'event',
                base_date,
                "Example event description that provides context for the scenario.",
                "Character Name 1",  # Replace with actual character name
                "http://example.org/ontology#EventType",  # Replace with actual event type URI
                {
                    'location': "Example location",
                    'duration': "60 minutes"
                }
            ],
            
            # Example Action (not a decision)
            [
                'action',
                base_date + timedelta(hours=2),
                "Example Action Name",
                "Example action description that explains what the character does.",
                "Character Name 2",  # Replace with actual character name
                "http://example.org/ontology#ActionType",  # Replace with actual action type URI
                {
                    'parameter1': "value1",
                    'parameter2': "value2"
                },
                False,  # is_decision
                None    # options (None for non-decisions)
            ],
            
            # Example Decision Point (special type of action)
            [
                'action',
                base_date + timedelta(days=1),
                "Example Decision Name",
                "Example decision description that presents an ethical choice.",
                "Character Name 1",  # Replace with actual character name
                "http://example.org/ontology#DecisionType",  # Replace with actual action type URI
                {
                    'decision_context': "ethical dilemma",
                    'importance': "high"
                },
                True,  # is_decision
                [
                    "Option 1: Description of first option",
                    "Option 2: Description of second option",
                    "Option 3: Description of third option"
                ]
            ],
            
            # Add more timeline items as needed...
        ]
        
        # Add timeline items
        for item in timeline_items:
            if item[0] == 'event':
                # Unpack event data
                _, event_time, description, character_name, event_type, parameters = item
                
                # Get character
                character = characters.get(character_name)
                if not character:
                    print(f"Warning: Character '{character_name}' not found. Skipping event.")
                    continue
                
                # Create event
                event = Event(
                    scenario_id=scenario.id,
                    character_id=character.id,
                    event_time=event_time,
                    description=description,
                    parameters=parameters
                )
                db.session.add(event)
                print(f"Added event: {event_time.strftime('%Y-%m-%d %H:%M')} - {event_type.split('#')[-1]}")
            
            elif item[0] == 'action':
                # Unpack action data
                _, action_time, name, description, character_name, action_type, parameters, is_decision, options = item
                
                # Get character
                character = characters.get(character_name)
                if not character:
                    print(f"Warning: Character '{character_name}' not found. Skipping action.")
                    continue
                
                # Create action
                action = Action(
                    name=name,
                    description=description,
                    scenario_id=scenario.id,
                    character_id=character.id,
                    action_time=action_time,
                    action_type=action_type,
                    parameters=parameters,
                    is_decision=is_decision,
                    options=options if is_decision else None
                )
                db.session.add(action)
                print(f"Added {'decision' if is_decision else 'action'}: {action_time.strftime('%Y-%m-%d %H:%M')} - {name}")
        
        # Commit all changes
        db.session.commit()
        print('Timeline added successfully!')

def verify_timeline():
    """Verify that timeline items were added correctly."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        print(f'\nVerifying timeline in scenario: {scenario.name}')
        
        # Get actions
        actions = Action.query.filter_by(scenario_id=scenario.id).all()
        print(f'Number of actions: {len(actions)}')
        
        for action in sorted(actions, key=lambda x: x.action_time):
            print(f'\n- Action: {action.name}')
            print(f'  Time: {action.action_time.strftime("%Y-%m-%d %H:%M")}')
            print(f'  Character: {Character.query.get(action.character_id).name if action.character_id else "None"}')
            print(f'  Description: {action.description[:100]}...' if len(action.description) > 100 else f'  Description: {action.description}')
            if action.is_decision:
                print(f'  Decision with options: {action.options}')
        
        # Get events
        events = Event.query.filter_by(scenario_id=scenario.id).all()
        print(f'\nNumber of events: {len(events)}')
        
        for event in sorted(events, key=lambda x: x.event_time):
            print(f'\n- Event at {event.event_time.strftime("%Y-%m-%d %H:%M")}')
            print(f'  Character: {Character.query.get(event.character_id).name if event.character_id else "None"}')
            print(f'  Description: {event.description[:100]}...' if len(event.description) > 100 else f'  Description: {event.description}')

if __name__ == "__main__":
    # Add timeline
    add_timeline_to_scenario()
    
    # Verify timeline was added correctly
    verify_timeline()
