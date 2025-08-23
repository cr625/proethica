#!/usr/bin/env python3
"""
Debug script to check pending concepts for document 38 in world 1.
"""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, '/home/chris/onto/proethica')

# Set environment variable for database
os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

# Set up Flask app context
from app import create_app
app = create_app()

def check_pending_concepts():
    """Check what pending concepts exist for document 38."""
    with app.app_context():
        try:
            from app.services.temporary_concept_service import TemporaryConceptService
            from app.models.temporary_concept import TemporaryConcept
            from app.models.document import Document
            from app.models.world import World
            
            document_id = 38
            world_id = 1
            
            print(f"🔍 Checking pending concepts for document {document_id} in world {world_id}")
            print("=" * 60)
            
            # Check if document exists
            document = Document.query.get(document_id)
            if document:
                print(f"✓ Document found: {document.title}")
                print(f"  World ID: {document.world_id}")
                print(f"  Document belongs to world {world_id}: {document.world_id == world_id}")
            else:
                print(f"❌ Document {document_id} not found!")
                return
            
            # Check world
            world = World.query.get(world_id)
            if world:
                print(f"✓ World found: {world.name}")
            else:
                print(f"❌ World {world_id} not found!")
                return
                
            print()
            
            # Direct query to temporary_concepts table
            temp_concepts = TemporaryConcept.query.filter_by(
                document_id=document_id,
                world_id=world_id
            ).all()
            
            print(f"📊 Direct query results:")
            print(f"   Total temporary concepts: {len(temp_concepts)}")
            
            if temp_concepts:
                print(f"   Concepts by session:")
                session_groups = {}
                for concept in temp_concepts:
                    session_id = concept.session_id
                    if session_id not in session_groups:
                        session_groups[session_id] = []
                    session_groups[session_id].append(concept)
                
                for session_id, concepts in session_groups.items():
                    print(f"     Session {session_id}: {len(concepts)} concepts (status: {concepts[0].status if concepts else 'unknown'})")
                    
                    # Show first few concept labels
                    for i, concept in enumerate(concepts[:3]):
                        label = concept.concept_data.get('label', 'No label') if concept.concept_data else 'No data'
                        print(f"       {i+1}. {label}")
                    if len(concepts) > 3:
                        print(f"       ... and {len(concepts) - 3} more")
                    print()
            
            print()
            
            # Use the service methods
            print(f"🔧 Using TemporaryConceptService methods:")
            
            # Get document sessions
            sessions = TemporaryConceptService.get_document_sessions(
                document_id=document_id,
                world_id=world_id
            )
            
            print(f"   Document sessions found: {len(sessions)}")
            
            for session in sessions:
                session_concepts = TemporaryConceptService.get_session_concepts(session.session_id)
                concept_count = len(session_concepts) if session_concepts else 0
                print(f"     Session {session.session_id}: {concept_count} concepts")
                
                if session_concepts:
                    for concept in session_concepts[:2]:
                        label = concept.concept_data.get('label', 'No label') if concept.concept_data else 'No data'
                        status = concept.status
                        print(f"       - {label} (status: {status})")
            
            # Check latest session
            latest_session = TemporaryConceptService.get_latest_session_for_document(
                document_id=document_id,
                world_id=world_id
            )
            
            if latest_session:
                print(f"\n📅 Latest session: {latest_session}")
                latest_concepts = TemporaryConceptService.get_session_concepts(latest_session)
                print(f"   Latest session has {len(latest_concepts) if latest_concepts else 0} concepts")
            else:
                print(f"\n📅 No latest session found")
                
        except Exception as e:
            print(f"❌ Error checking pending concepts: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_pending_concepts()