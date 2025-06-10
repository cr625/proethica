#!/usr/bin/env python3
"""
Test enhanced service with Document ID 19
"""

import os
import sys
import traceback

# Set up environment
os.environ['DATABASE_URL'] = 'postgresql://ai_ethical_dm_user:password@localhost:5433/ai_ethical_dm'
os.environ['FLASK_ENV'] = 'development'

# Add project to path
sys.path.insert(0, '/home/chris/proethica')

from app import create_app, db

def main():
    app = create_app()
    with app.app_context():
        
        try:
            # Test document retrieval
            from app.models.document import Document
            
            doc = Document.query.get(19)
            if doc:
                print(f"✅ Found document {doc.id}: {doc.title}")
                print(f"   Type: {doc.document_type}")
                print(f"   Has metadata: {doc.doc_metadata is not None}")
                
                if doc.doc_metadata:
                    print(f"   Metadata keys: {list(doc.doc_metadata.keys()) if isinstance(doc.doc_metadata, dict) else 'Not a dict'}")
                    
                    if isinstance(doc.doc_metadata, dict) and 'document_structure' in doc.doc_metadata:
                        ds = doc.doc_metadata['document_structure']
                        print(f"   Document structure keys: {list(ds.keys())}")
                        
                        if 'sections' in ds:
                            sections = ds['sections']
                            print(f"   Sections count: {len(sections)}")
                            for i, section in enumerate(sections[:3]):
                                print(f"     Section {i}: {section.get('type', 'Unknown')} - {len(section.get('content', ''))} chars")
                
                # Test enhanced service
                print("\n🧪 Testing Enhanced Service...")
                from app.services.enhanced_guideline_association_service import EnhancedGuidelineAssociationService
                
                service = EnhancedGuidelineAssociationService()
                
                # Test section extraction
                sections = service._extract_case_sections(doc)
                print(f"✅ Extracted {len(sections)} sections:")
                for section_type, content in sections.items():
                    print(f"   {section_type}: {len(content)} chars")
                
                # Test guideline concepts
                concepts = service._get_guideline_concepts()
                print(f"✅ Found {len(concepts)} guideline concepts")
                
                if sections and concepts:
                    print("\n🚀 Testing association generation...")
                    associations = service.generate_associations_for_case(19)
                    print(f"✅ Generated {len(associations)} associations")
                    
                    if associations:
                        top_assoc = associations[0]
                        print(f"   Top association: {top_assoc.section_type} -> concept {top_assoc.guideline_concept_id}")
                        print(f"   Confidence: {top_assoc.score.overall_confidence:.3f}")
                        print(f"   Reasoning: {top_assoc.score.reasoning[:100]}...")
                else:
                    print("❌ No sections or concepts - cannot test associations")
                
            else:
                print("❌ Document 19 not found")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    main()