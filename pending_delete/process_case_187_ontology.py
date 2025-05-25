#!/usr/bin/env python3
"""
Process Case 187 Ontology Integration
-------------------------------------
This script:
1. Integrates identified entities from case 187 with a world ontology
2. Adds McLaren extensional definition triples to the case
3. Demonstrates the process that will be integrated into the NSPE case pipeline

Usage:
    python process_case_187_ontology.py [--world-id WORLD_ID]
"""

import sys
import os
import logging
import argparse
from datetime import datetime
import traceback

# Add parent directory to path to import from app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import Flask app to create application context
from app import create_app

# Create app instance
app = create_app()

# Import integration components
import sys
import os

# Add nspe-pipeline to path to handle the hyphenated directory name
nspe_pipeline_path = os.path.join(os.path.dirname(__file__), 'nspe-pipeline')
sys.path.append(nspe_pipeline_path)

from utils.world_entity_integration import integrate_case_with_world
from app.services.application_context_service import ApplicationContextService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("case_187_ontology_integration")

def get_world_id_for_case(case_id):
    """Get the world ID associated with a case."""
    try:
        # Create Flask application context
        with app.app_context():
            app_context = ApplicationContextService()
            case = app_context.get_case(case_id)
            if not case:
                logger.error(f"Case with ID {case_id} not found")
                return None
                
            world_id = case.get('world_id')
            if not world_id:
                logger.error(f"Case with ID {case_id} is not associated with any world")
                return None
                
            return world_id
    except Exception as e:
        logger.error(f"Error getting world ID for case: {str(e)}")
        traceback.print_exc()
        return None

