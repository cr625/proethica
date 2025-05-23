#!/usr/bin/env python3
"""
Compare HTML vs Clean content for Case 252 to demonstrate the improvement.
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

def compare_content_quality():
    """Compare HTML vs Clean content quality for Case 252."""
    app = create_app('config')
    
    with app.app_context():
        print("📊 COMPARING HTML vs CLEAN CONTENT FOR CASE 252")
        print("="*60)
        
        # Get document
        document = Document.query.get(252)
        
        # Get clean text from metadata
        clean_sections = document.doc_metadata.get('sections', {})
        
        # Get HTML content from DocumentSection records
        html_sections = {}
        doc_sections = DocumentSection.query.filter_by(document_id=252).all()
        for section in doc_sections:
            section_type = section.section_type.lower()
            html_sections[section_type] = section.content
        
        # Compare key sections
        sections_to_compare = ['facts', 'references', 'discussion']
        
        for section_name in sections_to_compare:
            print(f"\n🔍 COMPARING '{section_name.upper()}' SECTION:")
            print("="*40)
            
            # Clean version
            clean_content = clean_sections.get(section_name, '')
            if clean_content:
                print(f"✅ CLEAN VERSION ({len(clean_content)} chars):")
                print(f"   Sample: {clean_content[:200]}...")
                html_tags = clean_content.count('<') + clean_content.count('>')
                print(f"   HTML tags: {html_tags}")
            else:
                print(f"❌ No clean version found")
            
            # HTML version  
            html_content = html_sections.get(section_name, '')
            if html_content:
                print(f"\n📝 HTML VERSION ({len(html_content)} chars):")
                print(f"   Sample: {html_content[:200]}...")
                html_tags = html_content.count('<') + html_content.count('>')
                print(f"   HTML tags: {html_tags}")
            else:
                print(f"❌ No HTML version found")
            
            # Quality assessment
            if clean_content and html_content:
                clean_tags = clean_content.count('<') + clean_content.count('>')
                html_tags = html_content.count('<') + html_content.count('>')
                
                print(f"\n📈 QUALITY ASSESSMENT:")
                if clean_tags < html_tags:
                    print(f"   🎯 CLEAN VERSION IS BETTER ({clean_tags} vs {html_tags} HTML tags)")
                elif html_tags < clean_tags:
                    print(f"   🎯 HTML VERSION IS BETTER ({html_tags} vs {clean_tags} HTML tags)")
                else:
                    print(f"   ⚖️  SIMILAR QUALITY ({clean_tags} vs {html_tags} HTML tags)")
        
        # Show the impact on LLM prompts
        print(f"\n🚀 IMPACT ON LLM PROMPTS:")
        print("="*30)
        
        # Facts section comparison (most important)
        clean_facts = clean_sections.get('facts', '')
        html_facts = html_sections.get('facts', '')
        
        if clean_facts and html_facts:
            print(f"📝 FACTS SECTION - LLM PROMPT IMPACT:")
            print(f"   Clean version: {len(clean_facts)} chars, ready for LLM")
            print(f"   HTML version: {len(html_facts)} chars, needs cleaning")
            
            # Show how they'd appear in prompt
            print(f"\n   🎯 CLEAN PROMPT PREVIEW:")
            print(f"   # FACTS:\\n{clean_facts[:300]}...")
            
            print(f"\n   ❌ HTML PROMPT PREVIEW:")
            print(f"   # FACTS:\\n{html_facts[:300]}...")

if __name__ == "__main__":
    compare_content_quality()
