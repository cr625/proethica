#!/usr/bin/env python3
"""
Script to populate the resource_types table with resource types from the OWL ontology.
"""
import os
import sys
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

def populate_resource_types():
    """Populate the resource_types table with resource types from the OWL ontology."""
    # Add the parent directory to the path so we can import the app
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        from app import create_app, db
        from app.models import World, ResourceType
        print("Imported modules successfully")
    except Exception as e:
        print(f"Error importing modules: {e}")
        return

    app = create_app()
    with app.app_context():
        # Check if the resource_types table exists
        try:
            from sqlalchemy import text
            db.session.execute(text("SELECT 1 FROM resource_types LIMIT 1"))
            print("Resource types table exists")
        except Exception as e:
            print(f"Error checking resource_types table: {e}")
            print("Running database migrations...")
            try:
                from flask_migrate import upgrade
                upgrade("add_resource_types_table")
                print("Migrations complete")
            except Exception as e:
                print(f"Error running migrations: {e}")
                return
        
        # Find or create the Military Medical Triage world
        world = World.query.filter_by(name="Military Medical Triage").first()
        if not world:
            print("Creating Military Medical Triage world...")
            world = World(
                name="Military Medical Triage",
                description="A world representing military medical triage scenarios",
                ontology_source="mcp/ontology/military_medical_triage.ttl"
            )
            db.session.add(world)
            db.session.commit()
            print(f"Created world with ID {world.id}")
        else:
            print(f"Found existing world with ID {world.id}")
        
        # Load the OWL ontology
        g = Graph()
        ontology_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                     "mcp/ontology/military_medical_triage.ttl")
        
        # Check if the ontology file exists
        if not os.path.exists(ontology_path):
            print(f"Ontology file not found: {ontology_path}")
            # Create a basic ontology file with some resource types
            create_basic_ontology(ontology_path)
            print(f"Created basic ontology file: {ontology_path}")
            g.parse(ontology_path, format="turtle")
        else:
            g.parse(ontology_path, format="turtle")
        
        # Define namespaces
        MMT = Namespace("http://example.org/military-medical-triage#")
        
        # Query for resource type instances
        resource_types_query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX mmt: <http://example.org/military-medical-triage#>
        
        SELECT ?resource_type ?label ?category ?description
        WHERE {
            ?resource_type rdf:type ?resourceTypeClass .
            ?resourceTypeClass rdfs:subClassOf mmt:ResourceType .
            ?resource_type rdfs:label ?label .
            OPTIONAL { ?resource_type mmt:category ?category . }
            OPTIONAL { ?resourceTypeClass mmt:description ?description . }
        }
        """
        
        # Execute the query
        results = g.query(resource_types_query)
        
        # If no results, create some basic resource types
        if not results:
            print("No resource types found in ontology, creating basic resource types")
            create_basic_resource_types(world.id)
            return
        
        # Process the results
        for row in results:
            resource_type_uri = str(row.resource_type)
            label = str(row.label)
            category = str(row.category) if row.category else None
            description = str(row.description) if row.description else None
            
            # Check if the resource type already exists
            existing_resource_type = ResourceType.query.filter_by(
                name=label,
                world_id=world.id
            ).first()
            
            if existing_resource_type:
                print(f"Resource type '{label}' already exists, updating...")
                existing_resource_type.description = description
                existing_resource_type.category = category
                existing_resource_type.ontology_uri = resource_type_uri
            else:
                print(f"Creating resource type '{label}'...")
                resource_type = ResourceType(
                    name=label,
                    description=description,
                    world_id=world.id,
                    category=category,
                    ontology_uri=resource_type_uri
                )
                db.session.add(resource_type)
            
        # Commit the changes
        db.session.commit()
        print("Resource types populated successfully!")

def create_basic_ontology(ontology_path):
    """Create a basic ontology file with some resource types."""
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(ontology_path), exist_ok=True)
    
    # Basic ontology content
    ontology_content = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix mmt: <http://example.org/military-medical-triage#> .

# Resource Type hierarchy
mmt:ResourceType a owl:Class ;
    rdfs:label "Resource Type"@en ;
    rdfs:comment "A type of resource available in the military medical triage system"@en .

# Medical Equipment
mmt:MedicalEquipment a owl:Class ;
    rdfs:subClassOf mmt:ResourceType ;
    rdfs:label "Medical Equipment"@en ;
    mmt:category "Equipment"@en ;
    mmt:description "Medical equipment used in field operations, including diagnostic tools, treatment devices, and monitoring equipment."@en .

# Medical Supplies
mmt:MedicalSupplies a owl:Class ;
    rdfs:subClassOf mmt:ResourceType ;
    rdfs:label "Medical Supplies"@en ;
    mmt:category "Supplies"@en ;
    mmt:description "Consumable medical supplies used in treatment, including bandages, medications, IV fluids, and other disposable items."@en .

# Transport
mmt:Transport a owl:Class ;
    rdfs:subClassOf mmt:ResourceType ;
    rdfs:label "Transport"@en ;
    mmt:category "Vehicle"@en ;
    mmt:description "Vehicles used for patient transport, including ambulances, helicopters, and other medical evacuation vehicles."@en .

# Personnel
mmt:Personnel a owl:Class ;
    rdfs:subClassOf mmt:ResourceType ;
    rdfs:label "Personnel"@en ;
    mmt:category "Personnel"@en ;
    mmt:description "Medical and support personnel, including doctors, nurses, medics, and other healthcare providers."@en .

# Specific resource type instances
mmt:Tourniquet a mmt:MedicalSupplies ;
    rdfs:label "Tourniquet"@en ;
    mmt:category "Supplies"@en .

mmt:Bandage a mmt:MedicalSupplies ;
    rdfs:label "Bandage"@en ;
    mmt:category "Supplies"@en .

mmt:BloodProducts a mmt:MedicalSupplies ;
    rdfs:label "Blood Products"@en ;
    mmt:category "Supplies"@en .

mmt:IVFluids a mmt:MedicalSupplies ;
    rdfs:label "IV Fluids"@en ;
    mmt:category "Supplies"@en .

mmt:Medications a mmt:MedicalSupplies ;
    rdfs:label "Medications"@en ;
    mmt:category "Supplies"@en .

mmt:Stretcher a mmt:MedicalEquipment ;
    rdfs:label "Stretcher"@en ;
    mmt:category "Equipment"@en .

mmt:MonitoringEquipment a mmt:MedicalEquipment ;
    rdfs:label "Monitoring Equipment"@en ;
    mmt:category "Equipment"@en .

mmt:SurgicalInstruments a mmt:MedicalEquipment ;
    rdfs:label "Surgical Instruments"@en ;
    mmt:category "Equipment"@en .

mmt:Ambulance a mmt:Transport ;
    rdfs:label "Ambulance"@en ;
    mmt:category "Vehicle"@en .

mmt:MedicalHelicopter a mmt:Transport ;
    rdfs:label "Medical Helicopter"@en ;
    mmt:category "Vehicle"@en .

mmt:Doctor a mmt:Personnel ;
    rdfs:label "Doctor"@en ;
    mmt:category "Personnel"@en .

mmt:Nurse a mmt:Personnel ;
    rdfs:label "Nurse"@en ;
    mmt:category "Personnel"@en .

mmt:Medic a mmt:Personnel ;
    rdfs:label "Medic"@en ;
    mmt:category "Personnel"@en .
"""
    
    # Write the ontology to the file
    with open(ontology_path, 'w') as f:
        f.write(ontology_content)

