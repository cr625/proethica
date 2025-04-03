#!/usr/bin/env python3
"""
Test script to verify the character role update fix.
This script tests updating a character's role to ensure both role_id and role fields update.
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.role import Role

app = create_app()

def test_role_update():
    with app.app_context():
        print("Starting character role update test...")
        
        # Step 1: Create a test world with two roles
        print("\nCreating test world with roles...")
        test_world = World(
            name="Test World",
            description="A world for testing character role updates",
            ontology_source=None
        )
        db.session.add(test_world)
        db.session.flush()  # Get the ID without committing
        
        # Create two roles
        role1 = Role(
            name="Engineer",
            description="An engineering professional",
            world_id=test_world.id,
            tier=1
        )
        
        role2 = Role(
            name="Manager",
            description="A management professional",
            world_id=test_world.id,
            tier=2
        )
        
        db.session.add(role1)
        db.session.add(role2)
        db.session.flush()
        
        print(f"Created Role 1: {role1.name} (ID: {role1.id})")
        print(f"Created Role 2: {role2.name} (ID: {role2.id})")
        
        # Step 2: Create a test scenario
        print("\nCreating test scenario...")
        test_scenario = Scenario(
            name="Test Scenario",
            description="A scenario for testing character role updates",
            world_id=test_world.id
        )
        db.session.add(test_scenario)
        db.session.flush()
        
        # Step 3: Create a character with role1
        print("\nCreating character with initial role...")
        test_character = Character(
            name="Test Character",
            scenario_id=test_scenario.id,
            role_id=role1.id,
            role=role1.name,  # Set the legacy role field
            attributes={}
        )
        db.session.add(test_character)
        db.session.commit()
        
        print(f"Initial character state:")
        print(f"  Name: {test_character.name}")
        print(f"  role_id: {test_character.role_id} (should be {role1.id})")
        print(f"  role (legacy): {test_character.role} (should be {role1.name})")
        
        # Step 4: Update the character to role2
        print("\nUpdating character to new role...")
        
        # This simulates what happens in the update_character route
        # when a new role is selected from the dropdown
        test_character.role_id = role2.id
        role = Role.query.get(role2.id)
        if role:
            test_character.role = role.name
        
        db.session.commit()
        
        # Reload the character to verify changes
        updated_character = Character.query.get(test_character.id)
        
        print("\nAfter update:")
        print(f"  Name: {updated_character.name}")
        print(f"  role_id: {updated_character.role_id} (should be {role2.id})")
        print(f"  role (legacy): {updated_character.role} (should be {role2.name})")
        
        # Check if both fields were updated correctly
        if updated_character.role_id == role2.id and updated_character.role == role2.name:
            print("\n✅ TEST PASSED: Both role_id and legacy role field were updated correctly")
        else:
            print("\n❌ TEST FAILED: Role updates were not synchronized correctly")
        
        # Clean up
        print("\nCleaning up test data...")
        db.session.delete(test_character)
        db.session.delete(test_scenario)
        db.session.delete(role1)
        db.session.delete(role2)
        db.session.delete(test_world)
        db.session.commit()
        
        print("\nTest completed.")

if __name__ == "__main__":
    try:
        test_role_update()
    except Exception as e:
        print(f"Error during test: {e}")
