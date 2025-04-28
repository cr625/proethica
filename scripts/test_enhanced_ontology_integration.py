#!/usr/bin/env python3
"""
Test Enhanced Ontology-LLM Integration

This script demonstrates the enhanced ontology-LLM integration by:
1. Connecting to the enhanced MCP server
2. Performing various ontology queries
3. Formatting the results as they would appear in LLM context
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.enhanced_mcp_client import get_enhanced_mcp_client

def test_basic_entity_retrieval(client, ontology_source="engineering-ethics"):
    """
    Test basic entity retrieval.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
    """
    print(f"\n=== Testing Basic Entity Retrieval from {ontology_source} ===")
    
    # Get roles
    print("\nRetrieving roles...")
    roles = client.get_world_entities(ontology_source, "roles")
    if "entities" in roles and "roles" in roles["entities"]:
        role_count = len(roles["entities"]["roles"])
        print(f"Found {role_count} roles")
        if role_count > 0:
            print("Sample roles:")
            for role in roles["entities"]["roles"][:3]:  # Show up to 3 roles
                print(f"- {role.get('label', 'Unnamed')}: {role.get('description', 'No description')[:50]}...")
    else:
        print("No roles found or error in response")
    
    # Get capabilities
    print("\nRetrieving capabilities...")
    capabilities = client.get_world_entities(ontology_source, "capabilities")
    if "entities" in capabilities and "capabilities" in capabilities["entities"]:
        capability_count = len(capabilities["entities"]["capabilities"])
        print(f"Found {capability_count} capabilities")
        if capability_count > 0:
            print("Sample capabilities:")
            for cap in capabilities["entities"]["capabilities"][:3]:  # Show up to 3 capabilities
                print(f"- {cap.get('label', 'Unnamed')}: {cap.get('description', 'No description')[:50]}...")
    else:
        print("No capabilities found or error in response")

def test_entity_search(client, ontology_source="engineering-ethics", query="ethics"):
    """
    Test entity search functionality.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
        query: Search query
    """
    print(f"\n=== Testing Entity Search for '{query}' in {ontology_source} ===")
    
    search_results = client.search_entities(
        ontology_source=ontology_source,
        query=query
    )
    
    if "entities" in search_results:
        entity_count = len(search_results["entities"])
        print(f"Found {entity_count} entities matching '{query}'")
        if entity_count > 0:
            print("Matching entities:")
            for entity in search_results["entities"][:5]:  # Show up to 5 entities
                # Get types in simpler format
                types = entity.get("types", [])
                simplified_types = []
                for t in types:
                    # Extract the final part of the URI
                    type_parts = t.split("/")
                    if type_parts:
                        type_name = type_parts[-1].split("#")[-1]
                        simplified_types.append(type_name.replace("_", " "))
                
                type_str = ", ".join(simplified_types) if simplified_types else "Unknown type"
                print(f"- {entity.get('label', 'Unnamed')} ({type_str})")
    else:
        print(f"No entities found matching '{query}' or error in response")

def test_entity_details(client, ontology_source="engineering-ethics", entity_uri=None):
    """
    Test entity details retrieval.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
        entity_uri: URI of entity to retrieve details for (if None, will search for 'Engineer')
    """
    print(f"\n=== Testing Entity Details from {ontology_source} ===")
    
    # If no entity URI provided, search for "Engineer"
    if not entity_uri:
        search_results = client.search_entities(
            ontology_source=ontology_source,
            query="Engineer"
        )
        
        if "entities" in search_results and search_results["entities"]:
            entity_uri = search_results["entities"][0]["uri"]
            print(f"Using entity from search: {search_results['entities'][0].get('label', 'Unnamed')}")
        else:
            print("No entities found from search, cannot test entity details")
            return
    
    # Get entity details
    details = client.get_entity_details(
        ontology_source=ontology_source,
        entity_uri=entity_uri
    )
    
    # Format the details
    formatted_details = client.format_entity_for_context(details)
    print("\nFormatted Entity Details:")
    print(formatted_details)

def test_entity_relationships(client, ontology_source="engineering-ethics", entity_uri=None):
    """
    Test entity relationship retrieval.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
        entity_uri: URI of entity to retrieve relationships for (if None, will search for 'Engineer')
    """
    print(f"\n=== Testing Entity Relationships from {ontology_source} ===")
    
    # If no entity URI provided, search for "Engineer"
    if not entity_uri:
        search_results = client.search_entities(
            ontology_source=ontology_source,
            query="Engineer"
        )
        
        if "entities" in search_results and search_results["entities"]:
            entity_uri = search_results["entities"][0]["uri"]
            print(f"Using entity from search: {search_results['entities'][0].get('label', 'Unnamed')}")
        else:
            print("No entities found from search, cannot test entity relationships")
            return
    
    # Get entity relationships
    relationships = client.get_entity_relationships(
        ontology_source=ontology_source,
        entity_uri=entity_uri
    )
    
    # Format the relationships
    formatted_relationships = client.format_relationships_for_context(relationships)
    print("\nFormatted Entity Relationships:")
    print(formatted_relationships)

def test_ontology_guidelines(client, ontology_source="engineering-ethics"):
    """
    Test retrieval of ontology guidelines.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
    """
    print(f"\n=== Testing Ontology Guidelines from {ontology_source} ===")
    
    # Get guidelines
    guidelines = client.get_ontology_guidelines(ontology_source)
    
    # Format the guidelines
    formatted_guidelines = client.format_guidelines_for_context(guidelines)
    print("\nFormatted Ontology Guidelines:")
    print(formatted_guidelines)

def test_sparql_query(client, ontology_source="engineering-ethics"):
    """
    Test executing a SPARQL query.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
    """
    print(f"\n=== Testing SPARQL Query on {ontology_source} ===")
    
    # Define a simple SPARQL query to find all roles
    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX proeth: <http://proethica.org/ontology/intermediate#>
    
    SELECT ?role ?label
    WHERE {
        ?role rdf:type proeth:Role .
        OPTIONAL { ?role rdfs:label ?label }
    }
    LIMIT 5
    """
    
    # Execute the query
    results = client.query_ontology(
        ontology_source=ontology_source,
        query=query
    )
    
    if "results" in results:
        print(f"Found {len(results['results'])} results")
        if results["results"]:
            print("Query results:")
            for result in results["results"]:
                role = result.get("role", {})
                role_uri = role.get("uri", "Unknown")
                role_label = role.get("label", role_uri.split("/")[-1].replace("_", " "))
                print(f"- {role_label}: {role_uri}")
    else:
        error = results.get("error", "Unknown error")
        print(f"Error executing query: {error}")

