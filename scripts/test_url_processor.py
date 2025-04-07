#!/usr/bin/env python3
"""
Test script for the URL processor.

This script tests the URL processor by processing a sample URL and displaying the results.
Run this script from the project root directory.
"""

import sys
import json
import os
from pprint import pprint
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Flask application context
from app import create_app
app = create_app()
app_context = app.app_context()
app_context.push()

from app.services.case_url_processor import CaseUrlProcessor

def test_url_processor(url=None, world_id=1, save_output=True):
    """
    Test the URL processor with a sample URL.
    
    Args:
        url: URL to process (if None, uses a default NSPE URL)
        world_id: World ID to associate with the case
        save_output: Whether to save the output to a file
    """
    if url is None:
        # Default NSPE case URL
        url = "https://www.nspe.org/resources/ethics/ethics-resources/board-of-ethical-review-cases/competitive-bidding-vs-quality"
    
    print(f"Testing URL processor with URL: {url}")
    
    # Create processor instance
    processor = CaseUrlProcessor()
    
    # Process URL
    start_time = datetime.now()
    result = processor.process_url(url=url, world_id=world_id)
    end_time = datetime.now()
    processing_time = (end_time - start_time).total_seconds()
    
    # Print basic results
    print(f"\nProcessing completed in {processing_time:.2f} seconds")
    print(f"Title: {result.get('title', 'Unknown')}")
    
    if 'metadata' in result:
        print("\nExtracted Metadata:")
        # Print select metadata fields
        for field in ['case_number', 'year', 'outcome']:
            if field in result['metadata']:
                print(f"  {field}: {result['metadata'][field]}")
    
    # Print number of triples
    triples = result.get('triples', [])
    print(f"\nGenerated {len(triples)} RDF triples")
    
    # Print first 3 triples as examples
    if triples:
        print("\nExample triples:")
        for triple in triples[:3]:
            print(f"  {triple['subject']} - {triple['predicate']} - {triple['object']}")
    
    # Save full output to file if requested
    if save_output:
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename from URL and timestamp
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/url_processor_{domain}_{timestamp}.json"
        
        # Save result to file
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\nFull output saved to {filename}")
    
    return result

if __name__ == "__main__":
    # Check if URL provided as command line argument
    url = None
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    # Run test
    test_url_processor(url)
    
    # Clean up Flask application context
    app_context.pop()
