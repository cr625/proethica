#!/usr/bin/env python3
"""
List all worlds in the database.

This utility displays information about all worlds in the system,
including their IDs, names, descriptions, and associated ontology sources.
"""

import sys
import argparse
from scripts.triple_toolkit.common import db_utils, formatting

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='List all worlds in the database.')
    parser.add_argument('--detail', '-d', action='store_true',
                      help='Show detailed information for each world')
    return parser.parse_args()

def get_worlds():
    """Retrieve all worlds from the database using direct SQL queries."""
    try:
        # Direct SQL query to fetch worlds
        query = """
        SELECT 
            id, 
            name, 
            description, 
            ontology_id, 
            ontology_source,
            created_at,
            updated_at
        FROM worlds
        ORDER BY id
        """
        
        results = db_utils.execute_query(query)
        
        # Convert results to World-like objects
        worlds = []
        for row in results:
            world = WorldInfo(*row)
            worlds.append(world)
        
        # Fetch guideline counts for each world
        for world in worlds:
            guideline_query = """
            SELECT COUNT(*) 
            FROM guidelines 
            WHERE world_id = :world_id
            """
            guideline_count = db_utils.execute_query(guideline_query, {'world_id': world.id})
            world.guideline_count = guideline_count[0][0] if guideline_count else 0
        
        return worlds
    except Exception as e:
        print(f"Error retrieving worlds: {e}")
        return []

class WorldInfo:
    """Simple class to represent world information from direct query."""
    
    def __init__(self, id, name, description, ontology_id, ontology_source, created_at, updated_at):
        self.id = id
        self.name = name
        self.description = description
        self.ontology_id = ontology_id
        self.ontology_source = ontology_source
        self.created_at = created_at
        self.updated_at = updated_at
        # Default values to be updated later
        self.guideline_count = 0
        self.entity_triples = []

    def __str__(self):
        return f"World {self.id}: {self.name}"

def format_world_simple(world):
    """Format a world object for simple display."""
    return f"World {world.id}: {world.name}"

def format_world_detailed(world):
    """Format a world object for detailed display."""
    ontology_info = f"Ontology ID: {world.ontology_id}" if world.ontology_id else f"Source: {world.ontology_source}"
    
    result = f"World {world.id}: {world.name}\n"
    result += f"  Description: {world.description or 'No description'}\n"
    result += f"  {ontology_info}\n"
    result += f"  Guidelines: {world.guideline_count}\n"
    result += f"  Entity Triples: {len(world.entity_triples) if hasattr(world.entity_triples, '__len__') else 'Unknown'}\n"
    result += f"  Created: {formatting.format_datetime(world.created_at)}"
    
    return result

def list_worlds_simple():
    """List worlds in simple format."""
    worlds = get_worlds()
    
    if not worlds:
        print("No worlds found in the database.")
        return
    
    formatting.print_header("WORLDS")
    
    for world in worlds:
        print(format_world_simple(world))

def list_worlds_detailed():
    """List worlds with detailed information."""
    worlds = get_worlds()
    
    if not worlds:
        print("No worlds found in the database.")
        return
    
    formatting.print_header("WORLDS (DETAILED)")
    
    for i, world in enumerate(worlds):
        if i > 0:
            print()  # Add spacing between worlds
        print(format_world_detailed(world))

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        if args.detail:
            list_worlds_detailed()
        else:
            list_worlds_simple()
            print("\nTip: Use --detail for more information")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