def test_constraint_checking(client, ontology_source="engineering-ethics"):
    """
    Test constraint checking.
    
    Args:
        client: Enhanced MCP client
        ontology_source: Ontology source to query
    """
    print(f"\n=== Testing Constraint Checking on {ontology_source} ===")
    
    # First, search for an Engineer entity
    search_results = client.search_entities(
        ontology_source=ontology_source,
        query="Engineer"
    )
    
    if not search_results.get("entities"):
        print("No Engineer entity found, skipping constraint check")
        return
    
    engineer_uri = search_results["entities"][0]["uri"]
    engineer_label = search_results["entities"][0].get("label", "Engineer")
    
    print(f"Testing capability constraints for {engineer_label}")
    
    # Check if the Engineer has the required capabilities
    constraint_check = client.check_constraint(
        ontology_source=ontology_source,
        entity_uri=engineer_uri,
        constraint_type="custom",
        constraint_data={
            "validation_type": "role_capability",
            "required_capabilities": [
                "http://proethica.org/ontology/engineering-ethics#Technical_Design"
            ]
        }
    )
    
    if "is_valid" in constraint_check:
        if constraint_check["is_valid"]:
            print(f"✓ {engineer_label} has all required capabilities")
        else:
            print(f"✗ {engineer_label} is missing required capabilities:")
            for cap in constraint_check.get("missing_capabilities", []):
                print(f"  - {cap.split('/')[-1].replace('_', ' ')}")
        
        print(f"\nCapabilities of {engineer_label}:")
        for cap in constraint_check.get("role_capabilities", []):
            print(f"- {cap.split('/')[-1].replace('_', ' ')}")
    else:
        error = constraint_check.get("error", "Unknown error")
        print(f"Error checking constraints: {error}")

def main():
    """Run all tests."""
    # Get default ontology source (change to match your available ontologies)
    ontology_source = "engineering-ethics"
    
    print("=== Testing Enhanced Ontology-LLM Integration ===")
    print(f"Using ontology source: {ontology_source}")
    
    # Get the enhanced MCP client
    client = get_enhanced_mcp_client()
    
    # Check connection
    if not client.check_connection():
        print("\nWARNING: Could not connect to MCP server!")
        print("Make sure the enhanced MCP server is running with:")
        print("  python3 mcp/run_enhanced_mcp_server.py")
        
        # Ask if we should continue with mock data
        response = input("\nContinue with mock data? (y/n): ")
        if response.lower() != 'y':
            print("Exiting test.")
            return 1
        print("Continuing with mock data...")
    
    # Run each test
    tests = [
        test_basic_entity_retrieval,
        test_entity_search,
        test_entity_details,
        test_entity_relationships,
        test_ontology_guidelines,
        test_sparql_query,
        test_constraint_checking
    ]
    
    for test_func in tests:
        try:
            test_func(client, ontology_source)
        except Exception as e:
            print(f"Error in {test_func.__name__}: {str(e)}")
    
    print("\n=== Test Complete ===")
    print("\nIf all tests passed, the enhanced ontology-LLM integration is working correctly.")
    print("Next steps:")
    print("1. Enable the integration with: python3 scripts/enable_enhanced_ontology_integration.py")
    print("2. Restart the application to apply context provider changes")
    print("3. Check for 'Enhanced ontology context' in LLM responses")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
