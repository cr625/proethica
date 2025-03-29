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

def format_options(options):
    """Format decision options for better readability"""
    if not options:
        return "None"
    
    result = []
    for i, option in enumerate(options, 1):
        codes = ", ".join(option.get("ethical_codes", []))
        result.append(f"  {i}. {option.get('text', 'Unknown')}")
        result.append(f"     Description: {option.get('description', 'No description')}")
        if codes:
            result.append(f"     Ethical Codes: {codes}")
    
    return "\n".join(result)

def main():
    app = create_app()
    with app.app_context():
        scenario_id = 6  # Default to scenario 6
        
        # Check if a scenario ID was provided
        if len(sys.argv) > 1:
            try:
                scenario_id = int(sys.argv[1])
            except ValueError:
                print(f"Invalid scenario ID: {sys.argv[1]}")
                return
        
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
                    print(format_options(item.get('options', [])))
            
            if item['type'] == 'Event' and item.get('parameters') and item['parameters'].get('decision_point'):
                print("   CRITICAL EVENT: Decision required")
            
            print()  # Empty line for readability

if __name__ == '__main__':
    main()
