#!/usr/bin/env python3
"""
List all RDF triples associated with a specific world.

This utility displays triples that are connected to a world either directly
or through guidelines belonging to that world.
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
    parser = argparse.ArgumentParser(description='List RDF triples associated with a world.')
    parser.add_argument('--world-id', '-w', type=int, required=True,
                      help='World ID (required)')
    parser.add_argument('--limit', '-l', type=int, default=50,
                      help='Maximum number of triples to display (default: 50)')
    parser.add_argument('--format', '-f', choices=['simple', 'detailed'], default='simple',
                      help='Output format (default: simple)')
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

def get_world_name(conn, world_id):
    """Get the name of a world by ID."""
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name FROM worlds WHERE id = %s', (world_id,))
            result = cur.fetchone()
            return result[0] if result else f"Unknown World ({world_id})"
    except Exception as e:
        print(f"Error retrieving world name: {e}")
        return f"Unknown World ({world_id})"

def get_triples_for_world(conn, world_id, limit=50):
    """
    Get entity triples associated with a world, through guidelines.
    """
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # First, get guideline IDs for this world
            cur.execute('SELECT id, title FROM guidelines WHERE world_id = %s', (world_id,))
            guidelines = cur.fetchall()
            
            if not guidelines:
                print(f"No guidelines found for world ID {world_id}")
                return []
            
            # Prepare guideline IDs for query
            guideline_ids = [row['id'] for row in guidelines]
            guideline_map = {row['id']: row['title'] for row in guidelines}
            
            # Get triples associated with these guidelines
            placeholders = ', '.join(['%s'] * len(guideline_ids))
            query = f'''
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
                    et.guideline_id,
                    et.entity_type
                FROM 
                    entity_triples et
                WHERE 
                    et.guideline_id IN ({placeholders})
                    AND et.entity_type = 'guideline_concept'
                ORDER BY 
                    et.guideline_id, et.id
                LIMIT %s
            '''
            
            # Add limit to the parameters
            cur.execute(query, guideline_ids + [limit])
            
            # Fetch results
            results = cur.fetchall()
            
            # Convert to list of dictionaries to allow adding guideline_title
            result_dicts = []
            for row in results:
                row_dict = dict(row)
                row_dict['guideline_title'] = guideline_map.get(row_dict['guideline_id'], 'Unknown guideline')
                result_dicts.append(row_dict)
            
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
    
    # Add guideline information
    result += f"\nGuideline: {triple['guideline_title']} (ID: {triple['guideline_id']})"
    
    return result

def list_world_triples(world_id, limit=50, format_type='simple'):
    """List triples associated with a world."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        world_name = get_world_name(conn, world_id)
        triples = get_triples_for_world(conn, world_id, limit)
        
        if not triples:
            print(f"No triples found for world '{world_name}' (ID: {world_id}).")
            return
        
        # Display header
        title = f"TRIPLES FOR WORLD: {world_name} (ID: {world_id})"
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
        list_world_triples(
            args.world_id,
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
