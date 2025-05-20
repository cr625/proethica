#!/usr/bin/env python

import os
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_case():
    """Check case #206 metadata in more detail"""
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using database URL: {database_url}")
    
    try:
        # Create SQLAlchemy engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query for document with ID 206
        result = session.execute(
            text("SELECT doc_metadata FROM documents WHERE id = :id"),
            {"id": 206}
        )
        row = result.fetchone()
        
        if row and row.doc_metadata:
            print("\nFull metadata structure for Case #206:")
            
            # Try to parse and prettify the metadata
            if isinstance(row.doc_metadata, dict):
                metadata = row.doc_metadata
            else:
                metadata = json.loads(row.doc_metadata)
                
            # Pretty print with indentation
            print(json.dumps(metadata, indent=2))
            
            # Look specifically at the questions_list
            questions_list = metadata.get('questions_list', [])
            if questions_list:
                print("\nQuestions List Details:")
                print(f"Type: {type(questions_list)}")
                print(f"Length: {len(questions_list)}")
                for i, q in enumerate(questions_list):
                    print(f"Question {i+1} type: {type(q)}")
                    print(f"Question {i+1}: {q}")
                
                # Check for form submission debug info
                print("\nChecking form data in metadata:")
                form_data = metadata.get('_debug_form_data')
                if form_data:
                    print("Found form data in metadata:")
                    print(json.dumps(form_data, indent=2))
                else:
                    print("No form data debug info found in metadata")
        else:
            print("No metadata found for Case #206")
            
        # Close the session
        session.close()
        
    except Exception as e:
        print(f"Database query error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_case()
