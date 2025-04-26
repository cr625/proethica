#!/usr/bin/env python3
"""
Script to test the ontology diff API endpoint.
"""
import os
import sys
import requests
import json
from urllib.parse import urljoin
import time

def test_diff_endpoint(ontology_id=1, from_version=1, to_version=None, format_type="unified"):
    """
    Test the ontology diff API endpoint.
    
    Args:
        ontology_id (int): The ontology ID to get diffs for
        from_version (int): The version to compare from
        to_version (int): The version to compare to (if None, uses the latest version)
        format_type (str): The diff format - 'unified' or 'split'
    """
    base_url = "http://localhost:3333"
    
    print("Testing Ontology Diff API Endpoint")
    print("---------------------------------")
    print(f"Ontology ID: {ontology_id}")
    print(f"From Version: {from_version}")
    print(f"To Version: {to_version or 'latest'}")
    print(f"Format: {format_type}")
    print()
    
    # First check if the server is running
    try:
        response = requests.get(f"{base_url}/ontology-editor", timeout=2)
        if response.status_code != 200:
            print(f"Warning: Server returned status code {response.status_code}")
            print("The server may not be running or the ontology editor may not be accessible.")
            return False
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Is it running?")
        print(f"Please start the server and then try to access: {base_url}/ontology-editor/")
        return False
    except requests.exceptions.Timeout:
        print("Error: Connection to server timed out.")
        return False
    
    # Prepare the API URL
    url = f"{base_url}/ontology-editor/api/versions/{ontology_id}/diff"
    params = {
        "from": from_version,
        "format": format_type
    }
    
    if to_version:
        params["to"] = to_version
    
    print(f"API URL: {url}")
    print(f"Params: {params}")
    print()
    
    # Make the request
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=10)
        end_time = time.time()
        
        print(f"Request completed in {end_time - start_time:.2f} seconds")
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Pretty print the response metadata (but not the huge diff content)
            metadata = {k: v for k, v in data.items() if k != 'diff'}
            print("\nResponse metadata:")
            print(json.dumps(metadata, indent=2))
            
            # Print just a sample of the diff content
            diff_content = data.get('diff', '')
            if format_type == 'unified':
                # For unified format, show first few lines
                sample_lines = diff_content.split('\n')[:20]
                print("\nDiff content sample (first 20 lines):")
                for line in sample_lines:
                    print(line)
            else:
                # For HTML format, just show length and a note
                print(f"\nDiff content is HTML, {len(diff_content)} characters long")
                print("HTML content not displayed here for readability")
            
            print("\nSuccess! The diff endpoint is working correctly.")
            return True
        else:
            print("Error response:")
            try:
                print(response.json())
            except:
                print(response.text)
            
            print("\nFailed to get diff from the API.")
            return False
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return False

def get_available_versions(ontology_id=1):
    """
    Get a list of available versions for the specified ontology.
    
    Args:
        ontology_id (int): The ontology ID to get versions for
        
    Returns:
        list: List of version numbers if successful, None otherwise
    """
    base_url = "http://localhost:3333"
    url = f"{base_url}/ontology-editor/api/versions/{ontology_id}"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            versions = [v.get('version_number') for v in data.get('versions', [])]
            return sorted(versions)
        else:
            print(f"Error getting versions: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception while getting versions: {str(e)}")
        return None

if __name__ == "__main__":
    ontology_id = 1  # Default to Engineering Ethics ontology
    
    # Get available versions
    print("Checking available versions...")
    versions = get_available_versions(ontology_id)
    
    if not versions:
        print("Could not retrieve available versions. Using defaults.")
        from_version = 1
        to_version = None  # Latest
    else:
        print(f"Available versions: {', '.join(map(str, versions))}")
        # Use first and last version by default
        from_version = versions[0]
        to_version = versions[-1]
    
    # Run unified diff test
    print("\n=== Testing Unified Diff ===\n")
    test_diff_endpoint(ontology_id, from_version, to_version, "unified")
    
    # Run split diff test
    print("\n=== Testing Split Diff ===\n")
    test_diff_endpoint(ontology_id, from_version, to_version, "split")
    
    print("\nDiff endpoint testing complete!")
