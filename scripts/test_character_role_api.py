#!/usr/bin/env python3
"""
Test script to verify the character role update through the API.
This script directly calls the update API endpoint that the form uses.
"""

import os
import sys
import json
import requests
from datetime import datetime

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.role import Role

# Change this to your actual scenario and character ID
# You can get these from the URL when editing a character
SCENARIO_ID = 16  # Update this to a real scenario ID
CHARACTER_ID = 47  # Update this to a real character ID

app = create_app()

def setup_test_roles(world_id):
    """Create test roles for the test"""
    with app.app_context():
        # Create two roles in the same world
        role1 = Role(
            name="Test Role 1",
            description="A test role for API testing",
            world_id=world_id,
            tier=1
        )
        
        role2 = Role(
            name="Test Role 2",
            description="Another test role for API testing",
            world_id=world_id,
            tier=2
        )
        
        db.session.add(role1)
        db.session.add(role2)
        db.session.commit()
        
        return role1.id, role2.id

def get_scenario_world_id(scenario_id):
    """Get the world ID for a scenario"""
    with app.app_context():
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            print(f"Scenario with ID {scenario_id} not found!")
            return None
        return scenario.world_id

def test_api_update():
    """Test updating a character through the API"""
    # First, get the world ID for the scenario
    world_id = get_scenario_world_id(SCENARIO_ID)
    if not world_id:
        return
    
    # Create test roles
    role1_id, role2_id = setup_test_roles(world_id)
    
    # Base URL for the API
    base_url = 'http://localhost:3333'  # Change if your server runs on a different port
    
    try:
        # First get the current character to see its initial state
        with app.app_context():
            character = Character.query.get(CHARACTER_ID)
            if not character:
                print(f"Character with ID {CHARACTER_ID} not found!")
                return
            
            print(f"Initial character state:")
            print(f"  Name: {character.name}")
            print(f"  role_id: {character.role_id}")
            print(f"  role (legacy): {character.role}")
        
        # Update character with new role (role1)
        update_url = f"{base_url}/scenarios/{SCENARIO_ID}/characters/{CHARACTER_ID}/update"
        
        payload = {
            "name": "Test Character API Update",
            "role_id": role1_id,
            "conditions": []
        }
        
        print(f"\nMaking API call to update character with role_id: {role1_id}")
        response = requests.post(update_url, json=payload)
        response_data = response.json()
        
        print(f"API Response: {response.status_code}")
        print(f"Response data: {json.dumps(response_data, indent=2)}")
        
        # Check the updated character state in the database
        with app.app_context():
            updated_character = Character.query.get(CHARACTER_ID)
            
            print(f"\nCharacter state after first update:")
            print(f"  Name: {updated_character.name}")
            print(f"  role_id: {updated_character.role_id} (should be {role1_id})")
            print(f"  role (legacy): {updated_character.role} (should be 'Test Role 1')")
            
            if updated_character.role_id == role1_id and updated_character.role == "Test Role 1":
                print("\n✅ FIRST UPDATE PASSED: Both role_id and legacy role field were updated correctly")
            else:
                print("\n❌ FIRST UPDATE FAILED: Role updates were not synchronized correctly")
        
        # Now update with role2 to test a change
        payload = {
            "name": "Test Character API Update",
            "role_id": role2_id,
            "conditions": []
        }
        
        print(f"\nMaking second API call to update character with role_id: {role2_id}")
        response = requests.post(update_url, json=payload)
        response_data = response.json()
        
        print(f"API Response: {response.status_code}")
        print(f"Response data: {json.dumps(response_data, indent=2)}")
        
        # Check the updated character state in the database
        with app.app_context():
            updated_character = Character.query.get(CHARACTER_ID)
            
            print(f"\nCharacter state after second update:")
            print(f"  Name: {updated_character.name}")
            print(f"  role_id: {updated_character.role_id} (should be {role2_id})")
            print(f"  role (legacy): {updated_character.role} (should be 'Test Role 2')")
            
            if updated_character.role_id == role2_id and updated_character.role == "Test Role 2":
                print("\n✅ SECOND UPDATE PASSED: Both role_id and legacy role field were updated correctly")
            else:
                print("\n❌ SECOND UPDATE FAILED: Role updates were not synchronized correctly")
        
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        # Clean up test roles
        with app.app_context():
            try:
                Role.query.filter(Role.id.in_([role1_id, role2_id])).delete(synchronize_session=False)
                db.session.commit()
                print("\nTest roles removed")
            except Exception as e:
                print(f"Error removing test roles: {e}")

if __name__ == "__main__":
    test_api_update()
