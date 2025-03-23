#!/usr/bin/env python3
"""
Script template for adding characters to scenarios in the AI Ethical Decision-Making Simulator.
This template can be customized for different scenarios and characters.

Usage:
1. Modify the SCENARIO_ID and character definitions as needed
2. Run the script: python add_characters_script_template.py
"""

from app import create_app, db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.role import Role

# Configuration
SCENARIO_ID = 3  # Replace with the ID of your target scenario

# Character definitions
# Format: [name, role_uri, role_name, tier, [conditions]]
# Where conditions is a list of [condition_uri, condition_name, description, severity]
CHARACTERS = [
    # Example: Michael Reynolds (Partner) with Conflict of Interest
    [
        "Michael Reynolds",
        "http://example.org/nj-legal-ethics#Partner",
        "Partner",
        3,  # Senior level
        [
            [
                "http://example.org/nj-legal-ethics#ConflictOfInterest",
                "Conflict of Interest",
                "Representing clients with competing interests",
                8
            ]
        ]
    ],
    # Example: Horizon Technologies Inc. (Corporate Client) with no conditions
    [
        "Horizon Technologies Inc.",
        "http://example.org/nj-legal-ethics#CorporateClient",
        "Corporate Client",
        None,
        []
    ],
    # Add more characters as needed...
]

def add_characters_to_scenario():
    """Add defined characters to the specified scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
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
                        category='http://www.w3.org/2002/07/owl#Class'
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
