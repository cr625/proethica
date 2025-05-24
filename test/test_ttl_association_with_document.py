#!/usr/bin/env python3
"""
Test script to test the TTL-based section-triple association system with a sample document.

This script tests the implementation with a real document to verify that 
the system works end-to-end.
"""

import os
import sys
import logging
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any

# Import the main service and text for SQL queries
from ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test TTL-based section-triple association with a document",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--document-id', type=int, default=None,
                       help='Document ID to process (required)')
    parser.add_argument('--output', type=str, default='association_test_results.json',
                       help='Output file to save results')
    parser.add_argument('--similarity', type=float, default=0.5,
                       help='Similarity threshold (0-1)')
    parser.add_argument('--max-matches', type=int, default=5,
                       help='Maximum matches per section')
    
    return parser.parse_args()

def get_document_info(document_id: int, service: SectionTripleAssociationService) -> Dict[str, Any]:
    """Get information about the document."""
    try:
        session = service.Session()
        query = text("""
            SELECT d.id, d.title, d.document_type, 
                   COUNT(ds.id) AS section_count
            FROM documents d
            LEFT JOIN document_sections ds ON d.id = ds.document_id
            WHERE d.id = :document_id
            GROUP BY d.id, d.title, d.document_type
        """)
        result = session.execute(query, {"document_id": document_id}).fetchone()
        session.close()
        
        if not result:
            logger.error(f"Document {document_id} not found")
            return {}
            
        return {
            "id": result[0],
            "title": result[1],
            "document_type": result[2],
            "section_count": result[3]
        }
    except Exception as e:
        logger.error(f"Error getting document info: {e}")
        return {}

def process_document(document_id: int, service: SectionTripleAssociationService) -> Dict[str, Any]:
    """
    Process a document with the TTL-based section-triple association system.
    
    Args:
        document_id: ID of the document to process
        service: Initialized SectionTripleAssociationService
    
    Returns:
        Dictionary with results
    """
    # Get document info
    document_info = get_document_info(document_id, service)
    if not document_info:
        return {"success": False, "error": "Document not found or error retrieving info"}
    
    logger.info(f"Processing document: {document_info['title']} (ID: {document_id})")
    logger.info(f"Document has {document_info['section_count']} sections")
    
    # Process document sections
    start_time = datetime.now()
    result = service.batch_associate_sections(document_id=document_id)
    end_time = datetime.now()
    
    # Get associations for analysis
    associations = service.get_document_associations(document_id)
    
    # Calculate statistics
    section_counts = {}
    section_types = {}
    match_types = {}
    concept_counts = {}
    
    for section_id, matches in associations.get("sections", {}).items():
        section_counts[section_id] = len(matches)
        
        # Get section type
        session = service.Session()
        query = text("SELECT section_type FROM document_sections WHERE id = :section_id")
        section_type_result = session.execute(query, {"section_id": section_id}).fetchone()
        session.close()
        
        if section_type_result:
            section_type = section_type_result[0]
            section_types[section_id] = section_type
            
            # Count matches by section type
            if section_type not in match_types:
                match_types[section_type] = 0
            match_types[section_type] += len(matches)
        
        # Count concept types
        for match in matches:
            concept_type = match.get("match_type", "unknown")
            if concept_type not in concept_counts:
                concept_counts[concept_type] = 0
            concept_counts[concept_type] += 1
    
    # Build test results
    test_results = {
        "document": document_info,
        "processing_time": str(end_time - start_time),
        "processed_sections": result.get("processed", 0),
        "successful_sections": result.get("successful", 0),
        "failed_sections": result.get("failed", 0),
        "section_match_counts": section_counts,
        "section_types": section_types,
        "match_types_by_section": match_types,
        "concept_type_counts": concept_counts,
        "associations_sample": {
            # Include sample of 3 sections with their associations
            list(associations.get("sections", {}).keys())[i]: 
            associations.get("sections", {}).get(list(associations.get("sections", {}).keys())[i]) 
            for i in range(min(3, len(associations.get("sections", {}))))
        } if associations.get("sections") else {}
    }
    
    return test_results

def main():
    """Main entry point."""
    args = parse_args()
    
    if not args.document_id:
        logger.error("Document ID is required")
        return 1
    
    try:
        # Initialize service
        logger.info("Initializing section-triple association service...")
        service = SectionTripleAssociationService(
            similarity_threshold=args.similarity,
            max_matches=args.max_matches
        )
        
        # Process document
        logger.info(f"Testing TTL-based section-triple association with document {args.document_id}")
        results = process_document(args.document_id, service)
        
        # Save results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Test results saved to {args.output}")
        
        # Print summary
        print("\n===== TTL-based Section-Triple Association Test Results =====")
        print(f"Document: {results.get('document', {}).get('title', 'Unknown')}")
        print(f"Document Type: {results.get('document', {}).get('document_type', 'Unknown')}")
        print(f"Processing Time: {results.get('processing_time', 'Unknown')}")
        print(f"Processed Sections: {results.get('processed_sections', 0)}")
        print(f"Successful Sections: {results.get('successful_sections', 0)}")
        print(f"Failed Sections: {results.get('failed_sections', 0)}")
        print("\nConcept Type Counts:")
        for concept_type, count in results.get("concept_type_counts", {}).items():
            print(f"  {concept_type}: {count}")
        print("==============================================================\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in test process: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