def create_basic_resource_types(world_id):
    """Create basic resource types in the database."""
    from app import db
    from app.models import ResourceType
    
    # Define basic resource types
    resource_types = [
        {
            'name': 'Tourniquet',
            'description': 'A device used to apply pressure to a limb to stop bleeding',
            'category': 'Supplies',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Tourniquet'
        },
        {
            'name': 'Bandage',
            'description': 'Material used to cover and protect wounds',
            'category': 'Supplies',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Bandage'
        },
        {
            'name': 'Blood Products',
            'description': 'Blood and blood components used for transfusion',
            'category': 'Supplies',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#BloodProducts'
        },
        {
            'name': 'IV Fluids',
            'description': 'Fluids administered intravenously for hydration and medication delivery',
            'category': 'Supplies',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#IVFluids'
        },
        {
            'name': 'Medications',
            'description': 'Pharmaceutical drugs used for treatment',
            'category': 'Supplies',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Medications'
        },
        {
            'name': 'Stretcher',
            'description': 'A device used to carry injured or ill people',
            'category': 'Equipment',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Stretcher'
        },
        {
            'name': 'Monitoring Equipment',
            'description': 'Devices used to monitor patient vital signs',
            'category': 'Equipment',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#MonitoringEquipment'
        },
        {
            'name': 'Surgical Instruments',
            'description': 'Tools used in surgical procedures',
            'category': 'Equipment',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#SurgicalInstruments'
        },
        {
            'name': 'Ambulance',
            'description': 'Vehicle used for emergency medical transport',
            'category': 'Vehicle',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Ambulance'
        },
        {
            'name': 'Medical Helicopter',
            'description': 'Helicopter used for emergency medical transport',
            'category': 'Vehicle',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#MedicalHelicopter'
        },
        {
            'name': 'Doctor',
            'description': 'Medical professional with advanced training',
            'category': 'Personnel',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Doctor'
        },
        {
            'name': 'Nurse',
            'description': 'Medical professional who provides patient care',
            'category': 'Personnel',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Nurse'
        },
        {
            'name': 'Medic',
            'description': 'Medical professional who provides emergency care in the field',
            'category': 'Personnel',
            'world_id': world_id,
            'ontology_uri': 'http://example.org/military-medical-triage#Medic'
        }
    ]
    
    # Add resource types to the database
    for rt_data in resource_types:
        resource_type = ResourceType(**rt_data)
        db.session.add(resource_type)
    
    # Commit the changes
    db.session.commit()
    print("Basic resource types created successfully!")

if __name__ == "__main__":
    populate_resource_types()
