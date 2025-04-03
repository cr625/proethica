#!/usr/bin/env python3
"""
Script to create a sample engineering ethics case with RDF triples using the 
triple-based case creation API.
"""

import json
import requests
import sys

def create_triple_case_from_file(file_path, server_url="http://localhost:3333"):
    """
    Create a new case in the Engineering Ethics world using the triple-based approach.
    
    Args:
        file_path: Path to the JSON file containing case data
        server_url: Base URL of the ProEthica server
    """
    # Read the sample case file
    try:
        with open(file_path, 'r') as f:
            case_data = json.load(f)
            print(f"Successfully loaded case data from {file_path}")
    except Exception as e:
        print(f"Error loading case file: {str(e)}")
        return False
    
    # Extract case data
    title = case_data.get('title', '')
    description = case_data.get('description', '')
    source = case_data.get('source', '')
    
    # Extract RDF triple data
    rdf_data = case_data.get('rdf_triples', {})
    triples = rdf_data.get('triples', [])
    namespaces = rdf_data.get('namespaces', {})
    
    # Prepare the data for the triple-based API
    form_data = {
        'source_type': 'manual',
        'title': title,
        'world_id': 1,  # Engineering Ethics world ID
        'description': description,
        'source': source
    }
    
    # Create lists for triples and namespaces data
    subjects = []
    predicates = []
    objects = []
    is_literals = []
    prefixes = []
    uris = []
    
    # Add triple data to lists
    for triple in triples:
        subjects.append(triple['subject'])
        predicates.append(triple['predicate'])
        objects.append(triple['object'])
        is_literals.append('true' if triple.get('is_literal', False) else 'false')
    
    # Add namespace data to lists
    for prefix, uri in namespaces.items():
        prefixes.append(prefix)
        uris.append(uri)
    
    # Add lists to form data
    form_data['subjects[]'] = subjects
    form_data['predicates[]'] = predicates
    form_data['objects[]'] = objects
    form_data['is_literals[]'] = is_literals
    form_data['prefixes[]'] = prefixes
    form_data['uris[]'] = uris
    
    # Print the request data for debugging
    print("\nSending the following data to create triple-based case:")
    print(f"Title: {title}")
    print(f"Description: {description[:100]}...")
    print(f"Triples: {len(triples)}")
    print(f"Namespaces: {len(namespaces)}")
    
    # Send POST request to create the case
    try:
        response = requests.post(
            f"{server_url}/cases/triple/new",
            data=form_data
        )
        
        if response.status_code == 200 or response.status_code == 302:
            print("Case created successfully using triple-based approach!")
            # Try to extract the new case ID from the redirect URL
            if response.history and response.history[0].status_code == 302:
                redirect_url = response.history[0].headers.get('Location', '')
                case_id = redirect_url.split('/')[-1]
                print(f"New case ID: {case_id}")
                print(f"View the case at: {server_url}/cases/{case_id}")
            return True
        else:
            print(f"Error creating case. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error making request: {str(e)}")
        return False

if __name__ == "__main__":
    file_path = "sample_engineering_case.json"
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    create_triple_case_from_file(file_path)
