#!/usr/bin/env python
"""
Script to directly delete a world and all its related data using SQL.
This bypasses the ORM to avoid any model-related issues.
"""

import os
import sys
import argparse
from sqlalchemy import text

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

def delete_world_sql(world_id, force=False):
    """Delete a world and all related data using direct SQL."""
    session = db.session
    
    # Check if the world exists
    world_check = session.execute(
        text("SELECT id, name FROM worlds WHERE id = :id"),
        {"id": world_id}
    ).fetchone()
    
    if not world_check:
        print(f"World with ID {world_id} not found.")
        return False
    
    world_name = world_check[1]
    print(f"Found world: {world_name} (ID: {world_id})")
    
    # Get scenario IDs for this world
    scenario_ids_result = session.execute(
        text("SELECT id FROM scenarios WHERE world_id = :world_id"),
        {"world_id": world_id}
    ).fetchall()
    
    scenario_ids = [row[0] for row in scenario_ids_result]
    print(f"Found {len(scenario_ids)} related scenarios: {scenario_ids}")
    
    if not force:
        confirmation = input(
            f"\nAre you sure you want to delete world '{world_name}' with ID {world_id} and all related data? "
            f"This action cannot be undone. (y/N): "
        )
        if confirmation.lower() != 'y':
            print("Deletion cancelled.")
            return False
    
    # Start deletion with a transaction
    try:
        # For each scenario, delete related data
        for scenario_id in scenario_ids:
            # 1. Delete any entity triples related to the scenario
            session.execute(
                text("DELETE FROM entity_triples WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted entity triples for scenario {scenario_id}")
            
            # 2. Delete character triples
            session.execute(
                text("""
                    DELETE FROM character_triples 
                    WHERE character_id IN (SELECT id FROM characters WHERE scenario_id = :scenario_id)
                """),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted character triples for scenario {scenario_id}")
            
            # 3. Delete simulation states
            session.execute(
                text("DELETE FROM simulation_states WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted simulation states for scenario {scenario_id}")
            
            # 4. Delete simulation sessions
            session.execute(
                text("DELETE FROM simulation_sessions WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted simulation sessions for scenario {scenario_id}")
            
            # 5. Delete actions associated with events in this scenario
            session.execute(
                text("""
                    DELETE FROM actions 
                    WHERE id IN (SELECT action_id FROM events WHERE scenario_id = :scenario_id)
                """),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted actions for scenario {scenario_id}")
            
            # 6. Delete events
            session.execute(
                text("DELETE FROM events WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted events for scenario {scenario_id}")
            
            # 7. Delete characters
            session.execute(
                text("DELETE FROM characters WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted characters for scenario {scenario_id}")
            
            # 8. Delete resources
            session.execute(
                text("DELETE FROM resources WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted resources for scenario {scenario_id}")
            
            # 9. Delete resource types associated with the scenario
            session.execute(
                text("DELETE FROM resource_types WHERE scenario_id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted resource types for scenario {scenario_id}")
            
            # 10. Delete the scenario itself
            session.execute(
                text("DELETE FROM scenarios WHERE id = :scenario_id"),
                {"scenario_id": scenario_id}
            )
            print(f"- Deleted scenario {scenario_id}")
        
        # 11. Handle any remaining simulation states with this world_id in state_data
        session.execute(
            text("DELETE FROM simulation_states WHERE state_data->>'world_id' = :world_id"),
            {"world_id": str(world_id)}
        )
        print("- Deleted any additional simulation states referencing this world")
        
        # 12. Delete resource types associated with the world
        session.execute(
            text("DELETE FROM resource_types WHERE world_id = :world_id"),
            {"world_id": world_id}
        )
        print("- Deleted resource types for world")
        
        # 13. Finally delete the world
        session.execute(
            text("DELETE FROM worlds WHERE id = :world_id"),
            {"world_id": world_id}
        )
        print("- Deleted the world")
        
        # Commit all changes
        session.commit()
        print(f"\nWorld '{world_name}' with ID {world_id} has been successfully deleted.")
        
        return True
    
    except Exception as e:
        session.rollback()
        print(f"Error during deletion: {e}")
        print("Deletion failed. No changes were made to the database.")
        return False

def main():
    """Run the script."""
    parser = argparse.ArgumentParser(description='Force delete a world and all related data')
    parser.add_argument('world_id', type=int, help='ID of the world to delete')
    parser.add_argument('--force', '-f', action='store_true', help='Force deletion without confirmation')
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        result = delete_world_sql(args.world_id, args.force)
        
        if result:
            print("World deletion completed successfully.")
        else:
            print("World deletion failed or was cancelled.")

if __name__ == "__main__":
    main()
