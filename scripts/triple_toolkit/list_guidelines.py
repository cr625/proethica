#!/usr/bin/env python3
"""
List guidelines for a specific world.

This utility displays information about guidelines in a selected world,
including their IDs, titles, content excerpts, and metadata.
"""

import sys
import argparse
from scripts.triple_toolkit.common import db_utils, formatting, pagination

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='List guidelines for a world.')
    parser.add_argument('--world-id', '-w', type=int, default=1,
                      help='World ID (default: 1)')
    parser.add_argument('--detail', '-d', action='store_true',
                      help='Show detailed information for each guideline')
    parser.add_argument('--interactive', '-i', action='store_true',
                      help='Use interactive pager for navigation')
    return parser.parse_args()

def get_world(world_id):
    """Retrieve a world from the database by ID using direct SQL."""
    try:
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
        WHERE id = :world_id
        """
        
        results = db_utils.execute_query(query, {'world_id': world_id})
        
        if not results:
            return None
            
        # Convert to World-like object
        world_data = results[0]
        return WorldInfo(*world_data)
    except Exception as e:
        print(f"Error retrieving world: {e}")
        return None

def get_guidelines(world_id):
    """Retrieve all guidelines for a world using direct SQL."""
    try:
        query = """
        SELECT 
            id, 
            title, 
            content, 
            world_id,
            source_url,
            file_path,
            created_at,
            updated_at
        FROM guidelines
        WHERE world_id = :world_id
        ORDER BY id
        """
        
        results = db_utils.execute_query(query, {'world_id': world_id})
        
        # Convert to Guideline-like objects
        guidelines = []
        for row in results:
            guideline = GuidelineInfo(*row)
            guidelines.append(guideline)
            
        return guidelines
    except Exception as e:
        print(f"Error retrieving guidelines: {e}")
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

class GuidelineInfo:
    """Simple class to represent guideline information from direct query."""
    
    def __init__(self, id, title, content, world_id, source_url, file_path, created_at, updated_at):
        self.id = id
        self.title = title
        self.content = content
        self.world_id = world_id
        self.source_url = source_url
        self.file_path = file_path
        self.created_at = created_at
        self.updated_at = updated_at
        # Stub properties for compatibility
        self.entity_triples = CountableList()
        self.guideline_metadata = {}
        
    def get_content_excerpt(self, length=100):
        """Get a short excerpt of the content."""
        if not self.content:
            return "No content"
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + "..."

class CountableList:
    """A list-like object that supports count()."""
    
    def __init__(self):
        self.items = []
        
    def count(self):
        return len(self.items)
        
    def __len__(self):
        return len(self.items)

def format_guideline_simple(guideline):
    """Format a guideline object for simple display."""
    return f"Guideline {guideline.id}: {guideline.title}"

def format_guideline_detailed(guideline):
    """Format a guideline object for detailed display."""
    triple_count = guideline.entity_triples.count() if hasattr(guideline.entity_triples, 'count') else 'Unknown'
    result = f"Guideline {guideline.id}: {guideline.title}\n"
    result += f"  Content: {guideline.get_content_excerpt(100)}\n"
    result += f"  Entity Triples: {triple_count}\n"
    result += f"  Source: {guideline.source_url or guideline.file_path or 'Unknown'}\n"
    result += f"  Created: {formatting.format_datetime(guideline.created_at)}"
    
    # Add metadata if available
    if guideline.guideline_metadata and isinstance(guideline.guideline_metadata, dict):
        result += "\n  Metadata:"
        for key, value in guideline.guideline_metadata.items():
            if isinstance(value, dict) or isinstance(value, list):
                continue  # Skip complex metadata
            result += f"\n    {key}: {value}"
    
    return result

def list_guidelines_simple(world_id):
    """List guidelines in simple format."""
    world = get_world(world_id)
    if not world:
        print(f"World with ID {world_id} not found.")
        return
    
    guidelines = get_guidelines(world_id)
    if not guidelines:
        print(f"No guidelines found for world '{world.name}' (ID: {world_id}).")
        return
    
    formatting.print_header(f"GUIDELINES FOR WORLD: {world.name}")
    
    for guideline in guidelines:
        print(format_guideline_simple(guideline))

def list_guidelines_detailed(world_id):
    """List guidelines with detailed information."""
    world = get_world(world_id)
    if not world:
        print(f"World with ID {world_id} not found.")
        return
    
    guidelines = get_guidelines(world_id)
    if not guidelines:
        print(f"No guidelines found for world '{world.name}' (ID: {world_id}).")
        return
    
    formatting.print_header(f"GUIDELINES FOR WORLD: {world.name} (DETAILED)")
    
    for i, guideline in enumerate(guidelines):
        if i > 0:
            print()  # Add spacing between guidelines
        print(format_guideline_detailed(guideline))

def list_guidelines_interactive(world_id):
    """List guidelines using an interactive pager."""
    world = get_world(world_id)
    if not world:
        print(f"World with ID {world_id} not found.")
        return
    
    guidelines = get_guidelines(world_id)
    if not guidelines:
        print(f"No guidelines found for world '{world.name}' (ID: {world_id}).")
        return
    
    title = f"GUIDELINES FOR WORLD: {world.name}"
    pagination.interactive_pager(
        guidelines,
        formatter=format_guideline_detailed,
        title=title
    )

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        if args.interactive:
            list_guidelines_interactive(args.world_id)
        elif args.detail:
            list_guidelines_detailed(args.world_id)
        else:
            list_guidelines_simple(args.world_id)
            print("\nTips: Use --detail for more information or --interactive for navigation")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
