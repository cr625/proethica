#!/usr/bin/env python3
import sys
import os
import json
from datetime import datetime
from operator import attrgetter

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action

def format_options(options, selected_option=None, is_simulation=False):
    """Format decision options for better readability
    
    Args:
        options: List of option objects
        selected_option: The selected option (if any)
        is_simulation: Whether this is a simulation timeline (where selections should be shown)
    """
    if not options:
        return "None"
    
    result = []
    for i, option in enumerate(options, 1):
        # Handle different option formats (dictionary or string)
        if isinstance(option, dict):
            option_text = option.get('text', 'Unknown')
            option_description = option.get('description', 'No description')
            ethical_codes = option.get("ethical_codes", [])
        else:
            # If option is a string, use it directly as the text
            option_text = str(option)
            option_description = "No description"
            ethical_codes = []
        
        # Only indicate selection if this is a simulation timeline and there's a selection
        if is_simulation and selected_option and option_text == selected_option:
            result.append(f"  {i}. {option_text} [SELECTED]")
        else:
            result.append(f"  {i}. {option_text}")
            
        result.append(f"     Description: {option_description}")
        
        codes = ", ".join(ethical_codes)
        if codes:
            result.append(f"     Ethical Codes: {codes}")
    
    return "\n".join(result)

def main():
    app = create_app()
    with app.app_context():
        scenario_id = 6  # Default to scenario 6
        is_simulation = False  # Default to showing scenario timeline, not simulation
        
        # Parse command line arguments
        if len(sys.argv) > 1:
            try:
                scenario_id = int(sys.argv[1])
            except ValueError:
                print(f"Invalid scenario ID: {sys.argv[1]}")
                return
        
        # Check if simulation flag is provided
        if len(sys.argv) > 2 and sys.argv[2].lower() in ('sim', 'simulation', 'true', 'yes'):
            is_simulation = True
        
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            print(f"Scenario {scenario_id} not found")
            return
        
        print(f"Timeline for Scenario {scenario.id}: {scenario.name}")
        print(f"Description: {scenario.description}")
        print("\n" + "=" * 80 + "\n")
        
        # Get all characters for character name lookup
        characters = {char.id: char.name for char in Character.query.filter_by(scenario_id=scenario.id).all()}
        
        # Get all events and actions for this scenario
        events = Event.query.filter_by(scenario_id=scenario.id).all()
        actions = Action.query.filter_by(scenario_id=scenario.id).all()
        
        # Create a combined timeline of events and actions
        timeline_items = []
        
        for event in events:
            character_name = characters.get(event.character_id, 'Unknown')
            timeline_items.append({
                'time': event.event_time,
                'type': 'Event',
                'description': event.description,
                'character': character_name,
                'id': event.id,
                'action_id': event.action_id,
                'parameters': event.parameters
            })
        
        for action in actions:
            character_name = characters.get(action.character_id, 'Unknown')
            timeline_items.append({
                'time': action.action_time,
                'type': 'Action',
                'name': action.name,
                'description': action.description,
                'character': character_name,
                'id': action.id,
                'is_decision': action.is_decision,
                'options': action.options,
                'action_type': action.action_type
            })
        
        # Sort timeline by time
        timeline_items.sort(key=lambda x: x['time'])
        
        # Print timeline
        for i, item in enumerate(timeline_items, 1):
            time_str = item['time'].strftime("%Y-%m-%d %H:%M")
            print(f"{i}. [{time_str}] {item['type']}: {item.get('name', '')}")
            print(f"   Character: {item['character']}")
            print(f"   Description: {item['description']}")
            
            if item['type'] == 'Action':
                print(f"   Action Type: {item.get('action_type', 'Unknown')}")
                
                if item.get('is_decision', False):
                    print("   DECISION POINT")
                    print("   Options:")
                    print(format_options(
                        item.get('options', []), 
                        item.get('selected_option'), 
                        is_simulation
                    ))
            
            if item['type'] == 'Event' and item.get('parameters') and item['parameters'].get('decision_point'):
                print("   CRITICAL EVENT: Decision required")
            
            print()  # Empty line for readability

if __name__ == '__main__':
    main()
