#!/usr/bin/env python3
"""
Script to import Case 187 (NSPE Case 23-4: Acknowledging Errors in Design)
with improved triple handling.

This script:
1. Calls the NSPE pipeline to import the case
2. Uses the improved McLaren extensional triple implementation
3. Adds engineering ethics triples with proper URI structure
"""

import sys
import os
import logging
import argparse
from datetime import datetime

# Add the nspe-pipeline directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'nspe-pipeline')))

# Import the NSPE pipeline process_case_from_url function
from process_nspe_case import process_case_from_url

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("import_improved_case_187")

def main():
    """Main function to import the improved Case 187"""
    
    # URL for NSPE Case 23-4: Acknowledging Errors in Design
    case_url = "https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design"
    
    # Process the case with our improved triple handling
    logger.info(f"Importing case from URL: {case_url}")
    
    # Use the process_case_from_url function from the NSPE pipeline
    # The updated mclaren_extensions.py will be used automatically
    result = process_case_from_url(
        url=case_url,
        clear_existing_triples=True,
        integrate_with_world=True,
        world_id=1,  # Engineering world
        add_mclaren_triples=True  # This will use our improved implementation
    )
    
    if result['success']:
        logger.info(f"Successfully imported case: {result['title']} (ID: {result['case_id']})")
        logger.info(f"Generated {result['triple_count']} semantic triples")
        
        # Print entity integration info if available
        if result.get('integration', {}).get('success', False):
            added_count = sum(len(entities) for entities in result['integration'].get('added_entities', {}).values())
            logger.info(f"Added {added_count} entities to world {result['integration'].get('world_id')}")
            
        # Print engineering world triples info if available
        if result.get('engineering_world', {}).get('success', False):
            logger.info(f"Added {result['engineering_world'].get('triple_count')} engineering world ontology triples")
        
        # Print case view URL
        logger.info(f"Case can be viewed at: http://127.0.0.1:3333/cases/{result['case_id']}")
        return 0
    else:
        logger.error(f"Failed to import case: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
