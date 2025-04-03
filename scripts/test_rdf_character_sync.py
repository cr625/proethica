#!/usr/bin/env python
"""
Test script to verify proper synchronization between character database records 
and their RDF triple representations.

This script demonstrates:
1. Creating a character
2. Verifying the character is properly represented in the RDF triple store
3. Updating the character's role
4. Verifying the RDF representation is updated
5. Deleting the character and confirming triples are removed
"""

import os
import sys
import json
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.role import Role
from app.models.scenario import Scenario
from app.models.world import World
from app.models.triple import Triple
from app.services.rdf_service import RDFService
from sqlalchemy import func

def setup_test_env():
    """Set up test environment with a world, scenario, and roles"""
    app = create_app()
    
    with app.app_context():
        print("Setting up test environment...")
        
        # Check if we have an engineering ethics world
        world = World.query.filter_by(name="Engineering Ethics (Test)").first()
        if not world:
            print("Creating test world...")
            world = World(
                name="Engineering Ethics (Test)",
                description="Engineering Ethics world for testing RDF triple synchronization",
                ontology_source="engineering-ethics.ttl",
                world_metadata={
                    "domain": "engineering",
                    "region": "Test",
                    "test": True
                }
            )
            db.session.add(world)
            db.session.flush()
        
        # Create a test scenario if it doesn't exist
        scenario = Scenario.query.filter_by(name="RDF Sync Test Scenario", world_id=world.id).first()
        if not scenario:
            print("Creating test scenario...")
            scenario = Scenario(
                name="RDF Sync Test Scenario",
                description="Scenario for testing RDF triple synchronization",
                world_id=world.id,
                scenario_metadata={"test": True}
            )
            db.session.add(scenario)
            db.session.flush()
        
        # Create some test roles if they don't exist
        role_names = ["Engineer", "Designer", "Manager"]
        roles = {}
        
        for role_name in role_names:
            role = Role.query.filter_by(name=role_name, world_id=world.id).first()
            if not role:
                print(f"Creating role: {role_name}")
                role = Role(
                    name=role_name,
                    description=f"Test role for {role_name}",
                    world_id=world.id,
                    ontology_uri=f"http://test/role/{role_name.lower()}"
                )
                db.session.add(role)
                db.session.flush()
            roles[role_name] = role
        
        db.session.commit()
        
        return app, world.id, scenario.id, roles

def create_test_character(app, scenario_id, first_role_id):
    """Create a test character with the specified role"""
    with app.app_context():
        print("\n=== Creating test character ===")
        
        # Check if test character already exists
        character = Character.query.filter_by(
            name="Test Engineer",
            scenario_id=scenario_id
        ).first()
        
        if character:
            print(f"Deleting existing test character: {character.name} (ID: {character.id})")
            
            # Delete any existing triples
            rdf_service = RDFService()
            deleted_count = rdf_service.delete_triples(character_id=character.id)
            print(f"Deleted {deleted_count} existing triples for character")
            
            # Delete the character
            db.session.delete(character)
            db.session.commit()
        
        # Create a new test character
        character = Character(
            name="Test Engineer",
            scenario_id=scenario_id,
            role_id=first_role_id,
            attributes={
                "experience": 5,
                "specialty": "Testing",
                "education": "Test University"
            }
        )
        
        # Get the role object
        role = Role.query.get(first_role_id)
        if role:
            character.role = role.name
        
        db.session.add(character)
        db.session.commit()
        
        print(f"Created character: {character.name} (ID: {character.id})")
        print(f"Initial role: {character.role_from_role.name if character.role_from_role else 'None'} (ID: {character.role_id})")
        
        # Verify the character has been properly synchronized with the RDF store
        # This happens automatically in the routes, but for this test we need to do it manually
        rdf_service = RDFService()
        triples = rdf_service.character_to_triples(character)
        
        print(f"Created {len(triples)} triples for character")
        
        return character.id

