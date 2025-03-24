#!/usr/bin/env python3
"""
Script for adding timeline items (actions and events) to the "Report or Not" scenario in the 
"Engineering Ethics (US)" world in the AI Ethical Decision-Making Simulator.

This script adds a chronological sequence of actions and events that tell the story of the ethical
dilemma around reporting a design deficiency:

Timeline:
1. Project Milestone (Event) - Project kickoff meeting
2. Create Design (Action) - Initial structural design creation
3. Design Review (Event) - First design review meeting
4. Conduct Safety Review (Action) - Alex conducts initial safety assessment
5. Safety Incident (Event) - Alex discovers potential design deficiency
6. Ethical Dilemma Event (Event) - Alex faces ethical dilemma about reporting
7. Report Violation (Action/Decision) - Decision on whether to report the deficiency
8. Budget Review (Event) - Budget review meeting highlighting constraints
9. Implement Corrective Action (Action/Decision) - Decision on how to address the deficiency

Usage:
1. Run the script: python -m prompts.add_report_or_not_timeline
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
SCENARIO_ID = 2  # "Report or Not" scenario
WORLD_ID = 2     # "Engineering Ethics (US)" world

def add_timeline_to_scenario():
    """Add timeline items to the Report or Not scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        # Verify this is the correct scenario
        if scenario.name != "Report or Not" or scenario.world_id != WORLD_ID:
            print(f'Warning: Expected "Report or Not" scenario in world {WORLD_ID}')
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
            print("Warning: Not all expected characters found. Please run add_report_or_not_characters.py first.")
            return
        
        # Base date for the timeline (2 weeks ago)
        base_date = datetime.now() - timedelta(days=14)
        
        # Timeline items (in chronological order)
        timeline_items = [
            # 1. Project Milestone (Event) - Project kickoff meeting
            {
                'type': 'event',
                'event_time': base_date,
                'description': "Project kickoff meeting where the Westridge Development Corporation presents their requirements for the structural design project. Morgan Chen outlines the project timeline and budget constraints, emphasizing the importance of meeting the aggressive schedule.",
                'character': characters["Morgan Chen"],
                'event_type': "http://example.org/engineering-ethics#ProjectMilestone",
                'parameters': {
                    'milestone_type': "Project Kickoff",
                    'location': "Company conference room",
                    'attendees': ["Morgan Chen", "Alex Rodriguez", "Taylor Williams", "Westridge Development Corporation"]
                }
            },
            
            # 2. Create Design (Action) - Initial structural design creation
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=3),
                'name': "Create Initial Structural Design",
                'description': "Alex Rodriguez and Taylor Williams collaborate to create the initial structural design based on the project requirements. They work within the budget and timeline constraints provided by Morgan Chen and Westridge Development Corporation.",
                'character': characters["Alex Rodriguez"],
                'action_type': "http://example.org/engineering-ethics#CreateDesign",
                'parameters': {
                    'design_type': "Structural",
                    'collaborators': ["Taylor Williams"],
                    'software_used': "CAD Professional 2025"
                },
                'is_decision': False
            },
            
            # 3. Design Review (Event) - First design review meeting
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=5),
                'description': "First design review meeting where Alex Rodriguez presents the initial structural design to the project team. Dr. Jordan Patel provides high-level feedback and Morgan Chen emphasizes the importance of staying on schedule and within budget.",
                'character': characters["Dr. Jordan Patel"],
                'event_type': "http://example.org/engineering-ethics#DesignReview",
                'parameters': {
                    'review_type': "Preliminary",
                    'location': "Engineering department conference room",
                    'attendees': ["Dr. Jordan Patel", "Morgan Chen", "Alex Rodriguez", "Taylor Williams"]
                }
            },
            
            # 4. Conduct Safety Review (Action) - Alex conducts initial safety assessment
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=7),
                'name': "Conduct Initial Safety Assessment",
                'description': "Alex Rodriguez conducts a thorough safety assessment of the structural design using specialized testing equipment. This assessment is more rigorous than the standard review process and is initiated based on Alex's professional commitment to safety.",
                'character': characters["Alex Rodriguez"],
                'action_type': "http://example.org/engineering-ethics#ConductSafetyReview",
                'parameters': {
                    'review_depth': "Comprehensive",
                    'equipment_used': "Structural Testing Tools",
                    'standards_referenced': ["Building Safety Code", "Industry best practices"]
                },
                'is_decision': False
            },
            
            # 5. Safety Incident (Event) - Alex discovers potential design deficiency
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=7, hours=6),
                'description': "During the safety assessment, Alex Rodriguez discovers a potential structural deficiency that could compromise the integrity of the design under certain load conditions. The deficiency is subtle and might not be caught by standard review processes, but could potentially impact public safety if not addressed.",
                'character': characters["Alex Rodriguez"],
                'event_type': "http://example.org/engineering-ethics#SafetyIncident",
                'parameters': {
                    'severity': "Moderate to High",
                    'detection_method': "Advanced stress analysis",
                    'potential_impact': "Structural failure under extreme conditions"
                }
            },
            
            # 6. Ethical Dilemma Event (Event) - Alex faces ethical dilemma about reporting
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=8),
                'description': "Alex Rodriguez faces an ethical dilemma about whether to formally report the design deficiency. Reporting would likely cause significant project delays and budget overruns, potentially damaging relationships with Morgan Chen and Westridge Development Corporation. Not reporting could put public safety at risk and violate professional ethical standards.",
                'character': characters["Alex Rodriguez"],
                'event_type': "http://example.org/engineering-ethics#EthicalDilemmaEvent",
                'parameters': {
                    'dilemma_type': "Safety vs. Project Constraints",
                    'stakeholders_affected': ["Public", "Client", "Company", "Professional integrity"],
                    'ethical_principles': ["Public safety", "Professional responsibility", "Loyalty to employer"]
                }
            },
            
            # 7. Report Violation (Action/Decision) - Decision on whether to report the deficiency
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=9),
                'name': "Decide Whether to Report Design Deficiency",
                'description': "Alex Rodriguez must decide whether to formally report the design deficiency to Dr. Jordan Patel and Sam Washington. This decision represents the central ethical dilemma of the scenario, balancing professional responsibility against project constraints and team loyalty.",
                'character': characters["Alex Rodriguez"],
                'action_type': "http://example.org/engineering-ethics#ReportViolation",
                'parameters': {
                    'violation_type': "Design deficiency",
                    'reporting_channel': "Internal management",
                    'potential_consequences': ["Project delays", "Budget overruns", "Professional reputation"]
                },
                'is_decision': True,
                'options': [
                    "Report the deficiency immediately to both Dr. Jordan Patel and Sam Washington",
                    "Discuss concerns informally with Morgan Chen before formal reporting",
                    "Attempt to fix the deficiency quietly without formal reporting",
                    "Document concerns but delay reporting until after more testing"
                ]
            },
            
            # 8. Budget Review (Event) - Budget review meeting highlighting constraints
            {
                'type': 'event',
                'event_time': base_date + timedelta(days=10),
                'description': "Budget review meeting where Morgan Chen and representatives from Westridge Development Corporation emphasize that the project is already approaching its budget limits. Any significant design changes or delays would create serious financial problems for the project and potentially damage the firm's relationship with this important client.",
                'character': characters["Morgan Chen"],
                'event_type': "http://example.org/engineering-ethics#BudgetReview",
                'parameters': {
                    'budget_status': "At limit",
                    'location': "Finance department",
                    'attendees': ["Morgan Chen", "Westridge Development Corporation", "Dr. Jordan Patel"]
                }
            },
            
            # 9. Implement Corrective Action (Action/Decision) - Decision on how to address the deficiency
            {
                'type': 'action',
                'action_time': base_date + timedelta(days=11),
                'name': "Decide How to Address Design Deficiency",
                'description': "Assuming the deficiency has been reported, the team must now decide how to address it. This decision involves balancing safety requirements, budget constraints, and schedule pressures. Different stakeholders have different priorities, creating tension in the decision-making process.",
                'character': characters["Dr. Jordan Patel"],
                'action_type': "http://example.org/engineering-ethics#ImplementCorrectiveAction",
                'parameters': {
                    'correction_scope': "Design modification",
                    'approval_needed': ["Engineering Director", "Compliance Officer", "Client"],
                    'impact_areas': ["Budget", "Schedule", "Safety", "Client relationship"]
                },
                'is_decision': True,
                'options': [
                    "Complete redesign to eliminate the deficiency regardless of cost",
                    "Implement partial fixes that mitigate the worst risks while minimizing delays",
                    "Add safety factors and warnings without changing the core design",
                    "Seek regulatory exemption based on low probability of failure conditions"
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
