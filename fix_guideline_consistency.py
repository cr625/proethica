#!/usr/bin/env python3
"""
Fix guideline consistency issues:
1. Remove duplicate Document records with document_type='guideline'
2. Ensure all guidelines are only in the Guidelines table
3. Update sequences to be consistent
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def fix_guideline_consistency():
    """Fix guideline consistency issues"""
    database_uri = 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm'
    engine = create_engine(database_uri)
    
    with engine.connect() as conn:
        print("=== Fixing Guideline Consistency ===")
        print(f"Started at: {datetime.now()}")
        
        # Step 1: Check current state
        print("\n1. Current state:")
        result = conn.execute(text("SELECT id, title FROM documents WHERE document_type = 'guideline'"))
        docs = result.fetchall()
        print(f"   Documents with document_type='guideline': {len(docs)}")
        for doc in docs:
            print(f"     Document ID {doc[0]}: {doc[1]}")
        
        result = conn.execute(text("SELECT id, title FROM guidelines"))
        guidelines = result.fetchall()
        print(f"   Guidelines table: {len(guidelines)}")
        for g in guidelines:
            print(f"     Guideline ID {g[0]}: {g[1]}")
        
        # Step 2: Delete all Documents with document_type='guideline'
        print("\n2. Removing Document records with document_type='guideline'...")
        
        # First delete related document_chunks
        result = conn.execute(text("""
            DELETE FROM document_chunks 
            WHERE document_id IN (SELECT id FROM documents WHERE document_type = 'guideline')
        """))
        print(f"   Deleted {result.rowcount} document_chunks")
        
        # Then delete the documents
        result = conn.execute(text("DELETE FROM documents WHERE document_type = 'guideline'"))
        print(f"   Deleted {result.rowcount} documents")
        
        # Step 3: Check if we need to keep any Guidelines
        print("\n3. Verifying Guidelines table...")
        result = conn.execute(text("SELECT COUNT(*) FROM guidelines"))
        guideline_count = result.scalar()
        print(f"   Guidelines remaining: {guideline_count}")
        
        # Step 4: Reset sequences if needed
        if guideline_count == 0:
            print("\n4. No guidelines found, resetting sequence...")
            conn.execute(text("SELECT setval('guidelines_id_seq', 1, false)"))
            print("   Sequence reset to start at 1")
        else:
            print("\n4. Guidelines exist, keeping current data")
        
        conn.commit()
        
        # Step 5: Verify final state
        print("\n5. Final state:")
        result = conn.execute(text("SELECT COUNT(*) FROM documents WHERE document_type = 'guideline'"))
        doc_count = result.scalar()
        print(f"   Documents with document_type='guideline': {doc_count}")
        
        result = conn.execute(text("SELECT id, title FROM guidelines"))
        guidelines = result.fetchall()
        print(f"   Guidelines table: {len(guidelines)}")
        for g in guidelines:
            print(f"     Guideline ID {g[0]}: {g[1]}")
        
        print(f"\n=== Consistency fix completed at {datetime.now()} ===")
        return True

if __name__ == "__main__":
    fix_guideline_consistency()