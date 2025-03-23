#!/usr/bin/env python3
"""
Script for adding characters to the "Mass Casualty Triage" scenario in the 
"Tactical Combat Casualty Care (US Army)" world in the AI Ethical Decision-Making Simulator.

This script adds eight characters that represent different roles in a mass casualty incident:
1. Staff Sergeant James Miller - Combat Medic/Corpsman (CMC) - Main character making triage decisions
2. Private First Class Emma Rodriguez - Combat Lifesaver (CLS) - Assisting with treatment
3. Lieutenant Sarah Chen - Combat Paramedic/Provider (CPP) - Senior medical officer arriving later
4. Sergeant Michael Johnson - Patient with severe hemorrhage (Immediate/Red)
5. Corporal David Williams - Patient with blast injuries (Immediate/Red)
6. Private Thomas Garcia - Patient with penetration wounds (Delayed/Yellow)
7. Specialist Robert Lee - Patient with minor injuries (Minimal/Green)
8. Private First Class Kevin Martinez - Patient with catastrophic injuries (Expectant/Black)

Usage:
1. Run the script: python -m prompts.add_mass_casualty_triage_characters
"""

import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.role import Role

# Configuration
SCENARIO_ID = 5  # "Mass Casualty Triage" scenario
WORLD_ID = 1     # "Tactical Combat Casualty Care (US Army)" world

# Character definitions
# Format: [name, role_uri, role_name, tier, [conditions]]
# Where conditions is a list of [condition_uri, condition_name, description, severity]
CHARACTERS = [
    # Staff Sergeant James Miller - Combat Medic/Corpsman (CMC)
    [
        "Staff Sergeant James Miller",
        "http://example.org/military-medical-triage#CombatMedicCorpsman",
        "Combat Medic/Corpsman (CMC)",
        3,  # Tier 3
        []  # No medical conditions
    ],
    
    # Private First Class Emma Rodriguez - Combat Lifesaver (CLS)
    [
        "Private First Class Emma Rodriguez",
        "http://example.org/military-medical-triage#CombatLifeSaver",
        "Combat Lifesaver (CLS)",
        2,  # Tier 2
        []  # No medical conditions
    ],
    
    # Lieutenant Sarah Chen - Combat Paramedic/Provider (CPP)
    [
        "Lieutenant Sarah Chen",
        "http://example.org/military-medical-triage#CombatParamedicProvider",
        "Combat Paramedic/Provider (CPP)",
        4,  # Tier 4
        []  # No medical conditions
    ],
    
    # Sergeant Michael Johnson - Patient with severe hemorrhage (Immediate/Red)
    [
        "Sergeant Michael Johnson",
        "http://example.org/military-medical-triage#Patient",
        "Patient",
        None,  # Not applicable for patients
        [
            [
                "http://example.org/military-medical-triage#Hemorrhage",
                "Severe Hemorrhage",
                "Severe bleeding from shrapnel wounds to the right leg, with femoral artery involvement. Requires immediate intervention to prevent death from blood loss.",
                9  # Severity 9/10
            ]
        ]
    ],
    
    # Corporal David Williams - Patient with blast injuries (Immediate/Red)
    [
        "Corporal David Williams",
        "http://example.org/military-medical-triage#Patient",
        "Patient",
        None,  # Not applicable for patients
        [
            [
                "http://example.org/military-medical-triage#BlastInjury",
                "Blast Injury",
                "Primary and secondary blast injuries from IED explosion, including suspected pneumothorax, internal bleeding, and multiple shrapnel wounds to torso and face.",
                8  # Severity 8/10
            ]
        ]
    ],
    
    # Private Thomas Garcia - Patient with penetration wounds (Delayed/Yellow)
    [
        "Private Thomas Garcia",
        "http://example.org/military-medical-triage#Patient",
        "Patient",
        None,  # Not applicable for patients
        [
            [
                "http://example.org/military-medical-triage#PenetrationWound",
                "Penetration Wound",
                "Multiple shrapnel wounds to left arm and shoulder. Significant bleeding but controllable with pressure dressings. No major arterial involvement.",
                6  # Severity 6/10
            ]
        ]
    ],
    
    # Specialist Robert Lee - Patient with minor injuries (Minimal/Green)
    [
        "Specialist Robert Lee",
        "http://example.org/military-medical-triage#Patient",
        "Patient",
        None,  # Not applicable for patients
        [
            [
                "http://example.org/military-medical-triage#PenetrationWound",
                "Minor Penetration Wound",
                "Superficial shrapnel wounds to right arm and back. Minimal bleeding, ambulatory, and able to assist with other casualties if needed.",
                3  # Severity 3/10
            ]
        ]
    ],
    
    # Private First Class Kevin Martinez - Patient with catastrophic injuries (Expectant/Black)
    [
        "Private First Class Kevin Martinez",
        "http://example.org/military-medical-triage#Patient",
        "Patient",
        None,  # Not applicable for patients
        [
            [
                "http://example.org/military-medical-triage#BlastInjury",
                "Catastrophic Blast Injury",
                "Massive trauma from being in close proximity to IED explosion. Includes traumatic amputation of both legs, severe head trauma, and extensive internal injuries. Unlikely to survive even with immediate advanced care.",
                10  # Severity 10/10
            ]
        ]
    ]
]

