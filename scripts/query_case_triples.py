#!/usr/bin/env python3
"""
Simple script to query case triples and save to a file
"""

import os
import sys
import json
import psycopg2
from datetime import datetime

# Database connection parameters - make sure these match your setup
DB_NAME = "ai_ethical_dm"
DB_USER = "postgres"
DB_PASSWORD = "PASS"  # Replace with actual password if needed
DB_HOST = "localhost"
DB_PORT = "5433"      # PostgreSQL port used in Docker

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

def save_triples_to_file(case_id):
    """Query triples for a case and save to file."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Get case details
    cursor.execute("""
        SELECT id, title, doc_metadata->>'case_number' as case_number 
        FROM documents 
        WHERE id = %s
    """, (case_id,))
    
    case = cursor.fetchone()
    if not case:
        print(f"Case {case_id} not found.")
        return
    
    # Get all triples for this case
    cursor.execute("""
        SELECT subject, predicate, object_uri, object_literal, graph, triple_metadata
        FROM entity_triples
        WHERE case_id = %s
        ORDER BY graph, predicate
    """, (case_id,))
    
    triples = cursor.fetchall()
    conn.close()
    
    # Save output to file
    output_file = f"case_{case_id}_triples.txt"
    with open(output_file, 'w') as f:
        f.write(f"CASE: {case[1]} (ID: {case[0]}, Case Number: {case[2]})\n")
        f.write("="*80 + "\n\n")
        
        if not triples:
            f.write(f"No triples found for case {case_id}.\n")
            return
        
        # Group by graph/ontology
        graphs = {}
        for triple in triples:
            subject, predicate, object_uri, object_literal, graph, metadata = triple
            
            if graph not in graphs:
                graphs[graph] = []
                
            # Create readable triple
            triple_obj = {
                "subject": subject,
                "predicate": predicate,
                "object": object_uri if object_literal is None else object_literal,
                "is_literal": object_literal is not None,
                "metadata": json.loads(metadata) if metadata else {}
            }
            
            graphs[graph].append(triple_obj)
        
        # Write triples grouped by ontology
        total_count = 0
        for graph, graph_triples in graphs.items():
            # Get simplified graph name
            graph_name = graph.split("/")[-1].split("#")[0]
            f.write(f"{graph_name.upper()} ONTOLOGY TRIPLES\n")
            f.write("-"*80 + "\n")
            f.write(f"Total: {len(graph_triples)} triples\n\n")
            
            for triple in graph_triples:
                # Simplify URIs for readability
                subject_short = triple["subject"].split("/")[-1]
                predicate_short = triple["predicate"].split("/")[-1].split("#")[-1]
                
                if isinstance(triple["object"], str) and not triple["is_literal"]:
                    object_short = triple["object"].split("/")[-1].split("#")[-1]
                else:
                    object_short = triple["object"]
                    
                f.write(f"{subject_short} -> {predicate_short} -> {object_short}\n")
                
                # Include metadata
                if triple["metadata"] and "source" in triple["metadata"]:
                    f.write(f"    Source: {triple['metadata']['source']}\n")
                    
                if triple["metadata"] and "confidence" in triple["metadata"]:
                    f.write(f"    Confidence: {triple['metadata']['confidence']}\n")
                    
                f.write("\n")
                
            total_count += len(graph_triples)
            f.write("\n")
            
        f.write("="*80 + "\n")
        f.write(f"TOTAL: {total_count} triples for case {case_id}\n")
    
    print(f"Triples for case {case_id} saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            case_id = int(sys.argv[1])
            save_triples_to_file(case_id)
        except ValueError:
            print("Error: Case ID must be an integer")
    else:
        print("Usage: python query_case_triples.py <case_id>")
