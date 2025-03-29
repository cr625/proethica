#!/usr/bin/env python3
import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.world import World
from app.models.character import Character

def main():
    app = create_app()
    with app.app_context():
        scenario = Scenario.query.get(6)
        if scenario:
            print(f'Scenario 6: {scenario.name}')
            print(f'Description: {scenario.description}')
            print(f'World ID: {scenario.world_id}')
            
            world = World.query.get(scenario.world_id)
            print(f'World: {world.name if world else "Unknown"}')
            print(f'Ontology Source: {world.ontology_source if world else "Unknown"}')
            
            # List existing characters
            characters = Character.query.filter_by(scenario_id=scenario.id).all()
            print(f'\nExisting Characters ({len(characters)}):')
            for char in characters:
                print(f"- {char.name}: {char.role}")
        else:
            print('Scenario 6: Not found')

if __name__ == '__main__':
    main()
