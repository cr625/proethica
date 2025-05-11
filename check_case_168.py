import psycopg2, json

# Connect to database
conn = psycopg2.connect("dbname=ai_ethical_dm user=postgres password=PASS host=localhost port=5433")
cur = conn.cursor()

# Get case details
cur.execute("SELECT id, title, content, doc_metadata FROM documents WHERE id = 168")
row = cur.fetchone()

if row:
    case_id, title, content, metadata = row
    print(f"Case ID: {case_id}")
    print(f"Title: {title}")
    print("\nContent Preview (first 500 chars):\n{}".format(content[:500] if content else 'No content'))
    
    # Format metadata
    if metadata:
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
                print("\nMetadata:")
                print(json.dumps(metadata, indent=2))
            except:
                print("\nMetadata: Could not parse JSON")
        else:
            print("\nMetadata:")
            print(json.dumps(metadata, indent=2) if metadata else 'No metadata')
    else:
        print("\nNo metadata available")
else:
    print("Case not found")

# Close connection
cur.close()
conn.close()
