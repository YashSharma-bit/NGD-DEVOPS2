import psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
cur = conn.cursor()

print("=== SUMMARY ===")
cur.execute("SELECT COUNT(*) FROM districts")
print(f"Total districts: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code LIKE 'X%'")
print(f"X-coded (unresolved): {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code LIKE 'T%'")
print(f"Temp-coded: {cur.fetchone()[0]}")

cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT lgd_district_code FROM districts
        GROUP BY lgd_district_code HAVING COUNT(*) > 1
    ) t
""")
print(f"Duplicate codes: {cur.fetchone()[0]}")

print("\n=== ALL DISTRICTS BY STATE ===")
cur.execute("""
    SELECT s.state_name, d.district_name, d.lgd_district_code
    FROM districts d JOIN states s ON s.id = d.state_id
    ORDER BY s.state_name, d.district_name
""")
current_state = None
for state, dist, code in cur.fetchall():
    if state != current_state:
        print(f"\n{state}")
        current_state = state
    print(f"  {code} | {dist}")

conn.close()