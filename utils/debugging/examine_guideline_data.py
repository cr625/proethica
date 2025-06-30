#!/usr/bin/env python3
"""
Script to examine existing guideline associations and case outcomes for Phase 1 analysis.
"""

import os
import sys
import json
import psycopg2
from datetime import datetime

# Database connection parameters
DB_NAME = "ai_ethical_dm"
DB_USER = "postgres"
DB_PASSWORD = "PASS"
DB_HOST = "localhost"
DB_PORT = "5433"

def get_connection():
    """Get a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return None

def analyze_case_outcomes():
    """Analyze case outcomes and structures."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("="*80)
    print("CASE OUTCOMES ANALYSIS")
    print("="*80)
    
    # 1. Count total cases
    cursor.execute("""
        SELECT COUNT(*) 
        FROM documents 
        WHERE document_type IN ('case_study', 'case')
    """)
    total_cases = cursor.fetchone()[0]
    print(f"Total Cases: {total_cases}")
    
    # 2. Count cases with outcomes
    cursor.execute("""
        SELECT COUNT(*) 
        FROM documents 
        WHERE document_type IN ('case_study', 'case')
        AND doc_metadata->>'outcome' IS NOT NULL
        AND doc_metadata->>'outcome' != ''
    """)
    cases_with_outcomes = cursor.fetchone()[0]
    print(f"Cases with outcomes: {cases_with_outcomes}")
    
    # 3. Count unique outcome types
    cursor.execute("""
        SELECT doc_metadata->>'outcome' as outcome, COUNT(*) as count
        FROM documents 
        WHERE document_type IN ('case_study', 'case')
        AND doc_metadata->>'outcome' IS NOT NULL
        AND doc_metadata->>'outcome' != ''
        GROUP BY doc_metadata->>'outcome'
        ORDER BY count DESC
    """)
    outcome_types = cursor.fetchall()
    print(f"\nOutcome Types:")
    for outcome, count in outcome_types:
        print(f"  {outcome}: {count} cases")
    
    # 4. Count cases with decisions
    cursor.execute("""
        SELECT COUNT(*) 
        FROM documents 
        WHERE document_type IN ('case_study', 'case')
        AND doc_metadata->>'decision' IS NOT NULL
        AND doc_metadata->>'decision' != ''
    """)
    cases_with_decisions = cursor.fetchone()[0]
    print(f"\nCases with decisions: {cases_with_decisions}")
    
    # 5. Sample cases with both outcome and decision
    cursor.execute("""
        SELECT id, title, doc_metadata->>'outcome' as outcome, 
               doc_metadata->>'decision' as decision,
               doc_metadata->>'case_number' as case_number
        FROM documents 
        WHERE document_type IN ('case_study', 'case')
        AND doc_metadata->>'outcome' IS NOT NULL
        AND doc_metadata->>'outcome' != ''
        AND doc_metadata->>'decision' IS NOT NULL
        AND doc_metadata->>'decision' != ''
        LIMIT 5
    """)
    sample_cases = cursor.fetchall()
    
    print(f"\nSample Cases with Outcomes and Decisions:")
    for case_id, title, outcome, decision, case_number in sample_cases:
        print(f"\nCase ID: {case_id}")
        print(f"Title: {title[:60]}...")
        print(f"Case Number: {case_number}")
        print(f"Outcome: {outcome}")
        print(f"Decision: {decision[:100]}...")
    
    conn.close()

