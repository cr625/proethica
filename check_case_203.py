#!/usr/bin/env python

import os
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_case_exists():
    """Check if case #203 exists in the database and return its metadata."""
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using database URL: {database_url}")
    
    try:
        # Create SQLAlchemy engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query for document with ID 203
        result = session.execute(
            text("SELECT id, title, doc_metadata FROM documents WHERE id = :id"),
            {"id": 203}
        )
        case = result.fetchone()
        
        if not case:
            print(f"Case #203 not found!")
            
            # Check if it exists with a different ID
            alt_result = session.execute(
                text("SELECT id, title, doc_metadata FROM documents WHERE doc_metadata->>'case_number' = :case_number"),
                {"case_number": "203"}
            )
            alt_case = alt_result.fetchone()
            
            if alt_case:
                print(f"Found case with number 203 but different ID: {alt_case.id}")
                print(f"Title: {alt_case.title}")
                print(f"Full metadata structure:")
                print(json.dumps(alt_case.doc_metadata, indent=2))
            else:
                print("No case with case_number 203 found either.")
            
            return
            
        print(f"Found case #203: {case.title}")
        
        # Print full metadata
        print("Full metadata structure:")
        print(json.dumps(case.doc_metadata, indent=2))
        
        session.close()
        
    except Exception as e:
        print(f"Database query error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_case_exists()
