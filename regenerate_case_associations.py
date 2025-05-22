#!/usr/bin/env python3
"""
Regenerate ontology concept associations for a specific case
using the LLM-based approach.

This script:
1. Deletes existing associations for the specified document
2. Runs the LLM-based association process to create new associations
"""

import os
import sys
import argparse
import subprocess
from sqlalchemy import create_engine, text

def delete_existing_associations(document_id):
    """Delete existing ontology concept associations for a document."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Get sections for this document
        sections_query = text("""
            SELECT id FROM document_sections
            WHERE document_id = :doc_id
        """)
        
        # Count existing associations
        count_query = text("""
            SELECT COUNT(*) 
            FROM section_ontology_associations soa
            JOIN document_sections ds ON soa.section_id = ds.id
            WHERE ds.document_id = :doc_id
        """)
        
        sections = [row[0] for row in conn.execute(sections_query, {"doc_id": document_id})]
        
        # Get the count before deletion
        count_result = conn.execute(count_query, {"doc_id": document_id}).scalar()
        
        if count_result == 0:
            print(f"No existing associations found for document {document_id}")
            return 0
        
        # Delete existing associations
        deleted_total = 0
        for section_id in sections:
            delete_query = text("""
                DELETE FROM section_ontology_associations
                WHERE section_id = :section_id
                RETURNING id
            """)
            result = conn.execute(delete_query, {"section_id": section_id})
            deleted = result.rowcount
            deleted_total += deleted
            print(f"Deleted {deleted} associations for section {section_id}")
        
        conn.commit()
        print(f"Total: Deleted {deleted_total} existing associations for document {document_id}")
        return deleted_total

def regenerate_associations(document_id, method="llm"):
    """Regenerate ontology concept associations using the specified method."""
    
    print(f"\nRegenerating associations for document {document_id} using {method} method...")
    
    if method == "llm":
        # Run LLM-based association
        cmd = ["./run_llm_section_triple_association.sh", "--document-id", str(document_id)]
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print(f"✅ Successfully regenerated LLM-based associations for document {document_id}")
            return True
        else:
            print(f"❌ Failed to regenerate LLM-based associations for document {document_id}")
            return False
    else:
        # Run embedding-based association
        cmd = ["./run_ttl_section_triple_association.sh", "--document", str(document_id)]
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print(f"✅ Successfully regenerated embedding-based associations for document {document_id}")
            return True
        else:
            print(f"❌ Failed to regenerate embedding-based associations for document {document_id}")
            return False

def check_new_associations(document_id):
    """Check the newly created associations."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Count new associations
        count_query = text("""
            SELECT ds.id, COUNT(soa.id) 
            FROM document_sections ds
            LEFT JOIN section_ontology_associations soa ON ds.id = soa.section_id
            WHERE ds.document_id = :doc_id
            GROUP BY ds.id
        """)
        
        results = conn.execute(count_query, {"doc_id": document_id}).fetchall()
        
        print(f"\nNew association counts for document {document_id}:")
        total_sections = len(results)
        total_associations = sum(row[1] for row in results)
        
        for section_id, count in results:
            print(f"Section {section_id}: {count} associations")
        
        print(f"\nTotal: {total_associations} associations across {total_sections} sections")
        print(f"Average: {total_associations / total_sections:.1f} associations per section")
        
        return {
            "total_sections": total_sections,
            "total_associations": total_associations,
            "average_per_section": total_associations / total_sections if total_sections > 0 else 0
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Regenerate ontology concept associations for a case.')
    parser.add_argument('--document-id', type=int, required=True, help='Document ID to process')
    parser.add_argument('--method', choices=['embedding', 'llm'], default='llm', 
                        help='Association method to use (default: llm)')
    parser.add_argument('--skip-delete', action='store_true', 
                        help='Skip deletion of existing associations')
    
    args = parser.parse_args()
    
    # Process
    if not args.skip_delete:
        delete_existing_associations(args.document_id)
    
    regenerate_associations(args.document_id, args.method)
    check_new_associations(args.document_id)
