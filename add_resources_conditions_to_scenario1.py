#!/usr/bin/env python3
"""
Script to add resources and character conditions to Scenario 1.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models.character import Character
from app.models.resource import Resource
from app.models.condition import Condition
from app.models.scenario import Scenario

def add_resources_and_conditions():
    """Add resources to Scenario 1 and conditions to its characters."""
    app = create_app()
    with app.app_context():
        # Get Scenario 1
        scenario = Scenario.query.get(1)
        if not scenario:
            print("Error: Scenario 1 not found")
            return False
            
        print(f"Found scenario: {scenario.name} (ID: {scenario.id})")
        
        # ========== RESOURCES ==========
        
        # Check and remove existing resources
        existing_resources = Resource.query.filter_by(scenario_id=scenario.id).all()
        if existing_resources:
            print(f"Found {len(existing_resources)} existing resources for scenario {scenario.id}")
            print("Deleting existing resources...")
            for resource in existing_resources:
                db.session.delete(resource)
            db.session.commit()
            print("Existing resources deleted.")
        
        # Define resources to add
        resources = [
            {
                "name": "Building Structural Report",
                "type": "Document",
                "category": "Engineering Document",
                "quantity": 1,
                "description": "Report on the structural integrity of the building"
            },
            {
                "name": "Confidentiality Agreement",
                "type": "Legal Document",
                "category": "Contract",
                "quantity": 1,
                "description": "Legal agreement requiring the engineer to maintain confidentiality about findings"
            },
            {
                "name": "Building Code Guidelines",
                "type": "Reference Material",
                "category": "Regulatory",
                "quantity": 1,
                "description": "City regulations for building safety and code compliance"
            },
            {
                "name": "Professional Ethics Code",
                "type": "Reference Material",
                "category": "Professional Guidelines",
                "quantity": 1,
                "description": "Engineering code of ethics emphasizing public safety obligations"
            }
        ]
        
        # Add resources
        for resource_data in resources:
            resource = Resource(
                name=resource_data["name"],
                type=resource_data["type"],
                quantity=resource_data["quantity"],
                description=resource_data["description"],
                scenario_id=scenario.id
            )
            db.session.add(resource)
            print(f"Added resource: {resource.name} ({resource.type})")
        
        # Commit resource changes
        db.session.commit()
        print(f"Successfully added {len(resources)} resources to Scenario 1")
        
        # ========== CONDITIONS ==========
        
        # Get characters
        characters = Character.query.filter_by(scenario_id=scenario.id).all()
        if not characters:
            print("Error: No characters found for Scenario 1")
            return False
            
        # Check and remove existing conditions
        existing_conditions = Condition.query.filter(
            Condition.character_id.in_([c.id for c in characters])
        ).all()
        
        if existing_conditions:
            print(f"Found {len(existing_conditions)} existing conditions")
            print("Deleting existing conditions...")
            for condition in existing_conditions:
                db.session.delete(condition)
            db.session.commit()
            print("Existing conditions deleted.")
        
        # Define conditions for each character
        character_conditions = {
            "Engineer Smith": [
                {
                    "type": "Ethical Dilemma",
                    "category": "Professional",
                    "description": "Conflict between confidentiality and public safety obligations",
                    "severity": 8
                },
                {
                    "type": "Contractual Obligation",
                    "category": "Legal",
                    "description": "Bound by confidentiality agreement with client",
                    "severity": 7
                }
            ],
            "Building Owner Johnson": [
                {
                    "type": "Financial Pressure",
                    "category": "Economic",
                    "description": "Financial need to sell the building without further investment",
                    "severity": 8
                },
                {
                    "type": "Legal Liability",
                    "category": "Legal",
                    "description": "Potential liability for known safety issues",
                    "severity": 9
                }
            ],
            "Building Occupants": [
                {
                    "type": "Safety Risk",
                    "category": "Physical",
                    "description": "Exposed to potential safety hazards from building deficiencies",
                    "severity": 10
                },
                {
                    "type": "Lack of Information",
                    "category": "Knowledge",
                    "description": "Unaware of the potential dangers in the building",
                    "severity": 7
                }
            ]
        }
        
        # Add conditions to characters
        for character in characters:
            if character.name in character_conditions:
                for condition_data in character_conditions[character.name]:
                    condition = Condition(
                        name=condition_data["type"],  # Use name instead of type
                        description=condition_data["description"],
                        severity=condition_data["severity"],
                        character_id=character.id
                    )
                    db.session.add(condition)
                    print(f"Added condition '{condition.name}' to {character.name}")
        
        # Commit condition changes
        db.session.commit()
        print("Successfully added conditions to characters in Scenario 1")
        
        return True

if __name__ == "__main__":
    add_resources_and_conditions()
