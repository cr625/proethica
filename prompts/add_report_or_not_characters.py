#!/usr/bin/env python3
"""
Script for adding characters to the "Report or Not" scenario in the 
"Engineering Ethics (US)" world in the AI Ethical Decision-Making Simulator.

This script adds six characters that represent different perspectives in an engineering
ethics situation involving whether to report a deficiency:
1. Alex Rodriguez - Senior Engineer who discovers the deficiency
2. Morgan Chen - Project Manager concerned with deadlines and budget
3. Taylor Williams - Junior Engineer also aware of the deficiency
4. Dr. Jordan Patel - Engineering Director with higher-level authority
5. Sam Washington - Compliance Officer responsible for regulatory compliance
6. Westridge Development Corporation - Corporate Client commissioning the work

Usage:
1. Run the script: python -m prompts.add_report_or_not_characters
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
SCENARIO_ID = 2  # "Report or Not" scenario
WORLD_ID = 2     # "Engineering Ethics (US)" world

# Character definitions
# Format: [name, role_uri, role_name, tier, [conditions]]
# Where conditions is a list of [condition_uri, condition_name, description, severity]
CHARACTERS = [
    # Alex Rodriguez (Senior Engineer) with Conflict of Interest
    [
        "Alex Rodriguez",
        "http://example.org/engineering-ethics#SeniorEngineer",
        "Senior Engineer",
        3,  # Senior level
        [
            [
                "http://example.org/engineering-ethics#ConflictOfInterest",
                "Conflict of Interest",
                "Torn between professional obligation to report a deficiency and pressure to meet project deadlines and budget constraints.",
                8
            ],
            [
                "http://example.org/engineering-ethics#PublicSafetyRisk",
                "Public Safety Risk",
                "Aware that the deficiency could potentially impact public safety if not addressed properly.",
                7
            ]
        ]
    ],
    
    # Morgan Chen (Project Manager) with Time Constraint
    [
        "Morgan Chen",
        "http://example.org/engineering-ethics#ProjectManager",
        "Project Manager",
        2,  # Mid level
        [
            [
                "http://example.org/engineering-ethics#TimeConstraint",
                "Time Constraint",
                "Under significant pressure to complete the project on schedule, which could be jeopardized by addressing the deficiency.",
                9
            ],
            [
                "http://example.org/engineering-ethics#BudgetConstraint",
                "Budget Constraint",
                "Managing tight budget constraints that would be impacted by fixing the reported deficiency.",
                8
            ]
        ]
    ],
    
    # Taylor Williams (Junior Engineer) with Ethical Dilemma
    [
        "Taylor Williams",
        "http://example.org/engineering-ethics#JuniorEngineer",
        "Junior Engineer",
        1,  # Entry level
        [
            [
                "http://example.org/engineering-ethics#EthicalCondition",
                "Ethical Dilemma",
                "Struggling with loyalty to the team versus professional responsibility to support reporting the deficiency.",
                6
            ]
        ]
    ],
    
    # Dr. Jordan Patel (Engineering Director) with Conflict of Interest
    [
        "Dr. Jordan Patel",
        "http://example.org/engineering-ethics#EngineeringDirector",
        "Engineering Director",
        4,  # Executive level
        [
            [
                "http://example.org/engineering-ethics#ConflictOfInterest",
                "Conflict of Interest",
                "Balancing company reputation and client relationships with ethical obligations to ensure safety and quality.",
                7
            ]
        ]
    ],
    
    # Sam Washington (Compliance Officer) with Regulatory Noncompliance awareness
    [
        "Sam Washington",
        "http://example.org/engineering-ethics#ComplianceOfficer",
        "Compliance Officer",
        2,  # Mid level
        [
            [
                "http://example.org/engineering-ethics#RegulatoryNoncompliance",
                "Regulatory Noncompliance",
                "Responsible for ensuring the project meets all regulatory requirements and industry standards.",
                8
            ]
        ]
    ],
    
    # Westridge Development Corporation (Corporate Client) with Budget Constraint
    [
        "Westridge Development Corporation",
        "http://example.org/engineering-ethics#CorporateClient",
        "Corporate Client",
        None,  # Not applicable for clients
        [
            [
                "http://example.org/engineering-ethics#BudgetConstraint",
                "Budget Constraint",
                "Has strict budget limitations for the project and would resist additional costs to address the deficiency.",
                9
            ]
        ]
    ]
]

def add_characters_to_scenario():
    """Add defined characters to the Report or Not scenario."""
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
