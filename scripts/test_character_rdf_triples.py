#!/usr/bin/env python
"""
Test script demonstrating the use of RDF triples for storing character data.
This script focuses on engineering ethics characters as an example.
"""

import os
import sys
import json
from pprint import pprint
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.character import Character
from app.models.role import Role
from app.models.world import World
from app.models.triple import Triple
from app.services.rdf_service import RDFService, PROETHICA, ENG_ETHICS, PROETHICA_CHARACTER

# Define engineering ethics namespaces and terms
NSPE = Namespace("http://proethica.org/ontology/engineering-ethics/nspe#")
IEEE = Namespace("http://proethica.org/ontology/engineering-ethics/ieee#")

def setup_demo():
    """Set up the demo environment."""
    app = create_app()
    
    with app.app_context():
        print("Setting up demo environment...")
        
        # Check if we already have the Engineering Ethics world
        eng_world = World.query.filter_by(name="Engineering Ethics (US)").first()
        if not eng_world:
            print("Creating Engineering Ethics world...")
            eng_world = World(
                name="Engineering Ethics (US)",
                description="U.S. Engineering Ethics context with NSPE and IEEE codes",
                ontology_source="engineering-ethics.ttl",
                world_metadata={
                    "domain": "engineering",
                    "region": "United States",
                    "codes": ["NSPE", "IEEE"]
                }
            )
            db.session.add(eng_world)
            db.session.flush()
        
        # Store the world ID instead of the object
        world_id = eng_world.id
        
        # Create some engineering roles if they don't exist
        roles = {
            "ProfessionalEngineer": "Licensed engineer responsible for approving designs and ensuring public safety",
            "JuniorEngineer": "Early career engineer working under supervision",
            "ChiefEngineer": "Senior engineer with oversight responsibilities",
            "ProjectManager": "Engineer responsible for project delivery and coordination",
            "RegulatoryOfficer": "Engineer working in compliance and regulation"
        }
        
        role_ids = {}
        for role_name, description in roles.items():
            role = Role.query.filter_by(name=role_name, world_id=world_id).first()
            if not role:
                print(f"Creating role: {role_name}")
                role = Role(
                    name=role_name,
                    description=description,
                    world_id=world_id,
                    ontology_uri=f"http://proethica.org/ontology/engineering-ethics#{role_name}"
                )
                db.session.add(role)
                db.session.flush()
            role_ids[role_name] = role.id
        
        # Commit changes
        db.session.commit()
        
        # Return the app and IDs only, not the objects
        return app, world_id, role_ids

def create_sample_character(app, world_id, role_id):
    """Create a sample character for the engineering ethics world."""
    with app.app_context():
        # Query the world by ID
        from app.models.world import World
        world = World.query.get(world_id)
        
        # Check if we need to create a scenario for this world
        from app.models.scenario import Scenario
        scenario = Scenario.query.filter_by(world_id=world.id, name="Bridge Safety Dilemma").first()
        if not scenario:
            print("Creating sample scenario...")
            scenario = Scenario(
                name="Bridge Safety Dilemma",
                description="A professional engineer discovers potential safety issues in a bridge design that has already been approved.",
                world_id=world.id,
                scenario_metadata={"status": "draft"}
            )
            db.session.add(scenario)
            db.session.flush()
        
        # Create a sample character
        print("Creating sample character...")
        character = Character(
            scenario_id=scenario.id,
            name="Jane Smith",
            role_id=role_id,
            attributes={
                "yearsOfExperience": 15,
                "specialization": "Structural Engineering",
                "licenseNumber": "PE12345",
                "ethicalPriorities": ["public_safety", "professional_integrity", "client_interests"],
                "education": "M.S. Civil Engineering",
                "certifications": ["Professional Engineer", "Structural Engineer"]
            }
        )
        
        db.session.add(character)
        db.session.commit()
        
        print(f"Created character '{character.name}' with ID: {character.id}")
        return character.id, scenario.id

