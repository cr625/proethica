#!/usr/bin/env python3
"""
Fix event parameters that might be stored as strings instead of JSON.
This script finds all events in the database and ensures their parameters
are properly stored as JSON objects.
"""

import sys
import os
import json

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.event import Event

def fix_event_parameters():
    """
    Find all events with parameters stored as strings and convert them to JSON objects.
    """
    print("Fixing event parameters...")
    
    # Create app context
    app = create_app()
    with app.app_context():
        events = Event.query.all()
        
        fixed_count = 0
        for event in events:
            # Check if parameters is a string
            if event.parameters and isinstance(event.parameters, str):
                try:
                    # Try to parse the string as JSON
                    parameters_dict = json.loads(event.parameters)
                    event.parameters = parameters_dict
                    fixed_count += 1
                    print(f"Fixed event {event.id} parameters")
                except json.JSONDecodeError:
                    # If it's not valid JSON, set it to an empty dict
                    print(f"WARNING: Event {event.id} has invalid JSON parameters: {event.parameters}")
                    event.parameters = {}
                    fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"Fixed {fixed_count} events with string parameters")
        else:
            print("No events with string parameters found")

if __name__ == "__main__":
    fix_event_parameters()
    print("Done!")
