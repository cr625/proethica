#!/usr/bin/env python3
"""Debug script to examine case 8 content extraction"""

import sys
import os
from pathlib import Path

# Add parent directory to path and change to proethica directory
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent)

from app import create_app, db
from app.models.document import Document
from app.services.document_annotation_service import DocumentAnnotationService

# Create Flask app context
app = create_app()

with app.app_context():
    # Get case 8 as a Document
    document = Document.query.get(8)
    
    if document:
        print(f"=== Document 8 Analysis ===")
        print(f"ID: {document.id}")
        print(f"Title: {document.title}")
        print(f"Content exists: {bool(document.content)}")
        print(f"Content length: {len(document.content) if document.content else 0} chars")
        if document.content:
            print(f"Content preview: {document.content[:200]}...")
        print()
        
        print(f"Doc metadata exists: {bool(document.doc_metadata)}")
        if document.doc_metadata:
            print(f"Metadata type: {type(document.doc_metadata)}")
            if isinstance(document.doc_metadata, dict):
                print(f"Metadata keys: {list(document.doc_metadata.keys())}")
                
                # Check sections
                sections = document.doc_metadata.get('sections', {})
                print(f"\nSections: {type(sections)} - {bool(sections)}")
                if sections:
                    for section_name, section_content in sections.items():
                        print(f"  {section_name}: {type(section_content)} - {len(str(section_content)) if section_content else 0} chars")
                        if section_content and len(str(section_content)) > 0:
                            print(f"    Preview: {str(section_content)[:100]}...")
                
                # Check other metadata fields
                for field in ['decision', 'outcome', 'ethical_analysis']:
                    value = document.doc_metadata.get(field)
                    if value:
                        print(f"\n{field}: {type(value)} - {len(str(value))} chars")
                        print(f"  Preview: {str(value)[:100]}...")
        
        print(f"\n=== Content Extraction Test ===")
        
        # Test our content extraction method
        extracted_content = DocumentAnnotationService.get_document_content_for_annotation(8, 'case')
        print(f"Extracted content exists: {bool(extracted_content)}")
        print(f"Extracted content length: {len(extracted_content) if extracted_content else 0} chars")
        if extracted_content:
            print(f"Extracted content preview:\n{extracted_content[:500]}...")
        else:
            print("❌ No content extracted!")
            
            # Try fallback method
            if hasattr(document, 'get_content'):
                fallback_content = document.get_content()
                print(f"Fallback get_content(): {bool(fallback_content)} - {len(str(fallback_content)) if fallback_content else 0} chars")
                if fallback_content:
                    print(f"Fallback preview: {str(fallback_content)[:200]}...")
            else:
                print("No get_content method available")
    else:
        print("❌ Document 8 not found!")

    # Also check if there are any other cases
    print(f"\n=== Other Documents ===")
    all_docs = Document.query.limit(10).all()
    for doc in all_docs:
        has_content = bool(doc.content)
        has_metadata = bool(doc.doc_metadata)
        print(f"Doc {doc.id}: '{doc.title[:50]}...' | content: {has_content} | metadata: {has_metadata}")
