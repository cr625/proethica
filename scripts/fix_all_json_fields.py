#!/usr/bin/env python
import os
import sys
import json

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.character import Character
from app.models.event import Event, Action
from sqlalchemy.exc import SQLAlchemyError

def fix_json_field(obj, field_name):
    """Fix a JSON field to ensure it's stored as a Python dictionary."""
    field_value = getattr(obj, field_name)
    fixed = False
    
    # Check if the field is a string and convert it to a dictionary
    if isinstance(field_value, str):
        try:
            print(f"{obj.__class__.__name__} {obj.id}: Converting {field_name} from string to dict")
            setattr(obj, field_name, json.loads(field_value))
            fixed = True
        except json.JSONDecodeError:
            print(f"{obj.__class__.__name__} {obj.id}: Invalid JSON in {field_name}, setting to empty dict")
            setattr(obj, field_name, {})
            fixed = True
    # Check if the field is None
    elif field_value is None:
        print(f"{obj.__class__.__name__} {obj.id}: {field_name} is None, setting to empty dict")
        setattr(obj, field_name, {})
        fixed = True
    # Make sure it's actually a dict
    elif not isinstance(field_value, dict):
        print(f"{obj.__class__.__name__} {obj.id}: {field_name} is not a dict, setting to empty dict")
        setattr(obj, field_name, {})
        fixed = True
    
    return fixed

def fix_character_attributes():
    """Fix character attributes."""
    print("\nFixing Character Attributes")
    characters = Character.query.all()
    print(f"Found {len(characters)} characters to process")
    
    fixed_count = 0
    
    for character in characters:
        try:
            # Fix attributes field
            if fix_json_field(character, 'attributes'):
                fixed_count += 1
                
            # Handle role_id if it's an empty string
            if character.role_id == '':
                print(f"Character {character.id}: Setting empty string role_id to None")
                character.role_id = None
                fixed_count += 1
                
        except Exception as e:
            print(f"Error processing character {character.id}: {str(e)}")
    
    return fixed_count

def fix_event_parameters():
    """Fix event parameters."""
    print("\nFixing Event Parameters")
    events = Event.query.all()
    print(f"Found {len(events)} events to process")
    
    fixed_count = 0
    
    for event in events:
        try:
            # Fix parameters field
            if fix_json_field(event, 'parameters'):
                fixed_count += 1
                
        except Exception as e:
            print(f"Error processing event {event.id}: {str(e)}")
    
    return fixed_count

def fix_action_parameters():
    """Fix action parameters."""
    print("\nFixing Action Parameters")
    actions = Action.query.all()
    print(f"Found {len(actions)} actions to process")
    
    fixed_count = 0
    
    for action in actions:
        try:
            # Fix parameters field
            if fix_json_field(action, 'parameters'):
                fixed_count += 1
                
            # Fix options field for decision actions
            if action.is_decision and hasattr(action, 'options'):
                options = action.options
                options_fixed = False
                
                if isinstance(options, str):
                    try:
                        print(f"Action {action.id}: Converting options from string to list")
                        action.options = json.loads(options)
                        options_fixed = True
                    except json.JSONDecodeError:
                        print(f"Action {action.id}: Invalid JSON in options, setting to empty list")
                        action.options = []
                        options_fixed = True
                elif options is None:
                    print(f"Action {action.id}: Options is None, setting to empty list")
                    action.options = []
                    options_fixed = True
                elif not isinstance(options, list):
                    print(f"Action {action.id}: Options is not a list, setting to empty list")
                    action.options = []
                    options_fixed = True
                
                if options_fixed:
                    fixed_count += 1
                
        except Exception as e:
            print(f"Error processing action {action.id}: {str(e)}")
    
    return fixed_count

def fix_all_json_fields():
    """Fix all JSON fields in the database."""
    print("Starting JSON fields fix script")
    
    total_fixed = 0
    total_fixed += fix_character_attributes()
    total_fixed += fix_event_parameters()
    total_fixed += fix_action_parameters()
    
    # Commit changes to the database
    if total_fixed > 0:
        try:
            db.session.commit()
            print(f"\nSuccessfully fixed {total_fixed} database records")
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"\nDatabase error: {str(e)}")
    else:
        print("\nNo records needed fixing")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        fix_all_json_fields()
