#!/usr/bin/env python3
"""
Check Case Structure Script
---------------------------
Verify document structure annotations for a specific case
"""

import os
import sys
import json
from pprint import pprint

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the database module directly from nspe-pipeline
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), 'nspe-pipeline'))
from utils.database import get_db_connection

def check_case_structure(case_id):
    """Check document structure annotations for a specific case ID."""
    try:
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First get basic case info with document metadata
        cursor.execute("""
            SELECT id, title, doc_metadata->>'case_number' as case_number, doc_metadata
            FROM documents
            WHERE id = %s
        """, (case_id,))
        
        case = cursor.fetchone()
        if not case:
            print(f"Case {case_id} not found.")
            return
            
        print(f"\nCASE: {case[1]} (ID: {case[0]}, Case Number: {case[2]})")
        print("="*80)
        
        # Check for document structure in doc_metadata
        if isinstance(case[3], str):
            doc_metadata = json.loads(case[3]) if case[3] else {}
        else:
            doc_metadata = case[3] if case[3] else {}
        if 'document_structure' in doc_metadata:
            print("\nDOCUMENT STRUCTURE FOUND")
            print("-"*80)
            doc_structure = doc_metadata['document_structure']
            
            print(f"Document URI: {doc_structure.get('document_uri', 'N/A')}")
            
            # Check if structure_triples exists
            if 'structure_triples' in doc_structure:
                triples_str = doc_structure['structure_triples']
                print(f"Structure triples found! ({len(triples_str)} characters)")
                
                # Print first 500 characters as preview
                print("\nPreview of structure triples:")
                print("-"*40)
                print(triples_str[:500] + "..." if len(triples_str) > 500 else triples_str)
                print("-"*40)
            else:
                print("No structure triples found in doc_metadata.")
                
            # Check for section embedding metadata
            if 'section_embeddings_metadata' in doc_metadata:
                section_metadata = doc_metadata['section_embeddings_metadata']
                print(f"\nSection embedding metadata found! ({len(section_metadata)} sections)")
                print("\nSections:")
                for uri, data in section_metadata.items():
                    print(f"- {uri.split('/')[-1]}: {data.get('type')}")
            else:
                print("\nNo section embedding metadata found.")
        else:
            print("\nNo document structure information found in doc_metadata.")
        
        # Get all entity triples
        cursor.execute("""
            SELECT subject, predicate, object_uri, is_literal, object_literal, graph, triple_metadata
            FROM entity_triples
            WHERE entity_id = %s
            ORDER BY graph, predicate
        """, (case_id,))
        
        triples = cursor.fetchall()
        
        if not triples:
            print(f"\nNo entity triples found for case {case_id} in the entity_triples table.")
        else:
            # Group triples by graph
            graphs = {}
            for triple in triples:
                subject, predicate, object_uri, is_literal, object_value, graph, metadata = triple
                
                if graph not in graphs:
                    graphs[graph] = []
                    
                # Create a more readable triple representation
                readable_triple = {
                    "subject": subject,
                    "predicate": predicate,
                    "object": object_uri if not is_literal else object_value,
                    "is_literal": is_literal,
                    "metadata": json.loads(metadata) if metadata else {}
                }
                
                graphs[graph].append(readable_triple)
            
            # Print triples grouped by graph
            total_triples = 0
            for graph, graph_triples in graphs.items():
                graph_name = graph.split("/")[-1].split("#")[0]
                print(f"\n{graph_name.upper()} ONTOLOGY TRIPLES")
                print("-"*80)
                print(f"Total: {len(graph_triples)} triples\n")
                
                for triple in graph_triples:
                    subject_short = triple["subject"].split("/")[-1]
                    predicate_short = triple["predicate"].split("/")[-1].split("#")[-1]
                    
                    if isinstance(triple["object"], str) and not triple["is_literal"]:
                        object_short = triple["object"].split("/")[-1].split("#")[-1]
                    else:
                        object_short = triple["object"]
                        
                    print(f"{subject_short} -> {predicate_short} -> {object_short}")
                    
                    # Print metadata source if available
                    if triple["metadata"] and "source" in triple["metadata"]:
                        print(f"    Source: {triple['metadata']['source']}")
                        
                    # Print confidence if available
                    if triple["metadata"] and "confidence" in triple["metadata"]:
                        print(f"    Confidence: {triple['metadata']['confidence']}")
                        
                    print("")
                    
                total_triples += len(graph_triples)
            
            print("="*80)
            print(f"TOTAL: {total_triples} entity triples for case {case_id}")
        
        # Close connection
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        
if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            case_id = int(sys.argv[1])
            check_case_structure(case_id)
        except ValueError:
            print("Error: Case ID must be an integer.")
    else:
        print("Usage: python check_case_structure.py <case_id>")
