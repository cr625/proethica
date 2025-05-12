#!/usr/bin/env python3
"""
Cleanup RDF Type Triples
------------------------
This script removes generic RDF type triples from the database that 
don't provide meaningful semantic information to the user.

For example, triples like:
- "22-rdf-syntax-ns#type: intermediate#Role"
- "22-rdf-syntax-ns#type: engineering-ethics#Resource"

These generic type triples are redundant and clutter the UI when more specific
predicates like 'hasRole' or 'involvesResource' are already present.

Usage:
    python cleanup_rdf_type_triples.py [--dry-run]
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import required modules
try:
    from app import create_app, db
    from app.models.entity_triple import EntityTriple
except ImportError:
    print("Error: Cannot import required modules. Make sure you're running this script from the project root.")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cleanup_rdf_type_triples")

def cleanup_rdf_type_triples(dry_run=False, app=None):
    """
    Remove generic RDF type triples from the database.
    
    Args:
        dry_run: If True, only show what would be deleted without actually deleting
        app: Flask application instance
        
    Returns:
        int: Number of triples removed
    """
    try:
        # Create app context if app is provided
        ctx = app.app_context() if app else None
        if ctx:
            ctx.push()
        # Find all triples with rdf-syntax-ns#type predicate
        rdf_type_pattern = '%rdf-syntax-ns#type%'
        generic_patterns = [
            '%intermediate#Role%',
            '%intermediate#Resource%',
            '%intermediate#Condition%',
            '%intermediate#Event%',
            '%intermediate#Action%',
            '%intermediate#Capability%'
        ]
        
        # Construct the query
        # We want to find triples where:
        # 1. The predicate contains "rdf-syntax-ns#type"
        # 2. AND the object_uri matches one of our generic patterns
        query = EntityTriple.query.filter(
            EntityTriple.predicate.like(rdf_type_pattern)
        )
        
        # Add OR conditions for each generic pattern
        from sqlalchemy import or_
        object_conditions = []
        for pattern in generic_patterns:
            object_conditions.append(EntityTriple.object_uri.like(pattern))
        
        query = query.filter(or_(*object_conditions))
        
        # Get the results
        triples_to_remove = query.all()
        count = len(triples_to_remove)
        
        logger.info(f"Found {count} generic RDF type triples to remove")
        
        if count > 0:
            # Print the triples that will be removed
            for i, triple in enumerate(triples_to_remove[:10]):  # Show first 10
                logger.info(f"  {i+1}. Document {triple.document_id}: {triple.predicate} -> {triple.object_uri}")
            
            if count > 10:
                logger.info(f"  ... and {count - 10} more")
            
            # Remove the triples if not a dry run
            if not dry_run:
                # Delete the triples
                for triple in triples_to_remove:
                    db.session.delete(triple)
                
                # Commit the changes
                db.session.commit()
                logger.info(f"Successfully removed {count} generic RDF type triples")
            else:
                logger.info("DRY RUN: No triples were actually removed")
        
        return count
    
    except Exception as e:
        logger.error(f"Error cleaning up RDF type triples: {str(e)}")
        if not dry_run:
            # Rollback any changes
            db.session.rollback()
        return 0
    finally:
        # Pop context if we pushed one
        if ctx:
            ctx.pop()

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Clean up generic RDF type triples')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Show what would be deleted without actually deleting')
    args = parser.parse_args()
    
    logger.info("Starting RDF type triple cleanup")
    
    if args.dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")
    
    # Create Flask app
    try:
        app = create_app()
        logger.info("Created Flask application")
    except Exception as e:
        logger.error(f"Error creating Flask application: {str(e)}")
        return 1
    
    # Run the cleanup with the app
    count = cleanup_rdf_type_triples(dry_run=args.dry_run, app=app)
    
    if count > 0:
        if args.dry_run:
            logger.info(f"DRY RUN: Would have removed {count} generic RDF type triples")
        else:
            logger.info(f"Successfully removed {count} generic RDF type triples")
    else:
        logger.info("No generic RDF type triples found to remove")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
