#!/usr/bin/env python3
"""
Script for adding timeline items (actions and events) to the "Mass Casualty Triage" scenario in the 
"Tactical Combat Casualty Care (US Army)" world in the AI Ethical Decision-Making Simulator.

This script adds a chronological sequence of actions and events that tell the story of a mass casualty
incident and the ethical dilemmas faced by medical personnel:

Timeline:
1. IED Detonation (Event) - Initial explosion creating multiple casualties
2. Perform Triage (Action) - SSG Miller performs initial triage of casualties
3. Treatment Event (Event) - Initial treatment begins with limited resources
4. Resource Allocation Decision (Action/Decision) - Decision on how to allocate limited medical supplies
5. Evacuation Priority Decision (Action/Decision) - Decision on evacuation order
6. Medical Evacuation (Event) - MEDEVAC arrives but can only transport limited patients
7. Ethical Dilemma Event (Event) - Dilemma about treating expectant patient vs. others
8. Treatment Action (Action) - Continued treatment of remaining casualties
9. Arrival of Additional Medical Personnel (Event) - LT Chen arrives with additional resources

Usage:
1. Run the script: python -m prompts.add_mass_casualty_triage_timeline
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
SCENARIO_ID = 5  # "Mass Casualty Triage" scenario
WORLD_ID = 1     # "Tactical Combat Casualty Care (US Army)" world

def add_timeline_to_scenario():
    """Add timeline items to the Mass Casualty Triage scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        # Verify this is the correct scenario
        if scenario.name != "Mass Casualty Triage" or scenario.world_id != WORLD_ID:
            print(f'Warning: Expected "Mass Casualty Triage" scenario in world {WORLD_ID}')
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
            print("Warning: Not all expected characters found. Please run add_mass_casualty_triage_characters.py first.")
            return
        
        # Base date for the timeline (2 hours ago)
        base_date = datetime.now() - timedelta(hours=2)
        
        # Timeline items (in chronological order)
        timeline_items = [
            # 1. IED Detonation (Event) - Initial explosion creating multiple casualties
            {
                'type': 'event',
                'event_time': base_date,
                'description': "An improvised explosive device (IED) detonates near a patrol, causing multiple casualties with varying severity of injuries. The explosion creates a chaotic scene with five injured service members requiring immediate medical attention.",
                'character': None,  # No specific character for this event
                'event_type': "http://example.org/military-medical-triage#IEDDetonation",
                'parameters': {
                    'location': "Rural road in combat zone",
                    'casualties': 5,
                    'severity': "High"
                }
            },
            
            # 2. Perform Triage (Action) - SSG Miller performs initial triage of casualties
            {
                'type': 'action',
                'action_time': base_date + timedelta(minutes=5),
                'name': "Perform Initial Triage",
                'description': "Staff Sergeant James Miller performs rapid initial triage of all casualties, categorizing them according to the severity of their injuries: Sergeant Johnson (Immediate/Red), Corporal Williams (Immediate/Red), Private Garcia (Delayed/Yellow), Specialist Lee (Minimal/Green), and Private Martinez (Expectant/Black).",
                'character': characters["Staff Sergeant James Miller"],
                'action_type': "http://example.org/military-medical-triage#PerformTriage",
                'parameters': {
                    'triage_method': "START Triage",
                    'casualties_assessed': 5,
                    'time_pressure': "Extreme"
                },
                'is_decision': False
            },
            
            # 3. Treatment Event (Event) - Initial treatment begins with limited resources
            {
                'type': 'event',
                'event_time': base_date + timedelta(minutes=10),
                'description': "Initial treatment begins with SSG Miller directing PFC Rodriguez to assist. They begin applying tourniquets to Sergeant Johnson's leg wound and stabilizing Corporal Williams' chest injuries. Resources are limited, and they must make difficult decisions about how to allocate them among the casualties.",
                'character': characters["Staff Sergeant James Miller"],
                'event_type': "http://example.org/military-medical-triage#TreatmentEvent",
                'parameters': {
                    'resources_available': "Limited",
                    'treatment_priority': "Immediate (Red) casualties",
                    'personnel': ["SSG Miller", "PFC Rodriguez"]
                }
            },
            
            # 4. Resource Allocation Decision (Action/Decision) - Decision on how to allocate limited medical supplies
            {
                'type': 'action',
                'action_time': base_date + timedelta(minutes=15),
                'name': "Allocate Limited Medical Resources",
                'description': "SSG Miller must decide how to allocate limited medical resources, particularly tourniquets, hemostatic bandages, and IV fluids. With multiple casualties requiring these resources, he faces an ethical dilemma about prioritization based on injury severity, survival probability, and resource effectiveness.",
                'character': characters["Staff Sergeant James Miller"],
                'action_type': "http://example.org/military-medical-triage#ResourceAllocationDecision",
                'parameters': {
                    'critical_resources': ["Tourniquets", "Blood products", "Morphine"],
                    'competing_needs': "Multiple casualties requiring same resources",
                    'ethical_framework': "Greatest good for greatest number vs. individual patient needs"
                },
                'is_decision': True,
                'options': [
                    "Distribute resources equally among all salvageable casualties",
                    "Prioritize resources for the most severely injured casualties with chance of survival",
                    "Reserve some resources for potential additional casualties",
                    "Use minimal resources on expectant casualty to provide comfort measures only"
                ]
            },
            
            # 5. Evacuation Priority Decision (Action/Decision) - Decision on evacuation order
            {
                'type': 'action',
                'action_time': base_date + timedelta(minutes=25),
                'name': "Determine MEDEVAC Evacuation Priority",
                'description': "SSG Miller must determine the evacuation priority for the MEDEVAC helicopter, which can only transport two casualties on its first run. This decision requires balancing the severity of injuries, likelihood of survival, and time-sensitivity of medical needs.",
                'character': characters["Staff Sergeant James Miller"],
                'action_type': "http://example.org/military-medical-triage#EvacuationPriorityDecision",
                'parameters': {
                    'transport_capacity': 2,
                    'candidates': ["SGT Johnson", "CPL Williams", "PVT Garcia", "PVT Martinez"],
                    'time_to_higher_care': "15 minutes flying time to field hospital"
                },
                'is_decision': True,
                'options': [
                    "Evacuate the two immediate (red) casualties: SGT Johnson and CPL Williams",
                    "Evacuate SGT Johnson (red) and PVT Martinez (expectant) to give the expectant casualty a chance",
                    "Evacuate one immediate casualty and PVT Garcia (yellow) whose condition might deteriorate",
                    "Evacuate based strictly on survival probability regardless of current triage category"
                ]
            },
            
            # 6. Medical Evacuation (Event) - MEDEVAC arrives but can only transport limited patients
            {
                'type': 'event',
                'event_time': base_date + timedelta(minutes=40),
                'description': "MEDEVAC helicopter arrives at the casualty collection point. Based on SSG Miller's prioritization, the first two casualties are loaded for transport to the field hospital. The remaining casualties must wait for a second MEDEVAC, which is approximately 30 minutes away.",
                'character': characters["Staff Sergeant James Miller"],
                'event_type': "http://example.org/military-medical-triage#MedicalEvacuation",
                'parameters': {
                    'evacuation_platform': "UH-60 Blackhawk MEDEVAC helicopter",
                    'destination': "Role 2 Field Hospital",
                    'next_available_transport': "30 minutes"
                }
            },
            
            # 7. Ethical Dilemma Event (Event) - Dilemma about treating expectant patient vs. others
            {
                'type': 'event',
                'event_time': base_date + timedelta(minutes=50),
                'description': "PVT Martinez (expectant/black) shows signs of consciousness and is in severe pain. SSG Miller faces an ethical dilemma about using limited morphine and medical attention on an expectant patient versus conserving these resources for casualties with higher survival probability. This represents the classic tension between utilitarian approaches (greatest good for greatest number) and duty-based ethics (care for all patients regardless of prognosis).",
                'character': characters["Staff Sergeant James Miller"],
                'event_type': "http://example.org/military-medical-triage#EthicalDilemmaEvent",
                'parameters': {
                    'dilemma_type': "Resource allocation for expectant casualty",
                    'competing_values': ["Duty to all patients", "Utilitarian resource management", "Compassionate care"],
                    'time_pressure': "High - second MEDEVAC approaching"
                }
            },
            
            # 8. Treatment Action (Action) - Continued treatment of remaining casualties
            {
                'type': 'action',
                'action_time': base_date + timedelta(minutes=55),
                'name': "Provide Continued Care to Remaining Casualties",
                'description': "SSG Miller and PFC Rodriguez continue to provide care to the remaining casualties while awaiting the second MEDEVAC. They must monitor vital signs, redress wounds, and manage pain with limited resources. This includes making ongoing decisions about resource allocation and treatment priorities.",
                'character': characters["Staff Sergeant James Miller"],
                'action_type': "http://example.org/military-medical-triage#TreatmentAction",
                'parameters': {
                    'casualties_remaining': 3,
                    'resources_remaining': "Critically limited",
                    'treatment_focus': "Stabilization and pain management"
                },
                'is_decision': False
            },
            
            # 9. Arrival of Additional Medical Personnel (Event) - LT Chen arrives with additional resources
            {
                'type': 'event',
                'event_time': base_date + timedelta(minutes=70),
                'description': "Lieutenant Sarah Chen, a Combat Paramedic/Provider, arrives at the scene with additional medical supplies and equipment. Her arrival changes the resource equation and brings higher-level medical capabilities, but still requires difficult decisions about casualty management and evacuation priorities for the remaining patients.",
                'character': characters["Lieutenant Sarah Chen"],
                'event_type': "http://example.org/military-medical-triage#TreatmentEvent",
                'parameters': {
                    'additional_resources': ["Advanced airway equipment", "Additional blood products", "Advanced medications"],
                    'new_capabilities': "Advanced procedures including surgical airways and chest tubes",
                    'impact': "Improved care options but still insufficient for all casualties"
                }
            }
        ]
        
        # Add timeline items
        for item in timeline_items:
            if item['type'] == 'event':
                # Create event
                event = Event(
                    scenario_id=scenario.id,
                    character_id=item['character'].id if 'character' in item and item['character'] else None,
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
