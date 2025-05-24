#!/usr/bin/env python3
"""
Script to remove McLaren extensional triples and add proper engineering world ontology triples for case 187
"""

import sys
import os
import logging
import psycopg2
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("case187_engineering_world_integration")

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

def remove_mclaren_triples(case_id: int) -> Dict[str, Any]:
    """Remove McLaren extensional triples from a case"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, count the McLaren triples to be removed
        cursor.execute("""
            SELECT COUNT(*) FROM entity_triples
            WHERE entity_id = %s AND source = 'mclaren-extensional'
        """, (case_id,))
        
        count = cursor.fetchone()[0]
        
        # Now delete them
        cursor.execute("""
            DELETE FROM entity_triples
            WHERE entity_id = %s AND source = 'mclaren-extensional'
        """, (case_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f"Successfully removed {count} McLaren extensional triples from case {case_id}",
            'removed_count': count
        }
    except Exception as e:
        logger.error(f"Error removing McLaren triples: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }

def add_engineering_world_triples_for_case_187():
    """Add engineering world ontology triples for case 187"""
    try:
        # Import module here to avoid circular imports
        # Add the NSPE pipeline to the path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        nspe_pipeline_dir = os.path.join(script_dir, 'nspe-pipeline')
        sys.path.append(nspe_pipeline_dir)
        
        # Now import the module
        from utils.engineering_world_integration import add_engineering_world_triples
        
        # Call the function with case 187
        case_id = 187
        
        # Remove McLaren triples first
        removal_result = remove_mclaren_triples(case_id)
        logger.info(removal_result['message'])
        
        # Add engineering world triples
        result = add_engineering_world_triples(case_id)
        
        if result['success']:
            logger.info(f"Successfully added {result['triple_count']} engineering world triples to case {case_id}")
            logger.info(f"Added concepts: {result['concepts']}")
            return 0
        else:
            logger.error(f"Failed to add engineering world triples: {result['message']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error adding engineering world triples: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(add_engineering_world_triples_for_case_187())
