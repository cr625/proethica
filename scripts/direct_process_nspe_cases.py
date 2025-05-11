#!/usr/bin/env python3
"""
Direct process script for NSPE cases using McLaren's extensional definition approach.

This script bypasses the Flask application and directly interacts with the database
to process NSPE cases.

Usage:
    python scripts/direct_process_nspe_cases.py --cases-file data/nspe_cases.json
"""

import sys
import os
import logging
import json
import argparse
import traceback
import psycopg2
import psycopg2.extras
from datetime import datetime
from rdflib import Graph, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD

# Add the parent directory to sys.path to be able to import the module
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import the McLaren module
from mcp.modules.mclaren_case_analysis_module import McLarenCaseAnalysisModule

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_process_nspe_cases")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

# Define ontology sources
ENGINEERING_ETHICS_ONTOLOGY = "engineering-ethics.ttl"
PROETHICA_ONTOLOGY = "proethica-intermediate.ttl"
BFO_ONTOLOGY = "bfo.ttl"

class DirectServer:
    """
    A simple class that implements the necessary interface for the McLaren module
    without requiring Flask or SQLAlchemy.
    """
    def __init__(self):
        self.app = None  # No Flask app
    
    def _load_graph_from_file(self, source):
        """Load an RDF graph from a file."""
        g = Graph()
        g.parse(f"ontologies/{source}", format="turtle")
        return g

def get_db_connection():
    """Get a connection to the database."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to the database: {str(e)}")
        traceback.print_exc()
        return None

def prepare_case_document(conn, case_data):
    """
    Prepare a document for a case.
    
    Args:
        conn: Database connection
        case_data: Dictionary containing case information
        
    Returns:
        int: The ID of the document in the database
    """
    try:
        cur = conn.cursor()
        
        # Check if a document with this case number already exists
        cur.execute(
            "SELECT id FROM documents WHERE doc_metadata->>'case_number' = %s",
            (case_data.get("case_number"),)
        )
        
        result = cur.fetchone()
        if result:
            logger.info(f"Case {case_data.get('case_number')} already exists in database with ID {result[0]}")
            return result[0]
        
        # Create a new document for this case
        metadata = case_data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            
        # Make sure case_number is in the metadata
        metadata["case_number"] = case_data.get("case_number")
        metadata["year"] = case_data.get("year")
        
        cur.execute(
            """
            INSERT INTO documents 
            (title, content, document_type, source, doc_metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                case_data.get("title", f"Case {case_data.get('case_number')}"),
                case_data.get("full_text", ""),
                "case",
                case_data.get("url"),
                json.dumps(metadata),
                datetime.now()
            )
        )
        
        document_id = cur.fetchone()[0]
        conn.commit()
        
        logger.info(f"Added case {case_data.get('case_number')} to database with ID {document_id}")
        return document_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error preparing case document: {str(e)}")
        traceback.print_exc()
        return None

def store_principle_instantiations(conn, case_id, instantiations):
    """
    Store principle instantiations in the database.
    
    Args:
        conn: Database connection
        case_id: ID of the case
        instantiations: List of principle instantiations
    """
    try:
        cur = conn.cursor()
        
        for inst in instantiations:
            # Only store instantiations that have a matching principle in the ontology
            if not inst.get("principle_uri"):
                continue
                
            cur.execute(
                """
                INSERT INTO principle_instantiations
                (case_id, principle_uri, principle_label, fact_text, fact_context,
                confidence, is_negative, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    case_id,
                    inst.get("principle_uri"),
                    inst.get("principle_label"),
                    inst.get("fact"),
                    inst.get("context", ""),
                    float(inst.get("match_confidence", 0.5)),
                    bool(inst.get("is_negative", False)),
                    datetime.now()
                )
            )
            
        conn.commit()
        logger.info(f"Stored {len(instantiations)} principle instantiations for case {case_id}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing principle instantiations: {str(e)}")
        traceback.print_exc()

def store_principle_conflicts(conn, case_id, conflicts):
    """
    Store principle conflicts in the database.
    
    Args:
        conn: Database connection
        case_id: ID of the case
        conflicts: List of principle conflicts
    """
    try:
        cur = conn.cursor()
        
        for conflict in conflicts:
            # Only store conflicts that have matching principles in the ontology
            if not conflict.get("principle1_uri") or not conflict.get("principle2_uri"):
                continue
                
            cur.execute(
                """
                INSERT INTO principle_conflicts
                (case_id, principle1_uri, principle2_uri, principle1_label,
                principle2_label, resolution_type, context, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    case_id,
                    conflict.get("principle1_uri"),
                    conflict.get("principle2_uri"),
                    conflict.get("principle1_label"),
                    conflict.get("principle2_label"),
                    conflict.get("resolution_type", "unknown"),
                    conflict.get("context", ""),
                    datetime.now()
                )
            )
            
        conn.commit()
        logger.info(f"Stored {len(conflicts)} principle conflicts for case {case_id}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing principle conflicts: {str(e)}")
        traceback.print_exc()

