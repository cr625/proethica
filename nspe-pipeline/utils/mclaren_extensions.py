"""
McLaren Extensions
-----------------
Adds McLaren's extensional definition related triples to cases.

This module:
1. Extracts principles mentioned in a case
2. Creates PrincipleInstantiation triples
3. Creates PrincipleConflict triples if multiple principles are found
4. Creates OperationalizationTechnique triples

All triples are properly formed with complete subject-predicate-object format
and use document URIs for subjects consistently.
"""

import logging
import traceback
from datetime import datetime
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mclaren_extensions")

def format_name_for_uri(name):
    """
    Format a name for inclusion in a URI by removing invalid characters
    and converting spaces to underscores.
    """
    # Remove any characters that aren't allowed in a URI
    name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name)
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Convert to lowercase for consistency
    return name.lower()

def get_document_uri(document_id):
    """
    Generate a URI for a document based on its ID.
    """
    return f"http://proethica.org/entity/document_{document_id}"

def validate_triple(triple):
    """
    Validate that a triple has all required fields and consistent structure.
    
    Args:
        triple: The triple dictionary to validate
        
    Returns:
        bool: True if the triple is valid, False otherwise
    """
    # Check required fields
    required_fields = ['subject', 'predicate', 'is_literal']
    for field in required_fields:
        if field not in triple:
            logger.warning(f"Triple missing required field: {field}")
            return False
    
    # Check that either object_uri or object_literal is set
    if (not triple.get('object_uri') and not triple.get('object_literal')) or \
       (triple.get('is_literal') and not triple.get('object_literal')) or \
       (not triple.get('is_literal') and not triple.get('object_uri')):
        logger.warning("Triple has inconsistent object specification")
        return False
        
    return True

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
        
        # Consistent document URI as subject
        document_uri = get_document_uri(case_id)
            
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
        
        # Define namespaces for clarity
        mclaren_ns = "http://proethica.org/ontology/mclaren-extensional#"
        rdf_ns = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        
        # 1. Create PrincipleInstantiation triples with complete subject-predicate-object form
        for i, principle in enumerate(principles):
            # Create unique identifiers for instantiation entities
            instantiation_id = f"PrincipleInstantiation_{case_id}_{i}"
            instantiation_uri = f"{mclaren_ns}{instantiation_id}"
            
            # Triple linking document to instantiation
            instantiation_triple = {
                'subject': document_uri,
                'predicate': f"{mclaren_ns}hasInstantiation",
                'object_uri': instantiation_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'principle_uri': principle.get('uri'),
                    'principle_label': principle.get('label'),
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'entity_name': f"Principle Instantiation {i+1}",
                    'display_label': f"has instantiation: Principle Instantiation {i+1}"
                }
            }
            
            # Only add valid triples
            if validate_triple(instantiation_triple):
                new_triples.append(instantiation_triple)
            
            # Triple linking instantiation to principle
            principle_link_triple = {
                'subject': instantiation_uri,
                'predicate': f"{mclaren_ns}appliesPrinciple",
                'object_uri': principle.get('uri'),
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': f"applies principle: {principle.get('label')}"
                }
            }
            
            if validate_triple(principle_link_triple):
                new_triples.append(principle_link_triple)
            
            # Add the type triple but with a better structure
            type_triple = {
                'subject': instantiation_uri,
                'predicate': f"{rdf_ns}type",
                'object_uri': f"{mclaren_ns}PrincipleInstantiation",
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': f"is a: Principle Instantiation"
                }
            }
            
            if validate_triple(type_triple):
                new_triples.append(type_triple)
            
            # Add a triple back to the document for better navigation
            document_link_triple = {
                'subject': instantiation_uri,
                'predicate': f"{mclaren_ns}belongsToCase",
                'object_uri': document_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': f"belongs to case: {case.get('title', f'Case {case_id}')}"
                }
            }
            
            if validate_triple(document_link_triple):
                new_triples.append(document_link_triple)
        
        # 2. If multiple principles, create PrincipleConflict triple
        if len(principles) >= 2:
            # Create unique identifier for conflict entity
            conflict_id = f"PrincipleConflict_{case_id}"
            conflict_uri = f"{mclaren_ns}{conflict_id}"
            
            # Triple linking document to conflict
            conflict_triple = {
                'subject': document_uri,
                'predicate': f"{mclaren_ns}hasConflict",
                'object_uri': conflict_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'entity_name': "Principle Conflict",
                    'display_label': "has conflict: Principle Conflict"
                }
            }
            
            if validate_triple(conflict_triple):
                new_triples.append(conflict_triple)
            
            # Create triples linking conflict to first principle
            principle1_link_triple = {
                'subject': conflict_uri,
                'predicate': f"{mclaren_ns}hasPrinciple1",
                'object_uri': principles[0].get('uri'),
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': f"has first principle: {principles[0].get('label')}"
                }
            }
            
            if validate_triple(principle1_link_triple):
                new_triples.append(principle1_link_triple)
            
            # Create triple linking conflict to second principle
            principle2_link_triple = {
                'subject': conflict_uri,
                'predicate': f"{mclaren_ns}hasPrinciple2",
                'object_uri': principles[1].get('uri'),
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': f"has second principle: {principles[1].get('label')}"
                }
            }
            
            if validate_triple(principle2_link_triple):
                new_triples.append(principle2_link_triple)
            
            # Create RDF type triple for conflict
            conflict_type_triple = {
                'subject': conflict_uri,
                'predicate': f"{rdf_ns}type",
                'object_uri': f"{mclaren_ns}PrincipleConflict",
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': "is a: Principle Conflict"
                }
            }
            
            if validate_triple(conflict_type_triple):
                new_triples.append(conflict_type_triple)
            
            # Add a triple back to the document for better navigation
            conflict_document_link_triple = {
                'subject': conflict_uri,
                'predicate': f"{mclaren_ns}belongsToCase",
                'object_uri': document_uri,
                'object_literal': None,
                'is_literal': False,
                'graph': "mclaren-extensional",
                'triple_metadata': {
                    'case_id': case_id,
                    'triple_type': 'mclaren_extensional',
                    'display_label': f"belongs to case: {case.get('title', f'Case {case_id}')}"
                }
            }
            
            if validate_triple(conflict_document_link_triple):
                new_triples.append(conflict_document_link_triple)
        
        # 3. Create OperationalizationTechnique triple
        technique_id = f"PrincipleInstantiationTechnique_{case_id}"
        technique_uri = f"{mclaren_ns}{technique_id}"
        
        # Triple linking document to technique
        technique_triple = {
            'subject': document_uri,
            'predicate': f"{mclaren_ns}usesTechnique",
            'object_uri': technique_uri,
            'object_literal': None,
            'is_literal': False,
            'graph': "mclaren-extensional",
            'triple_metadata': {
                'case_id': case_id,
                'triple_type': 'mclaren_extensional',
                'entity_name': "Principle Instantiation Technique",
                'display_label': "uses technique: Principle Instantiation Technique"
            }
        }
        
        if validate_triple(technique_triple):
            new_triples.append(technique_triple)
        
        # Create RDF type triple for technique
        technique_type_triple = {
            'subject': technique_uri,
            'predicate': f"{rdf_ns}type",
            'object_uri': f"{mclaren_ns}PrincipleInstantiationTechnique",
            'object_literal': None,
            'is_literal': False,
            'graph': "mclaren-extensional",
            'triple_metadata': {
                'case_id': case_id,
                'triple_type': 'mclaren_extensional',
                'display_label': "is a: Principle Instantiation Technique"
            }
        }
        
        if validate_triple(technique_type_triple):
            new_triples.append(technique_type_triple)
        
        # Add a triple back to the document for better navigation
        technique_document_link_triple = {
            'subject': technique_uri,
            'predicate': f"{mclaren_ns}belongsToCase",
            'object_uri': document_uri,
            'object_literal': None,
            'is_literal': False,
            'graph': "mclaren-extensional",
            'triple_metadata': {
                'case_id': case_id,
                'triple_type': 'mclaren_extensional',
                'display_label': f"belongs to case: {case.get('title', f'Case {case_id}')}"
            }
        }
        
        if validate_triple(technique_document_link_triple):
            new_triples.append(technique_document_link_triple)
        
        # Store all the new triples
        valid_triples = [t for t in new_triples if validate_triple(t)]
        logger.info(f"Adding {len(valid_triples)} McLaren extensional definition triples to case {case_id}")
        app_context.store_entity_triples(case_id, valid_triples, replace=False)
        
        return {
            'success': True,
            'message': f"Successfully added {len(valid_triples)} McLaren extensional definition triples to case {case_id}",
            'triple_count': len(valid_triples)
        }
        
    except Exception as e:
        logger.error(f"Error adding McLaren extensional triples: {str(e)}")
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }
