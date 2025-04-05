#!/usr/bin/env python3
"""
Script to create the simulation_sessions table in the database.
This table stores simulation session data including decisions, evaluations, and timeline states.
"""

import sys
import os
import json
from datetime import datetime

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db
from app.models.simulation_session import SimulationSession

def create_simulation_sessions_table():
    """Create the simulation_sessions table if it doesn't exist."""
    print("Creating simulation_sessions table...")
    
    # Import the create_app function
    from app import create_app
    
    # Create the Flask app
    app = create_app()
    
    # Create an application context
    with app.app_context():
        # Create the table
        db.create_all()
        
        # Check if the table was created
        engine = db.engine
        inspector = db.inspect(engine)
        if 'simulation_sessions' in inspector.get_table_names():
            print("Table 'simulation_sessions' created successfully.")
        else:
            print("Failed to create table 'simulation_sessions'.")
            return False
    
    return True

if __name__ == "__main__":
    create_simulation_sessions_table()
