#!/usr/bin/env python3
"""
Script to populate database tables from the consolidated ontology.
This ensures that the characters, conditions, and resources available in scenarios
correspond to what's defined in the ontology.
"""

import os
import sys
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, create_app
from app.models.world import World
from app.models.role import Role
from app.models.resource_type import ResourceType
from app.models.condition_type import ConditionType

def populate_from_ontology():
    """Populate database tables from the consolidated ontology."""
    app = create_app()
    with app.app_context():
        # Check if the Military Medical Triage world exists
        world = World.query.filter_by(name="Military Medical Triage World").first()
        if not world:
            print("Creating Military Medical Triage World...")
            world = World(
                name="Military Medical Triage World",
                description="A world representing military medical triage scenarios",
                ontology_source="mcp/ontology/military_medical_triage_consolidated.ttl"
            )
            db.session.add(world)
            db.session.commit()
            print(f"Created world with ID: {world.id}")
        else:
            print(f"Using existing world with ID: {world.id}")
        
        # Load and parse the ontology
        g = Graph()
        ontology_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    "mcp/ontology/military_medical_triage_consolidated.ttl")
        g.parse(ontology_path, format="turtle")
        
        # Define namespaces
        MMT = Namespace("http://example.org/military-medical-triage#")
        
        # Populate roles
        print("\nPopulating roles...")
        populate_roles(g, MMT, world)
        
        # Populate condition types
        print("\nPopulating condition types...")
        populate_condition_types(g, MMT, world)
        
        # Populate resource types
        print("\nPopulating resource types...")
        populate_resource_types(g, MMT, world)
        
        print("\nDone!")

def populate_roles(g, MMT, world):
    """Populate roles from the ontology."""
    # Get all entities that are character types
    for s in g.subjects(RDF.type, MMT.CharacterType):
        if isinstance(s, URIRef):
            # Get the role name (the part after the #)
            role_name = str(s).split('#')[-1]
            
            # Get the label
            label = None
            for label_obj in g.objects(s, RDFS.label):
                label = str(label_obj)
                break
            
            if not label:
                label = role_name
            
            # Get the description
            description = None
            for desc_obj in g.objects(s, RDFS.comment):
                description = str(desc_obj)
                break
            
            # Get the tier
            tier = None
            for tier_obj in g.objects(s, MMT.hasTier):
                for tier_label in g.objects(tier_obj, RDFS.label):
                    tier_str = str(tier_label)
                    # Extract the tier number
                    if "Tier " in tier_str:
                        try:
                            tier = int(tier_str.split("Tier ")[1])
                        except ValueError:
                            pass
                    break
            
            # Get the ontology URI
            ontology_uri = str(s)
            
            # Check if the role already exists
            existing_role = Role.query.filter_by(name=label, world_id=world.id).first()
            if existing_role:
                print(f"  Role '{label}' already exists, updating...")
                existing_role.description = description
                existing_role.tier = tier
                existing_role.ontology_uri = ontology_uri
            else:
                print(f"  Creating role: {label}")
                role = Role(
                    name=label,
                    description=description,
                    world_id=world.id,
                    tier=tier,
                    ontology_uri=ontology_uri
                )
                db.session.add(role)
            
            db.session.commit()

def populate_condition_types(g, MMT, world):
    """Populate condition types from the ontology."""
    # Get all entities that are condition types
    for s in g.subjects(RDF.type, MMT.ConditionType):
        if isinstance(s, URIRef):
            # Get the condition type name (the part after the #)
            condition_type_name = str(s).split('#')[-1]
            
            # Get the label
            label = None
            for label_obj in g.objects(s, RDFS.label):
                label = str(label_obj)
                break
            
            if not label:
                label = condition_type_name
            
            # Get the description
            description = None
            for desc_obj in g.objects(s, RDFS.comment):
                description = str(desc_obj)
                break
            
            # Get the category
            category = None
            # Try to determine category from class hierarchy
            for _, _, parent in g.triples((s, RDFS.subClassOf, None)):
                if parent != MMT.MedicalCondition and parent != MMT.ConditionType:
                    parent_name = str(parent).split('#')[-1]
                    if parent_name in ["TraumaticInjury", "Hemorrhage", "Fracture", "BurnInjury", "PenetrationWound", "BlastInjury"]:
                        category = "Injury"
                    break
            
            if not category:
                category = "Medical"
            
            # Get the ontology URI
            ontology_uri = str(s)
            
            # Check if the condition type already exists
            existing_condition_type = ConditionType.query.filter_by(name=label, world_id=world.id).first()
            if existing_condition_type:
                print(f"  Condition type '{label}' already exists, updating...")
                existing_condition_type.description = description
                existing_condition_type.category = category
                existing_condition_type.ontology_uri = ontology_uri
            else:
                print(f"  Creating condition type: {label}")
                condition_type = ConditionType(
                    name=label,
                    description=description,
                    world_id=world.id,
                    category=category,
                    ontology_uri=ontology_uri
                )
                db.session.add(condition_type)
            
            db.session.commit()

def populate_resource_types(g, MMT, world):
    """Populate resource types from the ontology."""
    # Get all entities that are resource types
    for s in g.subjects(RDF.type, MMT.ResourceType):
        if isinstance(s, URIRef):
            # Get the resource type name (the part after the #)
            resource_type_name = str(s).split('#')[-1]
            
            # Get the label
            label = None
            for label_obj in g.objects(s, RDFS.label):
                label = str(label_obj)
                break
            
            if not label:
                label = resource_type_name
            
            # Get the description
            description = None
            for desc_obj in g.objects(s, RDFS.comment):
                description = str(desc_obj)
                break
            
            # Get the category
            category = None
            # Try to determine category from class hierarchy
            for _, _, parent in g.triples((s, RDFS.subClassOf, None)):
                if parent != MMT.MedicalResource and parent != MMT.ResourceType:
                    parent_name = str(parent).split('#')[-1]
                    if parent_name == "Medication":
                        category = "Medication"
                    elif parent_name == "MedicalEquipment":
                        category = "Equipment"
                    else:
                        category = parent_name
                    break
            
            if not category:
                category = "Medical"
            
            # Get the ontology URI
            ontology_uri = str(s)
            
            # Check if the resource type already exists
            existing_resource_type = ResourceType.query.filter_by(name=label, world_id=world.id).first()
            if existing_resource_type:
                print(f"  Resource type '{label}' already exists, updating...")
                existing_resource_type.description = description
                existing_resource_type.category = category
                existing_resource_type.ontology_uri = ontology_uri
            else:
                print(f"  Creating resource type: {label}")
                resource_type = ResourceType(
                    name=label,
                    description=description,
                    world_id=world.id,
                    category=category,
                    ontology_uri=ontology_uri
                )
                db.session.add(resource_type)
            
            db.session.commit()

if __name__ == "__main__":
    populate_from_ontology()
