#!/usr/bin/env python3
"""
Script to check the ontology source of the Engineering Ethics world.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def check_world_ontology():
    """
    Check the ontology source of the Engineering Ethics world.
    """
    app = create_app()
    with app.app_context():
        from app.models.world import World
        
        # Get the Engineering Ethics world
        world = World.query.filter_by(id=1).first()
        if not world:
            print("Error: Engineering Ethics world not found")
            return
        
        print(f"Engineering Ethics World: {world.name}")
        print(f"Ontology Source: {world.ontology_source}")
        
        return world

if __name__ == "__main__":
    check_world_ontology()