def add_mclaren_extensional_triples(case_id):
    """
    Add McLaren extensional definition related triples to the case.
    
    Args:
        case_id: ID of the case
        
    Returns:
        dict: Result of the operation
    """
    try:
        # Create Flask application context
        with app.app_context():
            app_context = ApplicationContextService()
        
            # First, check if the case exists
            case = app_context.get_case(case_id)
            if not case:
                return {
                    'success': False,
                    'message': f"Case with ID {case_id} not found"
                }
                
            # Get existing triples to find principles mentioned in the case
            existing_triples = app_context.get_entity_triples(case_id)
        
        # Extract principles from triples
        principles = []
        for triple in existing_triples:
            predicate = triple.get('predicate', '')
            object_uri = triple.get('object_uri', '')
            
            # Look for triples that reference principles
            if 'hasPrinciple' in predicate or 'appliesPrinciple' in predicate:
                if object_uri and object_uri not in [p.get('uri') for p in principles]:
                    principles.append({
                        'uri': object_uri,
                        'label': object_uri.split('/')[-1].split('#')[-1]
                    })
                    
        if not principles:
            logger.warning(f"No principles found in case {case_id}")
        
        # Create new triples for McLaren extensional definitions
        new_triples = []
        
        # 1. Create PrincipleInstantiation triples
        for i, principle in enumerate(principles):
            # Create triple for principle instantiation
            instantiation_triple = {
                'subject': f"Case {case_id}",
                'predicate': "http://proethica.org/ontology/mclaren-extensional#hasInstantiation",
                'object_uri': f"http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiation_{case_id}_{i}",
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'principle_uri': principle.get('uri'),
                    'principle_label': principle.get('label'),
                    'case_id': case_id
                }
            }
            new_triples.append(instantiation_triple)
            
            # Create triple linking instantiation to principle
            principle_link_triple = {
                'subject': f"http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiation_{case_id}_{i}",
                'predicate': "http://proethica.org/ontology/mclaren-extensional#appliesPrinciple",
                'object_uri': principle.get('uri'),
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id
                }
            }
            new_triples.append(principle_link_triple)
            
            # Create RDF type triple
            type_triple = {
                'subject': f"http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiation_{case_id}_{i}",
                'predicate': "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                'object_uri': "http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiation",
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id
                }
            }
            new_triples.append(type_triple)
        
        # 2. If multiple principles, create PrincipleConflict triple
        if len(principles) >= 2:
            # Create triple for principle conflict
            conflict_triple = {
                'subject': f"Case {case_id}",
                'predicate': "http://proethica.org/ontology/mclaren-extensional#hasConflict",
                'object_uri': f"http://proethica.org/ontology/mclaren-extensional#PrincipleConflict_{case_id}",
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id
                }
            }
            new_triples.append(conflict_triple)
            
            # Create triples linking conflict to principles
            principle1_link_triple = {
                'subject': f"http://proethica.org/ontology/mclaren-extensional#PrincipleConflict_{case_id}",
                'predicate': "http://proethica.org/ontology/mclaren-extensional#hasPrinciple1",
                'object_uri': principles[0].get('uri'),
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id
                }
            }
            new_triples.append(principle1_link_triple)
            
            principle2_link_triple = {
                'subject': f"http://proethica.org/ontology/mclaren-extensional#PrincipleConflict_{case_id}",
                'predicate': "http://proethica.org/ontology/mclaren-extensional#hasPrinciple2",
                'object_uri': principles[1].get('uri'),
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id
                }
            }
            new_triples.append(principle2_link_triple)
            
            # Create RDF type triple
            conflict_type_triple = {
                'subject': f"http://proethica.org/ontology/mclaren-extensional#PrincipleConflict_{case_id}",
                'predicate': "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                'object_uri': "http://proethica.org/ontology/mclaren-extensional#PrincipleConflict",
                'is_literal': False,
                'graph': f"http://proethica.org/mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id
                }
            }
            new_triples.append(conflict_type_triple)
        
        # 3. Create OperationalizationTechnique triple for principle instantiation
        technique_triple = {
            'subject': f"Case {case_id}",
            'predicate': "http://proethica.org/ontology/mclaren-extensional#usesTechnique",
            'object_uri': f"http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiationTechnique_{case_id}",
            'is_literal': False,
            'graph': f"http://proethica.org/mclaren-extensional",
            'triple_metadata': {
                'case_id': case_id
            }
        }
        new_triples.append(technique_triple)
        
        # Create RDF type triple
        technique_type_triple = {
            'subject': f"http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiationTechnique_{case_id}",
            'predicate': "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            'object_uri': "http://proethica.org/ontology/mclaren-extensional#PrincipleInstantiationTechnique",
            'is_literal': False,
            'graph': f"http://proethica.org/mclaren-extensional",
            'triple_metadata': {
                'case_id': case_id
            }
        }
        new_triples.append(technique_type_triple)
        
        with app.app_context():
            app_context = ApplicationContextService()
            # Store all the new triples
            logger.info(f"Adding {len(new_triples)} McLaren extensional definition triples to case {case_id}")
            app_context.store_entity_triples(case_id, new_triples, replace=False)
        
        return {
            'success': True,
            'message': f"Successfully added {len(new_triples)} McLaren extensional definition triples to case {case_id}",
            'triple_count': len(new_triples)
        }
        
    except Exception as e:
        logger.error(f"Error adding McLaren extensional triples: {str(e)}")
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Process Case 187 Ontology Integration')
    parser.add_argument('--world-id', type=int, help='ID of the world to integrate with (optional)')
    args = parser.parse_args()
    
    case_id = 187  # Case ID for "Acknowledging Errors in Design"
    
    # Step 1: Get the world ID if not provided
    world_id = args.world_id
    if not world_id:
        logger.info(f"No world ID provided, retrieving from case {case_id}")
        world_id = get_world_id_for_case(case_id)
        
    if not world_id:
        logger.error(f"Could not determine world ID for case {case_id}")
        logger.info(f"Using default world ID 1")
        world_id = 1  # Use default world ID if not found
        
    logger.info(f"Using world ID: {world_id}")
    
    # Step 2: Integrate case entities with world ontology
    logger.info(f"Step 1: Integrating entities from case {case_id} with world {world_id}")
    with app.app_context():
        integration_result = integrate_case_with_world(case_id, world_id)
    
    if integration_result['success']:
        added_count = sum(len(entities) for entities in integration_result['added_entities'].values())
        logger.info(f"Successfully integrated {added_count} entities with world {world_id}")
        
        # Print summary of added entities
        for entity_type, entities in integration_result['added_entities'].items():
            if entities:
                entity_labels = [e.get('label') for e in entities]
                logger.info(f"  {entity_type}: {', '.join(entity_labels)}")
    else:
        logger.error(f"Failed to integrate with world: {integration_result['message']}")
    
    # Step 3: Add McLaren extensional triples
    logger.info(f"Step 2: Adding McLaren extensional definition triples to case {case_id}")
    extensional_result = add_mclaren_extensional_triples(case_id)
    
    if extensional_result['success']:
        logger.info(f"Successfully added {extensional_result['triple_count']} McLaren extensional definition triples")
    else:
        logger.error(f"Failed to add McLaren extensional triples: {extensional_result['message']}")
    
    # Final result
    if integration_result['success'] or extensional_result['success']:
        logger.info(f"Case {case_id} processing complete.")
        logger.info(f"Case can be viewed at: http://localhost:5000/cases/{case_id}")
        return 0
    else:
        logger.error(f"Case {case_id} processing failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
