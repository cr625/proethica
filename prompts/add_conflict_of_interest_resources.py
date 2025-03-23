#!/usr/bin/env python3
"""
Script for adding resources to the "Conflict of Interest" scenario in the 
"Legal Ethics World (New Jersey)" in the AI Ethical Decision-Making Simulator.

This script adds resources that make sense in the context of the characters:
1. Case File: Horizon Technologies Inc. - Ongoing corporate legal work
2. Case File: Sarah Chen Whistleblower Claim - Potential new case
3. Legal Research: Conflict of Interest Rules - Research on ethical obligations
4. Legal Brief: Whistleblower Protections - Legal arguments for Sarah's case
5. Documentary Evidence: Horizon Technologies Financial Records - Evidence relevant to both cases
6. Court Time: Upcoming Hearing - Limited court time that might create scheduling conflicts

Usage:
1. Run the script: python -m prompts.add_conflict_of_interest_resources
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
SCENARIO_ID = 3  # "Conflict of Interest" scenario
WORLD_ID = 3     # "Legal Ethics World (New Jersey)"

# Resource definitions
# Format: [name, resource_uri, resource_name, description, quantity]
RESOURCES = [
    # Case File for Horizon Technologies Inc.
    [
        "Horizon Technologies Inc. Case File",
        "http://example.org/nj-legal-ethics#CaseFile",
        "Case File",
        "Ongoing corporate legal work for Horizon Technologies Inc., including contracts, compliance matters, and intellectual property protection. This file represents years of legal work and client relationship building by Michael Reynolds.",
        1
    ],
    # Case File for Sarah Chen
    [
        "Sarah Chen Whistleblower Claim",
        "http://example.org/nj-legal-ethics#CaseFile",
        "Case File",
        "Potential whistleblower case for Sarah Chen against Horizon Technologies Inc., alleging financial improprieties and securities violations. This new case directly conflicts with the firm's ongoing representation of Horizon Technologies.",
        1
    ],
    # Legal Research on conflict of interest rules
    [
        "Conflict of Interest Research",
        "http://example.org/nj-legal-ethics#LegalResearch",
        "Legal Research",
        "Research compiled by Jason Martinez on New Jersey Rules of Professional Conduct 1.7 (Conflict of Interest) and relevant case law. This research was conducted after Jason realized the potential conflict between the two cases.",
        1
    ],
    # Legal Brief on whistleblower protections
    [
        "Whistleblower Protections Brief",
        "http://example.org/nj-legal-ethics#LegalBrief",
        "Legal Brief",
        "Draft legal brief outlining whistleblower protections under federal and state law, prepared by Jason Martinez before the conflict of interest was identified. This document represents work product that may need to be transferred if the firm cannot represent Sarah Chen.",
        1
    ],
    # Documentary Evidence from Horizon Technologies
    [
        "Horizon Technologies Financial Records",
        "http://example.org/nj-legal-ethics#DocumentaryEvidence",
        "Documentary Evidence",
        "Financial records from Horizon Technologies that may be relevant to both their ongoing legal matters and to Sarah Chen's whistleblower claims. These documents create a particular ethical challenge as they were obtained during the firm's representation of Horizon.",
        5
    ],
    # Court Time
    [
        "Upcoming Court Hearing",
        "http://example.org/nj-legal-ethics#CourtTime",
        "Court Time",
        "Limited court time scheduled for a preliminary hearing that could potentially involve both Horizon Technologies and Sarah Chen matters. This resource represents the scheduling conflicts that can arise in conflict of interest situations.",
        1
    ],
]

def add_resources_to_scenario():
    """Add defined resources to the Conflict of Interest scenario."""
    app = create_app()
    with app.app_context():
        # Get the scenario
        scenario = Scenario.query.get(SCENARIO_ID)
        if not scenario:
            print(f'Scenario with ID {SCENARIO_ID} not found')
            return
        
        # Verify this is the correct scenario
        if scenario.name != "Conflict of Interest" or scenario.world_id != WORLD_ID:
            print(f'Warning: Expected "Conflict of Interest" scenario in world {WORLD_ID}')
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
                    category='Legal'
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
