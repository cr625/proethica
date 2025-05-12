"""
Database Utilities
-----------------
Provides database connection and operations for the NSPE case processing pipeline.

Functions:
- get_db_connection: Create a connection to the database
- store_case: Store a case in the database
- get_case: Get a case from the database
- store_entity_triples: Store entity triples for a case
- clear_entity_triples: Remove entity triples for a case
- remove_rdf_type_triples: Remove generic RDF type triples
"""

import os
import sys
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime
import traceback

# Add parent directory to path to import config
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from config import DB_PARAMS, RDF_TYPE_PREDICATE

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("database_utils")

def get_db_connection():
    """
    Create a connection to the database.
    
    Returns:
        conn: Database connection or None if failed
    """
    try:
        logger.debug(f"Connecting to database: {DB_PARAMS['dbname']} on {DB_PARAMS['host']}:{DB_PARAMS['port']}")
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return None

def store_case(case_data):
    """
    Store a case in the database.
    
    Args:
        case_data: Dictionary containing case information
        
    Returns:
        int: The ID of the document in the database, or None if failed
    """
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        
        # Extract core fields
        title = case_data.get('title', '')
        case_number = case_data.get('case_number', '')
        year = case_data.get('year', '')
        full_text = case_data.get('full_text', '')
        description = case_data.get('description', '')
        decision = case_data.get('decision', '')
        url = case_data.get('url', '')
        
        # Prepare metadata
        metadata = {
            "case_number": case_number,
            "year": year,
            "sections": case_data.get("sections", {})
        }
        
        # Add any additional metadata
        if 'metadata' in case_data and isinstance(case_data['metadata'], dict):
            for key, value in case_data['metadata'].items():
                metadata[key] = value
                
        metadata_json = json.dumps(metadata)
        
        # Check if the case already exists in the database
        cur.execute(
            """
            SELECT id FROM documents 
            WHERE doc_metadata->>'case_number' = %s
            """,
            (case_number,)
        )
        
        existing_id = cur.fetchone()
        
        if existing_id:
            # Update existing case
            document_id = existing_id[0]
            logger.info(f"Updating existing case {case_number} with ID {document_id}")
            
            cur.execute(
                """
                UPDATE documents
                SET title = %s,
                    content = %s,
                    doc_metadata = %s,
                    source = %s,
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                (
                    title,
                    full_text,
                    metadata_json,
                    url,
                    datetime.now(),
                    document_id
                )
            )
            
            # Also update the case data in documents_content
            cur.execute(
                """
                SELECT id FROM documents_content
                WHERE document_id = %s
                """,
                (document_id,)
            )
            
            existing_content = cur.fetchone()
            
            if existing_content:
                # Update existing content
                cur.execute(
                    """
                    UPDATE documents_content
                    SET description = %s,
                        decision = %s,
                        updated_at = %s
                    WHERE document_id = %s
                    """,
                    (
                        description,
                        decision,
                        datetime.now(),
                        document_id
                    )
                )
            else:
                # Insert new content
                cur.execute(
                    """
                    INSERT INTO documents_content
                    (document_id, description, decision, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        description,
                        decision,
                        datetime.now()
                    )
                )
        else:
            # Insert new case
            logger.info(f"Inserting new case: {title}")
            
            cur.execute(
                """
                INSERT INTO documents
                (title, content, document_type, source, doc_metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    title,
                    full_text,
                    "case",
                    url,
                    metadata_json,
                    datetime.now()
                )
            )
            
            document_id = cur.fetchone()[0]
            
            # Insert into documents_content
            cur.execute(
                """
                INSERT INTO documents_content
                (document_id, description, decision, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    document_id,
                    description,
                    decision,
                    datetime.now()
                )
            )
            
            logger.info(f"Inserted new case with ID {document_id}")
        
        # Commit the transaction
        conn.commit()
        
        # Close connection
        cur.close()
        conn.close()
        
        return document_id
        
    except Exception as e:
        logger.error(f"Error storing case: {str(e)}")
        traceback.print_exc()
        
        # Rollback transaction if an error occurred
        if 'conn' in locals() and conn:
            conn.rollback()
            
            # Close connections
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return None

def get_case(case_id=None, case_number=None):
    """
    Get a case from the database by ID or case number.
    
    Args:
        case_id: The ID of the case in the database
        case_number: The case number (e.g., "19-1")
        
    Returns:
        dict: Case data or None if not found
    """
    try:
        if not case_id and not case_number:
            logger.error("Must provide either case_id or case_number")
            return None
            
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        if case_id:
            # Get by ID
            query = """
                SELECT d.id, d.title, d.content, d.source, d.doc_metadata,
                       dc.description, dc.decision, dc.outcome, dc.ethical_analysis
                FROM documents d
                LEFT JOIN documents_content dc ON d.id = dc.document_id
                WHERE d.id = %s
                """
            cur.execute(query, (case_id,))
        else:
            # Get by case number
            query = """
                SELECT d.id, d.title, d.content, d.source, d.doc_metadata,
                       dc.description, dc.decision, dc.outcome, dc.ethical_analysis
                FROM documents d
                LEFT JOIN documents_content dc ON d.id = dc.document_id
                WHERE d.doc_metadata->>'case_number' = %s
                """
            cur.execute(query, (case_number,))
            
        result = cur.fetchone()
        
        if not result:
            logger.warning(f"Case not found: ID={case_id}, case_number={case_number}")
            cur.close()
            conn.close()
            return None
            
        # Convert to dictionary
        case_data = dict(result)
        
        # Get entity triples
        cur.execute(
            """
            SELECT id, subject, predicate, object_uri, object_literal, is_literal, 
                   graph, triple_metadata
            FROM entity_triples
            WHERE entity_type = 'document' AND entity_id = %s
            """,
            (case_data['id'],)
        )
        
        triples = [dict(triple) for triple in cur.fetchall()]
        case_data['entity_triples'] = triples
        
        # Close connection
        cur.close()
        conn.close()
        
        return case_data
        
    except Exception as e:
        logger.error(f"Error getting case: {str(e)}")
        traceback.print_exc()
        
        # Close connections if they exist
        if 'conn' in locals() and conn:
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return None

