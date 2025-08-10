#!/usr/bin/env python3
"""Analyze Case 7 content to understand how to create a proper scenario."""

from app import create_app
from app.models import db, Document
import json

app = create_app('config')

with app.app_context():
    # Get Case 7
    case = Document.query.get(7)
    if not case:
        print("❌ Case 7 not found")
        exit()
    
    print(f"📋 CASE 7: {case.title}")
    print("=" * 100)
    
    # Get the sections from metadata
    sections = case.doc_metadata.get('sections', {})
    
    print("\n📄 FACTS SECTION:")
    print("-" * 80)
    facts_content = sections.get('facts', {})
    if isinstance(facts_content, dict):
        facts_text = facts_content.get('text', facts_content.get('content', ''))
    else:
        facts_text = str(facts_content)
    print(facts_text[:1500] + "..." if len(facts_text) > 1500 else facts_text)
    
    print("\n\n❓ QUESTIONS SECTION:")
    print("-" * 80)
    questions_content = sections.get('question', {})
    if isinstance(questions_content, dict):
        questions_text = questions_content.get('text', questions_content.get('content', ''))
    else:
        questions_text = str(questions_content)
    print(questions_text)
    
    print("\n\n💭 DISCUSSION SECTION (first 1000 chars):")
    print("-" * 80)
    discussion_content = sections.get('discussion', {})
    if isinstance(discussion_content, dict):
        discussion_text = discussion_content.get('text', discussion_content.get('content', ''))
    else:
        discussion_text = str(discussion_content)
    print(discussion_text[:1000] + "..." if len(discussion_text) > 1000 else discussion_text)
    
    print("\n\n✅ CONCLUSION SECTION:")
    print("-" * 80)
    conclusion_content = sections.get('conclusion', {})
    if isinstance(conclusion_content, dict):
        conclusion_text = conclusion_content.get('text', conclusion_content.get('content', ''))
    else:
        conclusion_text = str(conclusion_content)
    print(conclusion_text)
    
    # Let's also check for case metadata
    print("\n\n📊 CASE METADATA:")
    print("-" * 80)
    print(f"Case Number: {case.doc_metadata.get('case_number', 'Unknown')}")
    print(f"Year: {case.doc_metadata.get('year', 'Unknown')}")
    print(f"Full Date: {case.doc_metadata.get('full_date', 'Unknown')}")
    
    # Check for document structure
    if 'document_structure' in case.doc_metadata:
        structure = case.doc_metadata['document_structure']
        print(f"\nDocument Structure Available: Yes")
        print(f"Sections in structure: {list(structure.get('sections', {}).keys())}")
    else:
        print(f"\nDocument Structure Available: No")