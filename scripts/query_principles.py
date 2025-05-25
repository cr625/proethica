
import psycopg2

conn = psycopg2.connect("dbname=ai_ethical_dm user=postgres password=PASS host=localhost port=5433")
cur = conn.cursor()

print("Checking principle_instantiations table:")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", ["principle_instantiations"])
columns = cur.fetchall()
print("principle_instantiations columns:")
for col in columns:
    print(f"  {col[0]}: {col[1]}")

cur.execute("SELECT COUNT(*) FROM principle_instantiations")
count = cur.fetchone()[0]
print(f"\nNumber of records in principle_instantiations: {count}")

conn.close()

