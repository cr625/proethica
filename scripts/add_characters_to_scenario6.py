#!/usr/bin/env python3
import sys
import os
import json

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.world import World
from app.models.character import Character
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.role import Role
from app.models.resource import Resource
from app.models.resource_type import ResourceType
from app.services.mcp_client import MCPClient

def find_or_create_role(world_id, ontology_uri, role_name, role_description=None, tier=None):
    """Find a role by ontology URI or create if it doesn't exist"""
    role = Role.query.filter_by(ontology_uri=ontology_uri, world_id=world_id).first()
    if not role:
        role = Role(
            name=role_name,
            description=role_description or f"Role for {role_name}",
            world_id=world_id,
            ontology_uri=ontology_uri,
            tier=tier
        )
        db.session.add(role)
        db.session.flush()
        print(f"Created new role: {role_name} with ID {role.id}")
    else:
        print(f"Found existing role: {role.name} with ID {role.id}")
    return role

def find_or_create_condition_type(world_id, ontology_uri, name, description=None, category=None):
    """Find a condition type by ontology URI or create if it doesn't exist"""
    condition_type = ConditionType.query.filter_by(ontology_uri=ontology_uri, world_id=world_id).first()
    if not condition_type:
        condition_type = ConditionType(
            name=name,
            description=description or f"Condition type for {name}",
            world_id=world_id,
            category=category or "Ethical",
            ontology_uri=ontology_uri,
            severity_range={"min": 1, "max": 10}
        )
        db.session.add(condition_type)
        db.session.flush()
        print(f"Created new condition type: {name} with ID {condition_type.id}")
    else:
        print(f"Found existing condition type: {condition_type.name} with ID {condition_type.id}")
    return condition_type

def create_character_with_conditions(scenario_id, name, role, role_id, attributes, conditions=None):
    """Create a character with optional conditions"""
    character = Character(
        scenario_id=scenario_id,
        name=name,
        role=role,
        role_id=role_id,
        attributes=attributes
    )
    db.session.add(character)
    db.session.flush()
    print(f"Created character: {name} with ID {character.id}")
    
    if conditions:
        for condition_data in conditions:
            condition = Condition(
                character_id=character.id,
                name=condition_data['name'],
                description=condition_data.get('description', ''),
                severity=condition_data.get('severity', 5),
                condition_type_id=condition_data.get('condition_type_id')
            )
            db.session.add(condition)
            print(f"Added condition: {condition.name} to character {name}")
    
    return character

