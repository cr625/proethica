#!/usr/bin/env python3
"""
Script to remove all cases from the Engineering Ethics world.
This script identifies and removes all case documents associated with the Engineering world,
ensuring proper cleanup of entity triples and world references.
"""

import sys
import os
import json
from datetime import datetime

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db
from app.models.document import Document
from app.models.world import World

# Constants
ENGINEERING_WORLD_ID = 1  # Engineering Ethics world ID

def remove_world_cases(world_id=ENGINEERING_WORLD_ID, dry_run=False):
    """
    Remove all case documents associated with the specified world.
    
    Args:
        world_id (int): ID of the world to clean up (default: Engineering world)
        dry_run (bool): If True, only show what would be deleted without actually deleting
        
    Returns:
        int: Number of cases deleted
    """
    # Find the world
    world = World.query.get(world_id)
    if not world:
        print(f"Error: World with ID {world_id} not found")
        return 0
    
    print(f"Processing world: {world.name} (ID: {world_id})")
    
    # Find all case documents for this world
    cases = Document.query.filter_by(
        world_id=world_id,
        document_type='case_study'
    ).all()
    
    print(f"Found {len(cases)} cases to remove")
    
    # Track deleted cases
    deleted_count = 0
    
    # Delete each case
    for case in cases:
        print(f"Processing case: {case.title} (ID: {case.id})")
        
        if dry_run:
            print(f"  [DRY RUN] Would delete case: {case.title} (ID: {case.id})")
            deleted_count += 1
            continue
        
        # Remove from world's cases list
        if world.cases and case.id in world.cases:
            print(f"  Removing case ID {case.id} from world's cases list")
            world.cases.remove(case.id)
        
        # Delete any associated entity triples
        try:
            from app.services.entity_triple_service import EntityTripleService
            triple_service = EntityTripleService()
            
            print(f"  Deleting entity triples for document ID {case.id}")
            # Check if the delete_triples_for_entity method exists
            if hasattr(triple_service, 'delete_triples_for_entity'):
                triple_service.delete_triples_for_entity('document', case.id)
            else:
                # Alternative approach if method doesn't exist
                from app.models.entity_triple import EntityTriple
                EntityTriple.query.filter_by(
                    entity_type='document',
                    entity_id=case.id
                ).delete()
                print(f"  Deleted triples using direct query")
        except Exception as e:
            print(f"  Warning: Error deleting entity triples: {str(e)}")
        
        # Delete any document chunks
        try:
            from app.models.document_chunk import DocumentChunk
            chunks = DocumentChunk.query.filter_by(document_id=case.id).all()
            for chunk in chunks:
                db.session.delete(chunk)
            print(f"  Deleted {len(chunks)} document chunks")
        except Exception as e:
            print(f"  Warning: Error deleting document chunks: {str(e)}")
        
        # Delete the document
        print(f"  Deleting document: {case.title} (ID: {case.id})")
        db.session.delete(case)
        deleted_count += 1
    
    # Update world
    if not dry_run and world.cases:
        db.session.add(world)
    
    # Commit changes
    if not dry_run:
        db.session.commit()
        print(f"Changes committed to database. Deleted {deleted_count} cases.")
    else:
        print(f"[DRY RUN] Would have deleted {deleted_count} cases.")
    
    return deleted_count

def main():
    """
    Main function to remove cases from the Engineering world.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Remove cases from the Engineering world')
    parser.add_argument('--world-id', type=int, default=ENGINEERING_WORLD_ID,
                        help=f'World ID to process (default: {ENGINEERING_WORLD_ID})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted without actually deleting')
    args = parser.parse_args()
    
    # Create app context
    app = create_app()
    with app.app_context():
        # Print a warning
        print("=" * 80)
        print("WARNING: This script will remove all cases from the specified world.")
        print(f"World ID: {args.world_id}")
        print("=" * 80)
        
        if not args.dry_run:
            confirmation = input("Are you sure you want to proceed? (yes/no): ")
            if confirmation.lower() != 'yes':
                print("Operation cancelled.")
                return
        
        # Remove cases
        removed = remove_world_cases(args.world_id, args.dry_run)
        
        print(f"Completed. {removed} cases were {'identified' if args.dry_run else 'removed'}.")

if __name__ == "__main__":
    main()
