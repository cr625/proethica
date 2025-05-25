#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def quick_check():
    from app import create_app
    
    app = create_app('config')
    with app.app_context():
        from app.models.document import Document
        from app.models.document_section import DocumentSection
        
        # Get Case 252
        doc = Document.query.get(252)
        print(f"Document 252: {doc.title}")
        
        # Check DocumentSection records
        sections = DocumentSection.query.filter_by(document_id=252).all()
        print(f"DocumentSection records: {len(sections)}")
        for s in sections[:3]:  # Show first 3
            print(f"  {s.section_type}: {len(s.content or '')} chars")
        
        # Check metadata
        if doc.doc_metadata:
            print(f"Metadata keys: {list(doc.doc_metadata.keys())}")
            if 'sections' in doc.doc_metadata:
                meta_sections = doc.doc_metadata['sections']
                print(f"Metadata sections: {list(meta_sections.keys())}")
                if 'facts' in meta_sections:
                    facts_data = meta_sections['facts']
                    print(f"Metadata facts type: {type(facts_data)}")
                    if isinstance(facts_data, str):
                        print(f"Metadata facts (string): {len(facts_data)} chars")
                    elif isinstance(facts_data, dict):
                        print(f"Metadata facts (dict): {list(facts_data.keys())}")

if __name__ == "__main__":
    quick_check()
