#!/usr/bin/env python3
"""
Script to import NSPE engineering ethics cases as world cases, rather than scenarios.
This script processes NSPE cases from JSON files and imports them as Document objects
with document_type='case_study', associating them with the Engineering world.
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

# Constants
CASE_TRIPLES_DIR = "data/case_triples"
ENGINEERING_WORLD_ID = 1  # Engineering Ethics world ID
NSPE_CASES_FILE = "data/modern_nspe_cases.json"

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

def update_world_cases(world_id, document_id):
    """
    Update the world's cases array to include the new document.
    """
    from app.models.world import World
    
    # Get the world
    world = World.query.get(world_id)
    if not world:
        print(f"Error: World with ID {world_id} not found")
        return False
    
    # Check if cases is None and initialize if needed
    if world.cases is None:
        world.cases = []
    
    # Check if the document is already in the world's cases
    if document_id not in world.cases:
        # Add the document to the world's cases
        world.cases.append(document_id)
        
        # Update the world
        db.session.add(world)
        db.session.commit()
        
        print(f"Added document ID {document_id} to world ID {world_id} cases")
        return True
    else:
        print(f"Document ID {document_id} is already in world ID {world_id} cases")
        return False

def import_nspe_case(case_data, world_id=ENGINEERING_WORLD_ID):
    """
    Import a NSPE case as a Document object with document_type='case_study'.
    """
    from app.models.document import Document
    from app.services.entity_triple_service import EntityTripleService
    from app.services.embedding_service import EmbeddingService
    
    if not case_data:
        return None
    
    # Create a title from the case data
    title = case_data.get('title', '')
    if not title and 'metadata' in case_data and 'case_number' in case_data['metadata']:
        title = f"NSPE Case {case_data['metadata']['case_number']}"
    
    # Get description/content
    description = case_data.get('description', '')
    if not description:
        # Try to get from full_text or html_content
        description = case_data.get('full_text', '') or case_data.get('html_content', '')
        
        # If it's HTML, do some basic cleaning
        if '<' in description and '>' in description:
            import re
            description = description.replace('<p>', '\n\n').replace('</p>', '')
            description = description.replace('<h2>', '\n\n').replace('</h2>', '\n')
            description = description.replace('<h3>', '\n\n').replace('</h3>', '\n')
            description = description.replace('<ol>', '\n').replace('</ol>', '')
            description = description.replace('<li>', '\n- ').replace('</li>', '')
            description = re.sub('<[^<]+?>', '', description)
    
    # Source information
    source = case_data.get('source', '')
    if not source and 'url' in case_data:
        source = case_data['url']
    elif not source and 'metadata' in case_data and 'case_number' in case_data['metadata']:
        source = f"NSPE Board of Ethical Review Case {case_data['metadata']['case_number']}"
    
    # Extract metadata
    metadata = {}
    
    # Copy existing metadata if available
    if 'metadata' in case_data:
        metadata.update(case_data['metadata'])
    
    # Extract any RDF triples if available
    rdf_triples = None
    rdf_namespaces = None
    
    if 'rdf_triples' in case_data:
        rdf_data = case_data['rdf_triples']
        if 'triples' in rdf_data:
            rdf_triples = rdf_data['triples']
        if 'namespaces' in rdf_data:
            rdf_namespaces = rdf_data['namespaces']
    
    # Create the document
    document = Document(
        title=title,
        content=description,
        document_type='case_study',
        world_id=world_id,
        source=source,
        doc_metadata=metadata,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    
    # Add to database
    db.session.add(document)
    db.session.commit()
    
    print(f"Created case document: {title} (ID: {document.id})")
    
    # Update the world's cases array
    update_world_cases(world_id, document.id)
    
    # Process document for embeddings
    try:
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        print(f"Generated embeddings for document ID {document.id}")
    except Exception as e:
        print(f"Error processing embeddings: {str(e)}")
    
    # Process entity triples if available
    if rdf_triples:
        try:
            triple_service = EntityTripleService()
            
            # Import each triple
            for triple in rdf_triples:
                subject = triple.get('subject', '')
                predicate = triple.get('predicate', '')
                object_value = triple.get('object', '')
                is_literal = triple.get('is_literal', False)
                
                # Expand namespaces if needed
                if rdf_namespaces and ':' in subject:
                    prefix, name = subject.split(':', 1)
                    if prefix in rdf_namespaces:
                        subject = rdf_namespaces[prefix] + name
                
                if rdf_namespaces and ':' in predicate:
                    prefix, name = predicate.split(':', 1)
                    if prefix in rdf_namespaces:
                        predicate = rdf_namespaces[prefix] + name
                
                if not is_literal and rdf_namespaces and ':' in object_value:
                    prefix, name = object_value.split(':', 1)
                    if prefix in rdf_namespaces:
                        object_value = rdf_namespaces[prefix] + name
                
                # Create the triple
                triple_service.create_triple(
                    subject=subject,
                    predicate=predicate,
                    object_value=object_value,
                    is_literal=is_literal,
                    graph=f"world:{world_id}/document:{document.id}",
                    entity_type='document',
                    entity_id=document.id,
                    scenario_id=None,  # Important: Not associating with a scenario
                )
            
            print(f"Imported {len(rdf_triples)} triples for document ID {document.id}")
        except Exception as e:
            print(f"Error importing triples: {str(e)}")
    
    return document.id

def import_all_cases(case_triples_dir=CASE_TRIPLES_DIR, world_id=ENGINEERING_WORLD_ID, verbose=True):
    """
    Import all NSPE cases as world cases rather than scenarios.
    """
    app = create_app()
    with app.app_context():
        # Find all JSON files
        json_files = glob.glob(os.path.join(case_triples_dir, "*.json"))
        print(f"Found {len(json_files)} case files to import")
        
        # Import each case
        imported_cases = []
        for json_file in json_files:
            case_data = load_case_from_json(json_file)
            if not case_data:
                continue
            
            # Import the case
            case_id = import_nspe_case(case_data, world_id)
            if case_id:
                imported_cases.append(case_id)
        
        print(f"Successfully imported {len(imported_cases)} NSPE cases")
        return imported_cases

def parse_arguments():
    """
    Parse command line arguments
    """
    import argparse
    parser = argparse.ArgumentParser(description='Import NSPE engineering ethics cases as world cases')
    parser.add_argument('--dir', type=str, default=CASE_TRIPLES_DIR,
                        help=f'Directory containing case triple JSON files (default: {CASE_TRIPLES_DIR})')
    parser.add_argument('--world-id', type=int, default=ENGINEERING_WORLD_ID,
                        help=f'World ID to associate cases with (default: {ENGINEERING_WORLD_ID})')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--skip-cleanup', action='store_true',
                        help='Skip running the cleanup script')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    
    print("===== Importing NSPE Engineering Ethics Cases as World Cases =====")
    
    # Skip cleanup step by default (to avoid import issues)
    if not args.skip_cleanup:
        print("Skipping cleanup step (use --run-cleanup to enable if needed)...")
    
    # Import the cases
    print(f"Importing cases from {args.dir} to world ID {args.world_id}...")
    num_imported = import_all_cases(case_triples_dir=args.dir, world_id=args.world_id, verbose=args.verbose)
    
    print(f"\nCompleted importing {num_imported} NSPE engineering ethics cases.")
    print("You can now view these cases in the Cases tab of the Engineering world.")
