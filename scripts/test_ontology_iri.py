#!/usr/bin/env python3
"""
Test script for ontology IRI resolution feature.

This script tests the dereferenceable IRI functionality by making 
HTTP requests to ontology entity IRIs with different content negotiation.
"""

import requests
import sys
import json
from urllib.parse import quote

# Configuration
BASE_URL = "http://localhost:3334"  # Change this to your server URL
TEST_ENTITY = "http://proethica.org/ontology/engineering-ethics#ProjectEngineerRole"

def print_separator():
    print("\n" + "="*80 + "\n")

def test_iri_resolution(entity_uri, accept_format=None, format_param=None):
    """
    Test IRI resolution with different content negotiation.
    
    Args:
        entity_uri: The IRI to resolve
        accept_format: Optional Accept header value
        format_param: Optional format URL parameter
    """
    print(f"Testing IRI: {entity_uri}")
    if accept_format:
        print(f"Accept header: {accept_format}")
    if format_param:
        print(f"Format parameter: {format_param}")
    
    # Extract the path part of the URI (after proethica.org)
    path = entity_uri.split("proethica.org", 1)[1]
    
    # Build URL
    url = f"{BASE_URL}{path}"
    if format_param:
        url += f"?format={format_param}"
    
    # Prepare headers
    headers = {}
    if accept_format:
        headers['Accept'] = accept_format
    
    # Make the request
    print(f"Making request to: {url}")
    try:
        response = requests.get(url, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'None')}")
        
        # Print the first 500 characters of the response
        content_preview = response.text[:500]
        if len(response.text) > 500:
            content_preview += "... [truncated]"
        print("Response preview:")
        print(content_preview)
        
        return response
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def main():
    print("ONTOLOGY IRI RESOLUTION TEST")
    print_separator()
    
    # Test alternative URL format (without hash) first since it's working
    print("TEST 1: Alternative URL format (without hash)")
    alt_iri = "http://proethica.org/ontology/engineering-ethics/ProjectEngineerRole"
    test_iri_resolution(alt_iri)
    print_separator()

    # Test with default format (should be Turtle)
    print("TEST 2: Default format (should be Turtle) with direct format parameter")
    test_iri_resolution(alt_iri, format_param="ttl")
    print_separator()

    # Test with RDF/XML format via format parameter
    print("TEST 3: RDF/XML format via format parameter")
    test_iri_resolution(alt_iri, format_param="xml")
    print_separator()

    # Test with JSON-LD format via format parameter
    print("TEST 4: JSON-LD format via format parameter") 
    test_iri_resolution(alt_iri, format_param="json")
    print_separator()

    # Test with HTML format via format parameter
    print("TEST 5: HTML format via format parameter")
    test_iri_resolution(alt_iri, format_param="html")
    print_separator()
    
    print("Tests completed.")

if __name__ == "__main__":
    main()
