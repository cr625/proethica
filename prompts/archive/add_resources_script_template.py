#!/usr/bin/env python3
"""
Script template for adding resources to scenarios in the AI Ethical Decision-Making Simulator.
This template can be customized for different scenarios and resources.

Usage:
1. Modify the SCENARIO_ID and resource definitions as needed
2. Run the script: python -m prompts.add_resources_script_template
"""

import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.scenario import Scenario
from app.models.resource import Resource
from app.models.resource_type import ResourceType

# Configuration
SCENARIO_ID = 3  # Replace with the ID of your target scenario

# Resource definitions
# Format: [name, resource_uri, resource_name, description, quantity]
RESOURCES = [
    # Example: Case File resource
    [
        "Example Case File",
        "http://example.org/nj-legal-ethics#CaseFile",
        "Case File",
        "A sample case file for demonstration purposes.",
        1
    ],
    # Example: Legal Research resource
    [
        "Example Legal Research",
        "http://example.org/nj-legal-ethics#LegalResearch",
        "Legal Research",
        "Sample legal research for demonstration purposes.",
        1
    ],
    # Add more resources as needed...
]

def add_resources_to_scenario():
    """Add defined resources to the specified scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        print(f'Adding resources to scenario: {scenario.name} (ID: {scenario.id})')
        print(f'World ID: {scenario.world_id}')
        
        # Process each resource
        for res_def in RESOURCES:
            name, resource_uri, resource_name, description, quantity = res_def
            
            # Check if resource already exists
            existing_res = Resource.query.filter_by(
                name=name, 
                scenario_id=scenario.id
            ).first()
            
            if existing_res:
                print(f'Resource "{name}" already exists in this scenario. Skipping.')
                continue
            
            # Get or create resource type
            resource_type = ResourceType.query.filter_by(
                ontology_uri=resource_uri, 
                world_id=scenario.world_id
            ).first()
            
            if not resource_type:
                # Create the resource type
                resource_type = ResourceType(
                    name=resource_name,
                    description=f'Resource type for {resource_name}',
                    world_id=scenario.world_id,
                    ontology_uri=resource_uri,
                    category='Legal'  # Adjust category as needed
                )
                db.session.add(resource_type)
                db.session.flush()
                print(f'Created resource type: {resource_name} (ID: {resource_type.id})')
            
            # Create the resource
            resource = Resource(
                name=name,
                scenario_id=scenario.id,
                resource_type_id=resource_type.id,
                type=resource_name,  # For backward compatibility
                quantity=quantity,
                description=description
            )
            db.session.add(resource)
            print(f'Added resource: {name} (Quantity: {quantity})')
            
        # Commit all changes
        db.session.commit()
        print('All resources added successfully!')

def verify_resources():
    """Verify that resources were added correctly."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        print(f'\nVerifying resources in scenario: {scenario.name}')
        print(f'Number of resources: {len(scenario.resources)}')
        
        for resource in scenario.resources:
            print(f'\n- {resource.name} (Type: {resource.type}, Quantity: {resource.quantity})')
            print(f'  Description: {resource.description}')

if __name__ == "__main__":
    # Add resources
    add_resources_to_scenario()
    
    # Verify resources were added correctly
    verify_resources()
