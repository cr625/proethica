#!/usr/bin/env python3
"""
Enhanced NSPE Case Import Script
-------------------------------
Imports an NSPE case with improved content cleaning and properly 
adds ontology triples for both engineering ethics and McLaren 
extensional definitions. Used to test the enhanced pipeline.

This script:
1. Takes a NSPE case URL as input
2. Imports it using the improved processing pipeline
3. Properly cleans header formatting including PDF references
4. Correctly extracts case number and year
5. Adds engineering ethics ontology triples
6. Adds McLaren extensional definition triples
7. Prints detailed output about the process and results
"""

import sys
import os
import logging
import argparse
import json
from datetime import datetime

# Add the NSPE pipeline directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'nspe-pipeline')))

# Import the case processing function
from process_nspe_case import process_case_from_url
from utils.database import get_case

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("enhanced_case_import")

def import_nspe_case(url, delete_existing=False):
    """
    Import an NSPE case from a URL with enhanced processing.
    
    Args:
        url: URL of the NSPE case
        delete_existing: Whether to delete any existing case with the same URL
        
    Returns:
        dict: Result of the processing operation
    """
    logger.info(f"Starting enhanced NSPE case import from URL: {url}")
    
    # Process the case
    result = process_case_from_url(
        url, 
        clear_existing_triples=True,
        integrate_with_world=True,
        add_mclaren_triples=True
    )
    
    if result['success']:
        case_id = result['case_id']
        logger.info(f"Successfully processed case: {result['title']} (ID: {case_id})")
        
        # Fetch the complete case with all associated data
        complete_case = get_case(case_id=case_id)
        
        # Display case details
        print("\n" + "="*80)
        print(f"CASE: {complete_case.get('title')} (ID: {case_id})")
        print(f"Case Number: {complete_case.get('doc_metadata', {}).get('case_number')}")
        print(f"Year: {complete_case.get('doc_metadata', {}).get('year')}")
        print("="*80)
        
        # Display ontology triples info
        if result.get('ontology', {}).get('success', False):
            eng_count = result['ontology'].get('eng_triple_count', 0)
            mclaren_count = result['ontology'].get('mclaren_triple_count', 0)
            total_count = result['ontology'].get('total_triple_count', 0)
            
            print("\n=== ONTOLOGY TRIPLES ADDED ===")
            print(f"Engineering Ethics: {eng_count} triples")
            print(f"McLaren Extensional: {mclaren_count} triples")
            print(f"Total: {total_count} triples")
        else:
            print("\nNo ontology triples were added.")
        
        # Display case viewing URL
        print("\nCase can be viewed at:")
        print(f"http://localhost:3333/cases/{case_id}\n")
        
        return result
    else:
        logger.error(f"Failed to process case: {result['message']}")
        return result

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Import an NSPE case with enhanced processing')
    parser.add_argument('url', nargs='?', 
                       default='https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design',
                       help='URL of the NSPE case to import (default: Acknowledging Errors in Design case)')
    parser.add_argument('--delete-existing', action='store_true',
                       help='Delete any existing case with the same URL')
    args = parser.parse_args()
    
    # Import the case
    result = import_nspe_case(args.url, args.delete_existing)
    
    if result['success']:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
