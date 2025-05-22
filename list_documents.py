#!/usr/bin/env python3
"""
List documents in the database to understand what's available.
"""

import os
from sqlalchemy import create_engine, text
from tabulate import tabulate

def list_documents():
    """List all documents in the database."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Query all documents
        query = text("""
            SELECT id, title, document_type, created_at
            FROM documents
            ORDER BY id
        """)
        
        results = conn.execute(query).fetchall()
        
        # Display results
        if results:
            print(f"Found {len(results)} documents:")
            
            table_data = [
                [row[0], row[1][:60] + '...' if len(row[1]) > 60 else row[1], row[2], row[3]] 
                for row in results
            ]
            
            headers = ["ID", "Title", "Type", "Created At"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No documents found in the database.")

def list_sections():
    """List document sections in the database."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Query section counts by document
        query = text("""
            SELECT d.id, d.title, COUNT(ds.id) as section_count
            FROM documents d
            JOIN document_sections ds ON d.id = ds.document_id
            GROUP BY d.id, d.title
            ORDER BY d.id
        """)
        
        results = conn.execute(query).fetchall()
        
        # Display results
        if results:
            print(f"\nFound {sum(row[2] for row in results)} sections across {len(results)} documents:")
            
            table_data = [
                [row[0], row[1][:60] + '...' if len(row[1]) > 60 else row[1], row[2]] 
                for row in results
            ]
            
            headers = ["Document ID", "Title", "Section Count"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No document sections found in the database.")

def list_associations():
    """List ontology concept associations in the database."""
    
    # Connect to database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Query association counts by document
        query = text("""
            SELECT d.id, d.title, COUNT(DISTINCT ds.id) as section_count, COUNT(soa.id) as assoc_count
            FROM documents d
            JOIN document_sections ds ON d.id = ds.document_id
            LEFT JOIN section_ontology_associations soa ON ds.id = soa.section_id
            GROUP BY d.id, d.title
            HAVING COUNT(soa.id) > 0
            ORDER BY d.id
        """)
        
        results = conn.execute(query).fetchall()
        
        # Display results
        if results:
            print(f"\nFound {sum(row[3] for row in results)} associations across {len(results)} documents:")
            
            table_data = [
                [row[0], 
                 row[1][:50] + '...' if len(row[1]) > 50 else row[1], 
                 row[2], 
                 row[3], 
                 f"{row[3]/row[2]:.1f}"] 
                for row in results
            ]
            
            headers = ["Document ID", "Title", "Sections", "Associations", "Avg/Section"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No ontology concept associations found in the database.")

if __name__ == "__main__":
    list_documents()
    list_sections()
    list_associations()
