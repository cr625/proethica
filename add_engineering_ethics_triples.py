#!/usr/bin/env python3
"""
Script to add engineering ethics ontology triples to case 187
This is a simplified version that adds triples directly without 
trying to remove previous triples
"""

import sys
import os
import logging
import psycopg2
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("engineering_ethics_integration")

# Engineering ethics ontology namespace
ENGINEERING_ETHICS_NS = "http://proethica.org/ontology/engineering-ethics#"

def get_db_connection():
    """Get a connection to the database"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="ai_ethical_dm",
            user="postgres",
            password="PASS",
            port=5433
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def add_engineering_ethics_triple(conn, entity_id, predicate, object_label, object_uri, predicate_label=None):
    """Add an engineering ethics triple to the database"""
    try:
        cursor = conn.cursor()
        
        now = datetime.now()
        
        # Get the title from documents table instead of entities
        cursor.execute("SELECT title FROM documents WHERE id = %s", (entity_id,))
        result = cursor.fetchone()
        if not result:
            logger.error(f"No document found with ID {entity_id}")
            return False
            
        # Create a subject URI using the document ID
        subject = f"http://proethica.org/entity/document_{entity_id}"
        
        if not predicate_label:
            predicate_label = predicate
            
        # Add the triple
        cursor.execute("""
            INSERT INTO entity_triples 
            (subject, predicate, object_uri, object_literal, is_literal, 
             entity_id, entity_type, graph, created_at, updated_at, triple_metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            subject,                              # subject
            predicate,                            # predicate
            object_uri,                           # object_uri
            object_label,                         # object_literal
            False,                                # is_literal
            entity_id,                            # entity_id
            'document',                           # entity_type
            'engineering-ethics',                 # graph
            now,                                  # created_at
            now,                                  # updated_at
            json.dumps({                          # triple_metadata
                'predicate_label': predicate_label,
                'added_by': 'engineering_ethics_integration'
            })
        ))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error adding triple: {e}")
        return False

def add_engineering_ethics_triples_for_case_187():
    """Add engineering ethics triples for case 187"""
    try:
        case_id = 187
        conn = get_db_connection()
        
        # Engineering ethics concepts for Case 187 (Acknowledging Errors in Design)
        concepts = {
            'roles': [
                ('StructuralEngineerRole', 'Structural Engineer Role'),
                ('ConsultingEngineerRole', 'Consulting Engineer Role')
            ],
            'actions': [
                ('DesignAction', 'Design Action'),
                ('ReviewAction', 'Review Action'),
                ('ReportAction', 'Report Action')
            ],
            'conditions': [
                ('StructuralDeficiency', 'Structural Deficiency'),
                ('SafetyHazard', 'Safety Hazard')
            ],
            'dilemmas': [
                ('ProfessionalResponsibilityDilemma', 'Professional Responsibility Dilemma'),
                ('EngineeringEthicalDilemma', 'Engineering Ethical Dilemma')
            ],
            'principles': [
                ('HonestyPrinciple', 'Honesty Principle'),
                ('DisclosurePrinciple', 'Disclosure Principle'),
                ('PublicSafetyPrinciple', 'Public Safety Principle')
            ]
        }
        
        triple_count = 0
        
        # Add role triples
        for role_id, role_label in concepts['roles']:
            uri = f"{ENGINEERING_ETHICS_NS}{role_id}"
            if add_engineering_ethics_triple(conn, case_id, 'hasRole', role_label, uri, 'has role'):
                triple_count += 1
                logger.info(f"Added role triple: {role_label}")
                
        # Add action triples
        for action_id, action_label in concepts['actions']:
            uri = f"{ENGINEERING_ETHICS_NS}{action_id}"
            if add_engineering_ethics_triple(conn, case_id, 'involvesAction', action_label, uri, 'involves action'):
                triple_count += 1
                logger.info(f"Added action triple: {action_label}")
                
        # Add condition triples
        for condition_id, condition_label in concepts['conditions']:
            uri = f"{ENGINEERING_ETHICS_NS}{condition_id}"
            if add_engineering_ethics_triple(conn, case_id, 'involvesCondition', condition_label, uri, 'involves condition'):
                triple_count += 1
                logger.info(f"Added condition triple: {condition_label}")
                
        # Add dilemma triples
        for dilemma_id, dilemma_label in concepts['dilemmas']:
            uri = f"{ENGINEERING_ETHICS_NS}{dilemma_id}"
            if add_engineering_ethics_triple(conn, case_id, 'presentsDilemma', dilemma_label, uri, 'presents dilemma'):
                triple_count += 1
                logger.info(f"Added dilemma triple: {dilemma_label}")
                
        # Add principle triples
        for principle_id, principle_label in concepts['principles']:
            uri = f"{ENGINEERING_ETHICS_NS}{principle_id}"
            if add_engineering_ethics_triple(conn, case_id, 'involvesPrinciple', principle_label, uri, 'involves principle'):
                triple_count += 1
                logger.info(f"Added principle triple: {principle_label}")
                
        conn.close()
        
        logger.info(f"Successfully added {triple_count} engineering ethics triples to case {case_id}")
        return 0
    except Exception as e:
        logger.error(f"Error adding engineering ethics triples: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(add_engineering_ethics_triples_for_case_187())
