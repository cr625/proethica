#!/usr/bin/env python3
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.world import World
from app.models.character import Character
from app.models.resource import Resource
from app.models.condition import Condition

def main():
    app = create_app()
    with app.app_context():
        scenario_id = 6  # Default to scenario 6
        
        # Check if a scenario ID was provided
        if len(sys.argv) > 1:
            try:
                scenario_id = int(sys.argv[1])
            except ValueError:
                print(f"Invalid scenario ID: {sys.argv[1]}")
                return
        
        scenario = Scenario.query.get(scenario_id)
        if scenario:
            print(f'Scenario {scenario.id}: {scenario.name}')
            print(f'Description: {scenario.description}')
            print(f'World ID: {scenario.world_id}')
            
            # Get world info
            world = World.query.get(scenario.world_id)
            print(f'World: {world.name if world else "Unknown"}')
            print(f'Ontology Source: {world.ontology_source if world else "Unknown"}')
            
            # List characters
            characters = Character.query.filter_by(scenario_id=scenario.id).all()
            print(f'\nCharacters ({len(characters)}):')
            for char in characters:
                print(f"- {char.name}: {char.role}")
                
                # List conditions for each character
                conditions = Condition.query.filter_by(character_id=char.id).all()
                if conditions:
                    print(f"  Conditions ({len(conditions)}):")
                    for condition in conditions:
                        print(f"    • {condition.name}: {condition.description} (Severity: {condition.severity})")
            
            # List resources
            resources = Resource.query.filter_by(scenario_id=scenario.id).all()
            print(f'\nResources ({len(resources)}):')
            for resource in resources:
                print(f"- {resource.name}: {resource.type}")
                print(f"  Description: {resource.description}")
                print(f"  Quantity: {resource.quantity}")
        else:
            print(f'Scenario {scenario_id}: Not found')

if __name__ == '__main__':
    main()
