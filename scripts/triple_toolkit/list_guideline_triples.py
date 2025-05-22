#!/usr/bin/env python3
"""
List all RDF triples associated with a specific guideline.

This utility displays triples that are connected to a guideline directly
through the entity_triples table.
"""

import sys
import argparse
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from scripts.triple_toolkit.common import formatting

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='List RDF triples associated with a guideline.')
    parser.add_argument('--guideline-id', '-g', type=int, required=True,
                      help='Guideline ID (required)')
    parser.add_argument('--limit', '-l', type=int, default=50,
                      help='Maximum number of triples to display (default: 50)')
    parser.add_argument('--format', '-f', choices=['simple', 'detailed'], default='simple',
                      help='Output format (default: simple)')
    parser.add_argument('--entity-type', '-e', default='guideline_concept',
                      help='Entity type to filter by (default: guideline_concept)')
    return parser.parse_args()

def get_db_connection():
    """Establish a database connection using environment variables."""
    # Load environment variables
    load_dotenv()
    
    # Get database connection details
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using DATABASE_URL: {db_url}")
    
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
    
    # Connect directly to database
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def get_guideline_info(conn, guideline_id):
    """Get the guideline information by ID."""
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, title, world_id FROM guidelines WHERE id = %s', (guideline_id,))
            result = cur.fetchone()
            
            if not result:
                return None
                
            guideline = {
                'id': result[0],
                'title': result[1],
                'world_id': result[2]
            }
            
            # Add world name
            cur.execute('SELECT name FROM worlds WHERE id = %s', (guideline['world_id'],))
            world_result = cur.fetchone()
            guideline['world_name'] = world_result[0] if world_result else f"Unknown World ({guideline['world_id']})"
            
            return guideline
    except Exception as e:
        print(f"Error retrieving guideline: {e}")
        return None

def get_triples_for_guideline(conn, guideline_id, entity_type='guideline_concept', limit=50):
    """
    Get entity triples associated with a guideline.
    """
    try:
        with conn.cursor() as cur:
            # Get triples associated with the guideline
            query = '''
                SELECT 
                    et.id,
                    et.subject,
                    et.predicate,
                    et.object_uri,
                    et.object_literal,
                    et.is_literal,
                    et.subject_label,
                    et.predicate_label,
                    et.object_label,
                    et.entity_type
                FROM 
                    entity_triples et
                WHERE 
                    et.guideline_id = %s
                    AND et.entity_type = %s
                ORDER BY 
                    et.id
                LIMIT %s
            '''
            
            cur.execute(query, (guideline_id, entity_type, limit))
            results = cur.fetchall()
            
            # Convert to list of dictionaries
            result_dicts = []
            for row in results:
                triple = {
                    'id': row[0],
                    'subject': row[1],
                    'predicate': row[2],
                    'object_uri': row[3],
                    'object_literal': row[4],
                    'is_literal': row[5],
                    'subject_label': row[6],
                    'predicate_label': row[7],
                    'object_label': row[8],
                    'entity_type': row[9]
                }
                result_dicts.append(triple)
            
            return result_dicts
    except Exception as e:
        print(f"Error retrieving triples: {e}")
        return []

def format_triple_simple(triple):
    """Format a triple for simple display."""
    object_value = triple['object_literal'] if triple['is_literal'] else triple['object_uri']
    return f"Subject: {triple['subject']}\nPredicate: {triple['predicate']}\nObject: {object_value}"

def format_triple_detailed(triple):
    """Format a triple for detailed display."""
    labels = {
        'subject_label': triple['subject_label'],
        'predicate_label': triple['predicate_label'],
        'object_label': triple['object_label']
    }
    
    object_value = triple['object_literal'] if triple['is_literal'] else triple['object_uri']
    
    result = formatting.format_triple(
        triple['subject'], 
        triple['predicate'], 
        object_value,
        triple['is_literal'],
        labels
    )
    
    return result

def list_guideline_triples(guideline_id, entity_type='guideline_concept', limit=50, format_type='simple'):
    """List triples associated with a guideline."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        guideline = get_guideline_info(conn, guideline_id)
        if not guideline:
            print(f"Guideline with ID {guideline_id} not found.")
            return
        
        triples = get_triples_for_guideline(conn, guideline_id, entity_type, limit)
        
        if not triples:
            print(f"No triples found for guideline '{guideline['title']}' (ID: {guideline_id}).")
            return
        
        # Display header
        title = f"TRIPLES FOR GUIDELINE: {guideline['title']} (ID: {guideline_id}, World: {guideline['world_name']})"
        formatting.print_header(title)
        
        # Format based on desired output type
        formatter = format_triple_detailed if format_type == 'detailed' else format_triple_simple
        
        for i, triple in enumerate(triples):
            if i > 0:
                print()  # Add spacing between triples
            print(formatter(triple))
        
        # Display count information
        print(f"\nShowing {len(triples)} triples out of limit {limit}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        print("Database connection closed")

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        list_guideline_triples(
            args.guideline_id,
            entity_type=args.entity_type,
            limit=args.limit,
            format_type=args.format
        )
        
        if args.format == 'simple':
            print("\nTip: Use --format detailed for more information")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