def analyze_guideline_associations():
    """Analyze guideline associations."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("GUIDELINE ASSOCIATIONS ANALYSIS")
    print("="*80)
    
    # 1. Count guidelines
    cursor.execute("SELECT COUNT(*) FROM guidelines")
    total_guidelines = cursor.fetchone()[0]
    print(f"Total Guidelines: {total_guidelines}")
    
    # 2. Count guideline triples/concepts
    cursor.execute("""
        SELECT COUNT(*) 
        FROM entity_triples 
        WHERE entity_type = 'guideline_concept'
    """)
    guideline_triples = cursor.fetchone()[0]
    print(f"Guideline Concept Triples: {guideline_triples}")
    
    # 3. Guidelines by world
    cursor.execute("""
        SELECT w.name, COUNT(g.id) as guideline_count
        FROM worlds w
        LEFT JOIN guidelines g ON w.id = g.world_id
        GROUP BY w.id, w.name
        ORDER BY guideline_count DESC
    """)
    guidelines_by_world = cursor.fetchall()
    print(f"\nGuidelines by World:")
    for world_name, count in guidelines_by_world:
        print(f"  {world_name}: {count} guidelines")
    
    # 4. Document sections (for guideline associations)
    cursor.execute("SELECT COUNT(*) FROM document_sections")
    total_sections = cursor.fetchone()[0]
    print(f"\nTotal Document Sections: {total_sections}")
    
    # 5. Sections with embeddings
    cursor.execute("""
        SELECT COUNT(*) 
        FROM document_sections 
        WHERE embedding IS NOT NULL
    """)
    sections_with_embeddings = cursor.fetchone()[0]
    print(f"Sections with embeddings: {sections_with_embeddings}")
    
    # 6. Check for guideline association data in metadata
    cursor.execute("""
        SELECT COUNT(*) 
        FROM documents 
        WHERE doc_metadata::text LIKE '%guideline%'
        AND document_type IN ('case_study', 'case')
    """)
    cases_with_guideline_data = cursor.fetchone()[0]
    print(f"Cases with guideline-related metadata: {cases_with_guideline_data}")
    
    # 7. Sample guideline association data
    cursor.execute("""
        SELECT id, title, doc_metadata
        FROM documents 
        WHERE doc_metadata::text LIKE '%guideline%'
        AND document_type IN ('case_study', 'case')
        LIMIT 3
    """)
    sample_guideline_cases = cursor.fetchall()
    
    print(f"\nSample Cases with Guideline Data:")
    for case_id, title, metadata in sample_guideline_cases:
        print(f"\nCase ID: {case_id}")
        print(f"Title: {title[:50]}...")
        # Look for guideline-related keys
        if metadata:
            guideline_keys = [k for k in metadata.keys() if 'guideline' in k.lower()]
            print(f"Guideline-related keys: {guideline_keys}")
            for key in guideline_keys[:3]:  # Show first 3
                value = metadata[key]
                if isinstance(value, (list, dict)):
                    print(f"  {key}: {type(value).__name__} with {len(value)} items")
                else:
                    print(f"  {key}: {str(value)[:100]}...")
    
    conn.close()

def analyze_section_associations():
    """Analyze section-level associations between cases and guidelines."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("SECTION ASSOCIATION ANALYSIS")  
    print("="*80)
    
    # Check for section triple associations
    cursor.execute("""
        SELECT COUNT(DISTINCT ds.document_id) as cases_with_sections
        FROM document_sections ds
        JOIN documents d ON ds.document_id = d.id
        WHERE d.document_type IN ('case_study', 'case')
    """)
    cases_with_sections = cursor.fetchone()[0]
    print(f"Cases with document sections: {cases_with_sections}")
    
    # Section types
    cursor.execute("""
        SELECT ds.section_type, COUNT(*) as count
        FROM document_sections ds
        JOIN documents d ON ds.document_id = d.id
        WHERE d.document_type IN ('case_study', 'case')
        GROUP BY ds.section_type
        ORDER BY count DESC
    """)
    section_types = cursor.fetchall()
    print(f"\nSection Types:")
    for section_type, count in section_types:
        print(f"  {section_type}: {count} sections")
    
    # Check if there's a separate association table
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%association%'
        OR table_name LIKE '%guideline%section%'
        OR table_name LIKE '%section%guideline%'
    """)
    association_tables = cursor.fetchall()
    if association_tables:
        print(f"\nAssociation Tables Found:")
        for table in association_tables:
            print(f"  {table[0]}")
            
            # Get count for each table
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                print(f"    Records: {count}")
            except Exception as e:
                print(f"    Error querying: {e}")
    else:
        print(f"\nNo dedicated association tables found.")
    
    conn.close()

def main():
    """Main analysis function."""
    print("GUIDELINE PREDICTION ENHANCEMENT - PHASE 1 DATA ANALYSIS")
    print("Generated on:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    analyze_case_outcomes()
    analyze_guideline_associations()
    analyze_section_associations()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()