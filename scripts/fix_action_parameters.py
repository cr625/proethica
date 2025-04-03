#!/usr/bin/env python3
"""
Fix action parameters that might be stored as strings instead of JSON.
This script finds all actions in the database and ensures their parameters
are properly stored as JSON objects.
"""

import sys
import os
import json

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.event import Action

def fix_action_parameters():
    """
    Find all actions with parameters stored as strings and convert them to JSON objects.
    """
    print("Fixing action parameters...")
    
    # Create app context
    app = create_app()
    with app.app_context():
        actions = Action.query.all()
        
        fixed_count = 0
        for action in actions:
            # Check if parameters is a string
            if action.parameters and isinstance(action.parameters, str):
                try:
                    # Try to parse the string as JSON
                    parameters_dict = json.loads(action.parameters)
                    action.parameters = parameters_dict
                    fixed_count += 1
                    print(f"Fixed action {action.id} ({action.name}) parameters")
                except json.JSONDecodeError:
                    # If it's not valid JSON, set it to an empty dict
                    print(f"WARNING: Action {action.id} ({action.name}) has invalid JSON parameters: {action.parameters}")
                    action.parameters = {}
                    fixed_count += 1
            
            # Also check if options is a string (for decision actions)
            if action.options and isinstance(action.options, str):
                try:
                    # Try to parse the string as JSON
                    options_list = json.loads(action.options)
                    action.options = options_list
                    fixed_count += 1
                    print(f"Fixed action {action.id} ({action.name}) options")
                except json.JSONDecodeError:
                    # If it's not valid JSON, set it to an empty list
                    print(f"WARNING: Action {action.id} ({action.name}) has invalid JSON options: {action.options}")
                    action.options = []
                    fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"Fixed {fixed_count} actions with string parameters or options")
        else:
            print("No actions with string parameters or options found")

if __name__ == "__main__":
    fix_action_parameters()
    print("Done!")
