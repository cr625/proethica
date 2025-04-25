#!/usr/bin/env python3
"""
Test script for the ontology visualization feature.

This script tests the ontology hierarchy API endpoint by fetching a 
hierarchy for a specified ontology ID and printing the result.
"""

import sys
import json
import requests
from pprint import pprint

def test_ontology_hierarchy(ontology_id, base_url="http://localhost:3333"):
    """
    Test the ontology hierarchy API endpoint.
    
    Args:
        ontology_id: ID of the ontology to test
        base_url: Base URL of the application
    """
    print(f"Testing ontology hierarchy for ontology_id: {ontology_id}")
    
    # Test the hierarchy API endpoint
    hierarchy_url = f"{base_url}/ontology-editor/api/hierarchy/{ontology_id}"
    print(f"Fetching hierarchy from: {hierarchy_url}")
    
    try:
        response = requests.get(hierarchy_url)
        response.raise_for_status()
        
        data = response.json()
        
        # Print ontology details
        print("\nOntology Details:")
        print(f"Name: {data['ontology'].get('name')}")
        print(f"Domain ID: {data['ontology'].get('domain_id')}")
        
        # Print hierarchy details
        hierarchy = data['hierarchy']
        print("\nHierarchy Overview:")
        print(f"Root Name: {hierarchy.get('name')}")
        print(f"Root Type: {hierarchy.get('type')}")
        print(f"Number of Top-Level Classes: {len(hierarchy.get('children', []))}")
        
        # Print first few levels of the hierarchy
        print("\nHierarchy Structure (first 2 levels):")
        print_hierarchy_levels(hierarchy, max_depth=2)
        
        print("\nTest completed successfully.")
        return True
    
    except requests.RequestException as e:
        print(f"Error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def print_hierarchy_levels(node, depth=0, max_depth=2):
    """Print hierarchy levels up to max_depth."""
    if depth > max_depth:
        return
    
    prefix = "  " * depth
    print(f"{prefix}- {node.get('name')} ({node.get('type', 'unknown')})")
    
    children = node.get('children', [])
    if depth == max_depth and children:
        print(f"{prefix}  (... {len(children)} more child nodes ...)")
    else:
        for child in children:
            print_hierarchy_levels(child, depth + 1, max_depth)

if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) < 2:
        print("Usage: python test_ontology_visualization.py <ontology_id> [base_url]")
        sys.exit(1)
    
    ontology_id = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:3333"
    
    # Run the test
    success = test_ontology_hierarchy(ontology_id, base_url)
    sys.exit(0 if success else 1)
