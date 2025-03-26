#!/usr/bin/env python3
"""
Test script to demonstrate how to process a specific NSPE case study URL
and add it to the Engineering Ethics (US) world (world_id=2).
"""

import os
import sys
import logging
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the process_nspe_url function
from utilities.process_nspe_url import process_nspe_url

# Import app modules
from app import create_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Example NSPE case study URLs
EXAMPLE_CASES = [
    {
        "url": "https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/public-health-and-safety-structural",
        "title": "Public Health and Safety - Structural Engineer Discovers Potentially Dangerous Condition"
    },
    {
        "url": "https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/conflict-interest-serving-public-board",
        "title": "Conflict of Interest - Serving on Public Board and Representing Clients"
    },
    {
        "url": "https://www.nspe.org/resources/ethics/ethics-resources/board-ethical-review-cases/expert-witness-conflict-interest",
        "title": "Expert Witness - Conflict of Interest"
    }
]

def main():
    """Main function to run the test script."""
    parser = argparse.ArgumentParser(description='Test processing a specific NSPE case study URL')
    parser.add_argument('--world-id', '-w', type=int, default=2,
                        help='ID of the world to add the case to (default: 2 for Engineering Ethics (US) world)')
    parser.add_argument('--case-index', '-c', type=int, default=0,
                        help=f'Index of the case to process (0-{len(EXAMPLE_CASES)-1}, default: 0)')
    parser.add_argument('--no-embeddings', '-n', action='store_true',
                        help='Do not process embeddings for the document')
    
    args = parser.parse_args()
    
    # Validate case index
    if args.case_index < 0 or args.case_index >= len(EXAMPLE_CASES):
        logger.error(f"Invalid case index: {args.case_index}. Must be between 0 and {len(EXAMPLE_CASES)-1}")
        sys.exit(1)
    
    # Get the selected case
    selected_case = EXAMPLE_CASES[args.case_index]
    
    # Initialize Flask app
    app = create_app()
    
    with app.app_context():
        # Process the selected case
        document_id = process_nspe_url(
            url=selected_case['url'],
            world_id=args.world_id,
            document_type='case_study',
            process_embeddings=not args.no_embeddings
        )
        
        if document_id:
            print(f"Successfully processed NSPE case study: {selected_case['title']}")
            print(f"Added to database with ID: {document_id}")
            print(f"World ID: {args.world_id}")
            
            # Suggest next steps
            print("\nNext steps:")
            print(f"1. Retrieve the case: python utilities/retrieve_cases.py --document-id {document_id}")
            print(f"2. Search for similar cases: python utilities/retrieve_cases.py --query \"conflict of interest\" --world-id {args.world_id}")
            print(f"3. Get all cases for this world: python utilities/retrieve_cases.py --world-id {args.world_id}")
        else:
            print(f"Failed to process NSPE case study: {selected_case['title']}")
            sys.exit(1)

if __name__ == '__main__':
    main()
