#!/usr/bin/env python3
from app import create_app
from app.models.world import World

app = create_app()
with app.app_context():
    world = World.query.get(1)
    if world:
        print(f"World 1 ontology_source: {world.ontology_source}")
        print(f"World 1 ontology_id: {world.ontology_id}")
    else:
        print("World with ID 1 not found")
