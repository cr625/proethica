#!/usr/bin/env python3
"""
Reset Guidelines Script

This script removes all guideline documents, associated triples, and resets numbering to 1.
Useful for Phase 3 iterations when importing NSPE Code of Ethics.

Usage:
    python scripts/reset_guidelines.py [--world-id WORLD_ID] [--dry-run]
    
Arguments:
    --world-id: Optional world ID to reset guidelines for specific world only
    --dry-run: Show what would be deleted without actually deleting
"""

import os
import sys
import argparse
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.models import db
from app.models.guideline import Guideline
from app.models.guideline_semantic_triple import GuidelineSemanticTriple
from app.models.entity_triple import EntityTriple
from app.models.document import Document
from app.models.world import World
from app.config import Config

def create_app():
    """Create Flask app for database operations."""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

def reset_guidelines(world_id=None, dry_run=False):
    """
    Reset guidelines by removing documents, triples, and resetting numbering.
    
    Args:
        world_id (int, optional): World ID to reset guidelines for specific world only
        dry_run (bool): If True, show what would be deleted without actually deleting
    """
    
    print("🔄 ProEthica Guidelines Reset Script")
    print("=" * 50)
    
    if world_id:
        world = World.query.get(world_id)
        if not world:
            print(f"❌ World with ID {world_id} not found")
            return False
        print(f"📍 Targeting world: {world.name} (ID: {world_id})")
    else:
        print("🌍 Targeting all worlds")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No actual deletions will be performed")
    
    print()
    
    # Query for guidelines to be removed
    if world_id:
        guidelines_query = Guideline.query.filter_by(world_id=world_id)
    else:
        guidelines_query = Guideline.query
    
    guidelines = guidelines_query.all()
    guideline_count = len(guidelines)
    
    print(f"📋 Found {guideline_count} guidelines to remove")
    
    if guideline_count == 0:
        print("✅ No guidelines found to reset")
        return True
    
    # Show what will be deleted
    print("\nGuidelines to be removed:")
    for guideline in guidelines:
        print(f"  - {guideline.title} (ID: {guideline.id})")
    
    # Count associated triples
    total_semantic_triples = 0
    total_entity_triples = 0
    
    for guideline in guidelines:
        # Count semantic triples
        semantic_triples = GuidelineSemanticTriple.query.filter_by(guideline_id=guideline.id).count()
        total_semantic_triples += semantic_triples
        
        # Count entity triples
        entity_triples = EntityTriple.query.filter_by(guideline_id=guideline.id).count()
        total_entity_triples += entity_triples
    
    print(f"\n🔗 Associated triples to be removed:")
    print(f"  - Semantic triples: {total_semantic_triples}")
    print(f"  - Entity triples: {total_entity_triples}")
    
    # Count documents (guidelines stored as documents)
    if world_id:
        documents_query = Document.query.filter_by(world_id=world_id, document_type='guideline')
    else:
        documents_query = Document.query.filter_by(document_type='guideline')
    
    documents = documents_query.all()
    document_count = len(documents)
    
    print(f"📄 Document records to be removed: {document_count}")
    
    if not dry_run:
        # Confirm deletion
        print(f"\n⚠️  WARNING: This will permanently delete:")
        print(f"   - {guideline_count} guideline records")
        print(f"   - {total_semantic_triples} semantic triples")
        print(f"   - {total_entity_triples} entity triples")
        print(f"   - {document_count} document records")
        
        confirm = input("\nAre you sure you want to continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Operation cancelled")
            return False
    
    if not dry_run:
        print(f"\n🗑️  Performing deletions...")
        
        try:
            # Delete semantic triples first (foreign key constraint)
            for guideline in guidelines:
                semantic_triples = GuidelineSemanticTriple.query.filter_by(guideline_id=guideline.id).all()
                for triple in semantic_triples:
                    db.session.delete(triple)
            
            # Delete entity triples
            for guideline in guidelines:
                entity_triples = EntityTriple.query.filter_by(guideline_id=guideline.id).all()
                for triple in entity_triples:
                    db.session.delete(triple)
            
            # Delete guideline records
            for guideline in guidelines:
                db.session.delete(guideline)
            
            # Delete document records
            for document in documents:
                db.session.delete(document)
            
            # Commit all deletions
            db.session.commit()
            
            print("✅ Successfully deleted all guideline data")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during deletion: {str(e)}")
            return False
    
    print(f"\n🔄 Guidelines reset completed at {datetime.now()}")
    print("📝 Next guideline will be assigned ID 1")
    
    if world_id:
        print(f"🌍 Ready for Phase 3: Import NSPE Code of Ethics to world {world_id}")
    else:
        print("🌍 Ready for Phase 3: Import NSPE Code of Ethics")
    
    return True

def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description='Reset ProEthica guidelines')
    parser.add_argument('--world-id', type=int, help='World ID to reset guidelines for specific world only')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    
    args = parser.parse_args()
    
    app = create_app()
    
    with app.app_context():
        success = reset_guidelines(
            world_id=args.world_id,
            dry_run=args.dry_run
        )
        
        if success:
            print("\n🎉 Reset operation completed successfully!")
        else:
            print("\n❌ Reset operation failed!")
            sys.exit(1)

if __name__ == '__main__':
    main()