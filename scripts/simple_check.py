#!/usr/bin/env python3
import os
import sys
import psycopg2
from urllib.parse import urlparse

# Get database URL from .env file
db_url = None
with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), 'r') as f:
    for line in f:
        if line.startswith('DATABASE_URL='):
            db_url = line.strip().split('=', 1)[1]
            break

if not db_url:
    print("DATABASE_URL not found in .env file")
    sys.exit(1)

# Parse the database URL
parsed_url = urlparse(db_url)
dbname = parsed_url.path[1:]  # Remove leading slash
user = parsed_url.username
password = parsed_url.password
host = parsed_url.hostname

print(f"Connecting to database: {dbname} as user {user} on host {host}")

# Connect to the database
try:
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host
    )
    print("Connected to database")
    
    # Create a cursor
    cur = conn.cursor()
    
    # Query the roles table
    cur.execute("SELECT id, name, description, tier, ontology_uri FROM roles")
    roles = cur.fetchall()
    
    print(f"Found {len(roles)} roles:")
    for role in roles:
        print(f"ID: {role[0]}, Name: {role[1]}, Tier: {role[3]}")
        print(f"Description: {role[2]}")
        print(f"Ontology URI: {role[4]}")
        print("-" * 50)
    
    # Close the cursor and connection
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
