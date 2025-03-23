from app import create_app
from app.models.world import World

# Create app and push application context
app = create_app()
with app.app_context():
    # Query all worlds
    worlds = World.query.all()

    print(f"Found {len(worlds)} worlds in the database:")
    print("-" * 50)

    for world in worlds:
        print(f"ID: {world.id}")
        print(f"Name: {world.name}")
        print(f"Description: {world.description}")
        print(f"Ontology Source: {world.ontology_source}")
        print(f"Guidelines URL: {world.guidelines_url}")
        print(f"Guidelines Text: {world.guidelines_text}")
        print(f"Cases: {world.cases}")
        print(f"Rulesets: {world.rulesets}")
        print(f"Metadata: {world.world_metadata}")
        print("-" * 50)
