#!/usr/bin/env python3
"""
Cleanup script to remove orphaned triples for guideline 8.
This script identifies and removes triples that are associated with guideline 8 
but don't belong to world 1.
"""

import os
import sys

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.models.world import World
from app.models.document import Document
from app.models.guideline import Guideline

def analyze_guideline_8_triples():
    """Analyze triples associated with guideline 8 to identify orphans."""
    
    print("🔍 Analyzing triples for guideline/document 8...")
    
    # Get the document and its associated guideline
    document = Document.query.get(8)
    if not document:
        print("❌ Document 8 not found")
        return None, None, None
    
    print(f"📄 Document 8: {document.title}")
    print(f"🌍 Document world_id: {document.world_id}")
    
    # Get the actual guideline ID from metadata
    actual_guideline_id = None
    if document.doc_metadata and 'guideline_id' in document.doc_metadata:
        actual_guideline_id = document.doc_metadata['guideline_id']
        print(f"🔗 Associated guideline_id: {actual_guideline_id}")
    
    # Query triples using the same logic as the route
    if actual_guideline_id:
        all_triples = EntityTriple.query.filter_by(guideline_id=actual_guideline_id).all()
    else:
        all_triples = EntityTriple.query.filter_by(
            guideline_id=document.id,
            world_id=document.world_id
        ).all()
    
    print(f"📊 Total triples found: {len(all_triples)}")
    
    # Categorize triples by world
    correct_world_triples = []
    orphaned_triples = []
    
    target_world_id = 1  # World 1 as specified
    
    for triple in all_triples:
        if triple.world_id == target_world_id:
            correct_world_triples.append(triple)
        else:
            orphaned_triples.append(triple)
    
    print(f"✅ Triples belonging to world {target_world_id}: {len(correct_world_triples)}")
    print(f"🗑️  Orphaned triples (wrong world): {len(orphaned_triples)}")
    
    if orphaned_triples:
        print("\n🔍 Orphaned triples details:")
        world_counts = {}
        for triple in orphaned_triples:
            world_id = triple.world_id
            world_counts[world_id] = world_counts.get(world_id, 0) + 1
        
        for world_id, count in world_counts.items():
            world = World.query.get(world_id)
            world_name = world.name if world else "Unknown"
            print(f"   World {world_id} ({world_name}): {count} triples")
    
    return all_triples, correct_world_triples, orphaned_triples

def cleanup_orphaned_triples(orphaned_triples, dry_run=True):
    """Remove orphaned triples."""
    
    if not orphaned_triples:
        print("✅ No orphaned triples to clean up!")
        return
    
    print(f"\n{'🔄 DRY RUN: Would delete' if dry_run else '🗑️  DELETING'} {len(orphaned_triples)} orphaned triples:")
    
    for triple in orphaned_triples:
        print(f"   ID: {triple.id}, World: {triple.world_id}, Subject: {triple.subject_label}")
        
        if not dry_run:
            db.session.delete(triple)
    
    if not dry_run:
        try:
            db.session.commit()
            print(f"✅ Successfully deleted {len(orphaned_triples)} orphaned triples")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error deleting orphaned triples: {e}")
    else:
        print("\n💡 Run with --execute to actually delete these triples")

def main():
    """Main function."""
    import argparse
    from dotenv import load_dotenv
    
    parser = argparse.ArgumentParser(description='Clean up orphaned triples for guideline 8')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually delete orphaned triples (default is dry run)')
    args = parser.parse_args()
    
    # Load environment variables from .env file if it exists
    if os.path.exists('.env'):
        load_dotenv()
    
    # Set environment for development
    os.environ.setdefault('ENVIRONMENT', 'development')
    
    # Set database URL if not already set
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url
    
    print(f"Using database: {db_url}")
    
    # Create Flask app context
    app = create_app('config')
    
    with app.app_context():
        print("🧹 Orphaned Triples Cleanup for Guideline 8")
        print("=" * 50)
        
        # Analyze current state
        all_triples, correct_triples, orphaned_triples = analyze_guideline_8_triples()
        
        if all_triples is None:
            return
        
        # Clean up orphaned triples
        cleanup_orphaned_triples(orphaned_triples, dry_run=not args.execute)
        
        print("\n" + "=" * 50)
        print("🏁 Cleanup complete!")

if __name__ == '__main__':
    main()