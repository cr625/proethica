#!/usr/bin/env python3
"""
Script for adding resources to the "Report or Not" scenario in the 
"Engineering Ethics (US)" world in the AI Ethical Decision-Making Simulator.

This script adds resources that make sense in the context of the characters:
1. Blueprints: Structural Design Plans - The design with the deficiency
2. Specifications: Project Requirements - Technical requirements for the project
3. Inspection Report: Initial Safety Assessment - Report identifying potential issues
4. Regulatory Standard: Building Safety Code - Relevant safety regulations
5. Budget: Project Financial Plan - Financial resources allocated to the project
6. Time Resource: Project Schedule - Timeline for project completion
7. Testing Equipment: Structural Testing Tools - Equipment used to verify design safety

Usage:
1. Run the script: python -m prompts.add_report_or_not_resources
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
SCENARIO_ID = 2  # "Report or Not" scenario
WORLD_ID = 2     # "Engineering Ethics (US)" world

# Resource definitions
# Format: [name, resource_uri, resource_name, description, quantity]
RESOURCES = [
    # Blueprints: Structural Design Plans
    [
        "Structural Design Plans",
        "http://example.org/engineering-ethics#Blueprints",
        "Blueprints",
        "Detailed engineering drawings showing the structural design of the project. These plans contain the design deficiency that Alex Rodriguez has identified, which could potentially impact public safety if not addressed.",
        1
    ],
    
    # Specifications: Project Requirements
    [
        "Project Requirements Specification",
        "http://example.org/engineering-ethics#Specifications",
        "Specifications",
        "Comprehensive document outlining the technical requirements, performance criteria, and quality standards for the project. The specifications include safety requirements that the current design may not fully meet.",
        1
    ],
    
    # Inspection Report: Initial Safety Assessment
    [
        "Initial Safety Assessment",
        "http://example.org/engineering-ethics#InspectionReport",
        "Inspection Report",
        "Preliminary safety assessment conducted by Alex Rodriguez that identifies potential issues with the current design. This report has not yet been officially submitted but documents the concerns about the design deficiency.",
        1
    ],
    
    # Regulatory Standard: Building Safety Code
    [
        "Building Safety Code",
        "http://example.org/engineering-ethics#RegulatoryStandard",
        "Regulatory Standard",
        "Official building safety code that governs the design and construction of this type of structure. The code includes specific requirements that the current design may violate, which Sam Washington is responsible for enforcing.",
        1
    ],
    
    # Budget: Project Financial Plan
    [
        "Project Financial Plan",
        "http://example.org/engineering-ethics#Budget",
        "Budget",
        "Detailed budget for the project showing cost allocations for design, materials, labor, and contingencies. The budget is already stretched thin, and addressing the design deficiency would require additional funds that Westridge Development Corporation is reluctant to provide.",
        1
    ],
    
    # Time Resource: Project Schedule
    [
        "Project Schedule",
        "http://example.org/engineering-ethics#TimeResource",
        "Time Resource",
        "Timeline for project completion showing key milestones, deadlines, and the critical path. Morgan Chen is under significant pressure to meet these deadlines, which would be jeopardized by addressing the design deficiency.",
        1
    ],
    
    # Testing Equipment: Structural Testing Tools
    [
        "Structural Testing Tools",
        "http://example.org/engineering-ethics#TestingEquipment",
        "Testing Equipment",
        "Specialized equipment used to test and verify the structural integrity and safety of the design. These tools were used by Alex Rodriguez to identify the potential deficiency and could be used to validate any proposed fixes.",
        3
    ]
]

def add_resources_to_scenario():
    """Add defined resources to the Report or Not scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        # Verify this is the correct scenario
        if scenario.name != "Report or Not" or scenario.world_id != WORLD_ID:
            print(f'Warning: Expected "Report or Not" scenario in world {WORLD_ID}')
            print(f'Found: "{scenario.name}" in world {scenario.world_id}')
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                print("Aborting.")
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
                    category='Engineering'
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
