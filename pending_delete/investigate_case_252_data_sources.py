#!/usr/bin/env python3
"""
Investigate what data sources are available for Case 252 to find the cleanest text.
"""

import os
import sys
import json

# Set environment
os.environ['FLASK_APP'] = 'run.py'
os.environ['FLASK_ENV'] = 'development'

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run import app
from app.models.document import Document
from app.models.document_section import DocumentSection

def investigate_case_252_sources():
    """Investigate all available data sources for Case 252."""
    
    print("🔍 INVESTIGATING CASE 252 DATA SOURCES")
    print("=" * 50)
    
    with app.app_context():
        
        # Get Case 252 document
        case_id = 252
        document = Document.query.get(case_id)
        
        if not document:
            print(f"❌ Case {case_id} not found")
            return
        
        print(f"📄 Document ID: {document.id}")
        print(f"📝 Title: {document.title}")
        print(f"🔗 Source: {document.source}")
        print(f"📁 Document Type: {document.document_type}")
        
        print(f"\n1. 📋 DOCUMENT CONTENT FIELD:")
        if document.content:
            content_sample = document.content[:200] + "..." if len(document.content) > 200 else document.content
            print(f"   Length: {len(document.content)} chars")
            print(f"   Sample: {content_sample}")
            # Check for HTML in content
            if '<' in document.content and '>' in document.content:
                print(f"   🟡 Contains HTML tags")
            else:
                print(f"   ✅ Appears to be clean text")
        else:
            print(f"   ❌ No content in document.content field")
        
        print(f"\n2. 📊 DOCUMENT METADATA:")
        if document.doc_metadata:
            print(f"   Metadata keys: {list(document.doc_metadata.keys())}")
            
            # Check for sections in metadata
            if 'sections' in document.doc_metadata:
                sections = document.doc_metadata['sections']
                print(f"   ✅ Found 'sections' in metadata with keys: {list(sections.keys())}")
                
                for section_name, section_content in sections.items():
                    if section_content:
                        sample = section_content[:100] + "..." if len(section_content) > 100 else section_content
                        print(f"   📋 {section_name}: {len(section_content)} chars")
                        print(f"      Sample: {sample}")
                        # Check for HTML
                        if '<' in section_content and '>' in section_content:
                            print(f"      🟡 Contains HTML")
                        else:
                            print(f"      ✅ Clean text")
                    else:
                        print(f"   ❌ {section_name}: Empty")
            else:
                print(f"   🟡 No 'sections' key in metadata")
            
            # Check other metadata
            if 'extraction_method' in document.doc_metadata:
                print(f"   📝 Extraction method: {document.doc_metadata['extraction_method']}")
                
        else:
            print(f"   ❌ No metadata available")
        
        print(f"\n3. 🗃️ DOCUMENT SECTION RECORDS:")
        doc_sections = DocumentSection.query.filter_by(document_id=case_id).all()
        
        if doc_sections:
            print(f"   ✅ Found {len(doc_sections)} DocumentSection records")
            
            for section in doc_sections:
                section_type = section.section_type or 'unknown'
                content_length = len(section.content) if section.content else 0
                
                print(f"   📋 Section '{section_type}' (ID: {section.id}): {content_length} chars")
                
                if section.content:
                    sample = section.content[:100] + "..." if len(section.content) > 100 else section.content
                    print(f"      Sample: {sample}")
                    # Check for HTML
                    if '<' in section.content and '>' in section.content:
                        print(f"      🟡 Contains HTML")
                    else:
                        print(f"      ✅ Clean text")
                else:
                    print(f"      ❌ Empty content")
                    
        else:
            print(f"   ❌ No DocumentSection records found")
        
        print(f"\n4. 🎯 RECOMMENDATIONS:")
        
        # Determine best data source
        best_source = None
        reason = ""
        
        if document.doc_metadata and 'sections' in document.doc_metadata:
            sections = document.doc_metadata['sections']
            html_count = sum(1 for content in sections.values() if content and '<' in content and '>' in content)
            
            if html_count == 0:
                best_source = "metadata['sections']"
                reason = "Clean text sections in metadata"
            elif html_count < len(sections):
                best_source = "metadata['sections'] (with cleaning)"
                reason = "Mostly clean sections in metadata, some HTML cleaning needed"
            else:
                best_source = "metadata['sections'] (needs HTML cleaning)"
                reason = "Sections in metadata but contain HTML"
        
        if doc_sections and not best_source:
            html_sections = sum(1 for s in doc_sections if s.content and '<' in s.content and '>' in s.content)
            
            if html_sections == 0:
                best_source = "DocumentSection records"
                reason = "Clean text in DocumentSection records"
            else:
                best_source = "DocumentSection records (with cleaning)"
                reason = "DocumentSection records but some contain HTML"
        
        if not best_source:
            best_source = "document.content (with cleaning)"
            reason = "Fallback to main content field"
        
        print(f"   🎯 Best source: {best_source}")
        print(f"   💡 Reason: {reason}")
        
        # Show how prediction service should be updated
        print(f"\n5. 🔧 PREDICTION SERVICE UPDATE STRATEGY:")
        
        if best_source.startswith("metadata['sections']"):
            print(f"   ✅ STRATEGY: Use document.doc_metadata['sections'] as primary source")
            print(f"   📝 Implementation: Modify get_document_sections() to prioritize metadata sections")
            print(f"   🧹 Benefit: Skip HTML cleaning step entirely if sections are clean")
            
        elif best_source.startswith("DocumentSection"):
            print(f"   ✅ STRATEGY: Current approach is good (DocumentSection records)")
            print(f"   📝 Implementation: Enhance HTML cleaning in get_document_sections()")
            
        else:
            print(f"   🟡 STRATEGY: Improve HTML cleaning for document.content")

if __name__ == "__main__":
    try:
        investigate_case_252_sources()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
