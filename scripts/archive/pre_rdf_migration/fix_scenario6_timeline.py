#!/usr/bin/env python3
import sys
import os
import argparse

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from sqlalchemy import desc

def fix_scenario6_timeline(force=False):
    """
    Fix the timeline for Scenario 6 by removing redundant entries
    and ensuring critical ethical elements are visible.
    """
    app = create_app()
    with app.app_context():
        # Get scenario 6
        scenario = Scenario.query.get(6)
        if not scenario:
            print("Scenario 6 not found")
            return
        
        print(f"Fixing timeline for Scenario: {scenario.name}")
        
        # Get all events and actions for the scenario
        events = Event.query.filter_by(scenario_id=scenario.id).all()
        actions = Action.query.filter_by(scenario_id=scenario.id).all()
        
        print(f"Found {len(events)} events and {len(actions)} actions")
        
        if not force:
            confirm = input("Do you want to remove redundant events to fix the timeline? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        try:
            # Strategy: Remove redundant events (keep actions)
            # This preserves the decision points which are in actions
            
            # For every action, find and remove the corresponding event with the same timestamp
            removed_count = 0
            
            for action in actions:
                matching_events = Event.query.filter_by(
                    scenario_id=scenario.id,
                    event_time=action.action_time,
                    action_id=action.id
                ).all()
                
                for event in matching_events:
                    print(f"Removing redundant event: {event.description}")
                    db.session.delete(event)
                    removed_count += 1
            
            # Verify critical actions are present
            code_violations_action = Action.query.filter(
                Action.scenario_id == scenario.id,
                Action.name.like('%Code Violations%')
            ).first()
            
            ethical_dilemma_action = Action.query.filter(
                Action.scenario_id == scenario.id,
                Action.name.like('%Ethical Dilemma%')
            ).first()
            
            if not code_violations_action:
                print("WARNING: Action for code violations disclosure not found!")
            else:
                print(f"Confirmed critical action exists: {code_violations_action.name}")
                
            if not ethical_dilemma_action:
                print("WARNING: Action for ethical dilemma not found!")
            else:
                print(f"Confirmed critical decision point exists: {ethical_dilemma_action.name}")
                
            # Commit changes
            db.session.commit()
            print(f"Successfully removed {removed_count} redundant events")
            
            # Display updated timeline
            print("\nUpdated Timeline:")
            timeline_items = []
            
            # Add remaining events
            for event in Event.query.filter_by(scenario_id=scenario.id).order_by(Event.event_time).all():
                timeline_items.append({
                    'time': event.event_time,
                    'type': 'Event',
                    'description': event.description
                })
            
            # Add actions
            for action in Action.query.filter_by(scenario_id=scenario.id).order_by(Action.action_time).all():
                timeline_items.append({
                    'time': action.action_time,
                    'type': 'Action',
                    'name': action.name,
                    'description': action.description
                })
            
            # Sort and display
            timeline_items.sort(key=lambda x: x['time'])
            
            for i, item in enumerate(timeline_items, 1):
                if item['type'] == 'Event':
                    print(f"{i}. [{item['time']}] Event: {item['description']}")
                else:
                    print(f"{i}. [{item['time']}] Action: {item['name']} - {item['description']}")
                    if 'Ethical Dilemma' in item['name']:
                        print("   DECISION POINT with options")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error fixing timeline: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix timeline for Scenario 6')
    parser.add_argument('--force', action='store_true', help='Force changes without confirmation')
    
    args = parser.parse_args()
    fix_scenario6_timeline(force=args.force)
