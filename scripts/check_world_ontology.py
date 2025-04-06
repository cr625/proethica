#!/usr/bin/env python3
"""
Script to check the ontology source for World with ID 1
"""

import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.world import World

app = create_app()
with app.app_context():
    world = World.query.get(1)
    if world:
        print(f"World: {world.name}")
        print(f"Ontology Source: {world.ontology_source}")
    else:
        print("World with ID 1 not found")
