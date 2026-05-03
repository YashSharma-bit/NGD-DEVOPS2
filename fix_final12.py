import psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
conn.autocommit = True
cur = conn.cursor()

# Fix each duplicate by updating to correct code
fixes = [
    # (district_name, state_name, correct_code)
    ('Gurgaon',           'HARYANA',          '0062'),  # Gurugram
    ('Mewat',             'HARYANA',          '0604'),  # Nuh
    ('Lahul AND Spiti',   'HIMACHAL PRADESH', '0021'),  # Lahaul And Spiti
    ('Kanshiram Nagar',   'UTTAR PRADESH',    '0633'),  # Kasganj
    ('Purba Champaran',   'BIHAR',            '0226'),  # East Champaran
    ('Subarnapur',        'ORISSA',           '0372'),  # Sonepur
    ('Koriya',            'CHHATTISGARH',     '0384'),  # Korea
    ('Ahmadabad',         'GUJARAT',          '0438'),  # Ahmedabad
    ('Dohad',             'GUJARAT',          '0445'),  # Dahod
    ('Kamrup Metropolitan','ASSAM',           '0618'),  # Kamrup Metro
]

for dist_name, state_name, code in fixes:
    cur.execute("""
        UPDATE districts d SET lgd_district_code = %s
        FROM states s
        WHERE s.id = d.state_id
        AND d.district_name = %s
        AND s.state_name = %s
    """, (code, dist_name, state_name))
    print(f"{'OK' if cur.rowcount > 0 else 'NOT FOUND'} | {dist_name} | {state_name} -> {code}")

# Anantapur and Ramanagara - look up what code they currently have vs what's correct
print("\n=== Anantapur and Ramanagara current state ===")
for dist, state in [('Anantapur', 'ANDHRA PRADESH'), ('Ramanagara', 'KARNATAKA'), ('Chittoor', 'ANDHRA PRADESH'), ('Pratapgarh', 'UTTAR PRADESH')]:
    cur.execute("""
        SELECT d.district_name, s.state_name, d.lgd_district_code
        FROM districts d JOIN states s ON s.id = d.state_id
        WHERE d.district_name = %s AND s.state_name = %s
    """, (dist, state))
    r = cur.fetchone()
    if r:
        print(f"  {r[0]} | {r[1]} | code={r[2]}")

# Check remaining duplicates
cur.execute("""
    SELECT lgd_district_code, COUNT(*), array_agg(district_name)
    FROM districts
    GROUP BY lgd_district_code
    HAVING COUNT(*) > 1
    ORDER BY lgd_district_code
""")
dupes = cur.fetchall()
if dupes:
    print(f"\nStill {len(dupes)} duplicates:")
    for r in dupes:
        print(f"  {r[0]} | {r[2]}")
else:
    print("\nNo duplicates!")
    try:
        cur.execute('ALTER TABLE districts ADD CONSTRAINT districts_lgd_district_code_key UNIQUE (lgd_district_code)')
        print("Unique constraint added successfully!")
    except Exception as e:
        print('Constraint error:', str(e)[:100])

conn.close()
print("Done")