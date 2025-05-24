#!/usr/bin/env python3
"""
Process NSPE cases using McLaren's extensional definition approach.

This script:
1. Loads NSPE cases from a JSON file
2. Analyzes them using McLaren's extensional definition techniques
3. Extracts principle instantiations, principle conflicts, and operationalization techniques
4. Stores the results in the database
5. Generates RDF triples for the ontology

Usage:
    python scripts/process_nspe_cases_mclaren.py --cases-file data/nspe_cases.json
"""

import sys
import os
import logging
import json
import argparse
import traceback
from datetime import datetime

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from app import create_app, db
from app.models.document import Document
from app.models.triple import Triple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("process_nspe_cases")

# Define ontology sources
ENGINEERING_ETHICS_ONTOLOGY = "engineering-ethics.ttl"
PROETHICA_ONTOLOGY = "proethica-intermediate.ttl"
BFO_ONTOLOGY = "bfo.ttl"

def prepare_case_document(case_data):
    """
    Prepare a Document object from case data.
    
    Args:
        case_data: Dictionary containing case information
        
    Returns:
        Document: A Document object representing the case
    """
    # Check if a document with this case number already exists
    existing_doc = Document.query.filter_by(external_id=case_data.get("case_number")).first()
    if existing_doc:
        logger.info(f"Case {case_data.get('case_number')} already exists in database with ID {existing_doc.id}")
        return existing_doc
    
    # Create a new document for this case
    doc = Document(
        title=case_data.get("title", f"Case {case_data.get('case_number')}"),
        content=case_data.get("full_text", ""),
        doc_type="case",
        external_id=case_data.get("case_number"),
        source_url=case_data.get("url"),
        doc_date=datetime.strptime(str(case_data.get("year", "2000")), "%Y"),
        doc_metadata=json.dumps(case_data.get("metadata", {}))
    )
    
    db.session.add(doc)
    db.session.commit()
    
    logger.info(f"Added case {case_data.get('case_number')} to database with ID {doc.id}")
    return doc

def store_principle_instantiations(case_id, instantiations):
    """
    Store principle instantiations in the database.
    
    Args:
        case_id: ID of the case
        instantiations: List of principle instantiations
    """
    try:
        from sqlalchemy import text
        
        for inst in instantiations:
            # Only store instantiations that have a matching principle in the ontology
            if not inst.get("principle_uri"):
                continue
                
            # Insert into principle_instantiations table
            query = text("""
                INSERT INTO principle_instantiations 
                (case_id, principle_uri, principle_label, fact_text, fact_context, 
                confidence, is_negative, created_at)
                VALUES (:case_id, :principle_uri, :principle_label, :fact_text, 
                :fact_context, :confidence, :is_negative, CURRENT_TIMESTAMP)
            """)
            
            db.session.execute(query, {
                "case_id": case_id,
                "principle_uri": inst.get("principle_uri"),
                "principle_label": inst.get("principle_label"),
                "fact_text": inst.get("fact"),
                "fact_context": inst.get("context", ""),
                "confidence": float(inst.get("match_confidence", 0.5)),
                "is_negative": bool(inst.get("is_negative", False))
            })
        
        db.session.commit()
        logger.info(f"Stored {len(instantiations)} principle instantiations for case {case_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error storing principle instantiations: {str(e)}")
        traceback.print_exc()

def store_principle_conflicts(case_id, conflicts):
    """
    Store principle conflicts in the database.
    
    Args:
        case_id: ID of the case
        conflicts: List of principle conflicts
    """
    try:
        from sqlalchemy import text
        
        for conflict in conflicts:
            # Only store conflicts that have matching principles in the ontology
            if not conflict.get("principle1_uri") or not conflict.get("principle2_uri"):
                continue
                
            # Insert into principle_conflicts table
            query = text("""
                INSERT INTO principle_conflicts 
                (case_id, principle1_uri, principle2_uri, principle1_label, 
                principle2_label, resolution_type, context, created_at)
                VALUES (:case_id, :principle1_uri, :principle2_uri, :principle1_label, 
                :principle2_label, :resolution_type, :context, CURRENT_TIMESTAMP)
            """)
            
            db.session.execute(query, {
                "case_id": case_id,
                "principle1_uri": conflict.get("principle1_uri"),
                "principle2_uri": conflict.get("principle2_uri"),
                "principle1_label": conflict.get("principle1_label"),
                "principle2_label": conflict.get("principle2_label"),
                "resolution_type": conflict.get("resolution_type", "unknown"),
                "context": conflict.get("context", "")
            })
        
        db.session.commit()
        logger.info(f"Stored {len(conflicts)} principle conflicts for case {case_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error storing principle conflicts: {str(e)}")
        traceback.print_exc()

