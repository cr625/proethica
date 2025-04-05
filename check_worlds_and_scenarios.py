#!/usr/bin/env python3
"""
Script to check all worlds and their scenarios in the database.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def list_worlds_and_scenarios():
    """
    List all worlds and their scenarios in the database.
    """
    app = create_app()
    with app.app_context():
        from app.models.scenario import Scenario
        from app.models.world import World
        
        # Get all worlds
        worlds = World.query.all()
        print(f"Found {len(worlds)} worlds:")
        print("=" * 50)
        
        # Display each world and its scenarios
        for world in worlds:
            print(f"World: {world.name} (ID: {world.id})")
            print(f"Description: {world.description[:100]}..." if world.description and len(world.description) > 100 else f"Description: {world.description}")
            print(f"Created at: {world.created_at}")
            print(f"Updated at: {world.updated_at}")
            print()
            
            # Get scenarios for this world
            scenarios = Scenario.query.filter_by(world_id=world.id).all()
            print(f"  Found {len(scenarios)} scenarios for world {world.name}:")
            
            # List each scenario
            for i, scenario in enumerate(scenarios):
                print(f"  {i+1}. {scenario.name} (ID: {scenario.id})")
                print(f"     Description: {scenario.description[:100]}..." if scenario.description and len(scenario.description) > 100 else f"     Description: {scenario.description}")
                
                # Check if metadata contains any NSPE reference
                is_nspe = False
                if scenario.scenario_metadata:
                    scenario_metadata_str = str(scenario.scenario_metadata)
                    if "NSPE" in scenario_metadata_str or "nspe" in scenario_metadata_str or "Case" in scenario_metadata_str:
                        is_nspe = True
                
                print(f"     NSPE case: {'Yes' if is_nspe or scenario.name.startswith('NSPE') else 'No'}")
                print(f"     Created at: {scenario.created_at}")
                print()
            
            print("=" * 50)
        
        print(f"Successfully listed {len(worlds)} worlds and their scenarios.")
        return worlds

if __name__ == "__main__":
    list_worlds_and_scenarios()
