#!/usr/bin/env python3
"""
Script to enhance the display of ontology components in case views.
This script adds ontology-related information to case metadata to make
it available for display in the case detail view.
"""

import sys
import logging
import traceback
import psycopg2
import psycopg2.extras
import json
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("enhanced_ontology_display")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

def enhance_ontology_display():
    """
    Add ontology-related information to case metadata for display in case detail view
    """
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        logger.info("Connected to database")

        # Get all cases with entity triples
        cur.execute(
            """
            SELECT DISTINCT et.entity_id
            FROM entity_triples et
            WHERE et.entity_type = 'document'
            ORDER BY et.entity_id
            """
        )
        
        case_ids = [row['entity_id'] for row in cur.fetchall()]
        logger.info(f"Found {len(case_ids)} cases with entity triples")
        
        updated_count = 0
        
        for case_id in case_ids:
            logger.info(f"Processing case ID: {case_id}")
            
            # Get the document record
            cur.execute(
                """
                SELECT id, title, doc_metadata
                FROM documents
                WHERE id = %s
                """,
                (case_id,)
            )
            
            case = cur.fetchone()
            if not case:
                logger.warning(f"Case not found: {case_id}")
                continue
                
            # Get entity triples for this case
            cur.execute(
                """
                SELECT subject, predicate, object_literal, object_uri, is_literal
                FROM entity_triples
                WHERE entity_type = 'document' AND entity_id = %s
                ORDER BY id
                """,
                (case_id,)
            )
            
            triples = cur.fetchall()
            logger.info(f"Found {len(triples)} triples for case {case_id}")
            
            # Process triples to extract principle instantiations
            principles = set()
            principle_instantiations = []
            
            for triple in triples:
                # Check for principle references
                predicate = triple['predicate']
                obj = triple['object_literal'] if triple['is_literal'] else triple['object_uri']
                
                if 'principle' in predicate.lower() or 'principle' in str(obj).lower():
                    if 'instantiation' in predicate.lower() or 'appliesTo' in predicate:
                        fact = None
                        principle = None
                        
                        if 'principle' in predicate.lower():
                            # Predicate indicates principle, object is the fact
                            principle = extract_name_from_uri(predicate)
                            fact = obj
                        else:
                            # Object is principle, subject is the fact
                            principle = extract_name_from_uri(obj)
                            fact = extract_name_from_uri(triple['subject'])
                        
                        if principle:
                            principles.add(principle)
                            
                            principle_instantiations.append({
                                'principle': principle,
                                'fact': fact
                            })
                
                # Other predicate categories can be added here
            
            # Create metadata updates with ontology information
            metadata = case['doc_metadata'] if case['doc_metadata'] else {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            
            # Add ontology-related information
            metadata['ontology_info'] = {
                'triple_count': len(triples),
                'principles': list(principles),
                'principle_instantiations': principle_instantiations,
                'last_updated': datetime.now().isoformat()
            }
            
            # Update the case metadata
            cur.execute(
                """
                UPDATE documents
                SET doc_metadata = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (json.dumps(metadata), datetime.now(), case_id)
            )
            
            updated_count += 1
            
            # Commit every 10 cases to avoid long transactions
            if updated_count % 10 == 0:
                conn.commit()
                logger.info(f"Committed batch of cases - {updated_count} processed so far")
        
        # Final commit
        conn.commit()
        
        # Close cursor and connection
        cur.close()
        conn.close()
        
        logger.info(f"Enhanced display for {updated_count} cases in total")
        return True
    except Exception as e:
        logger.error(f"Error enhancing ontology display: {str(e)}")
        traceback.print_exc()
        
        # Rollback and close connections if there's an error
        if 'conn' in locals() and conn:
            conn.rollback()
            
            if 'cur' in locals() and cur:
                cur.close()
            
            conn.close()
            
        return False

def extract_name_from_uri(uri):
    """
    Extract a readable name from a URI.
    For example, 'http://proethica.org/ontology/engineering-ethics#PublicSafety'
    would become 'Public Safety'
    """
    if not uri:
        return None
    
    # Handle string URIs
    uri_str = str(uri)
    
    # Extract the last part after # or /
    if '#' in uri_str:
        name = uri_str.split('#')[-1]
    else:
        name = uri_str.split('/')[-1]
    
    # Convert camelCase or PascalCase to space-separated words
    import re
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    
    return name

if __name__ == "__main__":
    if enhance_ontology_display():
        logger.info("Ontology display enhancement completed successfully")
        sys.exit(0)
    else:
        logger.error("Ontology display enhancement failed")
        sys.exit(1)
