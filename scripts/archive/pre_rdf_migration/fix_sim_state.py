#!/usr/bin/env python
"""
Script to delete the problematic simulation state (ID: 179) that's preventing world deletion.
"""

import os
import sys
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

def fix_sim_state():
    """Delete the problematic simulation state."""
    print("Attempting to delete simulation state with ID 179")
    
    session = db.session
    
    # First, check if the state exists
    check_query = text("SELECT id, session_id, scenario_id FROM simulation_states WHERE id = 179")
    result = session.execute(check_query).fetchone()
    
    if not result:
        print("No simulation state with ID 179 found.")
        return
    
    print(f"Found simulation state: {result}")
    
    # Try to directly delete the state
    try:
        delete_query = text("DELETE FROM simulation_states WHERE id = 179")
        session.execute(delete_query)
        session.commit()
        print("Successfully deleted simulation state with ID 179.")
    except Exception as e:
        session.rollback()
        print(f"Error deleting state: {e}")
        
        # Try a more advanced approach: first set scenario_id to a valid value
        try:
            print("Trying to set scenario_id to a valid value first...")
            
            # Find a valid scenario ID
            scenario_query = text("SELECT id FROM scenarios LIMIT 1")
            scenario_id = session.execute(scenario_query).fetchone()[0]
            
            update_query = text(f"UPDATE simulation_states SET scenario_id = {scenario_id} WHERE id = 179")
            session.execute(update_query)
            session.commit()
            print(f"Set scenario_id to {scenario_id}. Now trying to delete again...")
            
            # Now try to delete
            session.execute(delete_query)
            session.commit()
            print("Successfully deleted simulation state with ID 179.")
        except Exception as e2:
            session.rollback()
            print(f"Error with alternate approach: {e2}")
            
            # Last resort: alter the constraint 
            try:
                print("Trying to temporarily alter the constraint...")
                # Temporarily disable the constraint
                disable_query = text("ALTER TABLE simulation_states ALTER COLUMN scenario_id DROP NOT NULL")
                session.execute(disable_query)
                session.commit()
                
                # Try to delete again
                session.execute(delete_query)
                session.commit()
                print("Successfully deleted simulation state with ID 179.")
                
                # Restore the constraint
                restore_query = text("ALTER TABLE simulation_states ALTER COLUMN scenario_id SET NOT NULL")
                session.execute(restore_query)
                session.commit()
                print("Restored NOT NULL constraint on scenario_id.")
            except Exception as e3:
                session.rollback()
                print(f"Failed with constraint approach: {e3}")
                print("Could not delete simulation state with ID 179.")

def main():
    """Run the script."""
    app = create_app()
    
    with app.app_context():
        fix_sim_state()

if __name__ == "__main__":
    main()
