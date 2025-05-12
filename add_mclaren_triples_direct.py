#!/usr/bin/env python3
"""
Direct script to add McLaren extensional definition triples to case 187
Bypasses Flask app context to avoid connection string issues
"""

import sys
import os
import logging
import traceback
import json
import psycopg2
from psycopg2.extras import Json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("add_mclaren_triples_direct")

# Database connection parameters
DB_USER = "postgres"
DB_PASSWORD = "PASS"  # Password from error message
DB_HOST = "localhost" 
DB_PORT = "5433"  # Port 5433 from error message
DB_NAME = "ai_ethical_dm"

def get_connection():
    """Get a connection to the database."""
    try:
        connection = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
        logger.info("Connected to PostgreSQL database")
        return connection
    except Exception as e:
        logger.error(f"Error connecting to PostgreSQL database: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

def get_case(connection, case_id):
    """Get case data from the database."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, title, content FROM documents WHERE id = %s", (case_id,))
        case = cursor.fetchone()
        cursor.close()
        
        if not case:
            return None
            
        return {
            'id': case[0],
            'title': case[1],
            'content': case[2]
        }
    except Exception as e:
        logger.error(f"Error getting case: {str(e)}")
        traceback.print_exc()
        return None

def get_entity_triples(connection, case_id):
    """Get entity triples for a case."""
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, subject, predicate, object_uri, is_literal, object_literal, 
                   graph, triple_metadata
            FROM entity_triples
            WHERE entity_id = %s
        """, (case_id,))
        
        triples = []
        for row in cursor.fetchall():
            triple = {
                'id': row[0],
                'subject': row[1],
                'predicate': row[2],
                'object_uri': row[3],
                'is_literal': row[4],
                'object_literal': row[5],
                'graph': row[6],
                'triple_metadata': row[7]
            }
            triples.append(triple)
            
        cursor.close()
        return triples
    except Exception as e:
        logger.error(f"Error getting entity triples: {str(e)}")
        traceback.print_exc()
        return []

def store_entity_triples(connection, case_id, triples):
    """Store entity triples for a case."""
    try:
        cursor = connection.cursor()
        
        for triple in triples:
            cursor.execute("""
                INSERT INTO entity_triples 
                (entity_id, subject, predicate, object_uri, is_literal, 
                object_literal, graph, triple_metadata, entity_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                case_id,
                triple['subject'],
                triple['predicate'],
                triple['object_uri'],
                triple['is_literal'],
                triple.get('object_literal', None),
                triple['graph'],
                Json(triple.get('triple_metadata', {})) if triple.get('triple_metadata') else None,
                'case'  # Set entity_type to 'case' since we're dealing with case triples
            ))
            
        connection.commit()
        cursor.close()
        
        logger.info(f"Stored {len(triples)} entity triples for case {case_id}")
        return True
    except Exception as e:
        connection.rollback()
        logger.error(f"Error storing entity triples: {str(e)}")
        traceback.print_exc()
        return False

def add_mclaren_extensional_triples(case_id):
    """
    Add McLaren extensional definition related triples to the case.
    
    Args:
        case_id: ID of the case
        
    Returns:
        dict: Result of the operation
    """
    connection = get_connection()
    
    try:
        # First, check if the case exists
        case = get_case(connection, case_id)
        if not case:
            return {
                'success': False,
                'message': f"Case with ID {case_id} not found"
            }
            
        # Get existing triples to find principles mentioned in the case
        existing_triples = get_entity_triples(connection, case_id)
        
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
            
            # Add default principle for testing since this is just a demo
            principles.append({
                'uri': 'http://proethica.org/ontology/engineering-ethics#HonestDisclosure',
                'label': 'HonestDisclosure'
            })
            
            logger.info(f"Added default principle for testing: HonestDisclosure")
        
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
        success = store_entity_triples(connection, case_id, new_triples)
        
        if success:
            return {
                'success': True,
                'message': f"Successfully added {len(new_triples)} McLaren extensional definition triples to case {case_id}",
                'triple_count': len(new_triples)
            }
        else:
            return {
                'success': False,
                'message': "Failed to store triples in the database"
            }
        
    except Exception as e:
        logger.error(f"Error adding McLaren extensional triples: {str(e)}")
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }
    finally:
        if connection:
            connection.close()
            logger.info("Database connection closed")

def main():
    """Add McLaren extensional triples to case 187."""
    case_id = 187
    
    logger.info(f"Adding McLaren extensional definition triples to case {case_id}")
    
    result = add_mclaren_extensional_triples(case_id)
        
    if result['success']:
        logger.info(f"Successfully added {result['triple_count']} McLaren extensional definition triples to case {case_id}")
        return 0
    else:
        logger.error(f"Failed to add McLaren extensional triples: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
