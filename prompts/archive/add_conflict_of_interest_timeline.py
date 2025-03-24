#!/usr/bin/env python3
"""
Script for adding timeline items (actions and events) to the "Conflict of Interest" scenario in the 
"Legal Ethics World (New Jersey)" in the AI Ethical Decision-Making Simulator.

This script adds a chronological sequence of actions and events that tell the story of the conflict
of interest situation involving the characters and resources previously added to the scenario.

Timeline:
1. Initial Client Interview (Event) - Sarah Chen meets with Michael Reynolds
2. Provide Advice (Action) - Michael provides initial legal advice to Sarah
3. Client Disclosure (Event) - Sarah discloses information about Horizon Technologies
4. Draft Document (Action) - Jason drafts the whistleblower protections brief
5. Ethical Dilemma (Event) - Jason realizes the conflict of interest
6. Disclose Conflict (Action) - Jason discloses the conflict to Michael
7. Seek Ethics Opinion (Action/Decision) - Michael consults with Eleanor
8. Client Meeting (Event) - Michael meets with Horizon Technologies
9. Withdraw From Case (Action/Decision) - Decision on whether to withdraw

Usage:
1. Run the script: python -m prompts.add_conflict_of_interest_timeline
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
SCENARIO_ID = 3  # "Conflict of Interest" scenario
WORLD_ID = 3     # "Legal Ethics World (New Jersey)"

def add_timeline_to_scenario():
    """Add timeline items to the Conflict of Interest scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        # Verify this is the correct scenario
        if scenario.name != "Conflict of Interest" or scenario.world_id != WORLD_ID:
            print(f'Warning: Expected "Conflict of Interest" scenario in world {WORLD_ID}')
            print(f'Found: "{scenario.name}" in world {scenario.world_id}')
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborting.")
                return
        
        print(f'Adding timeline to scenario: {scenario.name} (ID: {scenario.id})')
        
        # Get characters
        characters = {}
        for character in scenario.characters:
            characters[character.name] = character
        
        if len(characters) < 5:
            print("Warning: Not all expected characters found. Please run add_conflict_of_interest_characters.py first.")
            return
        
        # Base date for the timeline (2 weeks ago)
        base_date = datetime.now() - timedelta(days=14)
        
        # Timeline items (in chronological order)
        timeline_items = [
            # 1. Initial Client Interview (Event)
            {
                'type': 'event',
                'event_time': base_date,
                'description': "Initial client interview with Sarah Chen. Sarah explains that she has discovered financial improprieties at her employer, Horizon Technologies Inc., and is considering becoming a whistleblower. She seeks legal representation for potential claims under securities laws and whistleblower protection statutes.",
                'character': characters["Sarah Chen"],
                'event_type': "http://example.org/nj-legal-ethics#ClientInterview",
                'parameters': {
                    'location': "Law firm conference room",
                    'duration': "90 minutes"
                }
            },
            
            # 2. Provide Advice (Action)
            {
                'type': 'action',
                'action_time': base_date + timedelta(hours=2),
                'name': "Initial Legal Advice to Sarah Chen",
                'description': "Michael Reynolds provides preliminary legal advice to Sarah Chen regarding whistleblower protections and securities law violations. He explains the legal process, potential remedies, and risks involved in pursuing a whistleblower claim against a large corporation.",
                'character': characters["Michael Reynolds"],
                'action_type': "http://example.org/nj-legal-ethics#ProvideAdvice",
                'parameters': {
                    'advice_type': "preliminary",
                    'legal_areas': ["securities law", "whistleblower protection", "employment law"]
                },
                'is_decision': False
            },
            
            # 3. Client Disclosure (Event)
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=2),
                'description': "Sarah Chen provides detailed information about Horizon Technologies' financial improprieties, including specific documents and data that suggest accounting fraud and misrepresentations to investors. She explains her role at the company and how she discovered the issues.",
                'character': characters["Sarah Chen"],
                'event_type': "http://example.org/nj-legal-ethics#ClientDisclosure",
                'parameters': {
                    'disclosure_type': "confidential",
                    'evidence_provided': True
                }
            },
            
            # 4. Draft Document (Action)
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=3),
                'name': "Draft Whistleblower Brief",
                'description': "Jason Martinez drafts a legal brief outlining whistleblower protections applicable to Sarah Chen's case. The brief analyzes relevant statutes, regulations, and case law to support potential claims against Horizon Technologies.",
                'character': characters["Jason Martinez"],
                'action_type': "http://example.org/nj-legal-ethics#DraftDocument",
                'parameters': {
                    'document_type': "legal brief",
                    'pages': 15
                },
                'is_decision': False
            },
            
            # 5. Ethical Dilemma (Event)
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=4),
                'description': "While researching Horizon Technologies for the whistleblower case, Jason Martinez discovers that the company is an existing client of the firm. He realizes that representing Sarah Chen against Horizon Technologies would create a significant conflict of interest under Rule of Professional Conduct 1.7.",
                'character': characters["Jason Martinez"],
                'event_type': "http://example.org/nj-legal-ethics#EthicalDilemma",
                'parameters': {
                    'rule_violated': "RPC 1.7 - Conflict of Interest",
                    'severity': "high"
                }
            },
            
            # 6. Disclose Conflict (Action)
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=4, hours=2),
                'name': "Disclose Conflict to Partner",
                'description': "Jason Martinez immediately discloses the conflict of interest to Michael Reynolds. He explains that the firm currently represents Horizon Technologies in various corporate matters and that taking on Sarah Chen's whistleblower case would create a direct conflict with an existing client.",
                'character': characters["Jason Martinez"],
                'action_type': "http://example.org/nj-legal-ethics#DiscloseConflict",
                'parameters': {
                    'disclosure_recipient': "supervising attorney",
                    'conflict_type': "concurrent client conflict"
                },
                'is_decision': False
            },
            
            # 7. Seek Ethics Opinion (Action/Decision)
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=5),
                'name': "Consult with Managing Partner",
                'description': "Michael Reynolds consults with Eleanor Washington, the firm's managing partner, about the conflict of interest situation. They discuss the ethical implications, potential remedies, and the firm's obligations to both clients under the Rules of Professional Conduct.",
                'character': characters["Michael Reynolds"],
                'action_type': "http://example.org/nj-legal-ethics#SeekEthicsOpinion",
                'parameters': {
                    'consultation_type': "internal",
                    'ethical_issue': "concurrent client conflict"
                },
                'is_decision': True,
                'options': [
                    "Attempt to get conflict waivers from both clients",
                    "Withdraw from representing Sarah Chen",
                    "Withdraw from representing Horizon Technologies",
                    "Refer Sarah Chen to another law firm"
                ]
            },
            
            # 8. Client Meeting (Event)
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=6),
                'description': "Michael Reynolds meets with representatives from Horizon Technologies for a previously scheduled meeting regarding ongoing corporate matters. He is careful not to disclose any information about Sarah Chen's potential case while still fulfilling his professional obligations to Horizon as a current client.",
                'character': characters["Michael Reynolds"],
                'event_type': "http://example.org/nj-legal-ethics#ClientMeeting",
                'parameters': {
                    'client': "Horizon Technologies Inc.",
                    'meeting_purpose': "regular corporate representation"
                }
            },
            
            # 9. Withdraw From Case (Action/Decision)
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=7),
                'name': "Make Final Decision on Representation",
                'description': "After careful consideration of the ethical implications and consultation with Eleanor Washington, Michael Reynolds must make a final decision about how to handle the conflict of interest situation. This decision will have significant consequences for all parties involved.",
                'character': characters["Michael Reynolds"],
                'action_type': "http://example.org/nj-legal-ethics#WithdrawFromCase",
                'parameters': {
                    'decision_type': "ethical conflict resolution",
                    'rules_considered': ["RPC 1.7", "RPC 1.9", "RPC 1.16"]
                },
                'is_decision': True,
                'options': [
                    "Withdraw from representing Sarah Chen and refer her to another attorney",
                    "Withdraw from representing Horizon Technologies after proper notice",
                    "Attempt to maintain both representations with ethical screens and informed consent",
                    "Withdraw from both representations to avoid any appearance of impropriety"
                ]
            }
        ]
        
        # Add timeline items
        for item in timeline_items:
            if item['type'] == 'event':
                # Create event
                event = Event(
                    scenario_id=scenario.id,
                    character_id=item['character'].id if 'character' in item else None,
                    event_time=item['event_time'],
                    description=item['description'],
                    parameters=item.get('parameters', {})
                )
                db.session.add(event)
                print(f"Added event: {item['event_time'].strftime('%Y-%m-%d %H:%M')} - {item['event_type'].split('#')[-1]}")
            
            elif item['type'] == 'action':
                # Create action
                action = Action(
                    name=item['name'],
                    description=item['description'],
                    scenario_id=scenario.id,
                    character_id=item['character'].id if 'character' in item else None,
                    action_time=item['action_time'],
                    action_type=item['action_type'],
                    parameters=item.get('parameters', {}),
                    is_decision=item.get('is_decision', False),
                    options=item.get('options', []) if item.get('is_decision', False) else None
                )
                db.session.add(action)
                print(f"Added action: {item['action_time'].strftime('%Y-%m-%d %H:%M')} - {item['name']}")
        
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