def store_entity_triples(case_id, triples):
    """
    Store entity triples for a case.
    
    Args:
        case_id: ID of the case
        triples: List of triple dictionaries with keys:
                 - subject
                 - predicate
                 - object_uri or object_literal
                 - is_literal
                 - graph (optional)
                 - triple_metadata (optional)
                 
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cur = conn.cursor()
        
        # Process each triple
        inserted_count = 0
        for triple in triples:
            # Ensure required fields are present
            if 'subject' not in triple or 'predicate' not in triple:
                logger.warning("Skipping triple with missing subject or predicate")
                continue
                
            if ('object_uri' not in triple and 'object_literal' not in triple):
                logger.warning("Skipping triple with missing object")
                continue
                
            # Set is_literal based on which object field is provided
            is_literal = triple.get('is_literal', False)
            if 'object_literal' in triple and triple['object_literal']:
                is_literal = True
                
            # Prepare metadata
            triple_metadata = triple.get('triple_metadata', {})
            if isinstance(triple_metadata, dict):
                triple_metadata = json.dumps(triple_metadata)
                
            # Set default graph if not provided
            graph = triple.get('graph', 'http://proethica.org/ontology/case-analysis')
            
            # Insert the triple
            cur.execute(
                """
                INSERT INTO entity_triples
                (subject, predicate, object_uri, object_literal, is_literal,
                 entity_type, entity_id, graph, triple_metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    triple['subject'],
                    triple['predicate'],
                    triple.get('object_uri', None),
                    triple.get('object_literal', None),
                    is_literal,
                    'document',
                    case_id,
                    graph,
                    triple_metadata,
                    datetime.now(),
                    datetime.now()
                )
            )
            
            inserted_count += 1
            
        # Commit the transaction
        conn.commit()
        
        logger.info(f"Inserted {inserted_count} triples for case ID {case_id}")
        
        # Close connection
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Error storing entity triples: {str(e)}")
        traceback.print_exc()
        
        # Rollback transaction if an error occurred
        if 'conn' in locals() and conn:
            conn.rollback()
            
            # Close connections
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return False

def clear_entity_triples(case_id):
    """
    Remove all entity triples for a case.
    
    Args:
        case_id: ID of the case
        
    Returns:
        int: Number of triples removed, or -1 if an error occurred
    """
    try:
        conn = get_db_connection()
        if not conn:
            return -1
            
        cur = conn.cursor()
        
        # Get count of triples to be deleted
        cur.execute(
            """
            SELECT COUNT(*) FROM entity_triples
            WHERE entity_type = 'document' AND entity_id = %s
            """,
            (case_id,)
        )
        
        count = cur.fetchone()[0]
        
        # Delete all triples for this case
        cur.execute(
            """
            DELETE FROM entity_triples
            WHERE entity_type = 'document' AND entity_id = %s
            """,
            (case_id,)
        )
        
        # Commit the transaction
        conn.commit()
        
        logger.info(f"Removed {count} triples for case ID {case_id}")
        
        # Close connection
        cur.close()
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error clearing entity triples: {str(e)}")
        traceback.print_exc()
        
        # Rollback transaction if an error occurred
        if 'conn' in locals() and conn:
            conn.rollback()
            
            # Close connections
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return -1

def remove_rdf_type_triples(case_id=None):
    """
    Remove generic RDF type triples for a specific case or all cases.
    
    Args:
        case_id: ID of the case, or None for all cases
        
    Returns:
        int: Number of triples removed, or -1 if an error occurred
    """
    try:
        conn = get_db_connection()
        if not conn:
            return -1
            
        cur = conn.cursor()
        
        # Build the query
        if case_id:
            # For a specific case
            query = """
                DELETE FROM entity_triples
                WHERE predicate = %s AND entity_type = 'document' AND entity_id = %s
                """
            cur.execute(query, (RDF_TYPE_PREDICATE, case_id))
        else:
            # For all cases
            query = """
                DELETE FROM entity_triples
                WHERE predicate = %s AND entity_type = 'document'
                """
            cur.execute(query, (RDF_TYPE_PREDICATE,))
            
        # Get count of affected rows
        count = cur.rowcount
        
        # Commit the transaction
        conn.commit()
        
        if case_id:
            logger.info(f"Removed {count} RDF type triples for case ID {case_id}")
        else:
            logger.info(f"Removed {count} RDF type triples across all cases")
        
        # Close connection
        cur.close()
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error removing RDF type triples: {str(e)}")
        traceback.print_exc()
        
        # Rollback transaction if an error occurred
        if 'conn' in locals() and conn:
            conn.rollback()
            
            # Close connections
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return -1
