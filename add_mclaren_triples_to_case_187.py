#!/usr/bin/env python3
"""
Add McLaren extensional definition triples to case 187
"""

import sys
import os
import logging
import traceback
from datetime import datetime

# Add parent directory to path to import from app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import Flask app to create application context
from app import create_app

# Create app instance
app = create_app()

from app.services.application_context_service import ApplicationContextService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("add_mclaren_triples")

def add_mclaren_extensional_triples(case_id, app_context):
    """
    Add McLaren extensional definition related triples to the case.
    
    Args:
        case_id: ID of the case
        app_context: ApplicationContextService instance
        
    Returns:
        dict: Result of the operation
    """
    try:
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
    """Add McLaren extensional triples to case 187."""
    case_id = 187
    
    logger.info(f"Adding McLaren extensional definition triples to case {case_id}")
    
    # Use application context to interact with the database
    with app.app_context():
        app_context = ApplicationContextService()
        result = add_mclaren_extensional_triples(case_id, app_context)
        
    if result['success']:
        logger.info(f"Successfully added {result['triple_count']} McLaren extensional definition triples to case {case_id}")
        return 0
    else:
        logger.error(f"Failed to add McLaren extensional triples: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
