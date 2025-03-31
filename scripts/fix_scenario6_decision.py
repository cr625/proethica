#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.event import Event, Action
from sqlalchemy import or_

def fix_scenario6_decision(force=False):
    """
    Fix the ethical decision display in Scenario 6 by:
    1. Removing the Event entry for the ethical decision
    2. Ensuring the Action entry is properly configured as a decision
    3. Moving the decision's timestamp to ensure it appears in the visible timeline
    """
    app = create_app()
    with app.app_context():
        # Get scenario 6
        scenario = Scenario.query.get(6)
        if not scenario:
            print("Scenario 6 not found")
            return
        
        print(f"Fixing ethical decision display for Scenario: {scenario.name}")
        
        if not force:
            confirm = input("Ready to fix the ethical decision display? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        try:
            # Step 1: Find the Event and Action entries for the ethical decision
            decision_event = Event.query.filter(
                Event.scenario_id == scenario.id,
                Event.description.like('%ethical decision%')
            ).first()
            
            decision_action = Action.query.filter(
                Action.scenario_id == scenario.id,
                Action.name.like('%Ethical Dilemma%')
            ).first()
            
            if not decision_action:
                print("ERROR: Could not find the ethical decision action in the database")
                return
                
            print(f"Found decision action: {decision_action.name} (ID: {decision_action.id})")
            
            if decision_event:
                print(f"Found decision event: {decision_event.description} (ID: {decision_event.id})")
            
            # Step 2: Remove the decision event if it exists
            if decision_event:
                print(f"Removing decision event: {decision_event.description}")
                db.session.delete(decision_event)
                
            # Step 3: Ensure the decision action has the correct properties
            # Check if action is properly configured as a decision
            if not decision_action.is_decision:
                print("Setting is_decision flag to True")
                decision_action.is_decision = True
                
            if decision_action.action_type != "EthicalDecision":
                print(f"Updating action_type from '{decision_action.action_type}' to 'EthicalDecision'")
                decision_action.action_type = "EthicalDecision"
            
            # Check if decision has options
            if not decision_action.options or len(decision_action.options) == 0:
                print("WARNING: Decision has no options defined. Adding default options.")
                decision_action.options = [
                    {
                        "text": "Maintain client confidentiality",
                        "description": "Respect the confidentiality agreement and do not report the violations to the authorities.",
                        "ethical_codes": ["NSPE Code III.4 - Do not Disclose Confidential Information Without Consent", "NSPE Code I.4 - Act as a Faithful Agent or Trustee"]
                    },
                    {
                        "text": "Report violations to authorities",
                        "description": "Report the electrical and mechanical code violations to the Building Safety Authority to protect public safety.",
                        "ethical_codes": ["NSPE Code I.1 - Safety, Health, and Welfare of Public is Paramount", "NSPE Code II.1.A - Primary Obligation is to Protect Public"]
                    },
                    {
                        "text": "Convince owner to address violations",
                        "description": "Try to persuade the Building Owner to address the violations before selling the building.",
                        "ethical_codes": ["NSPE Code III.1 - Be Guided by Highest Standards of Integrity", "NSPE Code II.1.A - Primary Obligation is to Protect Public"]
                    },
                    {
                        "text": "Seek professional ethics guidance",
                        "description": "Consult with the professional engineering association for guidance on this ethical conflict.",
                        "ethical_codes": ["NSPE Code III.2.B - Do not Complete or Sign Documents that are not Safe for Public"]
                    }
                ]
            
            # Step 4: Move the decision's timestamp to appear earlier in the timeline
            # Find the earliest and latest timestamps
            actions = Action.query.filter_by(scenario_id=scenario.id).all()
            timestamps = [a.action_time for a in actions]
            
            if timestamps:
                earliest_time = min(timestamps)
                latest_time = max(timestamps)
                
                # Pick a timestamp that is 75% through the timeline
                # This ensures the decision appears prominently but after most events
                timeline_duration = latest_time - earliest_time
                target_position = 0.75  # Position in timeline (0.0 to 1.0)
                
                target_time = earliest_time + timedelta(seconds=timeline_duration.total_seconds() * target_position)
                
                # Adjust timestamps of actions to make space for decision
                for action in actions:
                    # If action is after target time but not the decision, move it later
                    if action.id != decision_action.id and action.action_time >= target_time:
                        action.action_time += timedelta(minutes=30)
                
                original_time = decision_action.action_time
                decision_action.action_time = target_time
                
                print(f"Moved decision from {original_time} to {target_time}")
            
            # Step 5: Commit all changes
            db.session.commit()
            print("Successfully fixed ethical decision display")
            
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
                    'description': action.description,
                    'is_decision': action.is_decision
                })
            
            # Sort and display
            timeline_items.sort(key=lambda x: x['time'])
            
            for i, item in enumerate(timeline_items, 1):
                if item['type'] == 'Event':
                    print(f"{i}. [{item['time']}] Event: {item['description']}")
                else:
                    print(f"{i}. [{item['time']}] Action: {item['name']} - {item['description']}")
                    if item.get('is_decision'):
                        print("   DECISION POINT with options")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error fixing decision display: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix ethical decision display for Scenario 6')
    parser.add_argument('--force', action='store_true', help='Force changes without confirmation')
    
    args = parser.parse_args()
    fix_scenario6_decision(force=args.force)
