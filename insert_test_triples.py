#!/usr/bin/env python3
"""
Script to insert test entity triples for demonstration purposes.
This allows testing the ontology integration display functionality.
"""

import sys
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("insert_test_triples")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

def insert_test_triples():
    """
    Insert test entity triples for the first case study document.
    This allows testing the ontology integration display.
    """
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        logger.info("Connected to database")

        # Get the first case study document
        cur.execute(
            """
            SELECT id, title
            FROM documents
            WHERE document_type = 'case_study'
            ORDER BY id
            LIMIT 1
            """
        )

        case = cur.fetchone()
        if not case:
            logger.error("No case study documents found")
            return False

        case_id = case['id']
        case_title = case['title']
        logger.info(f"Adding test triples for case ID: {case_id}, Title: {case_title}")

        # Define test triples
        test_triples = [
            {
                'subject': f"http://proethica.org/case/{case_id}/entity/CityAdministrator",
                'predicate': "http://proethica.org/ontology/engineering-ethics#criticizes",
                'object_literal': "Engineer B's judgment",
                'is_literal': True,
                'timeline_order': 1
            },
            {
                'subject': f"http://proethica.org/case/{case_id}/entity/EngineerC",
                'predicate': "http://proethica.org/ontology/engineering-ethics#answersQuestionsFrom",
                'object_literal': "City Administrator",
                'is_literal': True,
                'timeline_order': 2
            },
            {
                'subject': f"http://proethica.org/case/{case_id}",
                'predicate': "http://proethica.org/ontology/engineering-ethics#instantiatesPrinciple",
                'object_uri': "http://proethica.org/ontology/engineering-ethics#CompetitiveEdge",
                'is_literal': False,
                'timeline_order': 3
            },
            {
                'subject': f"http://proethica.org/case/{case_id}",
                'predicate': "http://proethica.org/ontology/engineering-ethics#instantiatesPrinciple",
                'object_uri': "http://proethica.org/ontology/engineering-ethics#ProfessionalIntegrity",
                'is_literal': False,
                'timeline_order': 4
            },
            {
                'subject': f"http://proethica.org/case/{case_id}/event/QuestionAndAnswer",
                'predicate': "http://proethica.org/ontology/engineering-ethics#appliesTo",
                'object_uri': "http://proethica.org/ontology/engineering-ethics#ProfessionalIntegrity",
                'is_literal': False,
                'timeline_order': 5
            }
        ]

        # Insert the triples
        for triple in test_triples:
            cur.execute(
                """
                INSERT INTO entity_triples (
                    subject, predicate, 
                    object_literal, object_uri, is_literal,
                    entity_type, entity_id,
                    created_at, updated_at,
                    timeline_order
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    triple['subject'],
                    triple['predicate'],
                    triple.get('object_literal'),
                    triple.get('object_uri'),
                    triple['is_literal'],
                    'document',
                    case_id,
                    datetime.now(),
                    datetime.now(),
                    triple['timeline_order']
                )
            )

        # Commit the transaction
        conn.commit()
        logger.info(f"Inserted {len(test_triples)} test triples for case ID: {case_id}")

        # Close cursor and connection
        cur.close()
        conn.close()

        return True
    except Exception as e:
        logger.error(f"Error inserting test triples: {str(e)}")
        
        # Rollback and close connections if there's an error
        if 'conn' in locals() and conn:
            conn.rollback()
            
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return False

if __name__ == "__main__":
    if insert_test_triples():
        logger.info("Test triples insertion completed successfully")
        sys.exit(0)
    else:
        logger.error("Test triples insertion failed")
        sys.exit(1)
