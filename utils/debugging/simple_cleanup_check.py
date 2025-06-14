#!/usr/bin/env python3
"""
Simple script to check triple associations for guideline 8.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment for development
os.environ.setdefault('ENVIRONMENT', 'development')

# Set database URL if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from app.models.entity_triple import EntityTriple
from app.models.world import World
from app.models.document import Document

# Configure logging to reduce noise
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Create app instance with proper configuration
app = create_app()
app.config['DEBUG'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Use the same app context as debug app
with app.app_context():
    print("🔍 Checking Triple Associations for Guideline 8")
    print("=" * 50)
    
    # Get the document
    document = Document.query.get(8)
    if not document:
        print("❌ Document 8 not found")
        exit(1)
    
    print(f"📄 Document 8: {document.title[:50]}...")
    print(f"🌍 Document world_id: {document.world_id}")
    
    # Get the actual guideline ID from metadata
    actual_guideline_id = None
    if document.doc_metadata and 'guideline_id' in document.doc_metadata:
        actual_guideline_id = document.doc_metadata['guideline_id']
        print(f"🔗 Associated guideline_id: {actual_guideline_id}")
    
    # Query triples using the CURRENT logic (reproducing the bug)
    print("\n📊 Current query results (reproducing the bug):")
    if actual_guideline_id:
        current_query_triples = EntityTriple.query.filter_by(guideline_id=actual_guideline_id).all()
        print(f"   Query: EntityTriple.query.filter_by(guideline_id={actual_guideline_id}).all()")
    else:
        current_query_triples = EntityTriple.query.filter_by(
            guideline_id=document.id,
            world_id=document.world_id
        ).all()
        print(f"   Query: EntityTriple.query.filter_by(guideline_id={document.id}, world_id={document.world_id}).all()")
    
    print(f"   Total triples found: {len(current_query_triples)}")
    
    # Analyze by world
    world_breakdown = {}
    for triple in current_query_triples:
        world_id = triple.world_id
        if world_id not in world_breakdown:
            world = World.query.get(world_id)
            world_breakdown[world_id] = {
                'name': world.name if world else 'Unknown',
                'count': 0,
                'triples': []
            }
        world_breakdown[world_id]['count'] += 1
        world_breakdown[world_id]['triples'].append(triple)
    
    print("\n🌍 Breakdown by World:")
    for world_id, info in world_breakdown.items():
        print(f"   World {world_id} ({info['name']}): {info['count']} triples")
        if world_id != 1:  # Show details for non-target worlds
            print(f"      Sample subjects: {[t.subject_label[:30] for t in info['triples'][:3]]}")
    
    # Query with CORRECT logic (what it should be)
    print("\n✅ Correct query results (what it should be):")
    if actual_guideline_id:
        correct_query_triples = EntityTriple.query.filter_by(
            guideline_id=actual_guideline_id,
            world_id=document.world_id
        ).all()
        print(f"   Query: EntityTriple.query.filter_by(guideline_id={actual_guideline_id}, world_id={document.world_id}).all()")
    else:
        correct_query_triples = EntityTriple.query.filter_by(
            guideline_id=document.id,
            world_id=document.world_id
        ).all()
        print(f"   Query: EntityTriple.query.filter_by(guideline_id={document.id}, world_id={document.world_id}).all()")
    
    print(f"   Total triples found: {len(correct_query_triples)}")
    
    # Calculate orphaned triples
    orphaned_triples = [t for t in current_query_triples if t.world_id != document.world_id]
    print(f"\n🗑️  Orphaned triples to delete: {len(orphaned_triples)}")
    
    if orphaned_triples:
        print("   Sample orphaned triples:")
        for triple in orphaned_triples[:5]:
            print(f"      ID {triple.id}: {triple.subject_label} (world {triple.world_id})")
    
    print("\n💡 To fix this:")
    print("   1. Delete the orphaned triples")
    print("   2. Fix the query logic in app/routes/worlds.py")
    print("   3. Add proper world filtering")