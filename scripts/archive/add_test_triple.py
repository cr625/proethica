#!/usr/bin/env python3
import psycopg2

# Create a simple test triple for the first case
conn = psycopg2.connect("dbname=ai_ethical_dm user=postgres password=PASS host=localhost port=5433")
cur = conn.cursor()

# Get a case ID
cur.execute("SELECT id FROM documents WHERE document_type = %s ORDER BY id LIMIT 1", ["case_study"])
case_id = cur.fetchone()[0]

# Insert a simple test triple
cur.execute("""
    INSERT INTO entity_triples (
        subject, predicate, object_uri, is_literal,
        entity_type, entity_id, created_at, updated_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, NOW(), NOW()
    )
""", (
    f"http://proethica.org/case/{case_id}", 
    "http://proethica.org/ontology/engineering-ethics#instantiatesPrinciple",
    "http://proethica.org/ontology/engineering-ethics#ProfessionalIntegrity",
    False, "document", case_id
))

conn.commit()
print(f"Inserted test triple for case ID: {case_id}")

# Check the count
cur.execute("SELECT COUNT(*) FROM entity_triples")
count = cur.fetchone()[0]
print(f"Total entity triples: {count}")

cur.close()
conn.close()