def add_characters_to_scenario():
    """Add defined characters to the Mass Casualty Triage scenario."""
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
        
        print(f'Adding characters to scenario: {scenario.name} (ID: {scenario.id})')
        print(f'World ID: {scenario.world_id}')
        
        # Process each character
        for char_def in CHARACTERS:
            name, role_uri, role_name, tier, conditions = char_def
            
            # Check if character already exists
            existing_char = Character.query.filter_by(
                name=name, 
                scenario_id=scenario.id
            ).first()
            
            if existing_char:
                print(f'Character "{name}" already exists in this scenario. Skipping.')
                continue
            
            # Get or create role
            role = Role.query.filter_by(
                ontology_uri=role_uri, 
                world_id=scenario.world_id
            ).first()
            
            if not role:
                # Create the role
                role = Role(
                    name=role_name,
                    description=f'Role created for {name}',
                    world_id=scenario.world_id,
                    ontology_uri=role_uri,
                    tier=tier
                )
                db.session.add(role)
                db.session.flush()
                print(f'Created role: {role_name} (ID: {role.id})')
            
            # Create the character
            character = Character(
                name=name,
                scenario_id=scenario.id,
                role_id=role.id,
                role=role_name,
                attributes={}
            )
            db.session.add(character)
            db.session.flush()
            print(f'Added character: {name} (ID: {character.id})')
            
            # Add conditions if any
            for cond_def in conditions:
                cond_uri, cond_name, description, severity = cond_def
                
                # Get or create condition type
                cond_type = ConditionType.query.filter_by(
                    ontology_uri=cond_uri, 
                    world_id=scenario.world_id
                ).first()
                
                if not cond_type:
                    # Create the condition type
                    cond_type = ConditionType(
                        name=cond_name,
                        description=f'Condition type for {cond_name}',
                        world_id=scenario.world_id,
                        ontology_uri=cond_uri,
                        category='Medical'
                    )
                    db.session.add(cond_type)
                    db.session.flush()
                    print(f'Created condition type: {cond_name} (ID: {cond_type.id})')
                
                # Create the condition
                condition = Condition(
                    character_id=character.id,
                    name=cond_name,
                    description=description,
                    severity=severity,
                    condition_type_id=cond_type.id
                )
                db.session.add(condition)
                print(f'Added condition: {cond_name} (Severity: {severity}) to {name}')
            
        # Commit all changes
        db.session.commit()
        print('All characters added successfully!')

def verify_characters():
    """Verify that characters were added correctly."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        print(f'\nVerifying characters in scenario: {scenario.name}')
        print(f'Number of characters: {len(scenario.characters)}')
        
        for character in scenario.characters:
            print(f'\n- {character.name} (Role: {character.role})')
            conditions = Condition.query.filter_by(character_id=character.id).all()
            if conditions:
                print('  Conditions:')
                for condition in conditions:
                    print(f'  - {condition.name} (Severity: {condition.severity})')
                    print(f'    Description: {condition.description}')
            else:
                print('  No conditions')

if __name__ == "__main__":
    # Add characters
    add_characters_to_scenario()
    
    # Verify characters were added correctly
    verify_characters()
