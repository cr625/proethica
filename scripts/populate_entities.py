#!/usr/bin/env python3
"""
Consolidated script for populating entities (roles, condition types, resource types) in the ProEthica system.
This script replaces the following scripts:
- populate_condition_types.py
- populate_resource_types.py 
- populate_from_ontology.py
- populate_military_roles.py
- test_add_action.py
- test_add_action_and_event.py

Usage:
1. Populate entity types from ontology:
   python populate_entities.py --world "Engineering Ethics" --ontology

2. Populate predefined entity types:
   python populate_entities.py --world "Engineering Ethics" --predefined

3. Add test actions and events to a scenario:
   python populate_entities.py --scenario 1 --test-timeline
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.world import World
from app.models.scenario import Scenario
from utilities.entity_manager import (
    populate_entity_types_from_ontology,
    create_timeline_event,
    create_timeline_action
)

# Predefined entity types for different worlds
ENTITY_TYPES = {
    "Military Medical Triage": {
        "condition_types": [
            {
                "name": "Hemorrhage",
                "description": "Severe bleeding that requires immediate intervention.",
                "category": "Injury",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#Hemorrhage"
            },
            {
                "name": "Tension Pneumothorax",
                "description": "Air trapped in the pleural space causing lung collapse and cardiovascular compromise.",
                "category": "Injury",
                "severity_range": {"min": 5, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#TensionPneumothorax"
            },
            {
                "name": "Airway Obstruction",
                "description": "Blockage of the airway that impedes breathing.",
                "category": "Injury",
                "severity_range": {"min": 4, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#AirwayObstruction"
            },
            {
                "name": "Burn",
                "description": "Tissue damage caused by heat, chemicals, electricity, or radiation.",
                "category": "Injury",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#Burn"
            }
        ],
        "roles": [
            {
                "name": "Combat Medic",
                "description": "Medical personnel who provide first aid and trauma care in combat situations.",
                "tier": 1,
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#CombatMedic"
            },
            {
                "name": "Battalion Surgeon",
                "description": "Physician assigned to a military battalion to provide advanced medical care.",
                "tier": 2,
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#BattalionSurgeon"
            },
            {
                "name": "Casualty",
                "description": "Military personnel who has been wounded or injured during combat.",
                "tier": 0,
                "ontology_uri": "http://proethica.org/ontology/military-medical-triage#Casualty"
            }
        ]
    },
    "Engineering Ethics": {
        "condition_types": [
            {
                "name": "Budget Constraint",
                "description": "Limited financial resources affecting project decisions.",
                "category": "Resource",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#BudgetConstraint"
            },
            {
                "name": "Time Pressure",
                "description": "Urgent deadline affecting quality and safety considerations.",
                "category": "Operational",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#TimePressure"
            },
            {
                "name": "Safety Risk",
                "description": "Potential for harm to users or the public.",
                "category": "Safety",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#SafetyRisk"
            },
            {
                "name": "Environmental Impact",
                "description": "Potential negative effects on the environment.",
                "category": "Environmental",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#EnvironmentalImpact"
            }
        ],
        "roles": [
            {
                "name": "Structural Engineer",
                "description": "Engineer specializing in structural analysis and design.",
                "tier": 2,
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#StructuralEngineer"
            },
            {
                "name": "Project Manager",
                "description": "Professional responsible for project planning and execution.",
                "tier": 3,
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#ProjectManager"
            },
            {
                "name": "Client",
                "description": "Organization commissioning the engineering project.",
                "tier": 1,
                "ontology_uri": "http://proethica.org/ontology/engineering-ethics#Client"
            }
        ]
    },
    "Law Practice": {
        "condition_types": [
            {
                "name": "Conflict of Interest",
                "description": "Situation where professional judgment may be compromised.",
                "category": "Ethical",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#ConflictOfInterest"
            },
            {
                "name": "Client Confidentiality Risk",
                "description": "Potential breach of client confidentiality.",
                "category": "Ethical",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#ClientConfidentialityRisk"
            },
            {
                "name": "Legal Deadline",
                "description": "Time-sensitive legal filing or action required.",
                "category": "Procedural",
                "severity_range": {"min": 1, "max": 10},
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#LegalDeadline"
            },
            {
                "name": "Resource Limitation",
                "description": "Limited access to legal resources or research materials.",
                "category": "Resource",
                "severity_range": {"min": 1, "max": 8},
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#ResourceLimitation"
            }
        ],
        "roles": [
            {
                "name": "Attorney",
                "description": "Legal professional licensed to practice law.",
                "tier": 2,
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#Attorney"
            },
            {
                "name": "Partner",
                "description": "Attorney with ownership stake in a law firm.",
                "tier": 3,
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#Partner"
            },
            {
                "name": "Client",
                "description": "Individual or entity seeking legal representation.",
                "tier": 1,
                "ontology_uri": "http://proethica.org/ontology/nj-legal-ethics#Client"
            }
        ]
    }
}

def populate_predefined_entity_types(world_name):
    """
    Populate predefined condition types and roles for a specified world.
    
    Args:
        world_name: Name of the world to populate with entity types
    """
    from app.models.condition_type import ConditionType
    from app.models.role import Role
    
    app = create_app()
    with app.app_context():
        # Get the world
        world = World.query.filter_by(name=world_name).first()
        if not world:
            print(f"Error: World '{world_name}' not found")
            return
        
        # Check if the world has predefined entity types
        if world_name not in ENTITY_TYPES:
            print(f"Error: No predefined entity types for world '{world_name}'")
            return
        
        # Get the predefined entity types for the world
        world_entity_types = ENTITY_TYPES[world_name]
        
        # Populate condition types
        for condition_data in world_entity_types.get("condition_types", []):
            # Check if the condition type already exists
            existing = ConditionType.query.filter_by(
                name=condition_data["name"],
                world_id=world.id
            ).first()
            
            if existing:
                print(f"Updating condition type: {condition_data['name']}")
                existing.description = condition_data["description"]
                existing.category = condition_data["category"]
                existing.severity_range = condition_data["severity_range"]
                existing.ontology_uri = condition_data["ontology_uri"]
            else:
                print(f"Creating condition type: {condition_data['name']}")
                condition_type = ConditionType(
                    name=condition_data["name"],
                    description=condition_data["description"],
                    world_id=world.id,
                    category=condition_data["category"],
                    severity_range=condition_data["severity_range"],
                    ontology_uri=condition_data["ontology_uri"]
                )
                db.session.add(condition_type)
        
        # Populate roles
        for role_data in world_entity_types.get("roles", []):
            # Check if the role already exists
            existing = Role.query.filter_by(
                name=role_data["name"],
                world_id=world.id
            ).first()
            
            if existing:
                print(f"Updating role: {role_data['name']}")
                existing.description = role_data["description"]
                existing.tier = role_data["tier"]
                existing.ontology_uri = role_data["ontology_uri"]
            else:
                print(f"Creating role: {role_data['name']}")
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    world_id=world.id,
                    tier=role_data["tier"],
                    ontology_uri=role_data["ontology_uri"]
                )
                db.session.add(role)
        
        # Commit changes
        db.session.commit()
        print(f"Successfully populated entity types for world '{world_name}'")

def populate_from_ontology(world_name):
    """
    Populate entity types from the world's ontology.
    
    Args:
        world_name: Name of the world to populate with entity types
    """
    app = create_app()
    with app.app_context():
        # Get the world
        world = World.query.filter_by(name=world_name).first()
        if not world:
            print(f"Error: World '{world_name}' not found")
            return
        
        # Check if the world has an ontology source
        if not world.ontology_source:
            print(f"Error: World '{world_name}' has no ontology_source")
            return
        
        # Populate entity types from the ontology
        try:
            result = populate_entity_types_from_ontology(world.id)
            print(f"Created/updated {result['roles']} roles")
            print(f"Created/updated {result['condition_types']} condition types")
            print(f"Created/updated {result['resource_types']} resource types")
            print(f"Successfully populated entity types for world '{world_name}' from ontology")
        except Exception as e:
            print(f"Error populating entity types from ontology: {e}")

def add_test_timeline(scenario_id):
    """
    Add test timeline items (events and actions) to a scenario.
    
    Args:
        scenario_id: ID of the scenario to add timeline items to
    """
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            print(f"Error: Scenario with ID {scenario_id} not found")
            return
        
        # Get characters (if any)
        character_id = None
        if scenario.characters:
            character_id = scenario.characters[0].id
            print(f"Using character: {scenario.characters[0].name} (ID: {character_id})")
        else:
            print("Warning: No characters in scenario, creating timeline items without a character")
        
        # Base time for the timeline
        base_time = datetime.now()
        
        # Add a test event
        event = create_timeline_event(
            scenario_id=scenario.id,
            description="Test event for timeline styling",
            character_id=character_id,
            event_time=base_time,
            parameters={"location": "Test location", "importance": "high"}
        )
        print(f"Created event with ID: {event.id}")
        
        # Add a test action
        action = create_timeline_action(
            scenario_id=scenario.id,
            name="Test Action",
            description="This is a test action to verify the timeline styling",
            character_id=character_id,
            action_time=base_time + timedelta(minutes=5),
            action_type="test",
            parameters={"purpose": "testing"}
        )
        print(f"Created action with ID: {action.id}")
        
        # Add a test decision
        decision = create_timeline_action(
            scenario_id=scenario.id,
            name="Test Decision",
            description="This is a test decision to verify the timeline styling",
            character_id=character_id,
            action_time=base_time + timedelta(minutes=10),
            action_type="test",
            parameters={"purpose": "testing decisions"},
            is_decision=True,
            options=[
                "Option 1: Do this",
                "Option 2: Do that",
                "Option 3: Do something else"
            ]
        )
        print(f"Created decision with ID: {decision.id}")
        
        print(f"Successfully added test timeline items to scenario '{scenario.name}' (ID: {scenario.id})")

def main():
    parser = argparse.ArgumentParser(description='Populate entities in the ProEthica system')
    parser.add_argument('--world', type=str, help='Name of the world to populate')
    parser.add_argument('--scenario', type=int, help='ID of the scenario to add test timeline items to')
    parser.add_argument('--ontology', action='store_true', help='Populate entity types from ontology')
    parser.add_argument('--predefined', action='store_true', help='Populate predefined entity types')
    parser.add_argument('--test-timeline', action='store_true', help='Add test timeline items to a scenario')
    
    args = parser.parse_args()
    
    if args.world and args.ontology:
        populate_from_ontology(args.world)
    elif args.world and args.predefined:
        populate_predefined_entity_types(args.world)
    elif args.scenario and args.test_timeline:
        add_test_timeline(args.scenario)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
