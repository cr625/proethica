#!/usr/bin/env python3
"""
Script to add characters to Scenario 1 (Building Inspection Safety vs. Confidentiality).
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models.character import Character
from app.models.scenario import Scenario
from app.services.entity_triple_service import EntityTripleService

def add_characters_to_scenario1():
    """Add characters to Scenario 1."""
    app = create_app()
    with app.app_context():
        # Get Scenario 1
        scenario = Scenario.query.get(1)
        if not scenario:
            print("Error: Scenario 1 not found")
            return False
            
        print(f"Found scenario: {scenario.name} (ID: {scenario.id})")
        
        # Initialize the entity triple service
        entity_triple_service = EntityTripleService()
        
        # Check if characters already exist for this scenario and delete them
        existing_characters = Character.query.filter_by(scenario_id=scenario.id).all()
        if existing_characters:
            print(f"Found {len(existing_characters)} existing characters for scenario {scenario.id}:")
            for char in existing_characters:
                print(f"- {char.name}: {char.role}")
            
            print("Deleting existing characters...")
            for char in existing_characters:
                db.session.delete(char)
            db.session.commit()
            print("Existing characters deleted.")
        
        # Add new characters
        characters = [
            {
                "name": "Engineer Smith",
                "role": "Structural Engineer",
                "tier": 1,  # Primary character
                "attributes": {
                    "expertise": "building structure",
                    "years_experience": 15,
                }
            },
            {
                "name": "Building Owner Johnson",
                "role": "Client",
                "tier": 2,  # Secondary character
                "attributes": {
                    "business_focused": True,
                    "selling_property": True
                }
            },
            {
                "name": "Building Occupants",
                "role": "Stakeholders",
                "tier": 3,  # Tertiary character
                "attributes": {
                    "at_risk": True,
                    "unaware_of_dangers": True
                }
            }
        ]
        
        # Create and add characters
        for char_data in characters:
            character = Character(
                name=char_data["name"],
                role=char_data["role"],
                scenario_id=scenario.id,
                attributes=char_data.get("attributes", {})
            )
            
            db.session.add(character)
            print(f"Added character: {character.name} ({character.role})")
            
            # Create RDF triples for the character
            try:
                entity_triple_service.create_triples_for_character(character)
                print(f"Created RDF triples for {character.name}")
            except Exception as e:
                print(f"Warning: Could not create RDF triples for {character.name}: {str(e)}")
        
        # Commit all changes
        db.session.commit()
        print(f"Successfully added {len(characters)} characters to Scenario 1")
        
        return True

if __name__ == "__main__":
    add_characters_to_scenario1()
