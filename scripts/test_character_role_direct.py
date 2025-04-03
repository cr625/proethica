#!/usr/bin/env python3
"""
Test script to verify the character role update directly in the database.
This script bypasses the API and directly tests the functionality in the database.
"""

import os
import sys
from datetime import datetime

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.role import Role
from app.routes.scenarios import update_character as update_character_route

app = create_app()

# Change this to your actual scenario and character ID
# You can get these from the URL when editing a character
SCENARIO_ID = 16  # Update this to a real scenario ID
CHARACTER_ID = 47  # Update this to a real character ID

class MockRequest:
    """A mock request object that simulates a Flask request with JSON data"""
    def __init__(self, json_data):
        self._json = json_data
    
    @property
    def json(self):
        return self._json

class MockResponse:
    """A mock response object that captures the JSON returned by a route function"""
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

def jsonify_mock(data):
    """A mock of Flask's jsonify function"""
    return MockResponse(data)

def test_direct_update():
    """Test the character update function directly"""
    with app.app_context():
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f"Scenario with ID {SCENARIO_ID} not found!")
            return
        
        character = Character.query.get(CHARACTER_ID)
        if not character:
            print(f"Character with ID {CHARACTER_ID} not found!")
            return
        
        world_id = scenario.world_id
        
        # Setup two test roles
        print(f"\nCreating test roles in world {world_id}...")
        role1 = Role(
            name="Test Role Direct 1",
            description="A test role for direct DB testing",
            world_id=world_id,
            tier=1
        )
        
        role2 = Role(
            name="Test Role Direct 2",
            description="Another test role for direct DB testing",
            world_id=world_id,
            tier=2
        )
        
        db.session.add(role1)
        db.session.add(role2)
        db.session.commit()
        
        role1_id = role1.id
        role2_id = role2.id
        
        print(f"Created Role 1: {role1.name} (ID: {role1_id})")
        print(f"Created Role 2: {role2.name} (ID: {role2_id})")
        
        # Show initial character state
        print(f"\nInitial character state:")
        print(f"  Name: {character.name}")
        print(f"  role_id: {character.role_id}")
        print(f"  role (legacy): {character.role}")
        
        try:
            # Directly update the character with the first test role
            print(f"\nUpdating character with role_id: {role1_id}")
            
            # For direct database update with our fix:
            character.role_id = role1_id
            
            # Get the role entity to update the legacy role field
            role = Role.query.get(role1_id)
            if role:
                character.role = role.name
            
            db.session.commit()
            
            # Refresh the character from the database
            db.session.refresh(character)
            
            print(f"\nCharacter state after direct update:")
            print(f"  Name: {character.name}")
            print(f"  role_id: {character.role_id} (should be {role1_id})")
            print(f"  role (legacy): {character.role} (should be '{role1.name}')")
            
            if character.role_id == role1_id and character.role == role1.name:
                print("\n✅ DIRECT UPDATE PASSED: Both role_id and legacy role field were updated correctly")
            else:
                print("\n❌ DIRECT UPDATE FAILED: Role updates were not synchronized correctly")
            
            # Now update with role2 to test a change
            print(f"\nUpdating character with role_id: {role2_id}")
            
            # Method 2: Test using the route logic but bypass authentication
            # Create a mock request with the payload
            mock_request = MockRequest({
                "name": character.name,
                "role_id": role2_id,
                "conditions": []
            })
            
            # Save the original jsonify function
            import app.routes.scenarios
            original_jsonify = app.routes.scenarios.jsonify
            
            # Replace with our mock
            app.routes.scenarios.jsonify = jsonify_mock
            
            # Call the route function directly
            result = update_character_route(SCENARIO_ID, CHARACTER_ID)
            
            # Restore original jsonify
            app.routes.scenarios.jsonify = original_jsonify
            
            print(f"Route function result: {result.data}")
            
            # Refresh the character from the database
            db.session.refresh(character)
            
            print(f"\nCharacter state after route function update:")
            print(f"  Name: {character.name}")
            print(f"  role_id: {character.role_id} (should be {role2_id})")
            print(f"  role (legacy): {character.role} (should be '{role2.name}')")
            
            if character.role_id == role2_id and character.role == role2.name:
                print("\n✅ ROUTE UPDATE PASSED: Both role_id and legacy role field were updated correctly")
            else:
                print("\n❌ ROUTE UPDATE FAILED: Role updates were not synchronized correctly")
            
        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up test roles
            try:
                # First restore original character role if needed
                if character.role_id in (role1_id, role2_id):
                    print("\nRestoring original character role...")
                    character.role_id = 21  # Original role_id from initial state
                    character.role = "Structural Engineer Role"  # Original role name
                    db.session.commit()
                
                # Now delete the test roles
                Role.query.filter(Role.id.in_([role1_id, role2_id])).delete(synchronize_session=False)
                db.session.commit()
                print("\nTest roles removed")
            except Exception as e:
                print(f"Error removing test roles: {e}")

if __name__ == "__main__":
    test_direct_update()
