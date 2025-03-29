#!/usr/bin/env python3
import sys
import os
import json
import argparse

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.world import World
from app.models.resource import Resource
from app.models.resource_type import ResourceType
from app.services.mcp_client import MCPClient

def find_or_create_resource_type(world_id, ontology_uri, name, description=None, category=None):
    """Find a resource type by ontology URI or create if it doesn't exist"""
    resource_type = ResourceType.query.filter_by(ontology_uri=ontology_uri, world_id=world_id).first()
    if not resource_type:
        resource_type = ResourceType(
            name=name,
            description=description or f"Resource type for {name}",
            world_id=world_id,
            category=category or "Document",
            ontology_uri=ontology_uri
        )
        db.session.add(resource_type)
        db.session.flush()
        print(f"Created new resource type: {name} with ID {resource_type.id}")
    else:
        print(f"Found existing resource type: {resource_type.name} with ID {resource_type.id}")
    return resource_type

def create_resource(scenario_id, name, resource_type_id=None, quantity=1, description=None, attributes=None):
    """Create a resource in a scenario"""
    resource = Resource(
        scenario_id=scenario_id,
        name=name,
        resource_type_id=resource_type_id,
        type=ResourceType.query.get(resource_type_id).name if resource_type_id else name,
        quantity=quantity,
        description=description or f"Resource: {name}"
    )
    db.session.add(resource)
    db.session.flush()
    print(f"Created resource: {name} with ID {resource.id}")
    return resource

def add_resources_to_scenario_6(force=False):
    """Add resources to Scenario 6 (Building Inspection Confidentiality Dilemma)"""
    app = create_app()
    with app.app_context():
        # Get scenario 6
        scenario = Scenario.query.get(6)
        if not scenario:
            print("Scenario 6 not found")
            return
        
        # Get world
        world = World.query.get(scenario.world_id)
        if not world:
            print(f"World with ID {scenario.world_id} not found")
            return
        
        print(f"Adding resources to Scenario: {scenario.name}")
        print(f"World: {world.name}")
        print(f"Ontology: {world.ontology_source}")
        
        # Get MCP client
        mcp_client = MCPClient.get_instance()
        
        # Check if we already have resources
        existing_resources = Resource.query.filter_by(scenario_id=scenario.id).all()
        if existing_resources and not force:
            print(f"Warning: Scenario already has {len(existing_resources)} resources")
            for res in existing_resources:
                print(f"- {res.name}: {res.type}")
            
            confirm = input("Do you want to continue and add more resources? (y/n): ")
            if confirm.lower() != 'y':
                print("Operation cancelled")
                return
        
        try:
            # Get resource types from ontology
            entities = mcp_client.get_world_entities(world.ontology_source, entity_type="resources")
            if not entities or 'entities' not in entities or 'resources' not in entities['entities']:
                print("Failed to get resources from ontology")
                return
            
            # Find resource types in ontology
            structural_report_type = None
            confidentiality_agreement_type = None
            building_code_type = None
            
            for resource in entities['entities']['resources']:
                if resource['label'] == "Structural Inspection Report":
                    structural_report_type = resource
                elif resource['label'] == "Confidentiality Agreement":
                    confidentiality_agreement_type = resource
                elif resource['label'] == "Building Code":
                    building_code_type = resource
            
            # Create or find resource types in database
            structural_report_db_type = None
            confidentiality_agreement_db_type = None
            building_code_db_type = None
            
            if structural_report_type:
                structural_report_db_type = find_or_create_resource_type(
                    world_id=world.id,
                    ontology_uri=structural_report_type['id'],
                    name=structural_report_type['label'],
                    description=structural_report_type['description'],
                    category="Document"
                )
            
            if confidentiality_agreement_type:
                confidentiality_agreement_db_type = find_or_create_resource_type(
                    world_id=world.id,
                    ontology_uri=confidentiality_agreement_type['id'],
                    name=confidentiality_agreement_type['label'],
                    description=confidentiality_agreement_type['description'],
                    category="Legal"
                )
            
            if building_code_type:
                building_code_db_type = find_or_create_resource_type(
                    world_id=world.id,
                    ontology_uri=building_code_type['id'],
                    name=building_code_type['label'],
                    description=building_code_type['description'],
                    category="Regulatory"
                )
            
            # 1. Create Structural Inspection Report resource
            structural_report = create_resource(
                scenario_id=scenario.id,
                name="Structural Integrity Report",
                resource_type_id=structural_report_db_type.id if structural_report_db_type else None,
                quantity=1,
                description="Report prepared by Engineer A documenting the structural integrity of the apartment building, with brief mention of electrical and mechanical system deficiencies"
            )
            
            # 2. Create Confidentiality Agreement resource
            confidentiality_agreement = create_resource(
                scenario_id=scenario.id,
                name="Client-Engineer Confidentiality Agreement",
                resource_type_id=confidentiality_agreement_db_type.id if confidentiality_agreement_db_type else None,
                quantity=1,
                description="Agreement between Building Owner and Engineer A stipulating that the structural report must remain confidential"
            )
            
            # 3. Create Building Code resource
            building_code = create_resource(
                scenario_id=scenario.id,
                name="Electrical and Mechanical Building Codes",
                resource_type_id=building_code_db_type.id if building_code_db_type else None,
                quantity=1,
                description="Local building codes that establish safety requirements for electrical and mechanical systems in apartment buildings"
            )
            
            # Commit all changes
            db.session.commit()
            print("Successfully added all resources to Scenario 6")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error adding resources: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Add resources to Scenario 6')
    parser.add_argument('--force', action='store_true', help='Force adding resources even if scenario already has resources')
    
    args = parser.parse_args()
    add_resources_to_scenario_6(force=args.force)
