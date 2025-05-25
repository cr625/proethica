#!/usr/bin/env python3
"""
View Case Triples Script
------------------------
A simple script to display the triples for a specific case
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

def view_case_triples(case_id):
    """View all triples for a specific case ID."""
    try:
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First get basic case info
        cursor.execute("""
            SELECT id, title, doc_metadata->>'case_number' as case_number
            FROM documents
            WHERE id = %s
        """, (case_id,))
        
        case = cursor.fetchone()
        if not case:
            print(f"Case {case_id} not found.")
            return
            
        print(f"\nCASE: {case[1]} (ID: {case[0]}, Case Number: {case[2]})")
        print("="*80)
        
        # Get all entity triples
        cursor.execute("""
            SELECT subject, predicate, object_uri, is_literal, object_value, graph, triple_metadata
            FROM entity_triples
            WHERE case_id = %s
            ORDER BY graph, predicate
        """, (case_id,))
        
        triples = cursor.fetchall()
        
        if not triples:
            print(f"No triples found for case {case_id}.")
            return
        
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
        print(f"TOTAL: {total_triples} triples for case {case_id}")
        
        # Close connection
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        
if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            case_id = int(sys.argv[1])
            view_case_triples(case_id)
        except ValueError:
            print("Error: Case ID must be an integer.")
    else:
        print("Usage: python view_case_triples.py <case_id>")
