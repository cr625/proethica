#!/usr/bin/env python3
"""
Script to check if the MCP server is properly returning roles from the ontology.
This script can be used to debug issues with the MCP server.
"""

import os
import sys
import json
import requests

# Get MCP server URL from environment variable or use default
# Make sure MCP_SERVER_URL is correctly set
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL')

if not MCP_SERVER_URL:
    # If not set in environment, try loading from .env file
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('MCP_SERVER_URL='):
                    MCP_SERVER_URL = line.strip().split('=', 1)[1]
                    break
    except:
        pass

# Use default if not found anywhere
if not MCP_SERVER_URL:
    MCP_SERVER_URL = 'http://localhost:5001'

print(f"Using MCP server URL: {MCP_SERVER_URL}")

def check_connection():
    """Check if the MCP server is running and accessible."""
    print(f"Testing connection to MCP server at {MCP_SERVER_URL}...")
    
    # Try different endpoints that might be available
    test_endpoints = [
        "/api/ping",
        "/api/guidelines/engineering-ethics",
        "/api/ontology/engineering_ethics.ttl/entities"
    ]
    
    for endpoint in test_endpoints:
        try:
            full_url = f"{MCP_SERVER_URL}{endpoint}"
            print(f"  Checking endpoint: {full_url}")
            response = requests.get(full_url, timeout=5)
            
            if response.status_code == 200:
                print(f"Successfully connected to MCP server at {full_url}")
                return True
            else:
                print(f"  Endpoint returned status code {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"  Could not connect to {full_url}")
        except Exception as e:
            print(f"  Error checking endpoint {full_url}: {str(e)}")
    
    print(f"All connection attempts to MCP server failed")
    return False

def get_roles(ontology_source="engineering_ethics.ttl"):
    """Get roles from the specified ontology."""
    print(f"\nFetching roles from {ontology_source}...")
    
    # Try to get roles from the MCP server
    api_url = f"{MCP_SERVER_URL}/api/ontology/{ontology_source}/entities"
    try:
        response = requests.get(api_url, params={"type": "roles"}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "entities" in data and "roles" in data["entities"]:
                roles = data["entities"]["roles"]
                print(f"Successfully retrieved {len(roles)} roles from the ontology:")
                for idx, role in enumerate(roles, 1):
                    print(f"  {idx}. {role.get('label', 'Unknown')} - {role.get('description', 'No description')}")
                return True
            else:
                print(f"Response does not contain roles: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        else:
            print(f"Error getting roles: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error retrieving roles: {str(e)}")
    
    print("Failed to retrieve roles from the MCP server")
    return False

def main():
    """Main function to check MCP server and roles."""
    connected = check_connection()
    
    if not connected:
        print("\nERROR: MCP server is not accessible!")
        print("Please make sure the MCP server is running on the correct port")
        sys.exit(1)
    
    # Check roles for different ontologies
    ontologies = ["engineering_ethics.ttl", "military_medical_ethics.ttl", "nj_legal_ethics.ttl"]
    success = False
    
    for ontology in ontologies:
        if get_roles(ontology):
            success = True
    
    if success:
        print("\nSUCCESS: Retrieved roles from at least one ontology")
        sys.exit(0)
    else:
        print("\nERROR: Could not retrieve roles from any ontology")
        print("Check the MCP server logs for more information")
        sys.exit(1)

if __name__ == "__main__":
    main()
