#!/usr/bin/env python3
"""
Test script to verify MCP server is correctly loading ontologies from the database.

This script:
1. Connects to the database to verify ontology content is present
2. Makes a direct call to the MCP server to retrieve entities
3. Compares entities from both sources to verify consistency
"""
import sys
import os
import json
import argparse
import requests
from flask import Flask, current_app

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models.ontology import Ontology
from app.services.ontology_entity_service import OntologyEntityService

# MCP server settings
MCP_SERVER_URL = "http://localhost:5001"  # Default MCP HTTP server port

def print_header(text):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)

def verify_database_ontologies():
    """Verify ontologies exist in the database"""
    print_header("Checking Database Ontologies")
    
    app = create_app()
    with app.app_context():
        ontologies = Ontology.query.all()
        
        if not ontologies:
            print("❌ No ontologies found in database!")
            return False
            
        print(f"✅ Found {len(ontologies)} ontologies in database:")
        for ontology in ontologies:
            content_length = len(ontology.content) if ontology.content else 0
            print(f"  - {ontology.name} (ID: {ontology.id}, domain: {ontology.domain_id})")
            print(f"    Content length: {content_length} bytes")
            
        return True

def test_mcp_entity_extraction(domain_id):
    """Test MCP server entity extraction from specified domain"""
    print_header(f"Testing MCP Entity Extraction for '{domain_id}'")
    
    try:
        # Call the MCP server directly
        jsonrpc_data = {
            "jsonrpc": "2.0",
            "method": "call_tool",
            "params": {
                "name": "get_world_entities",
                "arguments": {
                    "ontology_source": domain_id,
                    "entity_type": "all"
                }
            },
            "id": 1
        }
        
        response = requests.post(f"{MCP_SERVER_URL}/jsonrpc", json=jsonrpc_data, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ MCP server request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
        result = response.json()
        if "error" in result:
            print(f"❌ MCP server returned error: {result['error']}")
            return None
            
        # Parse the content
        content_text = result["result"]["content"][0]["text"]
        entities_data = json.loads(content_text)
        
        # Check if entities were found
        entities = entities_data.get("entities", {})
        if not entities:
            print("❌ No entities found in MCP response")
            return None
            
        # Count entities by type
        print("✅ Entities found in MCP response:")
        for entity_type, entity_list in entities.items():
            print(f"  - {entity_type}: {len(entity_list)} items")
            
        return entities
    except Exception as e:
        print(f"❌ Error calling MCP server: {str(e)}")
        return None

def test_direct_entity_extraction(domain_id):
    """Test direct entity extraction from database using OntologyEntityService"""
    print_header(f"Testing Direct Entity Extraction for '{domain_id}'")
    
    try:
        app = create_app()
        with app.app_context():
            # Find the ontology by domain_id
            ontology = Ontology.query.filter_by(domain_id=domain_id).first()
            if not ontology:
                print(f"❌ Ontology with domain_id '{domain_id}' not found in database")
                return None
                
            # Create a dummy world with the ontology ID
            class DummyWorld:
                def __init__(self, ontology_id):
                    self.ontology_id = ontology_id
                    
            dummy_world = DummyWorld(ontology.id)
            
            # Use the entity service to extract entities
            entity_service = OntologyEntityService.get_instance()
            entities_response = entity_service.get_entities_for_world(dummy_world)
            
            if "error" in entities_response:
                print(f"❌ Entity extraction error: {entities_response['error']}")
                return None
                
            entities = entities_response.get("entities", {})
            if not entities:
                print("❌ No entities found in direct extraction")
                return None
                
            # Count entities by type
            print("✅ Entities found in direct extraction:")
            for entity_type, entity_list in entities.items():
                print(f"  - {entity_type}: {len(entity_list)} items")
                
            return entities
    except Exception as e:
        print(f"❌ Error in direct entity extraction: {str(e)}")
        return None

def compare_entities(mcp_entities, direct_entities):
    """Compare entities from MCP server and direct extraction"""
    print_header("Comparing Entity Results")
    
    if not mcp_entities or not direct_entities:
        print("❌ Cannot compare entities (one or both sources failed)")
        return
        
    # Check if the same entity types are present
    mcp_types = set(mcp_entities.keys())
    direct_types = set(direct_entities.keys())
    
    if mcp_types != direct_types:
        print("❌ Entity type mismatch:")
        print(f"  - MCP types: {mcp_types}")
        print(f"  - Direct types: {direct_types}")
    else:
        print(f"✅ Entity types match: {mcp_types}")
        
    # Compare counts for each type
    for entity_type in mcp_types.intersection(direct_types):
        mcp_count = len(mcp_entities[entity_type])
        direct_count = len(direct_entities[entity_type])
        
        if mcp_count == direct_count:
            print(f"✅ {entity_type}: Both sources have {mcp_count} entities")
        else:
            print(f"❌ {entity_type}: Count mismatch - MCP: {mcp_count}, Direct: {direct_count}")
    
    # Overall consistency check
    all_counts_match = all(
        len(mcp_entities.get(t, [])) == len(direct_entities.get(t, []))
        for t in mcp_types.union(direct_types)
    )
    
    if all_counts_match:
        print("\n✅ SUCCESS: Entity extraction is consistent between MCP server and direct database access")
    else:
        print("\n❌ INCONSISTENCY: Entity extraction differs between MCP server and direct database access")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Test MCP server with database ontologies")
    parser.add_argument("domain_id", nargs="?", default="engineering-ethics", 
                        help="Domain ID to test (defaults to 'engineering-ethics')")
    args = parser.parse_args()
    
    print(f"Testing MCP server with database ontology: {args.domain_id}")
    
    # Step 1: Verify ontologies in database
    db_ok = verify_database_ontologies()
    if not db_ok:
        print("Database check failed, cannot continue")
        return
        
    # Step 2: Test MCP entity extraction
    mcp_entities = test_mcp_entity_extraction(args.domain_id)
    
    # Step 3: Test direct entity extraction
    direct_entities = test_direct_entity_extraction(args.domain_id)
    
    # Step 4: Compare results
    compare_entities(mcp_entities, direct_entities)

if __name__ == "__main__":
    main()