def add_characters_to_scenario_6(force=False):
    """Add characters to Scenario 6 (Building Inspection Confidentiality Dilemma)"""
    app = create_app()
    with app.app_context():
        # Get scenario 6
        scenario = Scenario.query.get(6)
        if not scenario:
            print("Scenario 6 not found")
            return
        
        # Get world
        world = World.query.get(scenario.world_id)
        if not world:
            print(f"World with ID {scenario.world_id} not found")
            return
        
        print(f"Adding characters to Scenario: {scenario.name}")
        print(f"World: {world.name}")
        print(f"Ontology: {world.ontology_source}")
        
        # Get MCP client
        mcp_client = MCPClient.get_instance()
        
        # Check if we already have characters
        existing_characters = Character.query.filter_by(scenario_id=scenario.id).all()
        if existing_characters and not force:
            print(f"Warning: Scenario already has {len(existing_characters)} characters")
            for char in existing_characters:
                print(f"- {char.name}: {char.role}")
            
            confirm = input("Do you want to continue and add more characters? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        try:
            # Get roles from ontology
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="roles")
            if not entities or 'entities' not in entities or 'roles' not in entities['entities']:
                print("Failed to get roles from ontology")
                return
            
            # Get condition types from ontology
            condition_entities = mcp_client.get_world_entities(world.ontology_source, entity_type="conditions")
            if not condition_entities or 'entities' not in condition_entities or 'conditions' not in condition_entities['entities']:
                print("Failed to get condition types from ontology")
                return
            
            # Find roles in ontology
            structural_engineer_role = None
            client_role = None
            regulator_role = None
            
            for role in entities['entities']['roles']:
                if role['label'] == "Structural Engineer":
                    structural_engineer_role = role
                elif role['label'] == "Client":
                    client_role = role
                elif role['label'] == "Regulator":
                    regulator_role = role
            
            # Find condition types in ontology
            confidentiality_condition = None
            ethical_conflict_condition = None
            building_deficiency_condition = None
            asis_property_condition = None
            
            for condition in condition_entities['entities']['conditions']:
                if condition['label'] == "Confidentiality Obligation":
                    confidentiality_condition = condition
                elif condition['label'] == "Ethical Principles Conflict":
                    ethical_conflict_condition = condition
                elif condition['label'] == "Building System Deficiency":
                    building_deficiency_condition = condition
                elif condition['label'] == "As-Is Property Condition":
                    asis_property_condition = condition
            
            # Create or find roles in database
            structural_engineer_db_role = None
            client_db_role = None
            regulator_db_role = None
            
            if structural_engineer_role:
                structural_engineer_db_role = find_or_create_role(
                    world_id=world.id,
                    ontology_uri=structural_engineer_role['id'],
                    role_name=structural_engineer_role['label'],
                    role_description=structural_engineer_role['description'],
                    tier=2  # Mid-Level
                )
            
            if client_role:
                client_db_role = find_or_create_role(
                    world_id=world.id,
                    ontology_uri=client_role['id'],
                    role_name=client_role['label'],
                    role_description=client_role['description'],
                    tier=1  # Entry-Level
                )
            
            if regulator_role:
                regulator_db_role = find_or_create_role(
                    world_id=world.id,
                    ontology_uri=regulator_role['id'],
                    role_name=regulator_role['label'],
                    role_description=regulator_role['description'],
                    tier=2  # Mid-Level
                )
            
            # Create or find condition types in database
            confidentiality_db_condition = None
            ethical_conflict_db_condition = None
            building_deficiency_db_condition = None
            asis_property_db_condition = None
            
            if confidentiality_condition:
                confidentiality_db_condition = find_or_create_condition_type(
                    world_id=world.id,
                    ontology_uri=confidentiality_condition['id'],
                    name=confidentiality_condition['label'],
                    description=confidentiality_condition['description'],
                    category="Ethical"
                )
            
            if ethical_conflict_condition:
                ethical_conflict_db_condition = find_or_create_condition_type(
                    world_id=world.id,
                    ontology_uri=ethical_conflict_condition['id'],
                    name=ethical_conflict_condition['label'],
                    description=ethical_conflict_condition['description'],
                    category="Ethical"
                )
            
            if building_deficiency_condition:
                building_deficiency_db_condition = find_or_create_condition_type(
                    world_id=world.id,
                    ontology_uri=building_deficiency_condition['id'],
                    name=building_deficiency_condition['label'],
                    description=building_deficiency_condition['description'],
                    category="Safety"
                )
            
            if asis_property_condition:
                asis_property_db_condition = find_or_create_condition_type(
                    world_id=world.id,
                    ontology_uri=asis_property_condition['id'],
                    name=asis_property_condition['label'],
                    description=asis_property_condition['description'],
                    category="Property"
                )
            
            # 1. Create Engineer A character
            engineer_conditions = []
            if confidentiality_db_condition:
                engineer_conditions.append({
                    'name': "Client Confidentiality Agreement",
                    'description': "Contractual obligation to maintain client confidentiality",
                    'severity': 8,
                    'condition_type_id': confidentiality_db_condition.id
                })
            
            if ethical_conflict_db_condition:
                engineer_conditions.append({
                    'name': "Duty to Public vs. Client Confidentiality",
                    'description': "Conflict between obligation to protect public safety and duty to maintain client confidentiality",
                    'severity': 9,
                    'condition_type_id': ethical_conflict_db_condition.id
                })
            
            engineer_a = create_character_with_conditions(
                scenario_id=scenario.id,
                name="Engineer A",
                role="Structural Engineer",
                role_id=structural_engineer_db_role.id if structural_engineer_db_role else None,
                attributes={
                    "years_experience": 12,
                    "license": "Professional Engineer",
                    "specialization": "Building Structural Integrity"
                },
                conditions=engineer_conditions
            )
            
            # 2. Create Building Owner/Client character
            client_conditions = []
            if asis_property_db_condition:
                client_conditions.append({
                    'name': "Selling Building As-Is",
                    'description': "Owner plans to sell the building without remediation of known issues",
                    'severity': 7,
                    'condition_type_id': asis_property_db_condition.id
                })
            
            if building_deficiency_db_condition:
                client_conditions.append({
                    'name': "Knowledge of Building Deficiencies",
                    'description': "Awareness of code violations in the building's electrical and mechanical systems",
                    'severity': 8,
                    'condition_type_id': building_deficiency_db_condition.id
                })
            
            building_owner = create_character_with_conditions(
                scenario_id=scenario.id,
                name="Building Owner",
                role="Client",
                role_id=client_db_role.id if client_db_role else None,
                attributes={
                    "business_type": "Property Management",
                    "owns_multiple_properties": True
                },
                conditions=client_conditions
            )
            
            # 3. Create Building Authority character
            authority_conditions = []
            
            building_authority = create_character_with_conditions(
                scenario_id=scenario.id,
                name="Building Safety Authority",
                role="Regulator",
                role_id=regulator_db_role.id if regulator_db_role else None,
                attributes={
                    "jurisdiction": "Local",
                    "enforcement_power": "Can issue violations and condemn unsafe buildings"
                },
                conditions=authority_conditions
            )
            
            # Commit all changes
            db.session.commit()
            print("Successfully added all characters to Scenario 6")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error adding characters: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Add characters to Scenario 6')
    parser.add_argument('--force', action='store_true', help='Force adding characters even if scenario already has characters')
    
    args = parser.parse_args()
    add_characters_to_scenario_6(force=args.force)
