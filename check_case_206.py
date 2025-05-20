#!/usr/bin/env python

import os
import sys
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_case_exists():
    """Check if case #206 exists in the database and compare with case #203."""
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using database URL: {database_url}")
    
    try:
        # Create SQLAlchemy engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query for both case IDs
        result = session.execute(
            text("SELECT id, title, source, doc_metadata FROM documents WHERE id IN (203, 206)")
        )
        cases = result.fetchall()
        
        # Print basic info for each case
        for case in cases:
            print(f"\nCase #{case.id}: {case.title}")
            print(f"Source: {case.source}")
            
            # Extract metadata
            metadata = case.doc_metadata
            case_number = metadata.get('case_number') if metadata else None
            year = metadata.get('year') if metadata else None
            
            print(f"Case Number in metadata: {case_number}")
            print(f"Year in metadata: {year}")
        
        # Compare URLs between cases
        url_result = session.execute(
            text("SELECT id, source FROM documents WHERE id IN (203, 206)")
        )
        url_data = {row.id: row.source for row in url_result.fetchall()}
        
        if 203 in url_data and 206 in url_data:
            print("\nURL Comparison:")
            print(f"Case #203 URL: {url_data[203]}")
            print(f"Case #206 URL: {url_data[206]}")
            if url_data[203] == url_data[206]:
                print("Same URL - likely duplicate entries of the same case")
            else:
                print("Different URLs - likely different cases")
                
        # Count how many cases have the same source URL
        source_check = session.execute(
            text("SELECT source, COUNT(*) FROM documents GROUP BY source HAVING COUNT(*) > 1")
        )
        duplicate_sources = source_check.fetchall()
        
        if duplicate_sources:
            print("\nDuplicate source URLs found:")
            for source, count in duplicate_sources:
                if source:  # Only print non-empty sources
                    print(f"Source: {source} - {count} instances")
                    
                    # Get the IDs of documents with this source
                    id_result = session.execute(
                        text("SELECT id, title FROM documents WHERE source = :source"),
                        {"source": source}
                    )
                    for row in id_result.fetchall():
                        print(f"  ID: {row.id}, Title: {row.title}")
        
        session.close()
        
    except Exception as e:
        print(f"Database query error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_case_exists()
