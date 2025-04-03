#!/usr/bin/env python3
"""
Script to update an existing world's ontology source.
"""

import os
import sys
import json
import sqlite3
import argparse

def update_world_ontology(world_id, ontology_source):
    """
    Update a world's ontology source in the database.
    
    Args:
        world_id (int): The ID of the world to update
        ontology_source (str): The ontology source to set
    """
    # Get database path from environment or use default
    db_path = os.environ.get("DATABASE_URL", "instance/proethica.db")
    
    # If the database URL starts with sqlite://, extract just the path
    if db_path.startswith("sqlite:///"):
        db_path = db_path[10:]

    # Connect to the database
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the world exists
        cursor.execute("SELECT id, name FROM worlds WHERE id = ?", (world_id,))
        world = cursor.fetchone()
        
        if not world:
            print(f"Error: World with ID {world_id} not found")
            return False
        
        print(f"Found world: {world[1]} (ID: {world[0]})")
        
        # Update the ontology source
        cursor.execute(
            "UPDATE worlds SET ontology_source = ? WHERE id = ?",
            (ontology_source, world_id)
        )
        
        # Commit the changes
        conn.commit()
        
        print(f"Successfully updated world {world[1]} (ID: {world[0]}) with ontology source: {ontology_source}")
        return True
        
    except Exception as e:
        print(f"Error updating world: {str(e)}")
        return False
    finally:
        conn.close()

def main():
    """Parse arguments and update the world."""
    parser = argparse.ArgumentParser(description="Update a world's ontology source")
    parser.add_argument("world_id", type=int, help="The ID of the world to update")
    parser.add_argument("ontology_source", help="The ontology source to set")
    
    args = parser.parse_args()
    
    success = update_world_ontology(args.world_id, args.ontology_source)
    
    if success:
        print("\nNext steps:")
        print("1. Restart the MCP server if it's running")
        print("2. Refresh the world details page in the browser")
        print("3. Use test_ontology_extraction.py to verify entity extraction is working")
        print("\nCommand to test extraction:")
        print(f"python scripts/test_ontology_extraction.py {args.ontology_source}")
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
