#!/usr/bin/env python
"""
Script demonstrating how to integrate RDF triples storage with the existing character model.
This shows how to transparently store character data as RDF triples while maintaining
compatibility with the existing application code.
"""

import os
import sys
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.role import Role
from app.models.world import World
from app.models.triple import Triple
from app.services.rdf_service import RDFService
from app.services.embedding_service import EmbeddingService
from sqlalchemy import event

def setup_character_observers():
    """
    Set up SQLAlchemy event listeners to automatically convert characters to RDF triples.
    This demonstrates how to make the RDF storage transparent to the application code.
    """
    rdf_service = RDFService()
    embedding_service = EmbeddingService()
    
    @event.listens_for(Character, 'after_insert')
    def character_after_insert(mapper, connection, character):
        """Convert a new character to RDF triples after it's inserted."""
        print(f"Character inserted: {character.name} (ID: {character.id})")
        # Converting to triples requires a db session, so we need to do it in a separate session
        db.session.flush()  # Ensure character has an ID
        triples = rdf_service.character_to_triples(character, commit=True)
        print(f"Created {len(triples)} RDF triples for character")
        
        # Add embeddings for the triples (async in a real app)
        for triple in triples:
            embedding_service.update_triple_embeddings(triple, commit=False)
        db.session.commit()
    
    @event.listens_for(Character, 'after_update')
    def character_after_update(mapper, connection, character):
        """Synchronize character changes to RDF triples after an update."""
        print(f"Character updated: {character.name} (ID: {character.id})")
        # Delete existing triples and create new ones
        rdf_service.sync_character(character, commit=True)
        print("Synchronized character changes to RDF triples")

def test_transparent_integration():
    """Test the transparent integration between characters and RDF triples."""
    app = create_app()
    
    with app.app_context():
        # Set up event listeners
        setup_character_observers()
        
        # Initialize services
        rdf_service = RDFService()
        
        print("Testing transparent integration between characters and RDF triples...")
        
        # Get engineering ethics world
        world = World.query.filter_by(name="Engineering Ethics (US)").first()
        if not world:
            print("Engineering Ethics world not found. Please run test_character_rdf_triples.py first.")
            return
        
        # Get scenario
        from app.models.scenario import Scenario
        scenario = Scenario.query.filter_by(world_id=world.id).first()
        if not scenario:
            print("No scenario found. Please run test_character_rdf_triples.py first.")
            return
        
        # Get role
        role = Role.query.filter_by(name="JuniorEngineer", world_id=world.id).first()
        if not role:
            print("JuniorEngineer role not found. Please run test_character_rdf_triples.py first.")
            return
        
        # Create a new character - this should automatically create RDF triples
        print("\nCreating a new character - this should automatically create RDF triples...")
        character = Character(
            scenario_id=scenario.id,
            name="Alex Rodriguez",
            role_id=role.id,
            attributes={
                "yearsOfExperience": 3,
                "specialization": "Electrical Engineering",
                "education": "B.S. Electrical Engineering",
                "supervisor": "Jane Smith",
                "ethicalPriorities": ["learning", "following_instructions", "team_work"]
            }
        )
        
        db.session.add(character)
        db.session.commit()
        
        # Verify RDF triples were created
        print("\nVerifying RDF triples were created...")
        triples = rdf_service.find_triples(character_id=character.id)
        print(f"Found {len(triples)} triples for the new character")
        
        # Show some sample triples
        print("\nSample triples:")
        for i, triple in enumerate(triples[:5]):
            print(f"{i+1}. {triple.subject} {triple.predicate} {triple.object}")
        
        if len(triples) > 5:
            print(f"...and {len(triples) - 5} more triples")
            
        # Update the character - this should automatically update the RDF triples
        print("\nUpdating the character - this should automatically update the RDF triples...")
        character.attributes["yearsOfExperience"] = 4
        character.attributes["project"] = "Smart Grid Deployment"
        db.session.commit()
        
        # Verify RDF triples were updated
        print("\nVerifying RDF triples were updated...")
        updated_triples = rdf_service.find_triples(character_id=character.id)
        print(f"Found {len(updated_triples)} triples for the updated character")
        
        # Demonstrate SPARQL-like querying
        print("\nDemonstrating SPARQL-like querying for character data...")
        
        # Find all junior engineers
        junior_engineers = rdf_service.find_characters_by_triple_pattern(
            predicate=str(rdf_service.namespaces['proethica'].hasRole),
            obj="JuniorEngineer",
            is_literal=True
        )
        
        print(f"\nFound {len(junior_engineers)} Junior Engineers:")
        for eng in junior_engineers:
            print(f"- {eng.name}")
            
        # Find characters supervised by Jane Smith
        supervised_chars = rdf_service.find_characters_by_triple_pattern(
            predicate=str(rdf_service.namespaces['proethica'].supervisor),
            obj="Jane Smith",
            is_literal=True
        )
        
        print(f"\nFound {len(supervised_chars)} characters supervised by Jane Smith:")
        for char in supervised_chars:
            print(f"- {char.name}")
        
        # Simulate deleting a character - in a full integration, we would add an event listener for this
        print("\nSimulating character deletion - this should delete related RDF triples...")
        rdf_service.delete_triples(character_id=character.id)
        
        remaining_triples = rdf_service.find_triples(character_id=character.id)
        print(f"Remaining triples after deletion: {len(remaining_triples)}")

def main():
    """Run the integration test."""
    test_transparent_integration()
    print("\nIntegration test completed")

if __name__ == "__main__":
    main()
