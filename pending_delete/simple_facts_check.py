#!/usr/bin/env python3
"""
Simple check for Facts section in Case 252.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app

def simple_facts_check():
    """Simple check for Facts section."""
    
    print("=== Simple Facts Check ===")
    
    # Create app context
    app = create_app('config')
    
    with app.app_context():
        try:
            # Check Case 252 sections directly
            from app.models.document_section import DocumentSection
            from app.services.experiment.prediction_service import PredictionService
            
            print("1. Direct DocumentSection query...")
            sections = DocumentSection.query.filter_by(document_id=252).all()
            print(f"   Found {len(sections)} sections:")
            
            facts_section = None
            for section in sections:
                print(f"   - {section.section_type}: {len(section.content or '')} chars")
                if section.section_type == 'facts':
                    facts_section = section
                    print(f"     ✓ FACTS FOUND: {section.content[:100]}...")
            
            if not facts_section:
                print("   ❌ No facts section found")
                return
            
            print("\n2. PredictionService.get_document_sections...")
            prediction_service = PredictionService()
            sections_dict = prediction_service.get_document_sections(252, leave_out_conclusion=True)
            
            print(f"   Retrieved sections: {list(sections_dict.keys())}")
            
            if 'facts' in sections_dict:
                print(f"   ✓ Facts in sections_dict: {len(sections_dict['facts'])} chars")
                print(f"   Preview: {sections_dict['facts'][:200]}...")
            else:
                print("   ❌ Facts NOT in sections_dict")
                
                # Debug: check document metadata
                from app.models.document import Document
                doc = Document.query.get(252)
                if doc and doc.doc_metadata:
                    print(f"   Document metadata keys: {list(doc.doc_metadata.keys())}")
                    if 'sections' in doc.doc_metadata:
                        print(f"   Metadata sections: {list(doc.doc_metadata['sections'].keys())}")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    simple_facts_check()
