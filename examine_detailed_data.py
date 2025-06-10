#!/usr/bin/env python3
"""
Detailed examination of the current data to understand case structure and guideline relationships.
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

def examine_single_case():
    """Examine the single case in detail."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("="*80)
    print("DETAILED CASE EXAMINATION")
    print("="*80)
    
    # Get the case details
    cursor.execute("""
        SELECT id, title, document_type, content, source, doc_metadata
        FROM documents 
        WHERE document_type IN ('case_study', 'case')
    """)
    
    case = cursor.fetchone()
    if case:
        case_id, title, doc_type, content, source, metadata = case
        print(f"Case ID: {case_id}")
        print(f"Title: {title}")
        print(f"Type: {doc_type}")
        print(f"Source: {source}")
        print(f"Content length: {len(content) if content else 0} characters")
        
        print(f"\nMetadata structure:")
        if metadata:
            print(f"Metadata type: {type(metadata)}")
            if isinstance(metadata, dict):
                print(f"Metadata keys: {list(metadata.keys())}")
                
                # Look for specific outcome-related keys
                important_keys = ['outcome', 'decision', 'case_number', 'year', 'conclusion_items', 'questions_list', 'sections']
                for key in important_keys:
                    if key in metadata:
                        value = metadata[key]
                        if isinstance(value, (list, dict)):
                            print(f"  {key}: {type(value).__name__} with {len(value)} items")
                            if key == 'sections' and isinstance(value, dict):
                                print(f"    Section types: {list(value.keys())}")
                        else:
                            print(f"  {key}: {str(value)[:100]}...")
        else:
            print("No metadata found")
    
    # Get sections for this case
    print(f"\n" + "-"*40)
    print("DOCUMENT SECTIONS")
    print("-"*40)
    
    cursor.execute("""
        SELECT ds.section_id, ds.section_type, ds.content, ds.section_metadata
        FROM document_sections ds
        JOIN documents d ON ds.document_id = d.id
        WHERE d.document_type IN ('case_study', 'case')
        ORDER BY ds.position
    """)
    
    sections = cursor.fetchall()
    for section_id, section_type, content, section_metadata in sections:
        print(f"\nSection: {section_id} ({section_type})")
        print(f"Content length: {len(content) if content else 0} characters")
        if content:
            preview = content[:200].replace('\n', ' ').strip()
            print(f"Preview: {preview}...")
        if section_metadata:
            print(f"Section metadata: {section_metadata}")
    
    conn.close()

def examine_guidelines():
    """Examine guideline structure and associations."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print(f"\n" + "="*80)
    print("DETAILED GUIDELINE EXAMINATION")
    print("="*80)
    
    # Get guideline details
    cursor.execute("""
        SELECT id, title, content, source_url, guideline_metadata
        FROM guidelines
    """)
    
    guideline = cursor.fetchone()
    if guideline:
        guide_id, title, content, source_url, metadata = guideline
        print(f"Guideline ID: {guide_id}")
        print(f"Title: {title}")
        print(f"Source URL: {source_url}")
        print(f"Content length: {len(content) if content else 0} characters")
        
        if metadata:
            print(f"Guideline metadata: {type(metadata)} with keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'N/A'}")
    
    # Get guideline concepts (entity triples)
    print(f"\n" + "-"*40)
    print("GUIDELINE CONCEPTS")
    print("-"*40)
    
    cursor.execute("""
        SELECT subject_label, predicate_label, object_label, object_literal, triple_metadata
        FROM entity_triples
        WHERE entity_type = 'guideline_concept'
        LIMIT 10
    """)
    
    concepts = cursor.fetchall()
    print(f"Sample of {len(concepts)} guideline concepts:")
    for subject, predicate, obj_label, obj_literal, metadata in concepts:
        print(f"\n{subject} -> {predicate} -> {obj_label or obj_literal}")
        if metadata:
            meta_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
            if isinstance(meta_dict, dict) and 'confidence' in meta_dict:
                print(f"  Confidence: {meta_dict['confidence']}")
    
    conn.close()

def check_case_import_data():
    """Check for case data in other locations."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print(f"\n" + "="*80)
    print("CHECKING FOR ADDITIONAL CASE DATA")
    print("="*80)
    
    # Check all tables that might contain case information
    case_related_tables = [
        'scenarios', 'events', 'characters', 'decisions', 
        'entity_triples', 'experiments'
    ]
    
    for table in case_related_tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} records")
            
            # If there are entity triples, check for case-related ones
            if table == 'entity_triples' and count > 0:
                cursor.execute("""
                    SELECT DISTINCT entity_type, COUNT(*) 
                    FROM entity_triples 
                    GROUP BY entity_type
                """)
                entity_types = cursor.fetchall()
                print(f"  Entity types: {entity_types}")
                
                # Check for case_id references
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM entity_triples 
                    WHERE case_id IS NOT NULL
                """)
                case_triples = cursor.fetchone()[0]
                print(f"  Triples with case_id: {case_triples}")
                
        except Exception as e:
            print(f"{table}: Error - {e}")
    
    # Check if there are any JSON files with case data
    print(f"\n" + "-"*40)
    print("CHECKING FOR CASE FILES")
    print("-"*40)
    
    data_dir = "/home/chris/proethica/data"
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith('.json') and 'case' in file.lower():
                filepath = os.path.join(data_dir, file)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        print(f"{file}: {len(data)} cases")
                    elif isinstance(data, dict):
                        print(f"{file}: 1 case (dict format)")
                    else:
                        print(f"{file}: {type(data)} format")
                except Exception as e:
                    print(f"{file}: Error reading - {e}")
    
    conn.close()

def examine_triples_for_associations():
    """Look for any existing associations between cases and guidelines."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print(f"\n" + "="*80)
    print("EXAMINING TRIPLES FOR ASSOCIATIONS")
    print("="*80)
    
    # Look for triples that might represent associations
    cursor.execute("""
        SELECT DISTINCT predicate_label, COUNT(*)
        FROM entity_triples
        GROUP BY predicate_label
        ORDER BY COUNT(*) DESC
    """)
    
    predicates = cursor.fetchall()
    print("Predicate types in entity_triples:")
    for predicate, count in predicates:
        print(f"  {predicate}: {count}")
        
    # Look for triples connecting cases to guidelines
    cursor.execute("""
        SELECT subject_label, predicate_label, object_label, object_literal
        FROM entity_triples
        WHERE (predicate_label LIKE '%guideline%' 
               OR predicate_label LIKE '%associated%'
               OR predicate_label LIKE '%related%')
        LIMIT 10
    """)
    
    associations = cursor.fetchall()
    if associations:
        print(f"\nPotential associations:")
        for subject, predicate, obj_label, obj_literal in associations:
            print(f"  {subject} -> {predicate} -> {obj_label or obj_literal}")
    else:
        print("\nNo obvious case-guideline associations found in triples")
    
    conn.close()

def main():
    """Main examination function."""
    print("DETAILED DATA EXAMINATION FOR GUIDELINE PREDICTION ENHANCEMENT")
    print("Generated on:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    examine_single_case()
    examine_guidelines()  
    check_case_import_data()
    examine_triples_for_associations()
    
    print(f"\n" + "="*80)
    print("DETAILED EXAMINATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()