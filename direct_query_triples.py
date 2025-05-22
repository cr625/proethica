#!/usr/bin/env python3
"""
Script to directly query RDF triples from the database without using Flask.
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

def main():
    # Load environment variables
    load_dotenv()
    
    # Get database connection details
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
    
    # Connect directly to database
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        print(f"Connected to database: {host}:{port}/{dbname}")
        
        # Use cursor factory for easier column access
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get total count of RDF triples
        cur.execute('SELECT COUNT(*) FROM rdf_triples')
        count = cur.fetchone()[0]
        print(f'RDF Triple count: {count}')
        
        # Get sample triples
        cur.execute('SELECT subject, predicate, object FROM rdf_triples LIMIT 5')
        print('\nSample triples:')
        for r in cur.fetchall():
            print(f"Subject: {r['subject']}")
            print(f"Predicate: {r['predicate']}")
            print(f"Object: {r['object']}")
            print("-" * 50)
        
        # Get triples by type - look for Role triples
        print('\nRole-related triples:')
        cur.execute('''
            SELECT subject, predicate, object FROM rdf_triples 
            WHERE object LIKE '%Role%' OR predicate LIKE '%role%'
            LIMIT 5
        ''')
        for r in cur.fetchall():
            print(f"Subject: {r['subject']}")
            print(f"Predicate: {r['predicate']}")
            print(f"Object: {r['object']}")
            print("-" * 50)
        
        # Get principle-related triples
        print('\nPrinciple-related triples:')
        cur.execute('''
            SELECT subject, predicate, object FROM rdf_triples 
            WHERE object LIKE '%Principle%' OR predicate LIKE '%principle%'
            LIMIT 5
        ''')
        for r in cur.fetchall():
            print(f"Subject: {r['subject']}")
            print(f"Predicate: {r['predicate']}")
            print(f"Object: {r['object']}")
            print("-" * 50)
        
        # Get top predicates
        print('\nMost common predicates:')
        cur.execute('''
            SELECT predicate, COUNT(*) as count FROM rdf_triples 
            GROUP BY predicate ORDER BY count DESC LIMIT 10
        ''')
        for r in cur.fetchall():
            print(f"{r['predicate']}: {r['count']}")
        
        # Get distribution by triple type
        print('\nTriple type distribution:')
        cur.execute('''
            SELECT 
                CASE 
                    WHEN object LIKE '%Role%' OR predicate LIKE '%role%' THEN 'Role'
                    WHEN object LIKE '%Principle%' OR predicate LIKE '%principle%' THEN 'Principle'
                    WHEN object LIKE '%Obligation%' OR predicate LIKE '%obligation%' THEN 'Obligation'
                    WHEN object LIKE '%Condition%' OR predicate LIKE '%condition%' THEN 'Condition'
                    WHEN object LIKE '%Resource%' OR predicate LIKE '%resource%' THEN 'Resource'
                    WHEN object LIKE '%Action%' OR predicate LIKE '%action%' THEN 'Action'
                    WHEN object LIKE '%Event%' OR predicate LIKE '%event%' THEN 'Event'
                    WHEN object LIKE '%Capability%' OR predicate LIKE '%capability%' THEN 'Capability'
                    ELSE 'Other'
                END as triple_type,
                COUNT(*) as count
            FROM rdf_triples
            GROUP BY triple_type
            ORDER BY count DESC
        ''')
        for r in cur.fetchall():
            print(f"{r['triple_type']}: {r['count']}")
                
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            print("Database connection closed")

if __name__ == "__main__":
    main()
