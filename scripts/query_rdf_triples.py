#!/usr/bin/env python3
"""
Script to query RDF triples from the database and display statistics.
"""
import os
from dotenv import load_dotenv
from app import db, create_app
from sqlalchemy import text

def main():
    # Load environment variables
    load_dotenv()
    # Ensure DATABASE_URL is set for the app
    if 'DATABASE_URL' not in os.environ:
        # Try to use a fallback if not in environment
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        print(f"Using default DATABASE_URL: {os.environ['DATABASE_URL']}")
    else:
        print(f"Using DATABASE_URL from environment")
    # Create app context
    app = create_app()
    with app.app_context():
        try:
            # Connect to the database
            conn = db.engine.connect()
            print('Connected to database')
            
            # Get total count of RDF triples
            res = conn.execute(text('SELECT COUNT(*) FROM rdf_triples'))
            count = res.fetchone()[0]
            print(f'RDF Triple count: {count}')
            
            # Get sample triples
            res = conn.execute(text('SELECT subject, predicate, object FROM rdf_triples LIMIT 5'))
            print('\nSample triples:')
            for r in res:
                print(r)
                
            # Get triples by type - look for Role triples
            print('\nRole-related triples:')
            res = conn.execute(text('''
                SELECT subject, predicate, object FROM rdf_triples 
                WHERE object LIKE '%Role%' OR predicate LIKE '%role%'
                LIMIT 5
            '''))
            for r in res:
                print(r)
                
            # Get principle-related triples
            print('\nPrinciple-related triples:')
            res = conn.execute(text('''
                SELECT subject, predicate, object FROM rdf_triples 
                WHERE object LIKE '%Principle%' OR predicate LIKE '%principle%'
                LIMIT 5
            '''))
            for r in res:
                print(r)
                
            # Get top predicates
            print('\nMost common predicates:')
            res = conn.execute(text('''
                SELECT predicate, COUNT(*) as count FROM rdf_triples 
                GROUP BY predicate ORDER BY count DESC LIMIT 10
            '''))
            for r in res:
                print(f"{r[0]}: {r[1]}")
                
        except Exception as e:
            print(f"Error querying database: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

if __name__ == "__main__":
    main()
