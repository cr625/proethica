#!/usr/bin/env python3
"""
Script to directly update the world's ontology source and force the MCP server to reload it.
This script uses both database access and API calls to perform a complete update.
"""

import os
import sys
import json
import requests
import argparse
import time
from pathlib import Path

# Check for psycopg2 and install if not available
try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    print("psycopg2 not installed. Installing...")
    os.system('pip install psycopg2-binary')
    import psycopg2
    from psycopg2.extras import DictCursor

def update_database(world_id, ontology_source, db_params=None):
    """Update the world's ontology source in the database."""
    # Default database parameters
    if db_params is None:
        db_params = {
            'dbname': 'ai_ethical_dm',
            'user': 'postgres',
            'password': '',
            'host': 'localhost',
            'port': '5432'
        }
    
    print(f"Connecting to database: {db_params['dbname']} on {db_params['host']}:{db_params['port']}")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        # Check if the world exists
        cursor.execute("SELECT id, name FROM worlds WHERE id = %s", (world_id,))
        world = cursor.fetchone()
        
        if not world:
            print(f"Error: World with ID {world_id} not found")
            return False
        
        print(f"Found world: {world['name']} (ID: {world['id']})")
        
        # Update the ontology source
        cursor.execute(
            "UPDATE worlds SET ontology_source = %s WHERE id = %s",
            (ontology_source, world_id)
        )
        
        # Commit the changes
        conn.commit()
        
        print(f"Successfully updated world {world['name']} (ID: {world['id']}) with ontology source: {ontology_source}")
        
        # Close the connection
        cursor.close()
        conn.close()
        
        return True
    
    except Exception as e:
        print(f"Error updating database: {str(e)}")
        return False

def verify_ontology_file(ontology_source):
    """Verify that the ontology file exists and has the proper type designations."""
    ontology_dir = os.path.join('mcp', 'ontology')
    ontology_path = os.path.join(ontology_dir, ontology_source)
    
    if not os.path.exists(ontology_path):
        print(f"Error: Ontology file not found: {ontology_path}")
        return False
    
    print(f"Found ontology file: {ontology_path}")
    
    # Check that the file contains the necessary type designations
    with open(ontology_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    designations = {
        'Role': content.count('rdf:type proeth:Role'),
        'ConditionType': content.count('rdf:type proeth:ConditionType'),
        'ResourceType': content.count('rdf:type proeth:ResourceType'),
        'EventType': content.count('rdf:type proeth:EventType'),
        'ActionType': content.count('rdf:type proeth:ActionType')
    }
    
    print("Type designations found:")
    for designation, count in designations.items():
        print(f"  {designation}: {count}")
    
    if sum(designations.values()) == 0:
        print("\nWarning: No type designations found. Entities may not appear in the UI.")
        return False
    
    return True

def test_entity_extraction(ontology_source, mcp_url="http://localhost:5001"):
    """Test entity extraction from the ontology directly using the MCP API."""
    print(f"\nTesting entity extraction from: {ontology_source}")
    
    try:
        # Make a direct request to the MCP server ontology endpoint
        url = f"{mcp_url}/api/ontology/{ontology_source}/entities"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract entities from the response
            entities = result.get("entities", {})
            
            # Count the number of entities in each category
            categories = ["roles", "conditions", "resources", "events", "actions"]
            entity_counts = {}
            
            for cat in categories:
                if cat in entities:
                    entity_list = entities[cat]
                    entity_counts[cat] = len(entity_list)
                    print(f"  {cat.capitalize()}: {len(entity_list)} entities")
                    
                    # Print up to 3 example entities
                    if entity_list:
                        print(f"\n{cat.capitalize()} examples:")
                        for item in entity_list[:3]:  # Print at most 3 examples
                            if isinstance(item, dict) and "label" in item:
                                print(f"  - {item['label']}: {item.get('description', 'No description')}")
                            else:
                                print(f"  - {item}")
                else:
                    entity_counts[cat] = 0
                    print(f"  {cat.capitalize()}: 0 entities (category not found)")
            
            if sum(entity_counts.values()) == 0:
                print("\nWarning: No entities were extracted. Entities may not appear in the UI.")
                return False
            
            return True
        else:
            print(f"Error: HTTP status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to MCP server at {mcp_url}")
        print("Make sure the MCP server is running.")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def restart_mcp_server():
    """Attempt to restart the MCP server if available."""
    restart_script = os.path.join('scripts', 'restart_mcp_server.sh')
    
    if os.path.exists(restart_script):
        print("\nRestarting MCP server...")
        try:
            os.system(f"bash {restart_script}")
            print("Waiting for server to restart...")
            time.sleep(5)  # Give the server time to start
            return True
        except Exception as e:
            print(f"Error restarting MCP server: {str(e)}")
            return False
    else:
        print(f"\nRestart script not found: {restart_script}")
        print("Please restart the MCP server manually.")
        return False

def main():
    """Parse arguments and update the world with a complete workflow."""
    parser = argparse.ArgumentParser(description="Update a world's ontology source with full verification")
    parser.add_argument("world_id", type=int, help="The ID of the world to update")
    parser.add_argument("ontology_source", help="The ontology source to set")
    
    # Optional PostgreSQL connection parameters
    parser.add_argument("--host", default="localhost", help="PostgreSQL host")
    parser.add_argument("--port", default="5432", help="PostgreSQL port")
    parser.add_argument("--dbname", default="ai_ethical_dm", help="PostgreSQL database name")
    parser.add_argument("--user", default="postgres", help="PostgreSQL user")
    parser.add_argument("--password", default="", help="PostgreSQL password")
    parser.add_argument("--mcp-url", default="http://localhost:5001", help="MCP server URL")
    parser.add_argument("--skip-restart", action="store_true", help="Skip restarting the MCP server")
    
    args = parser.parse_args()
    
    # Steps to get entities to appear
    print("\n=== World Entity Display Fix Workflow ===\n")
    
    # 1. Verify the ontology file
    print("Step 1: Verifying ontology file...")
    if not verify_ontology_file(args.ontology_source):
        print("Please fix issues with the ontology file before continuing.")
        if input("Continue anyway? (y/N): ").lower() != 'y':
            sys.exit(1)
    
    # 2. Update the database
    print("\nStep 2: Updating database...")
    db_params = {
        'host': args.host,
        'port': args.port,
        'dbname': args.dbname,
        'user': args.user,
        'password': args.password
    }
    
    if not update_database(args.world_id, args.ontology_source, db_params):
        print("Please fix database issues before continuing.")
        if input("Continue anyway? (y/N): ").lower() != 'y':
            sys.exit(1)
    
    # 3. Restart the MCP server (if not skipped)
    if not args.skip_restart:
        print("\nStep 3: Restarting MCP server...")
        restart_mcp_server()
    else:
        print("\nStep 3: Skipping MCP server restart.")
    
    # 4. Test entity extraction
    print("\nStep 4: Testing entity extraction...")
    test_entity_extraction(args.ontology_source, args.mcp_url)
    
    # 5. Provide next steps
    print("\n=== Workflow Complete ===\n")
    print("Next steps:")
    print("1. Go to the world detail page in your browser")
    print("2. If entities still don't appear, click the Edit button")
    print("3. Without making changes, click Save to refresh the entities")
    print("4. Check the World Entities section again")
    
    print("\nIf entities still don't appear, check the browser's developer console (F12)")
    print("for error messages. You may need to check the MCP server logs as well.")
    
if __name__ == "__main__":
    main()