def verify_triple_synchronization(app, character_id):
    """Verify the triples match the character state"""
    with app.app_context():
        print("\n=== Verifying triple synchronization ===")
        
        # Get the character
        character = Character.query.get(character_id)
        if not character:
            print("Character not found!")
            return
        
        # Get all triples for this character
        triples = Triple.query.filter_by(character_id=character_id).all()
        
        print(f"Found {len(triples)} triples for character {character.name}")
        
        # Verify presence of important triples
        role_triple_exists = False
        name_triple_exists = False
        type_triple_exists = False
        
        for triple in triples:
            # Check for role triple
            if triple.predicate == "http://proethica.org/ontology/hasRole" and triple.is_literal:
                role_triple_exists = True
                if triple.object_literal == character.role:
                    print(f"✓ Role triple matches character role: {character.role}")
                else:
                    print(f"✗ Role triple ({triple.object_literal}) doesn't match character role: {character.role}")
            
            # Check for name triple
            elif triple.predicate == "http://www.w3.org/2000/01/rdf-schema#label" and triple.is_literal:
                name_triple_exists = True
                if triple.object_literal == character.name:
                    print(f"✓ Name triple matches character name: {character.name}")
                else:
                    print(f"✗ Name triple ({triple.object_literal}) doesn't match character name: {character.name}")
            
            # Check for type triple
            elif triple.predicate == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" and not triple.is_literal:
                type_triple_exists = True
                print(f"✓ Type triple exists: {triple.object_uri}")
        
        # Report on missing triples
        if not role_triple_exists:
            print("✗ Role triple is missing")
        
        if not name_triple_exists:
            print("✗ Name triple is missing")
        
        if not type_triple_exists:
            print("✗ Type triple is missing")
        
        # Count triples by predicate for an overview
        predicates = db.session.query(
            Triple.predicate, 
            func.count(Triple.id)
        ).filter(
            Triple.character_id == character_id
        ).group_by(
            Triple.predicate
        ).all()
        
        print("\nTriple count by predicate:")
        for predicate, count in predicates:
            print(f"  {predicate}: {count}")

def update_character_role(app, character_id, new_role_id):
    """Update the character's role and verify synchronization"""
    with app.app_context():
        print("\n=== Updating character role ===")
        
        # Get the character
        character = Character.query.get(character_id)
        if not character:
            print("Character not found!")
            return
        
        # Get the old and new role names
        old_role = Role.query.get(character.role_id)
        new_role = Role.query.get(new_role_id)
        
        old_role_name = old_role.name if old_role else "None"
        new_role_name = new_role.name if new_role else "None"
        
        print(f"Changing role from {old_role_name} (ID: {character.role_id}) to {new_role_name} (ID: {new_role_id})")
        
        # Update the character's role
        character.role_id = new_role_id
        character.role = new_role_name  # Update legacy role field
        
        db.session.commit()
        
        # Manually sync the character with the RDF store
        # This happens automatically in the routes, but for this test we need to do it manually
        rdf_service = RDFService()
        triples = rdf_service.sync_character(character)
        
        print(f"Synced {len(triples)} triples for character after role update")
        
        # Verify the update
        verify_triple_synchronization(app, character_id)

def test_character_deletion(app, character_id):
    """Test that character deletion also removes triples"""
    with app.app_context():
        print("\n=== Testing character deletion and triple cleanup ===")
        
        # Get the character
        character = Character.query.get(character_id)
        if not character:
            print("Character not found!")
            return
        
        # Count triples before deletion
        triple_count_before = Triple.query.filter_by(character_id=character_id).count()
        print(f"Found {triple_count_before} triples for character before deletion")
        
        # Delete the character (this would be done via the route which includes triple cleanup,
        # but for this test we need to do it manually)
        rdf_service = RDFService()
        deleted_count = rdf_service.delete_triples(character_id=character_id)
        print(f"Deleted {deleted_count} triples for character")
        
        db.session.delete(character)
        db.session.commit()
        
        # Verify triples are deleted
        triple_count_after = Triple.query.filter_by(character_id=character_id).count()
        print(f"Found {triple_count_after} triples for character after deletion")
        
        if triple_count_after == 0:
            print("✓ All triples were successfully deleted")
        else:
            print(f"✗ {triple_count_after} triples remain after character deletion")

def main():
    """Run the sync test"""
    print("===== Character RDF Triple Synchronization Test =====")
    
    # Setup test environment
    app, world_id, scenario_id, roles = setup_test_env()
    
    # Get role IDs
    engineer_role_id = roles["Engineer"].id
    manager_role_id = roles["Manager"].id
    
    # Create test character
    character_id = create_test_character(app, scenario_id, engineer_role_id)
    
    # Verify initial synchronization
    verify_triple_synchronization(app, character_id)
    
    # Update character role and verify
    update_character_role(app, character_id, manager_role_id)
    
    # Test character deletion
    test_character_deletion(app, character_id)
    
    print("\n===== Test completed =====")

if __name__ == "__main__":
    main()
