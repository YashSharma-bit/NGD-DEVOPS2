import psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
conn.autocommit = True
cur = conn.cursor()

# First, let's see what codes the colliding districts already have
# so we know what codes are actually free to use
check = [
    ('Uttarkashi', 'UTTARAKHAND'),
    ('Hisar', 'HARYANA'),
    ('New Delhi', 'DELHI'),
    ('Mahoba', 'UTTAR PRADESH'),
    ('Sheikhpura', 'BIHAR'),
    ('Kamrup Metropolitan', 'ASSAM'),
    ('Nuapada', 'ORISSA'),
    ('Jabalpur', 'MADHYA PRADESH'),
    ('Anand', 'GUJARAT'),
    ('Jamnagar', 'GUJARAT'),
    ('Chittoor', 'ANDHRA PRADESH'),
    ('Pratapgarh', 'UTTAR PRADESH'),
]

print("=== Current codes of colliding districts ===")
for dist, state in check:
    cur.execute("""
        SELECT d.district_name, s.state_name, d.lgd_district_code
        FROM districts d JOIN states s ON s.id = d.state_id
        WHERE d.district_name = %s AND s.state_name = %s
    """, (dist, state))
    r = cur.fetchone()
    if r:
        print(f"  {r[0]} | {r[1]} | code={r[2]}")

print("\n=== Current codes of our unmatched districts ===")
unmatched = [
    ('Gurgaon', 'HARYANA'),
    ('Mewat', 'HARYANA'),
    ('Lahul AND Spiti', 'HIMACHAL PRADESH'),
    ('Kanshiram Nagar', 'UTTAR PRADESH'),
    ('Purba Champaran', 'BIHAR'),
    ('Subarnapur', 'ORISSA'),
    ('Koriya', 'CHHATTISGARH'),
    ('Ahmadabad', 'GUJARAT'),
    ('Dohad', 'GUJARAT'),
    ('Anantapur', 'ANDHRA PRADESH'),
    ('Ramanagara', 'KARNATAKA'),
    ('Kamrup', 'ASSAM'),
]
for dist, state in unmatched:
    cur.execute("""
        SELECT d.district_name, s.state_name, d.lgd_district_code
        FROM districts d JOIN states s ON s.id = d.state_id
        WHERE d.district_name = %s AND s.state_name = %s
    """, (dist, state))
    r = cur.fetchone()
    if r:
        print(f"  {r[0]} | {r[1]} | code={r[2]}")

conn.close()