#!/usr/bin/env python3
"""
Script for adding resources to the "Mass Casualty Triage" scenario in the 
"Tactical Combat Casualty Care (US Army)" world in the AI Ethical Decision-Making Simulator.

This script adds resources that make sense in the context of a mass casualty incident:
1. Tourniquets - Limited number of tourniquets for hemorrhage control
2. Bandages - Pressure dressings and hemostatic bandages
3. Morphine - Limited pain medication
4. IV Fluids - For fluid resuscitation
5. Blood Products - Limited blood products for transfusion
6. Medical Equipment - Various medical equipment
7. Communication Equipment - For MEDEVAC requests

Usage:
1. Run the script: python -m prompts.add_mass_casualty_triage_resources
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
SCENARIO_ID = 5  # "Mass Casualty Triage" scenario
WORLD_ID = 1     # "Tactical Combat Casualty Care (US Army)" world

# Resource definitions
# Format: [name, resource_uri, resource_name, description, quantity]
RESOURCES = [
    # Tourniquets
    [
        "Combat Application Tourniquets",
        "http://example.org/military-medical-triage#Tourniquet",
        "Tourniquet",
        "Combat Application Tourniquets (CATs) for controlling severe hemorrhage from limb injuries. These are critical, life-saving devices with limited availability in a mass casualty situation.",
        3
    ],
    
    # Bandages
    [
        "Pressure Dressings and Hemostatic Bandages",
        "http://example.org/military-medical-triage#Bandage",
        "Bandage",
        "Assortment of pressure dressings and hemostatic bandages for wound management and hemorrhage control. Includes standard field dressings, hemostatic gauze, and elastic bandages.",
        8
    ],
    
    # Morphine
    [
        "Morphine Autoinjectors",
        "http://example.org/military-medical-triage#Morphine",
        "Morphine",
        "Morphine autoinjectors for pain management in severely injured casualties. Limited supply requires careful allocation decisions based on severity of injuries and pain levels.",
        4
    ],
    
    # IV Fluids
    [
        "IV Fluid Bags",
        "http://example.org/military-medical-triage#MedicalResource",
        "IV Fluids",
        "Intravenous fluid bags for fluid resuscitation in casualties with significant blood loss. Includes normal saline and lactated Ringer's solution.",
        6
    ],
    
    # Blood Products
    [
        "Field Blood Transfusion Kit",
        "http://example.org/military-medical-triage#BloodProduct",
        "Blood Product",
        "Limited supply of blood products for emergency transfusion in cases of severe hemorrhage. Includes packed red blood cells and plasma. Requires special handling and is in extremely limited supply.",
        2
    ],
    
    # Medical Equipment
    [
        "Field Medical Equipment",
        "http://example.org/military-medical-triage#MedicalEquipment",
        "Medical Equipment",
        "Assorted medical equipment including chest decompression needles, airway management devices, stethoscope, blood pressure cuff, pulse oximeter, and other diagnostic and treatment tools.",
        1
    ],
    
    # Communication Equipment
    [
        "MEDEVAC Communication Equipment",
        "http://example.org/military-medical-triage#MedicalResource",
        "Communication Equipment",
        "Radio and other communication equipment for requesting and coordinating medical evacuation. Essential for arranging transport of casualties to higher levels of care.",
        1
    ]
]

def add_resources_to_scenario():
    """Add defined resources to the Mass Casualty Triage scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        # Verify this is the correct scenario
        if scenario.name != "Mass Casualty Triage" or scenario.world_id != WORLD_ID:
            print(f'Warning: Expected "Mass Casualty Triage" scenario in world {WORLD_ID}')
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
                    category='Medical'
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
