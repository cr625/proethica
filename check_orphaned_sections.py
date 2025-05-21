#!/usr/bin/env python
"""
Simple script to verify if there are any orphaned document sections in the database.
This validates that our cascade delete fix is working properly.
"""

from sqlalchemy import create_engine, text

# Create connection to database
db_url = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
engine = create_engine(db_url)
conn = engine.connect()

# Check which documents have been deleted without their sections
print("Checking for orphaned document sections...")
orphan_query = text("""
    SELECT ds.id, ds.document_id, ds.section_id, ds.section_type
    FROM document_sections ds
    LEFT JOIN documents d ON ds.document_id = d.id
    WHERE d.id IS NULL
    LIMIT 10
""")

orphans = conn.execute(orphan_query).fetchall()

if orphans:
    print(f"\n❌ FAILED: Found {len(orphans)} orphaned sections:")
    for orphan in orphans:
        print(f"  - Orphaned section {orphan.id}: document_id={orphan.document_id}, "
              f"section_id={orphan.section_id}, type={orphan.section_type}")
    print("\nThe cascade delete fix did NOT work correctly.")
else:
    print("\n✅ SUCCESS: No orphaned sections found!")
    print("The cascade delete fix is working correctly!")

# Check document section counts for the most recent documents
print("\nMost recent documents with section counts:")
recent_docs_query = text("""
    SELECT d.id, d.title, COUNT(ds.id) AS section_count
    FROM documents d
    LEFT JOIN document_sections ds ON d.id = ds.document_id
    GROUP BY d.id, d.title
    ORDER BY d.id DESC
    LIMIT 5
""")

recent_docs = conn.execute(recent_docs_query).fetchall()
for doc in recent_docs:
    print(f"  - Document {doc.id}: '{doc.title}' - {doc.section_count} sections")

conn.close()
