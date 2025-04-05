#!/usr/bin/env python3
"""
Script to cleanup incorrectly imported NSPE cases with the title "Pre Header Utility Links".
This script identifies and removes cases with incorrect titles and content
that were imported due to issues with content extraction from the NSPE website.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Import the application and database
from app import create_app, db

def cleanup_header_links_cases(world_id=1, delete=True):
    """
    Clean up cases with the title "Pre Header Utility Links" that were incorrectly imported.
    
    Args:
        world_id: ID of the world to clean up cases for
        delete: If True, delete the cases. If False, just print them.
    
    Returns:
        list of deleted document IDs
    """
    from app.models.document import Document
    from app.models.world import World
    
    app = create_app()
    with app.app_context():
        # Get the world
        world = World.query.get(world_id)
        if not world:
            print(f"Error: World with ID {world_id} not found")
            return []
        
        # Find documents with the title "Pre Header Utility Links"
        incorrect_docs = Document.query.filter_by(
            title="Pre Header Utility Links",
            document_type="case_study",
            world_id=world_id
        ).all()
        
        if not incorrect_docs:
            print(f"No incorrectly imported cases found in world ID {world_id}")
            return []
        
        print(f"Found {len(incorrect_docs)} incorrectly imported cases in world ID {world_id}")
        
        if not delete:
            # Just print the cases without deleting them
            for doc in incorrect_docs:
                print(f"ID: {doc.id}, Title: {doc.title}, Source: {doc.source}")
            return [doc.id for doc in incorrect_docs]
        
        # Delete the cases and update the world's cases list
        deleted_ids = []
        for doc in incorrect_docs:
            print(f"Deleting case: ID {doc.id}, Source: {doc.source}")
            
            # Remove the document ID from the world's cases list
            if world.cases and doc.id in world.cases:
                world.cases.remove(doc.id)
            
            # Add the document ID to the list of deleted IDs
            deleted_ids.append(doc.id)
            
            # Delete the document
            db.session.delete(doc)
        
        # Save changes
        db.session.add(world)
        db.session.commit()
        
        print(f"Successfully deleted {len(deleted_ids)} incorrectly imported cases")
        return deleted_ids

def main():
    """
    Main function to cleanup incorrectly imported cases.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Cleanup incorrectly imported NSPE cases')
    parser.add_argument('--world-id', type=int, default=1,
                        help='World ID to clean up cases for (default: 1)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Just print the cases without deleting them')
    args = parser.parse_args()
    
    print("===== Cleaning Up Incorrectly Imported NSPE Cases =====")
    deleted_ids = cleanup_header_links_cases(
        world_id=args.world_id,
        delete=not args.dry_run
    )
    
    if args.dry_run:
        print(f"\nFound {len(deleted_ids)} cases that would be deleted (dry run mode)")
    else:
        print(f"\nSuccessfully cleaned up {len(deleted_ids)} incorrectly imported cases")

if __name__ == "__main__":
    main()