def store_operationalization_techniques(case_id, techniques):
    """
    Store operationalization techniques in the database.
    
    Args:
        case_id: ID of the case
        techniques: Dictionary of techniques and their matches
    """
    try:
        from sqlalchemy import text
        
        for technique_name, matches in techniques.items():
            # Insert into case_operationalization table
            query = text("""
                INSERT INTO case_operationalization 
                (case_id, technique_name, technique_matches, confidence, created_at)
                VALUES (:case_id, :technique_name, :technique_matches, :confidence, CURRENT_TIMESTAMP)
            """)
            
            db.session.execute(query, {
                "case_id": case_id,
                "technique_name": technique_name,
                "technique_matches": json.dumps(matches),
                "confidence": min(1.0, len(matches) / 10.0)  # Normalize to 0-1 range
            })
        
        db.session.commit()
        logger.info(f"Stored {len(techniques)} operationalization techniques for case {case_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error storing operationalization techniques: {str(e)}")
        traceback.print_exc()

def store_case_triples(case_id, triples_content):
    """
    Store generated RDF triples in the database.
    
    Args:
        case_id: ID of the case
        triples_content: String containing RDF triples
    """
    try:
        from sqlalchemy import text
        
        # Insert into case_triples table
        query = text("""
            INSERT INTO case_triples 
            (case_id, triples, created_at)
            VALUES (:case_id, :triples, CURRENT_TIMESTAMP)
        """)
        
        db.session.execute(query, {
            "case_id": case_id,
            "triples": triples_content
        })
        
        db.session.commit()
        logger.info(f"Stored triples for case {case_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error storing case triples: {str(e)}")
        traceback.print_exc()

def process_case(case_data, mclaren_module):
    """
    Process a single case using McLaren's extensional definition approach.
    
    Args:
        case_data: Dictionary containing case information
        mclaren_module: Instance of McLarenCaseAnalysisModule
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Prepare case document
        doc = prepare_case_document(case_data)
        case_id = doc.id
        
        # Extract principle instantiations
        logger.info(f"Extracting principle instantiations for case {case_id}")
        instantiations_result = mclaren_module.extract_principle_instantiations({
            "case_id": case_id,
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY
        })
        
        if "error" in instantiations_result:
            logger.error(f"Error extracting principle instantiations: {instantiations_result['error']}")
        else:
            store_principle_instantiations(case_id, instantiations_result.get("instantiations", []))
        
        # Identify principle conflicts
        logger.info(f"Identifying principle conflicts for case {case_id}")
        conflicts_result = mclaren_module.identify_principle_conflicts({
            "case_id": case_id,
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY
        })
        
        if "error" in conflicts_result:
            logger.error(f"Error identifying principle conflicts: {conflicts_result['error']}")
        else:
            store_principle_conflicts(case_id, conflicts_result.get("conflicts", []))
        
        # Identify operationalization techniques
        logger.info(f"Identifying operationalization techniques for case {case_id}")
        techniques_result = mclaren_module.identify_operationalization_techniques({
            "case_id": case_id,
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY
        })
        
        if "error" in techniques_result:
            logger.error(f"Error identifying operationalization techniques: {techniques_result['error']}")
        else:
            store_operationalization_techniques(case_id, techniques_result.get("techniques", {}))
        
        # Convert to triples
        logger.info(f"Converting case {case_id} to RDF triples")
        triples_result = mclaren_module.convert_to_triples({
            "case_id": case_id,
            "ontology_source": ENGINEERING_ETHICS_ONTOLOGY,
            "output_format": "turtle"
        })
        
        if "error" in triples_result:
            logger.error(f"Error converting to triples: {triples_result['error']}")
        else:
            store_case_triples(case_id, triples_result.get("triples", ""))
        
        return True
    except Exception as e:
        logger.error(f"Error processing case: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(description='Process NSPE cases using McLaren\'s extensional definition approach')
    parser.add_argument('--cases-file', required=True, help='Path to JSON file containing NSPE cases')
    args = parser.parse_args()
    
    # Create Flask app
    app = create_app()
    
    # Process cases within app context
    with app.app_context():
        try:
            # Load case data
            logger.info(f"Loading cases from {args.cases_file}")
            with open(args.cases_file, 'r') as f:
                cases = json.load(f)
            
            logger.info(f"Loaded {len(cases)} cases")
            
            # Import here to avoid circular imports
            from mcp.modules.mclaren_case_analysis_module import McLarenCaseAnalysisModule
            
            # Create dummy server class with _load_graph_from_file method
            class DummyServer:
                def __init__(self):
                    self.app = app
                
                def _load_graph_from_file(self, source):
                    from rdflib import Graph
                    g = Graph()
                    g.parse(f"ontologies/{source}", format="turtle")
                    return g
            
            # Create McLarenCaseAnalysisModule instance
            server = DummyServer()
            mclaren_module = McLarenCaseAnalysisModule(server)
            
            # Process each case
            successful = 0
            for i, case in enumerate(cases):
                logger.info(f"Processing case {i+1}/{len(cases)}: {case.get('case_number')}")
                
                if process_case(case, mclaren_module):
                    successful += 1
            
            logger.info(f"Processed {len(cases)} cases, {successful} successful")
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            traceback.print_exc()
            return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
