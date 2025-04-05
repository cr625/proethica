#!/usr/bin/env python3
"""
Script to list NSPE ethics cases that have been imported into the database.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def list_nspe_ethics_cases():
    """
    List all NSPE ethics cases in the database.
    """
    app = create_app()
    with app.app_context():
        from app.models.scenario import Scenario
        from app.models.world import World
        from app.models.entity_triple import EntityTriple
        
        # Get the Engineering Ethics world
        world = World.query.filter_by(id=1).first()
        if not world:
            print("Error: Engineering Ethics world not found")
            return
        
        print(f"Engineering Ethics World: {world.name}")
        print("=" * 50)
        
        # Get all scenarios for this world that were imported from NSPE cases
        scenarios = Scenario.query.filter_by(world_id=world.id).all()
        
        nspe_scenarios = []
        for scenario in scenarios:
            # Check if it's an NSPE case by looking at the name or metadata
            if scenario.name.startswith("NSPE Case") or (scenario.scenario_metadata and "NSPE" in str(scenario.scenario_metadata)):
                nspe_scenarios.append(scenario)
        
        # Sort scenarios by creation date (newest first)
        nspe_scenarios = sorted(nspe_scenarios, key=lambda s: s.created_at, reverse=True)
        
        print(f"Found {len(nspe_scenarios)} NSPE ethics cases:")
        print("=" * 50)
        
        # List each case with some details
        for i, scenario in enumerate(nspe_scenarios):
            # Count triples for this scenario
            triple_count = EntityTriple.query.filter_by(scenario_id=scenario.id).count()
            
            # Extract metadata if available
            metadata = scenario.scenario_metadata or {}
            
            # Get case number and source if available
            case_number = metadata.get('case_number', '')
            if not case_number:
                # Try to extract from the name
                if "Case" in scenario.name:
                    case_number = scenario.name.split("Case", 1)[1].strip()
            
            # Get the principles
            principles = metadata.get('principles', [])
            principles_str = ", ".join(principles) if principles else "N/A"
            
            # Get the outcome
            outcome = metadata.get('outcome', 'Unknown')
            
            # Get source URL
            source = metadata.get('source', '')
            
            # Print the case details
            print(f"{i+1}. {scenario.name} (ID: {scenario.id})")
            print(f"   Description: {scenario.description[:100]}..." if scenario.description and len(scenario.description) > 100 else f"   Description: {scenario.description}")
            print(f"   Principles: {principles_str}")
            print(f"   Outcome: {outcome}")
            print(f"   Triple Count: {triple_count}")
            if source:
                print(f"   Source: {source}")
            print()
        
        print(f"Successfully found {len(nspe_scenarios)} NSPE ethics cases.")
        return nspe_scenarios

if __name__ == "__main__":
    list_nspe_ethics_cases()
