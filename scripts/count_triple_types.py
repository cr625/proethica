#!/usr/bin/env python3
"""
Script to count different types of RDF triples in the database.
"""
import os
import psycopg2
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
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        print(f"Connected to database: {host}:{port}/{dbname}")
        
        cur = conn.cursor()
        
        # Total count
        cur.execute('SELECT COUNT(*) FROM rdf_triples')
        total_count = cur.fetchone()[0]
        print(f"Total RDF triples: {total_count}")
        
        # Count by ontology entity type
        entity_types = [
            'Role', 'Principle', 'Obligation', 'Condition', 
            'Resource', 'Action', 'Event', 'Capability'
        ]
        
        print("\nTriple counts by ontology type:")
        print("-" * 40)
        
        for entity_type in entity_types:
            # Count triples where object contains the entity type
            cur.execute(f"""
                SELECT COUNT(*) FROM rdf_triples 
                WHERE object LIKE '%{entity_type}%' OR predicate LIKE '%{entity_type.lower()}%'
            """)
            type_count = cur.fetchone()[0]
            print(f"{entity_type}: {type_count} ({type_count/total_count*100:.2f}%)")
        
        # Count 'Other' triples
        other_condition = " AND ".join([
            f"object NOT LIKE '%{t}%' AND predicate NOT LIKE '%{t.lower()}%'" 
            for t in entity_types
        ])
        
        cur.execute(f"SELECT COUNT(*) FROM rdf_triples WHERE {other_condition}")
        other_count = cur.fetchone()[0]
        print(f"Other: {other_count} ({other_count/total_count*100:.2f}%)")
        
        # Get top predicates
        print("\nMost common predicates:")
        print("-" * 40)
        
        cur.execute("""
            SELECT predicate, COUNT(*) as count FROM rdf_triples 
            GROUP BY predicate ORDER BY count DESC LIMIT 10
        """)
        
        for row in cur.fetchall():
            predicate, count = row
            print(f"{predicate}: {count} ({count/total_count*100:.2f}%)")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            print("\nDatabase connection closed")

if __name__ == "__main__":
    main()
