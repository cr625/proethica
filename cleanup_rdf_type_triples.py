#!/usr/bin/env python3
"""
Cleanup RDF Type Triples
------------------------
This script removes RDF triples that use http://www.w3.org/1999/02/22-rdf-syntax-ns#type predicate
from the entity_triples table. These triples are no longer needed since we've transitioned to
using more semantic domain-specific predicates instead of generic rdf:type statements.

Example:
  Instead of: "22-rdf-syntax-ns#type: intermediate#Role"
  We now use: "engineering-ethics#hasRole: engineering-ethics#EngineeringConsultantRole"
"""

import psycopg2
import json
from datetime import datetime

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

RDF_TYPE_PREDICATE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

def cleanup_rdf_type_triples():
    """Remove all triples that use rdf:type predicate"""
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    # First, get a count of triples to be removed
    cur.execute(
        "SELECT COUNT(*) FROM entity_triples WHERE predicate = %s",
        (RDF_TYPE_PREDICATE,)
    )
    count = cur.fetchone()[0]
    
    if count == 0:
        print("No rdf:type triples found in the database.")
        conn.close()
        return 0
    
    print(f"Found {count} rdf:type triples to be removed.")
    
    # Get details about the triples to be removed for reporting
    cur.execute(
        """
        SELECT 
            entity_id, 
            subject, 
            object_uri, 
            object_literal,
            is_literal
        FROM entity_triples 
        WHERE predicate = %s
        """,
        (RDF_TYPE_PREDICATE,)
    )
    triples = cur.fetchall()
    
    # Group by case/document
    triples_by_case = {}
    for triple in triples:
        case_id = triple[0]
        if case_id not in triples_by_case:
            triples_by_case[case_id] = []
        
        object_value = triple[3] if triple[4] else triple[2]
        triples_by_case[case_id].append({
            "subject": triple[1],
            "object": object_value
        })
    
    # Now delete the triples
    cur.execute(
        "DELETE FROM entity_triples WHERE predicate = %s",
        (RDF_TYPE_PREDICATE,)
    )
    
    # Commit the transaction
    conn.commit()
    
    # Print summary
    print(f"\n=== Removed {count} rdf:type triples ===")
    print(f"Affected cases/documents: {len(triples_by_case)}")
    
    # Print details for each case
    for case_id, case_triples in triples_by_case.items():
        print(f"\nCase/Document ID: {case_id}")
        print(f"Removed {len(case_triples)} triples:")
        for t in case_triples:
            print(f"  - {t['subject']} -> {t['object']}")
    
    # Close connection
    cur.close()
    conn.close()
    print("\nCleanup complete. Database connection closed.")
    
    return count

if __name__ == "__main__":
    try:
        removed_count = cleanup_rdf_type_triples()
        if removed_count > 0:
            print("\nSUCCESS: All rdf:type triples have been removed from the database.")
            print("This improves the RDF property display in the case detail view and")
            print("prevents duplicate type information from being shown.")
    except Exception as e:
        print(f"ERROR: {e}")
