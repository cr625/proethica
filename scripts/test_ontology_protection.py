#!/usr/bin/env python3
"""
Script to test ontology protection by attempting to modify both protected 
and non-protected ontologies through the API.
"""

import sys
import os
import requests
import json

# Add parent directory to path for imports (if needed later)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define base URL for API
BASE_URL = "http://localhost:3333/ontology-editor/api"

# Valid Turtle content for testing updates
VALID_TTL_CONTENT = '''
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix test: <http://example.org/test#> .

test:TestClass a owl:Class ;
    rdfs:label "Test Class" ;
    rdfs:comment "This is a test class for ontology protection testing." .
'''

def test_update_ontology(ontology_id, content):
    """Attempt to update an ontology and display the result."""
    url = f"{BASE_URL}/ontology/{ontology_id}/content"
    
    print(f"\n=== Testing update for ontology ID={ontology_id} ===")
    print(f"URL: {url}")
    print("Sending content...")
    
    headers = {'Content-Type': 'application/json'}
    # Properly format the content as JSON
    json_data = json.dumps(content)
    print(f"\nResponse Status: {response.status_code}")
    try:
        response_json = response.json()
        print("Response Body:")
        print(json.dumps(response_json, indent=2))
        
        # Check if this is a protection error
        if "not editable" in str(response_json):
            print("\n➡️ RESULT: Ontology is PROTECTED from editing as expected")
        elif response.status_code == 200:
            print("\n➡️ RESULT: Ontology was successfully updated (NOT protected)")
        else:
            print("\n➡️ RESULT: Update failed for other reasons (validation error, etc.)")
    except:
        print("Response Body: (not JSON)")
        print(response.text)

def main():
    """Main function to test ontology protection."""
    print("===== ONTOLOGY PROTECTION TESTING =====")
    
    # Test 1: Try to update a protected ontology (BFO)
    print("\n\n🔒 TEST 1: Updating protected ontology (BFO, ID=2)")
    test_update_ontology(2, VALID_TTL_CONTENT)
    
    # Test 2: Try to update a non-protected ontology
    print("\n\n🔓 TEST 2: Updating non-protected ontology (Engineering Ethics, ID=1)")
    test_update_ontology(1, VALID_TTL_CONTENT)
    
    print("\n\n===== TESTING COMPLETE =====")

if __name__ == "__main__":
    main()
