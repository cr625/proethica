#!/usr/bin/env python3
"""
Migration script to extract subject tags from existing case references.

This script finds all cases without subject_tags and extracts them from
the existing references section HTML using the same logic as NSPEExtractionStep.
"""

import os
import sys
from bs4 import BeautifulSoup

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

from app import create_app, db
from app.models.document import Document
from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep


def extract_subject_tags_from_references(references_html):
    """
    Extract subject tags from references section HTML using NSPEExtractionStep logic.
    
    Args:
        references_html: HTML content from the references section
        
    Returns:
        list: List of subject tag strings
    """
    if not references_html:
        return []
    
    # Create a BeautifulSoup object from the references HTML
    soup = BeautifulSoup(references_html, 'html.parser')
    
    # Use the existing NSPECaseExtractionStep logic
    extraction_step = NSPECaseExtractionStep()
    subject_tags = extraction_step.extract_subject_tags(soup)
    
    return subject_tags


def migrate_subject_tags(dry_run=True):
    """
    Migrate subject tags for all cases that don't have them.
    
    Args:
        dry_run: If True, only shows what would be updated without making changes
    """
    print("🔄 MIGRATING SUBJECT TAGS FROM EXISTING REFERENCES")
    print("=" * 60)
    
    # Find all cases without subject_tags
    cases_without_tags = []
    all_cases = Document.query.filter_by(document_type='case_study').all()
    
    for case in all_cases:
        has_tags = (case.doc_metadata and 
                   'subject_tags' in case.doc_metadata and 
                   case.doc_metadata['subject_tags'])
        if not has_tags:
            cases_without_tags.append(case)
    
    print(f"📊 Found {len(cases_without_tags)} cases without subject tags")
    print(f"🔍 Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()
    
    successful_extractions = 0
    failed_extractions = 0
    
    for i, case in enumerate(cases_without_tags, 1):
        case_number = case.doc_metadata.get('case_number', 'N/A') if case.doc_metadata else 'N/A'
        print(f"[{i}/{len(cases_without_tags)}] Case {case.id} ({case_number}): {case.title[:50]}...")
        
        # Check if references section exists
        if not (case.doc_metadata and 'sections' in case.doc_metadata and 
                'references' in case.doc_metadata['sections']):
            print("  ❌ No references section found")
            failed_extractions += 1
            continue
        
        references_html = case.doc_metadata['sections']['references']
        
        # Extract subject tags from references
        try:
            subject_tags = extract_subject_tags_from_references(references_html)
            
            if subject_tags:
                print(f"  ✅ Extracted {len(subject_tags)} tags: {', '.join(subject_tags[:3])}{'...' if len(subject_tags) > 3 else ''}")
                
                if not dry_run:
                    # Update the case metadata
                    if not case.doc_metadata:
                        case.doc_metadata = {}
                    case.doc_metadata['subject_tags'] = subject_tags
                    
                    # Mark the document as modified (for SQLAlchemy to detect changes in JSONB)
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(case, 'doc_metadata')
                
                successful_extractions += 1
            else:
                print("  ❌ No subject tags found in references")
                failed_extractions += 1
                
        except Exception as e:
            print(f"  ❌ Error extracting tags: {str(e)}")
            failed_extractions += 1
    
    print()
    print("📊 MIGRATION SUMMARY:")
    print(f"  Total cases processed: {len(cases_without_tags)}")
    print(f"  Successful extractions: {successful_extractions}")
    print(f"  Failed extractions: {failed_extractions}")
    print(f"  Success rate: {(successful_extractions/len(cases_without_tags)*100):.1f}%" if cases_without_tags else "N/A")
    
    if not dry_run and successful_extractions > 0:
        print()
        print("💾 Committing changes to database...")
        try:
            db.session.commit()
            print("✅ Successfully updated database")
        except Exception as e:
            print(f"❌ Error committing changes: {str(e)}")
            db.session.rollback()
    elif dry_run:
        print()
        print("🔍 DRY RUN - No changes made to database")
        print("   Run with dry_run=False to apply changes")


def show_preview_cases(limit=3):
    """Show a preview of what tags would be extracted from a few cases."""
    print("🔍 PREVIEW - SUBJECT TAG EXTRACTION")
    print("=" * 40)
    
    cases_without_tags = []
    all_cases = Document.query.filter_by(document_type='case_study').all()
    
    for case in all_cases:
        has_tags = (case.doc_metadata and 
                   'subject_tags' in case.doc_metadata and 
                   case.doc_metadata['subject_tags'])
        if not has_tags:
            cases_without_tags.append(case)
    
    for case in cases_without_tags[:limit]:
        case_number = case.doc_metadata.get('case_number', 'N/A') if case.doc_metadata else 'N/A'
        print(f"\nCase {case.id} ({case_number}): {case.title}")
        
        if (case.doc_metadata and 'sections' in case.doc_metadata and 
            'references' in case.doc_metadata['sections']):
            references_html = case.doc_metadata['sections']['references']
            subject_tags = extract_subject_tags_from_references(references_html)
            
            if subject_tags:
                print(f"  📌 Would extract {len(subject_tags)} tags:")
                for i, tag in enumerate(subject_tags, 1):
                    print(f"     {i}. {tag}")
            else:
                print("  ❌ No subject tags found")
        else:
            print("  ❌ No references section")


if __name__ == "__main__":
    app = create_app('config')
    
    with app.app_context():
        # First show a preview
        show_preview_cases(3)
        
        print("\n" + "="*60)
        
        # Ask for confirmation before proceeding
        response = input("\nProceed with migration? (y/N): ").strip().lower()
        
        if response == 'y':
            # Run dry run first
            print("\n" + "="*60)
            print("STEP 1: DRY RUN")
            migrate_subject_tags(dry_run=True)
            
            # Ask for final confirmation
            response2 = input("\nApply changes to database? (y/N): ").strip().lower()
            
            if response2 == 'y':
                print("\n" + "="*60)
                print("STEP 2: APPLYING CHANGES")
                migrate_subject_tags(dry_run=False)
            else:
                print("Migration cancelled.")
        else:
            print("Migration cancelled.")