#!/usr/bin/env python3
"""
Non-interactive script to clean up incorrectly created NSPE scenarios.
This script removes the scenarios that were mistakenly created as NSPE cases,
as cases should be associated with worlds directly, not with scenarios.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def cleanup_nspe_scenarios_auto():
    """
    Remove the NSPE scenarios that were incorrectly created.
    """
    app = create_app()
    with app.app_context():
        from app.models.scenario import Scenario
        from app.models.entity_triple import EntityTriple
        
        # The IDs of the scenarios to remove
        # Based on the output of check_worlds_and_scenarios.py
        nspe_scenario_ids = [2, 3, 4]  # NSPE Case 22-5, NSPE Case 23-4, NSPE Case 22-10
        
        print(f"Looking for {len(nspe_scenario_ids)} NSPE scenarios to remove...")
        
        # Get the scenarios
        scenarios_to_remove = Scenario.query.filter(Scenario.id.in_(nspe_scenario_ids)).all()
        
        if not scenarios_to_remove:
            print("No NSPE scenarios found to remove.")
            return
        
        print(f"Found {len(scenarios_to_remove)} NSPE scenarios to remove:")
        for scenario in scenarios_to_remove:
            print(f"  - ID {scenario.id}: {scenario.name}")
        
        # Count triples associated with each scenario
        for scenario in scenarios_to_remove:
            triple_count = EntityTriple.query.filter_by(scenario_id=scenario.id).count()
            print(f"  - ID {scenario.id}: {scenario.name} has {triple_count} associated triples")
        
        # Remove the scenarios
        for scenario in scenarios_to_remove:
            try:
                # Delete associated entity triples first
                num_triples_deleted = EntityTriple.query.filter_by(scenario_id=scenario.id).delete()
                
                # Delete the scenario
                db.session.delete(scenario)
                
                print(f"Deleted scenario ID {scenario.id}: {scenario.name} with {num_triples_deleted} triples")
            except Exception as e:
                print(f"Error deleting scenario ID {scenario.id}: {str(e)}")
                db.session.rollback()
        
        # Commit the changes
        try:
            db.session.commit()
            print("Successfully removed the NSPE scenarios.")
        except Exception as e:
            print(f"Error committing changes: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    cleanup_nspe_scenarios_auto()
