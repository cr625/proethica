#!/usr/bin/env python3
"""
NSPE Case Processing Pipeline
----------------------------
A unified pipeline for processing NSPE engineering ethics cases directly from URLs.

This script:
1. Takes a NSPE case URL as input
2. Scrapes the case content
3. Cleans and structures the case content
4. Stores the case in the database
5. Applies semantic tagging (dual-layer ontology approach)
6. Generates semantic relationships with meaningful predicates
7. Removes generic RDF type triples for cleaner display
8. Optionally integrates identified entities with a world ontology

Usage:
    python process_nspe_case.py <nspe_case_url>

Example:
    python process_nspe_case.py https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design
"""

import sys
import os
import logging
import argparse
import traceback
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import pipeline components
from scrapers.nspe_case_scraper import scrape_case
from processors.case_content_cleaner import clean_case_content
from utils.database import store_case, get_case
from taggers.semantic_tagger import tag_case
from utils.world_entity_integration import integrate_case_with_world
from utils.engineering_world_integration import add_engineering_world_triples

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nspe_pipeline")

def process_case_from_url(url, clear_existing_triples=True, integrate_with_world=True, world_id=None, add_mclaren_triples=True):
    """
    Process an NSPE case from a URL.
    
    Args:
        url: URL of the NSPE case
        clear_existing_triples: Whether to clear existing triples for this case
        integrate_with_world: Whether to integrate identified entities with a world
        world_id: Optional ID of the world to integrate with (if None, will use the world
                 associated with the case)
        
    Returns:
        dict: Result of the processing operation
    """
    try:
        logger.info(f"Processing NSPE case from URL: {url}")
        
        # Step 1: Scrape the case content
        logger.info("Step 1: Scraping case content")
        case_data = scrape_case(url)
        
        if not case_data:
            return {
                'success': False,
                'message': f"Failed to scrape case from URL: {url}"
            }
            
        logger.info(f"Successfully scraped case: {case_data.get('title')} (Case #{case_data.get('case_number')})")
        
        # Step 2: Clean and process the case content
        logger.info("Step 2: Cleaning and processing case content")
        cleaned_case_data = clean_case_content(case_data)
        logger.info(f"Content cleaned and structured into {len(cleaned_case_data.get('sections', {}))} sections")
        
        # Step 3: Store the case in the database
        logger.info("Step 3: Storing case in database")
        case_id = store_case(cleaned_case_data)
        
        if not case_id:
            return {
                'success': False,
                'message': "Failed to store case in database"
            }
            
        logger.info(f"Successfully stored case with ID: {case_id}")
        
        # Step 4: Get the complete case from the database
        logger.info("Step 4: Retrieving complete case data")
        complete_case = get_case(case_id=case_id)
        
        if not complete_case:
            return {
                'success': False,
                'message': f"Failed to retrieve complete case with ID: {case_id}"
            }
            
        # Step 5: Apply semantic tagging
        logger.info("Step 5: Applying semantic tagging")
        tagging_result = tag_case(complete_case, clear_existing=clear_existing_triples)
        
        if not tagging_result.get('success'):
            return {
                'success': False,
                'message': f"Failed to apply semantic tagging: {tagging_result.get('message')}",
                'case_id': case_id
            }
            
        # Step 6: Get the final case with triples
        final_case = get_case(case_id=case_id)
        
        # Step 7: Integrate with world if requested
        integration_result = None
        if integrate_with_world:
            logger.info("Step 7: Integrating entities with world ontology")
            integration_result = integrate_case_with_world(case_id, world_id)
            
            if integration_result.get('success'):
                added_count = sum(len(entities) for entities in integration_result.get('added_entities', {}).values())
                logger.info(f"Successfully integrated {added_count} entities with world {integration_result.get('world_id')}")
            else:
                logger.warning(f"Failed to integrate with world: {integration_result.get('message')}")
                
        # Step 8: Add engineering world ontology triples
        eng_world_result = None
        if add_mclaren_triples:  # We keep the param name for backward compatibility
            logger.info("Step 8: Adding engineering world ontology triples")
            eng_world_result = add_engineering_world_triples(case_id)
            
            if eng_world_result.get('success'):
                logger.info(f"Successfully added {eng_world_result.get('triple_count')} engineering world ontology triples")
            else:
                logger.warning(f"Failed to add engineering world triples: {eng_world_result.get('message')}")
        
        # Successful result with integration information if applicable
        result = {
            'success': True,
            'message': f"Successfully processed case: {case_data.get('title')}",
            'case_id': case_id,
            'case_number': case_data.get('case_number'),
            'title': case_data.get('title'),
            'triple_count': tagging_result.get('triple_count', 0),
            'case_data': final_case
        }
        
        # Add integration results if available
        if integration_result:
            result['integration'] = {
                'success': integration_result.get('success', False),
                'world_id': integration_result.get('world_id'),
                'added_entities': integration_result.get('added_entities', {})
            }
            
        # Add engineering world results if available
        if eng_world_result:
            result['engineering_world'] = {
                'success': eng_world_result.get('success', False),
                'triple_count': eng_world_result.get('triple_count', 0)
            }
            
        return result
        
    except Exception as e:
        logger.error(f"Error processing case: {str(e)}")
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Process an NSPE case from a URL')
    parser.add_argument('url', help='URL of the NSPE case to process')
    parser.add_argument('--keep-existing', action='store_true',
                       help='Keep existing triples instead of clearing them')
    parser.add_argument('--no-world-integration', action='store_true',
                       help='Skip integration of entities with world ontology')
    parser.add_argument('--no-eng-world-triples', action='store_true',
                       help='Skip adding engineering world ontology triples')
    parser.add_argument('--world-id', type=int,
                       help='ID of the world to integrate with (if not specified, will use the world associated with the case)')
    args = parser.parse_args()
    
    # Process the case
    result = process_case_from_url(
        args.url, 
        clear_existing_triples=not args.keep_existing,
        integrate_with_world=not args.no_world_integration,
        world_id=args.world_id,
        add_mclaren_triples=not args.no_eng_world_triples
    )
    
    if result['success']:
        logger.info(f"Successfully processed case: {result['title']} (ID: {result['case_id']})")
        logger.info(f"Generated {result['triple_count']} semantic triples")
        
        # Print entity integration info if available
        if result.get('integration', {}).get('success', False):
            added_count = sum(len(entities) for entities in result['integration'].get('added_entities', {}).values())
            logger.info(f"Added {added_count} entities to world {result['integration'].get('world_id')}")
            
        # Print engineering world triples info if available
        if result.get('engineering_world', {}).get('success', False):
            logger.info(f"Added {result['engineering_world'].get('triple_count')} engineering world ontology triples")
        
        # Print case view URL - assuming the application is running on localhost:5000
        logger.info(f"Case can be viewed at: http://localhost:5000/cases/{result['case_id']}")
        return 0
    else:
        logger.error(f"Failed to process case: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