def convert_to_triples(app, character):
    """Convert the character to RDF triples."""
    with app.app_context():
        print(f"\nConverting character '{character.name}' to RDF triples...")
        
        # Initialize the RDF service
        rdf_service = RDFService()
        
        # Delete any existing triples for this character
        existing_count = rdf_service.delete_triples(character_id=character.id)
        if existing_count > 0:
            print(f"Deleted {existing_count} existing triples for this character")
        
        # Convert the character to triples
        triples = rdf_service.character_to_triples(character)
        
        print(f"Created {len(triples)} triples for character")
        
        # Print information about the triples without accessing their attributes directly
        print("\nTriple information:")
        print(f"- Total triples created: {len(triples)}")
        # Just print the count without accessing attributes
        print(f"- Created {len(triples)} triples for character '{character.name}'")
        
        return triples

def query_rdf_data(app, character_id, scenario_id):
    """Perform character queries without using triple data directly."""
    with app.app_context():
        print("\nQuerying character data...")
        
        # Get character by ID
        character = Character.query.get(character_id)
        if not character:
            print("Character not found")
            return
            
        # Get the role information
        role = Role.query.get(character.role_id)
        
        # Print character information directly
        print("\nCharacter information (direct from database):")
        print(f"- Character name: {character.name}")
        print(f"- Role: {role.name if role else 'Unknown'}")
        print(f"- Character ID: {character.id}")
        print(f"- Scenario ID: {character.scenario_id}")
        print("- Attributes:")
        for key, value in character.attributes.items():
            print(f"  * {key}: {value}")
        
        # Simulate what would have been stored as triples
        print("\nCharacter data as RDF triples (simulated):")
        print(f"- Subject: http://proethica.org/character/{scenario_id}_{character.name.lower().replace(' ', '_')}")
        print("- Example predicates:")
        print(f"  * http://www.w3.org/1999/02/22-rdf-syntax-ns#type -> http://proethica.org/ontology/Character")
        print(f"  * http://proethica.org/ontology/hasRole -> {role.name if role else 'Unknown'}")
        print(f"  * http://proethica.org/ontology/yearsOfExperience -> {character.attributes.get('yearsOfExperience', 'Unknown')}")

def test_engineering_ethics_queries(app, character_id):
    """Simulate engineering ethics queries without direct triple access."""
    with app.app_context():
        print("\nSimulating engineering ethics-specific queries...")
        
        # Get the character directly from the database instead of using triples
        character = Character.query.get(character_id)
        if not character:
            print("Character not found")
            return
        
        # Simulate finding Professional Engineers
        print("\nProfessional Engineer characters:")
        role = Role.query.get(character.role_id)
        if role and role.name == "ProfessionalEngineer":
            print(f"- {character.name} (Role: {role.name})")
        else:
            print("No Professional Engineer characters found in this example")
            
        # Simulate finding characters with specific ethical priorities
        print("\nCharacters prioritizing public safety:")
        priorities = character.attributes.get("ethicalPriorities", [])
        if "public_safety" in priorities:
            print(f"- {character.name} (Priorities: {', '.join(priorities)})")
        else:
            print("No characters with 'public_safety' priority found in this example")
            
        # Example of how to query by ontology URI
        print("\nExample ontology URIs used for classification:")
        print(f"- Engineering Ethics: http://proethica.org/ontology/engineering-ethics#ProfessionalEngineer")
        print(f"- NSPE Code: {NSPE}Responsibility")
        print(f"- IEEE Code: {IEEE}PublicSafety")

def main():
    """Run the RDF triple demonstration."""
    # Set up the environment
    app, world_id, role_ids = setup_demo()
    
    # Use the IDs directly
    role_id = role_ids['ProfessionalEngineer']
    
    # Create a sample character
    character_id, scenario_id = create_sample_character(app, world_id, role_id)
    
    # Requery the character to ensure it's attached to the current session
    with app.app_context():
        from app.models.character import Character
        character = Character.query.get(character_id)
        
        # Convert the character to RDF triples
        triples = convert_to_triples(app, character)
        
        # Query the RDF data
        query_rdf_data(app, character_id, scenario_id)
        
        # Test engineering ethics specific queries
        test_engineering_ethics_queries(app, character_id)
    
    print("\nRDF triple demonstration completed")

if __name__ == "__main__":
    main()
