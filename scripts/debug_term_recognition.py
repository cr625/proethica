#!/usr/bin/env python3
"""
Debug Term Recognition System

This script investigates why we're only finding limited ontology terms
in the document sections. It will check:
1. What ontology terms are actually loaded
2. What the case text actually looks like
3. Why common terms like "engineer" aren't being matched
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

from app import create_app, db
from app.models.document import Document
from app.models.section_term_link import SectionTermLink
from app.services.ontology_term_recognition_service import OntologyTermRecognitionService
import json
import re

def main():
    """Debug the term recognition system."""
    
    app = create_app('config')
    
    with app.app_context():
        print("=== ONTOLOGY TERM RECOGNITION DEBUG ===")
        print()
        
        # Initialize the service
        print("1. Initializing term recognition service...")
        recognition_service = OntologyTermRecognitionService()
        
        if not recognition_service.ontology_terms:
            print("❌ ERROR: No ontology terms loaded!")
            return
        
        print(f"✅ Loaded {len(recognition_service.ontology_terms)} ontology terms")
        print()
        
        # Show sample ontology terms
        print("2. Sample ontology terms loaded:")
        sample_terms = list(recognition_service.ontology_terms.keys())[:20]
        for i, term in enumerate(sample_terms, 1):
            term_info = recognition_service.ontology_terms[term]
            print(f"   {i:2d}. '{term}' -> {term_info['label']} ({term_info.get('entity_type', 'unknown')})")
        print(f"   ... and {len(recognition_service.ontology_terms) - 20} more")
        print()
        
        # Check for common terms we'd expect to find
        print("3. Checking for common expected terms:")
        expected_terms = [
            'engineer', 'engineers', 'engineering',
            'professional', 'profession', 
            'ethics', 'ethical',
            'safety', 'safe',
            'public', 'welfare',
            'conflict', 'interest',
            'responsibility', 'responsible',
            'client', 'employer'
        ]
        
        found_terms = []
        missing_terms = []
        
        for term in expected_terms:
            if term in recognition_service.ontology_terms:
                found_terms.append(term)
                print(f"   ✅ Found: '{term}'")
            else:
                missing_terms.append(term)
                print(f"   ❌ Missing: '{term}'")
        
        print(f"\n   Summary: {len(found_terms)}/{len(expected_terms)} expected terms found")
        print()
        
        # Get document 19 for detailed analysis
        print("4. Analyzing document 19 (test case):")
        document = Document.query.get(19)
        if not document:
            print("❌ ERROR: Document 19 not found!")
            return
        
        print(f"   Title: {document.title}")
        
        # Get document metadata and sections
        metadata = document.doc_metadata or {}
        
        # Extract sections using the same logic as the service
        sections_data = recognition_service._extract_sections_data(metadata)
        
        if not sections_data:
            print("❌ ERROR: No section data found!")
            return
        
        print(f"   Found {len(sections_data)} sections: {list(sections_data.keys())}")
        print()
        
        # Analyze each section
        print("5. Section analysis:")
        for section_id, section_content in sections_data.items():
            print(f"\n   Section: {section_id}")
            print(f"   Length: {len(section_content)} characters")
            
            # Clean the content
            clean_content = recognition_service._clean_section_content(section_content)
            print(f"   Clean length: {len(clean_content)} characters")
            
            # Show first 200 characters
            preview = clean_content[:200].replace('\n', ' ').replace('  ', ' ')
            print(f"   Preview: {preview}...")
            
            # Test term recognition on this section
            print("   Testing term recognition...")
            matches = recognition_service.recognize_terms_in_text(clean_content)
            print(f"   Found {len(matches)} matches: {[m['term_text'] for m in matches]}")
            
            # Manual search for expected terms
            print("   Manual search for expected terms:")
            text_lower = clean_content.lower()
            manual_matches = []
            for term in expected_terms:
                if term in text_lower:
                    manual_matches.append(term)
                    # Find all occurrences
                    start = 0
                    positions = []
                    while True:
                        pos = text_lower.find(term, start)
                        if pos == -1:
                            break
                        positions.append(pos)
                        start = pos + 1
                    print(f"      ✅ '{term}' found at positions: {positions}")
            
            if not manual_matches:
                print("      ❌ No expected terms found manually")
            
            print()
        
        # Check existing term links in database
        print("6. Checking existing term links in database:")
        existing_links = SectionTermLink.get_document_term_links(19)
        
        if existing_links:
            total_links = sum(len(links) for links in existing_links.values())
            print(f"   Found {total_links} existing term links across {len(existing_links)} sections")
            
            for section_id, links in existing_links.items():
                print(f"   {section_id}: {len(links)} links")
                for link in links[:3]:  # Show first 3
                    print(f"      - '{link['term_text']}' ({link['ontology_label']})")
                if len(links) > 3:
                    print(f"      ... and {len(links) - 3} more")
        else:
            print("   ❌ No existing term links found")
        
        print()
        
        # Test regex patterns
        print("7. Testing regex patterns:")
        if recognition_service.term_patterns:
            print(f"   Loaded {len(recognition_service.term_patterns)} patterns")
            
            # Test a few sample patterns
            sample_text = "The engineer must consider professional ethics and public safety."
            print(f"   Test text: '{sample_text}'")
            
            # Test just the expected terms we found
            expected_found_terms = ['engineer', 'professional', 'ethics', 'public', 'safety']
            matches_found = 0
            
            for term in expected_found_terms:
                if term in recognition_service.term_patterns:
                    pattern = recognition_service.term_patterns[term]
                    match = pattern.search(sample_text)
                    if match:
                        print(f"      ✅ Pattern '{term}' matched: '{match.group()}'")
                        matches_found += 1
                    else:
                        print(f"      ❌ Pattern '{term}' did not match")
                else:
                    print(f"      ❌ No pattern for term '{term}'")
            
            if matches_found == 0:
                print("      ❌ No expected term patterns matched the test text")
            
            # Also test using the actual recognition method
            print("   Testing with actual recognition method:")
            test_matches = recognition_service.recognize_terms_in_text(sample_text)
            print(f"      Found {len(test_matches)} matches: {[m['term_text'] for m in test_matches]}")
        else:
            print("   ❌ No regex patterns loaded")
        
        print("\n=== DEBUG COMPLETE ===")

if __name__ == '__main__':
    main()