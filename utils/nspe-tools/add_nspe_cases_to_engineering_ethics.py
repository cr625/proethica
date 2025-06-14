#!/usr/bin/env python3
"""
Script to add NSPE case studies to the Engineering Ethics (US) world.

This script scrapes case studies from the NSPE website and adds them to the
Engineering Ethics (US) world (world_id=2) in the database.
"""

import os
import sys
import logging
import argparse
import time
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app modules
from app import db, create_app
from app.models.world import World

# Import utility functions
from utilities.scrape_nspe_cases import scrape_nspe_cases
from utilities.add_cases_to_world import add_cases_to_world, load_cases

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
ENGINEERING_ETHICS_WORLD_ID = 2
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
NSPE_CASES_FILE = os.path.join(DATA_DIR, "nspe_cases.json")

def add_nspe_cases_to_engineering_ethics(
    limit: int = None,
    skip_scraping: bool = False,
    skip_embeddings: bool = False
) -> List[int]:
    """
    Add NSPE case studies to the Engineering Ethics (US) world.
    
    Args:
        limit: Maximum number of cases to scrape (None for all)
        skip_scraping: Skip the scraping step and use existing JSON file
        skip_embeddings: Skip the embedding generation step
        
    Returns:
        List of document IDs created
    """
    # Ensure the Engineering Ethics world exists
    world = World.query.get(ENGINEERING_ETHICS_WORLD_ID)
    if not world:
        logger.error(f"Engineering Ethics world (ID: {ENGINEERING_ETHICS_WORLD_ID}) not found")
        return []
    
    logger.info(f"Adding NSPE cases to world: {world.name} (ID: {ENGINEERING_ETHICS_WORLD_ID})")
    
    # Step 1: Scrape cases from NSPE website
    if not skip_scraping:
        logger.info("Scraping cases from NSPE website...")
        cases = scrape_nspe_cases(NSPE_CASES_FILE, limit)
        logger.info(f"Scraped {len(cases)} cases")
    else:
        logger.info(f"Skipping scraping, using existing file: {NSPE_CASES_FILE}")
    
    # Step 2: Add cases to the Engineering Ethics world
    logger.info("Adding cases to the Engineering Ethics world...")
    
    # Load cases from file
    cases = load_cases(NSPE_CASES_FILE)
    if not cases:
        logger.error(f"No cases found in {NSPE_CASES_FILE}")
        return []
    
    # Add cases to the world
    document_ids = add_cases_to_world(
        cases=cases,
        world_id=ENGINEERING_ETHICS_WORLD_ID,
        document_type='case_study',
        process_embeddings=not skip_embeddings
    )
    
    logger.info(f"Added {len(document_ids)} cases to the Engineering Ethics world")
    return document_ids

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Add NSPE case studies to the Engineering Ethics (US) world')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Maximum number of cases to scrape (default: all)')
    parser.add_argument('--skip-scraping', '-s', action='store_true',
                        help='Skip the scraping step and use existing JSON file')
    parser.add_argument('--skip-embeddings', '-e', action='store_true',
                        help='Skip the embedding generation step')
    
    args = parser.parse_args()
    
    # Initialize Flask app
    app = create_app()
    
    with app.app_context():
        # Add NSPE cases to the Engineering Ethics world
        document_ids = add_nspe_cases_to_engineering_ethics(
            limit=args.limit,
            skip_scraping=args.skip_scraping,
            skip_embeddings=args.skip_embeddings
        )
        
        if document_ids:
            print(f"Successfully added {len(document_ids)} NSPE cases to the Engineering Ethics world")
            print("Document IDs:", document_ids)
        else:
            print("Failed to add NSPE cases to the Engineering Ethics world")
            sys.exit(1)

if __name__ == '__main__':
    main()
