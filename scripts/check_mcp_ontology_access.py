#!/usr/bin/env python3
"""
Script to check if the MCP server can access the ontology data
"""

import os
import sys
import json
import requests

def check_mcp_ontology_access():
    """Check if the MCP server can access the ontology data"""
    
    # MCP server URL
    mcp_server_url = "http://localhost:5001"
    
    print(f"Checking MCP server at {mcp_server_url}...")
    
    # Check if server is running
    try:
        response = requests.get(f"{mcp_server_url}/api/ping")
        if response.status_code != 200:
            print(f"MCP server not responding correctly: Status {response.status_code}")
            try:
                # Try another endpoint
                response = requests.get(f"{mcp_server_url}/api/guidelines/engineering-ethics")
                if response.status_code == 200:
                    print(f"MCP server is running (alternate endpoint check successful)")
                else:
                    print(f"MCP server alternate endpoint check failed: Status {response.status_code}")
                    return
            except Exception as e:
                print(f"MCP server is not running or not accessible: {e}")
                return
    except Exception as e:
        print(f"MCP server is not running or not accessible: {e}")
        return
    
    # Check ontologies
    ontology_domain_ids = ["bfo", "proethica-intermediate", "engineering-ethics"]
    
    print("\nChecking ontology access through MCP server...")
    
    for domain_id in ontology_domain_ids:
        print(f"\nChecking ontology: {domain_id}")
        
        # Try to get entities from ontology
        try:
            response = requests.get(f"{mcp_server_url}/api/entities/{domain_id}")
            if response.status_code == 200:
                data = response.json()
                entities = data.get("entities", [])
                entity_count = len(entities) if isinstance(entities, list) else 'Unknown structure'
                print(f"- Successfully accessed entities: {entity_count} entities found")
                if entity_count == 0:
                    print("  Note: No entities returned, but endpoint accessible")
            else:
                print(f"- Failed to access entities: Status {response.status_code}")
                if response.text:
                    print(f"  Response: {response.text[:100]}...")
        except Exception as e:
            print(f"- Error accessing entities: {e}")
        
        # Try to get guidelines (for engineering-ethics only)
        if domain_id == "engineering-ethics":
            try:
                response = requests.get(f"{mcp_server_url}/api/guidelines/{domain_id}")
                if response.status_code == 200:
                    data = response.json()
                    guidelines = data.get("guidelines", [])
                    guideline_count = len(guidelines) if isinstance(guidelines, list) else 'Unknown structure'
                    print(f"- Successfully accessed guidelines: {guideline_count} guidelines found")
                    if guideline_count == 0:
                        print("  Note: No guidelines returned, but endpoint accessible")
                else:
                    print(f"- Failed to access guidelines: Status {response.status_code}")
                    if response.text:
                        print(f"  Response: {response.text[:100]}...")
            except Exception as e:
                print(f"- Error accessing guidelines: {e}")
        
        # Try JSON-RPC method to query ontology
        try:
            jsonrpc_payload = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "execute_sparql",
                    "arguments": {
                        "ontology_source": domain_id,
                        "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5"
                    }
                },
                "id": 1
            }
            
            response = requests.post(f"{mcp_server_url}/jsonrpc", json=jsonrpc_payload)
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                content = result.get("content", [])
                if content and len(content) > 0:
                    print("- Successfully executed SPARQL query through JSON-RPC")
                else:
                    print("- SPARQL query returned no results")
            else:
                print(f"- Failed to execute SPARQL query: Status {response.status_code}")
                if response.text:
                    print(f"  Response: {response.text[:100]}...")
        except Exception as e:
            print(f"- Error executing SPARQL query: {e}")
    
    print("\nMCP server ontology access check completed.")

if __name__ == "__main__":
    check_mcp_ontology_access()
