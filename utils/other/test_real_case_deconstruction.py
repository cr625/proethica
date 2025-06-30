#!/usr/bin/env python3
"""
Test case deconstruction with a real case from the database.
"""

import os
import sys

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.document import Document
from app.models.deconstructed_case import DeconstructedCase
from app.services.case_deconstruction.engineering_ethics_adapter import EngineeringEthicsAdapter

def test_with_real_case():
    """Test deconstruction with a real case and save to database."""
    app = create_app('config')
    
    with app.app_context():
        try:
            # Find a real case from the database (preferably from Engineering Ethics world)
            case = Document.query.filter(
                Document.document_type == 'case_study',
                Document.world_id == 1  # Engineering Ethics world
            ).first()
            
            if not case:
                print("❌ No case studies found in Engineering Ethics world (ID=1)")
                print("Looking for any case study...")
                case = Document.query.filter(Document.document_type == 'case_study').first()
                
            if not case:
                print("❌ No case studies found in database")
                return
                
            print(f"🎯 Testing with real case: {case.title} (ID: {case.id})")
            print(f"   World: {case.world.name if case.world else 'Unknown'}")
            print(f"   Source: {case.source}")
            print("=" * 60)
            
            # Initialize adapter
            adapter = EngineeringEthicsAdapter()
            
            # Convert case to format expected by adapter
            case_data = {
                'id': case.id,
                'title': case.title,
                'content': case.content,
                'doc_metadata': case.doc_metadata or {}
            }
            
            # Run deconstruction
            print("🔄 Running case deconstruction...")
            deconstructed = adapter.deconstruct_case(case_data)
            
            # Save to database
            print("💾 Saving results to database...")
            db_record = DeconstructedCase.from_data_model(deconstructed, case.id)
            db.session.add(db_record)
            db.session.commit()
            
            print(f"✅ Deconstruction saved with ID: {db_record.id}")
            print(f"   Stakeholders found: {len(deconstructed.analysis.stakeholders)}")
            print(f"   Decision points: {len(deconstructed.analysis.decision_points)}")
            print(f"   Confidence scores: S={deconstructed.analysis.stakeholder_confidence:.2f}, "
                  f"D={deconstructed.analysis.decision_points_confidence:.2f}, "
                  f"R={deconstructed.analysis.reasoning_confidence:.2f}")
            
            print(f"\n🌐 You can now view this in the UI!")
            print(f"   Case details: http://localhost:3333/cases/{case.id}")
            print(f"   Database record ID: {db_record.id}")
            
            # Show some sample results
            print(f"\n📊 Sample Results:")
            for i, stakeholder in enumerate(deconstructed.analysis.stakeholders[:3]):
                print(f"   👤 {stakeholder.name} ({stakeholder.role.value})")
            
            for i, decision in enumerate(deconstructed.analysis.decision_points[:2]):
                print(f"   ⚖️  {decision.title}")
                
            return db_record.id
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    test_with_real_case()