def store_operationalization_techniques(conn, case_id, techniques):
    """
    Store operationalization techniques in the database.
    
    Args:
        conn: Database connection
        case_id: ID of the case
        techniques: Dictionary of techniques and their matches
    """
    try:
        cur = conn.cursor()
        
        for technique_name, matches in techniques.items():
            cur.execute(
                """
                INSERT INTO case_operationalization
                (case_id, technique_name, technique_matches, confidence, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    case_id,
                    technique_name,
                    json.dumps(matches),
                    min(1.0, len(matches) / 10.0),  # Normalize to 0-1 range
                    datetime.now()
                )
            )
            
        conn.commit()
        logger.info(f"Stored {len(techniques)} operationalization techniques for case {case_id}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing operationalization techniques: {str(e)}")
        traceback.print_exc()

def store_case_triples(conn, case_id, triples_content):
    """
    Store generated RDF triples in the database.
    
    Args:
        conn: Database connection
        case_id: ID of the case
        triples_content: String containing RDF triples
    """
    try:
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO case_triples
            (case_id, triples, created_at)
            VALUES (%s, %s, %s)
            """,
            (
                case_id,
                triples_content,
                datetime.now()
            )
        )
            
        conn.commit()
        logger.info(f"Stored triples for case {case_id}")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing case triples: {str(e)}")
        traceback.print_exc()

def get_case_content(conn, case_id):
    """
    Get the content of a case from the database.
    
    Args:
        conn: Database connection
        case_id: ID of the case
        
    Returns:
        dict: Dictionary containing case information
    """
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute(
            """
            SELECT id, title, content, doc_metadata
            FROM documents
            WHERE id = %s
            """,
            (case_id,)
        )
        
        result = cur.fetchone()
        if result:
            return {
                "id": result["id"],
                "title": result["title"],
                "content": result["content"],
                "metadata": result["doc_metadata"] if result["doc_metadata"] else {}
            }
        else:
            logger.error(f"Case {case_id} not found in database")
            return None
            
    except Exception as e:
        logger.error(f"Error getting case content: {str(e)}")
        traceback.print_exc()
        return None

def process_case(conn, case_data, mclaren_module):
    """
    Process a single case using McLaren's extensional definition approach.
    
    Args:
        conn: Database connection
        case_data: Dictionary containing case information
        mclaren_module: Instance of McLarenCaseAnalysisModule
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Prepare case document
        case_id = prepare_case_document(conn, case_data)
        if not case_id:
            logger.error("Failed to prepare case document")
            return False
            
        # Get the case content back from the database
        case_content = get_case_content(conn, case_id)
        if not case_content:
            logger.error("Failed to get case content")
            return False
            
        # Extract principle instantiations
        logger.info(f"Extracting principle instantiations for case {case_id}")
        instantiations_result = mclaren_module.extract_principle_instantiations({
            "case_id": case_id,
            "case_text": case_content["content"],
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY
        })
        
        if "error" in instantiations_result:
            logger.error(f"Error extracting principle instantiations: {instantiations_result['error']}")
        else:
            store_principle_instantiations(conn, case_id, instantiations_result.get("instantiations", []))
            
        # Identify principle conflicts
        logger.info(f"Identifying principle conflicts for case {case_id}")
        conflicts_result = mclaren_module.identify_principle_conflicts({
            "case_id": case_id,
            "case_text": case_content["content"],
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY
        })
        
        if "error" in conflicts_result:
            logger.error(f"Error identifying principle conflicts: {conflicts_result['error']}")
        else:
            store_principle_conflicts(conn, case_id, conflicts_result.get("conflicts", []))
            
        # Identify operationalization techniques
        logger.info(f"Identifying operationalization techniques for case {case_id}")
        techniques_result = mclaren_module.identify_operationalization_techniques({
            "case_id": case_id,
            "case_text": case_content["content"],
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY
        })
        
        if "error" in techniques_result:
            logger.error(f"Error identifying operationalization techniques: {techniques_result['error']}")
        else:
            store_operationalization_techniques(conn, case_id, techniques_result.get("techniques", {}))
            
        # Convert to triples
        logger.info(f"Converting case {case_id} to RDF triples")
        triples_result = mclaren_module.convert_to_triples({
            "case_id": case_id,
            "case_text": case_content["content"],
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY,
            "output_format": "turtle"
        })
        
        if "error" in triples_result:
            logger.error(f"Error converting to triples: {triples_result['error']}")
        else:
            store_case_triples(conn, case_id, triples_result.get("triples", ""))
            
        return True
        
    except Exception as e:
        logger.error(f"Error processing case: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(description='Process NSPE cases using McLaren\'s extensional definition approach')
    parser.add_argument('--cases-file', required=True, help='Path to JSON file containing NSPE cases')
    parser.add_argument('--limit', type=int, help='Limit the number of cases to process')
    args = parser.parse_args()
    
    try:
        # Load case data
        logger.info(f"Loading cases from {args.cases_file}")
        with open(args.cases_file, 'r') as f:
            cases = json.load(f)
            
        if args.limit and args.limit > 0:
            cases = cases[:args.limit]
            
        logger.info(f"Loaded {len(cases)} cases")
        
        # Get database connection
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to connect to the database")
            return 1
            
        # Create McLarenCaseAnalysisModule instance
        server = DirectServer()
        mclaren_module = McLarenCaseAnalysisModule(server)
        
        # Process each case
        successful = 0
        for i, case in enumerate(cases):
            logger.info(f"Processing case {i+1}/{len(cases)}: {case.get('case_number')}")
            
            if process_case(conn, case, mclaren_module):
                successful += 1
                
        logger.info(f"Processed {len(cases)} cases, {successful} successful")
        
        # Close database connection
        conn.close()
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
