#!/usr/bin/env python3
"""
Investigate where clean text content is stored for Case 252.
Compare different sources to find the best content for LLM prompts.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

from app import create_app
from app.models.document import Document
from app.models.document_section import DocumentSection
import json

def investigate_case_252_content():
    """Investigate all content sources for Case 252."""
    app = create_app('config')
    
    with app.app_context():
        print("🔍 INVESTIGATING CLEAN TEXT SOURCES FOR CASE 252")
        print("="*60)
        
        # Get Case 252 document
        document = Document.query.get(252)
        if not document:
            print("❌ Case 252 document not found!")
            return
            
        print(f"✅ Found document: {document.title}")
        print(f"   Document type: {document.document_type}")
        print(f"   Created: {document.created_at}")
        
        # 1. Check Document.content field
        print(f"\n📄 DOCUMENT.CONTENT FIELD:")
        if document.content:
            content_preview = document.content[:300].replace('\n', '\\n')
            print(f"   Length: {len(document.content)} characters")
            print(f"   Preview: {content_preview}...")
            print(f"   Contains HTML: {'<' in document.content and '>' in document.content}")
        else:
            print("   ❌ No content in Document.content field")
        
        # 2. Check Document.doc_metadata
        print(f"\n📋 DOCUMENT.DOC_METADATA:")
        if document.doc_metadata:
            print(f"   Metadata keys: {list(document.doc_metadata.keys())}")
            
            # Look for clean text in metadata
            if 'sections' in document.doc_metadata:
                print(f"   ✅ Found 'sections' in metadata")
                sections = document.doc_metadata['sections']
                print(f"   Section keys: {list(sections.keys())}")
                
                # Check a sample section (facts) for clean vs HTML content
                if 'facts' in sections:
                    facts_content = sections['facts']
                    if isinstance(facts_content, str):
                        preview = facts_content[:200].replace('\n', '\\n')
                        print(f"   Facts preview: {preview}...")
                        print(f"   Facts contains HTML: {'<' in facts_content and '>' in facts_content}")
                    elif isinstance(facts_content, dict):
                        print(f"   Facts is dict with keys: {list(facts_content.keys())}")
                        if 'content' in facts_content:
                            content = facts_content['content']
                            preview = content[:200].replace('\n', '\\n')
                            print(f"   Facts content preview: {preview}...")
                            print(f"   Facts content contains HTML: {'<' in content and '>' in content}")
            
            if 'document_structure' in document.doc_metadata:
                print(f"   ✅ Found 'document_structure' in metadata")
                doc_struct = document.doc_metadata['document_structure']
                if 'sections' in doc_struct:
                    print(f"   Document structure sections: {list(doc_struct['sections'].keys())}")
        else:
            print("   ❌ No metadata in Document.doc_metadata field")
        
        # 3. Check DocumentSection records (current source)
        print(f"\n📑 DOCUMENT_SECTIONS RECORDS:")
        doc_sections = DocumentSection.query.filter_by(document_id=252).all()
        print(f"   Found {len(doc_sections)} DocumentSection records")
        
        for section in doc_sections[:3]:  # Show first 3 sections
            content_preview = section.content[:200].replace('\n', '\\n')
            print(f"   Section '{section.section_type}' (ID: {section.id}):")
            print(f"     Length: {len(section.content)} characters")
            print(f"     Preview: {content_preview}...")
            print(f"     Contains HTML: {'<' in section.content and '>' in section.content}")
        
        # 4. Look for other potential clean text sources
        print(f"\n🔍 SEARCHING FOR CLEAN TEXT ALTERNATIVES:")
        
        # Check if there are any fields with clean text
        if document.doc_metadata and 'sections' in document.doc_metadata:
            sections = document.doc_metadata['sections']
            if 'facts' in sections:
                facts = sections['facts']
                if isinstance(facts, str):
                    # Compare HTML content vs metadata content
                    facts_section = DocumentSection.query.filter_by(
                        document_id=252, 
                        section_type='facts'
                    ).first()
                    
                    if facts_section:
                        print(f"\n📊 COMPARISON: Facts Section")
                        print(f"   DocumentSection.content length: {len(facts_section.content)}")
                        print(f"   Metadata sections['facts'] length: {len(facts)}")
                        
                        # Check if they're different (indicating clean vs HTML)
                        if len(facts) != len(facts_section.content):
                            print(f"   📍 DIFFERENT LENGTHS - potential clean vs HTML!")
                            
                            # Show samples
                            print(f"\n   DocumentSection sample:")
                            print(f"   {facts_section.content[:150]}...")
                            print(f"\n   Metadata sample:")
                            print(f"   {facts[:150]}...")
                            
                            # Determine which is cleaner
                            html_count_ds = facts_section.content.count('<') + facts_section.content.count('>')
                            html_count_meta = facts.count('<') + facts.count('>')
                            
                            print(f"\n   HTML tag count comparison:")
                            print(f"   DocumentSection: {html_count_ds} HTML tags")
                            print(f"   Metadata: {html_count_meta} HTML tags")
                            
                            if html_count_meta < html_count_ds:
                                print(f"   🎯 METADATA APPEARS CLEANER!")
                            elif html_count_ds < html_count_meta:
                                print(f"   🎯 DOCUMENTSECTION APPEARS CLEANER!")
                            else:
                                print(f"   ⚠️  Similar HTML content in both")

if __name__ == "__main__":
    investigate_case_252_content()
