#!/usr/bin/env python3
"""
Script to import case triples from JSON files directly to the database
using the EntityTripleService, instead of relying on the HTTP API.
"""

import json
import sys
import os
import glob
import datetime
from collections import defaultdict

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.services.entity_triple_service import EntityTripleService

# Constants
CASE_TRIPLES_DIR = "data/case_triples"
ENGINEERING_WORLD_ID = 1  # Assuming Engineering Ethics world ID is 1

def load_case_from_json(file_path):
    """
    Load a case from a JSON file.
    """
    try:
        with open(file_path, 'r') as f:
            case_data = json.load(f)
            print(f"Successfully loaded case data from {file_path}")
            return case_data
    except Exception as e:
        print(f"Error loading case file: {str(e)}")
        return None

def import_case_triples(case_data, scenario_id, entity_triple_service):
    """
    Import case triples into the database using the EntityTripleService.
    """
    if not case_data:
        return False
    
    # Extract case information
    title = case_data.get('title', '')
    description = case_data.get('description', '')
    source = case_data.get('source', '')
    
    # Extract triples and namespaces from the case data
    rdf_triples = case_data.get('rdf_triples', {})
    triples = rdf_triples.get('triples', [])
    namespaces = rdf_triples.get('namespaces', {})
    
    # Track success and failure counts
    success_count = 0
    failure_count = 0
    
    print(f"Importing {len(triples)} triples for case: {title}")
    
    # Convert each triple to an EntityTriple record
    for triple in triples:
        subject = triple.get('subject', '')
        predicate = triple.get('predicate', '')
        object_value = triple.get('object', '')
        is_literal = triple.get('is_literal', False)
        
        # Create the EntityTriple record
        try:
            # Check if using a namespace prefix
            subject_parts = subject.split(':')
            if len(subject_parts) > 1 and subject_parts[0] in namespaces:
                # Expand the namespace
                namespace = namespaces[subject_parts[0]]
                subject = namespace + subject_parts[1]
            
            # Same for predicate
            predicate_parts = predicate.split(':')
            if len(predicate_parts) > 1 and predicate_parts[0] in namespaces:
                namespace = namespaces[predicate_parts[0]]
                predicate = namespace + predicate_parts[1]
            
            # And for object if not literal
            if not is_literal:
                object_parts = object_value.split(':')
                if len(object_parts) > 1 and object_parts[0] in namespaces:
                    namespace = namespaces[object_parts[0]]
                    object_value = namespace + object_parts[1]
            
            # Create EntityTriple with these values
            entity_triple = EntityTriple(
                subject=subject,
                predicate=predicate,
                object_literal=object_value if is_literal else None,
                object_uri=None if is_literal else object_value,
                is_literal=is_literal,
                graph=f"scenario:{scenario_id}",
                entity_type="case",
                entity_id=scenario_id,
                scenario_id=scenario_id,
                created_at=datetime.datetime.utcnow()
            )
            
            # Add to the database
            db.session.add(entity_triple)
            success_count += 1
        except Exception as e:
            print(f"Error creating triple: {str(e)}")
            failure_count += 1
    
    # Commit changes
    try:
        db.session.commit()
        print(f"Successfully imported {success_count} triples")
        if failure_count > 0:
            print(f"Failed to import {failure_count} triples")
        return True
    except Exception as e:
        print(f"Error committing changes: {str(e)}")
        db.session.rollback()
        return False

def create_scenario_for_case(case_data, app_context):
    """
    Create a scenario for the case in the database.
    """
    if not case_data:
        return None
    
    from app.models.scenario import Scenario
    from app.models.world import World
    
    # Check if a world exists for Engineering Ethics
    world = World.query.get(ENGINEERING_WORLD_ID)
    if not world:
        print(f"Error: Engineering Ethics world (ID: {ENGINEERING_WORLD_ID}) not found")
        return None
    
    # Extract case information
    title = case_data.get('title', '')
    description = case_data.get('description', '')
    source = case_data.get('source', '')
    
    # Create a unique name for the scenario using the case number or title
    metadata = case_data.get('metadata', {})
    case_number = metadata.get('case_number', '')
    if not case_number and 'rdf_triples' in case_data:
        # Try to find a case number in the triples
        for triple in case_data['rdf_triples'].get('triples', []):
            if triple.get('predicate') == 'NSPE:caseNumber' and triple.get('is_literal', False):
                case_number = triple.get('object', '')
                break
    
    # Generate scenario name
    scenario_name = f"NSPE Case {case_number}" if case_number else title
    
    # Check if a scenario with this name already exists
    existing_scenario = Scenario.query.filter_by(
        world_id=world.id, 
        name=scenario_name
    ).first()
    
    if existing_scenario:
        print(f"Scenario already exists: {scenario_name} (ID: {existing_scenario.id})")
        return existing_scenario.id
    
    # Create a new scenario
    try:
        # Initialize metadata dictionary if it doesn't exist
        scenario_metadata = metadata.copy() if metadata else {}
        
        # Add source to metadata
        if source:
            scenario_metadata['source'] = source
        
        scenario = Scenario(
            name=scenario_name,
            description=description,
            world_id=world.id,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            scenario_metadata=scenario_metadata
        )
        
        db.session.add(scenario)
        db.session.commit()
        
        print(f"Created scenario: {scenario_name} (ID: {scenario.id})")
        return scenario.id
    except Exception as e:
        print(f"Error creating scenario: {str(e)}")
        db.session.rollback()
        return None

def import_all_cases(case_triples_dir=CASE_TRIPLES_DIR, app=None, verbose=True):
    """
    Import all cases from JSON files in the specified directory.
    """
    # Create the app and app context if not provided
    if not app:
        app = create_app()
    
    # Use the app context
    with app.app_context():
        # Create the EntityTripleService
        entity_triple_service = EntityTripleService()
        
        # Find all JSON files
        json_files = glob.glob(os.path.join(case_triples_dir, "*.json"))
        print(f"Found {len(json_files)} case files to import")
        
        # Import each case
        imported_cases = 0
        for json_file in json_files:
            case_data = load_case_from_json(json_file)
            if not case_data:
                continue
            
            # Create a scenario for the case
            scenario_id = create_scenario_for_case(case_data, app)
            if not scenario_id:
                continue
            
            # Import the triples
            if import_case_triples(case_data, scenario_id, entity_triple_service):
                imported_cases += 1
        
        print(f"Successfully imported {imported_cases} cases")
        return imported_cases

def parse_arguments():
    """
    Parse command line arguments
    """
    import argparse
    parser = argparse.ArgumentParser(description='Import case triples from JSON files to the database')
    parser.add_argument('--dir', type=str, default=CASE_TRIPLES_DIR,
                        help=f'Directory containing case triple JSON files (default: {CASE_TRIPLES_DIR})')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose output')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    
    print("===== Importing NSPE Engineering Ethics Cases to Database =====")
    num_imported = import_all_cases(case_triples_dir=args.dir, verbose=args.verbose)
    print(f"\nCompleted importing {num_imported} engineering ethics cases.")
