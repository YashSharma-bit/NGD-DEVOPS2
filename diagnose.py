import psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
cur = conn.cursor()

# Show duplicates
print("=== DUPLICATE CODES ===")
cur.execute("""
    SELECT lgd_district_code, COUNT(*), array_agg(district_name)
    FROM districts
    GROUP BY lgd_district_code
    HAVING COUNT(*) > 1
    ORDER BY lgd_district_code
""")
for r in cur.fetchall():
    print(f"  {r[0]} | count={r[1]} | {r[2]}")

# Show unmatched
print("\n=== UNMATCHED DISTRICTS (X codes) ===")
cur.execute("""
    SELECT d.lgd_district_code, d.district_name, s.state_name
    FROM districts d JOIN states s ON s.id = d.state_id
    WHERE d.lgd_district_code LIKE 'X%'
    ORDER BY s.state_name, d.district_name
""")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]} | {r[2]}")

conn.close()