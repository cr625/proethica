#!/usr/bin/env python
"""
Test script for querying similar sections using the section embeddings.
This demonstrates how to use the pgvector extension to find semantically similar
sections across different documents in the AI Ethical DM database.
"""
import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
import numpy as np
from sentence_transformers import SentenceTransformer

# Set up argument parser
parser = argparse.ArgumentParser(description='Test section embeddings similarity search')
parser.add_argument('--query', '-q', type=str, help='Text query to find similar sections')
parser.add_argument('--case-id', '-c', type=int, help='Use a specific section from this case ID as the query source')
parser.add_argument('--section-id', '-s', type=str, help='Use this section ID from the specified case as query source')
parser.add_argument('--limit', '-l', type=int, default=5, help='Limit results (default: 5)')
parser.add_argument('--section-type', '-t', type=str, help='Filter results by section type')
parser.add_argument('--list-sections', action='store_true', help='List all available sections')
args = parser.parse_args()

# Load environment variables from .env file
if os.path.exists('.env'):
    load_dotenv()
    print("Loaded environment from .env file")

def get_db_connection():
    """Create a connection to the database."""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    
    # Parse connection string
    conn_parts = db_url.replace('postgresql://', '').split('/')
    dbname = conn_parts[1]
    user_host_port = conn_parts[0].split('@')
    user_pass = user_host_port[0].split(':')
    user = user_pass[0]
    password = user_pass[1]
    host_port = user_host_port[1].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    
    # Connect to database
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    print(f"Connected to database: {host}:{port}/{dbname}")
    return conn

def get_embedding_model():
    """Load the embedding model."""
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"Loaded model: {model.get_sentence_embedding_dimension()} dimensions")
    return model

def list_available_sections(conn):
    """List all sections available in the database."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("""
            SELECT ds.document_id, ds.section_id, ds.section_type, 
                   d.title, LEFT(ds.content, 100) as content_preview
            FROM document_sections ds
            JOIN documents d ON ds.document_id = d.id
            ORDER BY ds.document_id, ds.section_type
        """)
        
        sections = cur.fetchall()
        
        print(f"\nFound {len(sections)} sections in the database:\n")
        print(f"{'CASE ID':7} | {'SECTION ID':15} | {'TYPE':15} | {'TITLE':30} | PREVIEW")
        print(f"{'-'*7} | {'-'*15} | {'-'*15} | {'-'*30} | {'-'*50}")
        
        for section in sections:
            preview = section['content_preview']
            if len(preview) >= 100:
                preview = preview[:97] + "..."
            
            print(f"{section['document_id']:7d} | {section['section_id']:15} | {section['section_type']:15} | {section['title'][:30]:30} | {preview}")
    
    finally:
        cur.close()

def get_section_content(conn, case_id, section_id):
    """Get the content of a specific section."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("""
            SELECT content FROM document_sections
            WHERE document_id = %s AND section_id = %s
        """, (case_id, section_id))
        
        result = cur.fetchone()
        
        if not result:
            print(f"Error: Section '{section_id}' not found in case {case_id}")
            return None
            
        return result['content']
    
    finally:
        cur.close()

def find_similar_sections(conn, embedding, section_type=None, limit=5):
    """Find sections similar to the provided embedding."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    embedding_array = np.array(embedding)
    embedding_list = embedding_array.tolist()
    
    try:
        query = """
            SELECT 
                ds.document_id,
                ds.section_id,
                ds.section_type,
                d.title,
                ds.content,
                1 - (ds.embedding <=> %s::vector) as similarity
            FROM document_sections ds
            JOIN documents d ON ds.document_id = d.id
        """
        
        params = [json.dumps(embedding_list)]
        
        if section_type:
            query += " WHERE ds.section_type = %s"
            params.append(section_type)
            
        query += " ORDER BY similarity DESC LIMIT %s"
        params.append(limit)
        
        cur.execute(query, params)
        
        results = cur.fetchall()
        return results
    
    finally:
        cur.close()

def print_results(results):
    """Print similarity search results."""
    if not results:
        print("No similar sections found")
        return
        
    print(f"\nFound {len(results)} similar sections:\n")
    
    for i, result in enumerate(results):
        print(f"Result #{i+1} - Similarity: {result['similarity']:.4f}")
        print(f"Case ID: {result['document_id']} | Section: {result['section_id']} ({result['section_type']})")
        print(f"Case Title: {result['title']}")
        print(f"Content Preview: {result['content'][:200]}...")
        print("-" * 80)

def main():
    """Main function."""
    # Connect to database
    conn = get_db_connection()
    
    try:
        # List sections if requested
        if args.list_sections:
            list_available_sections(conn)
            return
            
        # Make sure we have a query
        if not args.query and (not args.case_id or not args.section_id):
            print("Error: You must provide either a text query or a case+section ID")
            parser.print_help()
            return
            
        # Get the embedding model
        model = get_embedding_model()
        
        # Get the query embedding
        if args.query:
            # Use direct text query
            query_text = args.query
            print(f"Generating embedding for query: '{query_text[:50]}...'")
            query_embedding = model.encode(query_text)
            
        else:
            # Use section content as query
            section_content = get_section_content(conn, args.case_id, args.section_id)
            if not section_content:
                return
                
            print(f"Using section '{args.section_id}' from case {args.case_id} as query")
            print(f"Section content (preview): '{section_content[:50]}...'")
            query_embedding = model.encode(section_content)
            
        # Find similar sections
        print(f"Finding similar sections...")
        if args.section_type:
            print(f"Filtering by section type: {args.section_type}")
            
        results = find_similar_sections(
            conn=conn,
            embedding=query_embedding,
            section_type=args.section_type,
            limit=args.limit
        )
        
        # Display results
        print_results(results)
        
    finally:
        conn.close()

if __name__ == "__main__":
    start_time = datetime.now()
    main()
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Execution completed in {elapsed:.2f} seconds")
