#!/usr/bin/env python
import os
import sys
import json

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.character import Character
from sqlalchemy.exc import SQLAlchemyError

def fix_character_attributes():
    """Fix character attributes to ensure they are stored as Python dictionaries."""
    print("Starting character attributes fix script")
    
    # Get all characters
    characters = Character.query.all()
    print(f"Found {len(characters)} characters to process")
    
    fixed_count = 0
    
    for character in characters:
        try:
            # Check if attributes is a string and convert it to a dictionary
            if isinstance(character.attributes, str):
                try:
                    print(f"Character {character.id}: Converting attributes from string to dict")
                    character.attributes = json.loads(character.attributes)
                    fixed_count += 1
                except json.JSONDecodeError:
                    print(f"Character {character.id}: Invalid JSON in attributes, setting to empty dict")
                    character.attributes = {}
                    fixed_count += 1
            elif character.attributes is None:
                print(f"Character {character.id}: Attributes is None, setting to empty dict")
                character.attributes = {}
                fixed_count += 1
                
            # Make sure it's a dict
            if not isinstance(character.attributes, dict):
                print(f"Character {character.id}: Attributes is not a dict, setting to empty dict")
                character.attributes = {}
                fixed_count += 1
                
            # Handle role_id if it's an empty string
            if character.role_id == '':
                print(f"Character {character.id}: Setting empty string role_id to None")
                character.role_id = None
                fixed_count += 1
                
        except Exception as e:
            print(f"Error processing character {character.id}: {str(e)}")
    
    # Commit changes to the database
    if fixed_count > 0:
        try:
            db.session.commit()
            print(f"Successfully fixed {fixed_count} character records")
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Database error: {str(e)}")
    else:
        print("No characters needed fixing")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        fix_character_attributes()
