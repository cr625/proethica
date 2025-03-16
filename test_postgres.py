import psycopg2

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="ai_ethical_dm",
    user="postgres",
    password="PASS"
)

# Create a cursor
cur = conn.cursor()

# Execute a query
cur.execute("SELECT 1")
result = cur.fetchone()
print(f"Result: {result}")

# Close the cursor and connection
cur.close()
conn.close()
