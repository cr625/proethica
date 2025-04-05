#!/usr/bin/env python3
"""
Simple script to verify that character roles are properly set.
Directly checks a character in the database to verify both role_id and legacy role field.
"""

import os
import sys

# Add the project root to the Python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.character import Character
from app.models.role import Role

# This should be a real character ID from your database
CHARACTER_ID = 47

app = create_app()

def verify_character_role():
    """Verify that a character's role_id and role fields are in sync"""
    with app.app_context():
        print("Checking character role consistency...")
        
        # Get the character
        character = Character.query.get(CHARACTER_ID)
        if not character:
            print(f"Error: Character with ID {CHARACTER_ID} not found!")
            return
        
        print(f"Character: {character.name}")
        print(f"  role_id: {character.role_id}")
        print(f"  role (legacy): '{character.role}'")
        
        # Get the role from the role_id
        if character.role_id:
            role = Role.query.get(character.role_id)
            if role:
                print(f"Role from role_id: {role.name}")
                
                # Check if they match
                if character.role == role.name:
                    print("\n✅ ROLE VERIFIED: Both role_id and legacy role field are synchronized correctly")
                else:
                    print("\n❌ ROLE MISMATCH: role_id points to '{role.name}' but legacy role field is '{character.role}'")
            else:
                print(f"Error: Role with ID {character.role_id} not found!")
        else:
            print("Character has no role_id assigned")

if __name__ == "__main__":
    verify_character_role()
