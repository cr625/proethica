#!/usr/bin/env python3
"""
Script to create a sample engineering ethics case with RDF triples metadata
from the sample_engineering_case.json file.
"""

import json
import requests
import sys

def create_case_from_file(file_path, server_url="http://localhost:3333"):
    """
    Create a new case in the Engineering Ethics world using sample data.
    
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
    decision = case_data.get('decision', '')
    outcome = case_data.get('outcome', '')
    ethical_analysis = case_data.get('ethical_analysis', '')
    rdf_metadata = json.dumps(case_data.get('rdf_triples', {}))
    
    # Create form data for POST request
    form_data = {
        'title': title,
        'world_id': 1,  # Engineering Ethics world ID
        'description': description,
        'decision': decision,
        'outcome': outcome,
        'ethical_analysis': ethical_analysis,
        'rdf_metadata': rdf_metadata
    }
    
    # Send POST request to create the case
    try:
        response = requests.post(
            f"{server_url}/cases/new",
            data=form_data
        )
        
        if response.status_code == 200 or response.status_code == 302:
            print("Case created successfully!")
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
    
    create_case_from_file(file_path)
