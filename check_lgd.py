import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
cur = conn.cursor()

cur.execute("""
    SELECT d.lgd_district_code, d.district_name, s.state_name
    FROM districts d JOIN states s ON s.id=d.state_id
    WHERE d.district_name IN ('Ernakulam','Wayanad','Pune','Chennai','Lucknow','Kolkata','Patna')
    ORDER BY d.district_name
""")
print('Current LGD codes:')
for r in cur.fetchall():
    print('  ' + r[0] + ' | ' + r[1] + ' | ' + r[2])

cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code LIKE 'T%'")
print('Temp codes (T...): ' + str(cur.fetchone()[0]))

cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code LIKE 'X%'")
print('Unmatched codes (X...): ' + str(cur.fetchone()[0]))

cur.execute("SELECT COUNT(*) FROM districts")
print('Total districts: ' + str(cur.fetchone()[0]))

conn.close()