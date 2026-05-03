import psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
conn.autocommit = True
cur = conn.cursor()

# First remove the wrong codes we assigned previously, so no duplicates block us
cur.execute("UPDATE districts SET lgd_district_code = 'X' || id::text WHERE lgd_district_code LIKE 'X%'")

# mapping: (district_name_in_db, state_name_in_db) -> correct_lgd_code
manual_map = {
    # Telangana (stored as Andhra Pradesh in old data)
    ('Adilabad',    'ANDHRA PRADESH'): '0501',
    ('Hyderabad',   'ANDHRA PRADESH'): '0507',
    ('Karimnagar',  'ANDHRA PRADESH'): '0508',
    ('Khammam',     'ANDHRA PRADESH'): '0509',
    ('Mahbubnagar', 'ANDHRA PRADESH'): '0512',
    ('Medak',       'ANDHRA PRADESH'): '0513',
    ('Nalgonda',    'ANDHRA PRADESH'): '0514',
    ('Nizamabad',   'ANDHRA PRADESH'): '0516',
    ('Rangareddy',  'ANDHRA PRADESH'): '0518',
    ('Warangal',    'ANDHRA PRADESH'): '0522',
    ('Anantapur',   'ANDHRA PRADESH'): '0503',  # stayed in AP

    # Assam
    ('Karimganj', 'ASSAM'): '0293',  # Sribhumi/Karimganj old code
    ('Morigaon',  'ASSAM'): '0296',

    # Bihar
    ('Purba Champaran', 'BIHAR'): '0219',

    # Chhattisgarh
    ('Koriya', 'CHHATTISGARH'): '0411',

    # Dadra & Nagar Haveli and Daman & Diu (merged state)
    ('Dadra AND Nagar Haveli', 'DADRA AND NAGAR HAVELI'): '0465',
    ('Daman', 'DAMAN AND DIU'): '0463',
    ('Diu',   'DAMAN AND DIU'): '0464',

    # Gujarat
    ('Ahmadabad', 'GUJARAT'): '0440',
    ('Dohad',     'GUJARAT'): '0447',

    # Haryana
    ('Gurgaon', 'HARYANA'): '0057',
    ('Mewat',   'HARYANA'): '0063',

    # Himachal Pradesh
    ('Lahul AND Spiti', 'HIMACHAL PRADESH'): '0079',

    # J&K
    ('Badgam',     'JAMMU AND KASHMIR'): '0002',
    ('Bandipore',  'JAMMU AND KASHMIR'): '0623',
    ('Baramula',   'JAMMU AND KASHMIR'): '0003',
    ('Kargil',     'JAMMU AND KASHMIR'): '0006',   # now Ladakh but keep mapping
    ('Leh(Ladakh)','JAMMU AND KASHMIR'): '0009',
    ('Punch',      'JAMMU AND KASHMIR'): '0010',
    ('Shupiyan',   'JAMMU AND KASHMIR'): '0625',

    # Jharkhand
    ('Kodarma',           'JHARKHAND'): '0334',
    ('Pashchimi Singhbhum','JHARKHAND'): '0343',
    ('Purbi Singhbhum',   'JHARKHAND'): '0327',
    ('Sahibganj',         'JHARKHAND'): '0340',

    # Karnataka (old names -> new LGD names)
    ('Bangalore',       'KARNATAKA'): '0525',  # Bengaluru Urban
    ('Bangalore Rural', 'KARNATAKA'): '0526',  # Bengaluru Rural
    ('Belgaum',         'KARNATAKA'): '0527',  # Belagavi
    ('Bellary',         'KARNATAKA'): '0528',  # Ballari
    ('Bijapur',         'KARNATAKA'): '0530',  # Vijayapura
    ('Chikmagalur',     'KARNATAKA'): '0532',  # Chikkamagaluru
    ('Gulbarga',        'KARNATAKA'): '0538',  # Kalaburagi
    ('Mysore',          'KARNATAKA'): '0545',  # Mysuru
    ('Ramanagara',      'KARNATAKA'): '0629',
    ('Shimoga',         'KARNATAKA'): '0547',  # Shivamogga
    ('Tumkur',          'KARNATAKA'): '0548',  # Tumakuru

    # Madhya Pradesh
    ('Hoshangabad', 'MADHYA PRADESH'): '0409',  # Narmadapuram

    # Maharashtra (old names -> new LGD names)
    ('Ahmadnagar', 'MAHARASHTRA'): '0466',  # Ahilyanagar
    ('Aurangabad', 'MAHARASHTRA'): '0469',  # Chhatrapati Sambhajinagar
    ('Bid',        'MAHARASHTRA'): '0470',  # Beed
    ('Buldana',    'MAHARASHTRA'): '0472',  # Buldhana
    ('Gondiya',    'MAHARASHTRA'): '0476',  # Gondia
    ('Osmanabad',  'MAHARASHTRA'): '0488',  # Dharashiv
    ('Raigarh',    'MAHARASHTRA'): '0491',  # Raigad

    # Meghalaya
    ('Ribhoi', 'MEGHALAYA'): '0276',  # Ri Bhoi

    # Mizoram
    ('Saiha', 'MIZORAM'): '0267',  # Siaha

    # Odisha (stored as Orissa)
    ('Anugul',      'ORISSA'): '0344',
    ('Baleshwar',   'ORISSA'): '0346',
    ('Baudh',       'ORISSA'): '0349',
    ('Debagarh',    'ORISSA'): '0351',
    ('Jajapur',     'ORISSA'): '0356',
    ('Kendujhar',   'ORISSA'): '0361',
    ('Nabarangapur','ORISSA'): '0366',
    ('Subarnapur',  'ORISSA'): '0368',

    # Puducherry
    ('Mahe',        'PONDICHERRY'): '0599',
    ('PONDICHERRY', 'PONDICHERRY'): '0600',
    ('Yanam',       'PONDICHERRY'): '0601',

    # Punjab
    ('Firozpur',                  'PUNJAB'): '0031',
    ('Sahibzada Ajit Singh Nagar','PUNJAB'): '0608',  # S.A.S Nagar

    # Rajasthan
    ('Chittaurgarh', 'RAJASTHAN'): '0095',
    ('Dhaulpur',     'RAJASTHAN'): '0098',

    # Sikkim — LGD now has district names not North/South/East/West
    ('East District',  'SIKKIM'): '0225',  # Gangtok
    ('North  District','SIKKIM'): '0226',  # Mangan
    ('South District', 'SIKKIM'): '0227',  # Namchi
    ('West District',  'SIKKIM'): '0228',  # Gyalshing

    # Uttar Pradesh (renamed districts)
    ('Allahabad',                  'UTTAR PRADESH'): '0120',  # Prayagraj
    ('Faizabad',                   'UTTAR PRADESH'): '0140',  # Ayodhya
    ('Jyotiba Phule Nagar',        'UTTAR PRADESH'): '0154',  # Amroha
    ('Kanshiram Nagar',            'UTTAR PRADESH'): '0165',
    ('Mahamaya Nagar',             'UTTAR PRADESH'): '0163',  # Hathras
    ('Sant Ravidas Nagar (Bhadohi)','UTTAR PRADESH'): '0179',

    # Uttarakhand
    ('Hardwar', 'UTTARAKHAND'): '0050',  # Haridwar

    # West Bengal
    ('Barddhaman',              'WEST BENGAL'): '0306',  # Purba Bardhaman
    ('Darjiling',               'WEST BENGAL'): '0309',
    ('Haora',                   'WEST BENGAL'): '0313',
    ('Hugli',                   'WEST BENGAL'): '0312',
    ('Koch Bihar',              'WEST BENGAL'): '0308',
    ('North Twenty Four Parganas','WEST BENGAL'): '0303',
    ('Puruliya',                'WEST BENGAL'): '0321',
    ('South Twenty Four Parganas','WEST BENGAL'): '0304',
}

updated = 0
not_found = []

for (dist_name, state_name), code in manual_map.items():
    cur.execute("""
        UPDATE districts d SET lgd_district_code = %s
        FROM states s
        WHERE s.id = d.state_id
        AND d.district_name = %s
        AND s.state_name = %s
    """, (code, dist_name, state_name))
    if cur.rowcount > 0:
        updated += 1
    else:
        not_found.append(f"{dist_name} | {state_name}")

print(f"Updated: {updated}/{len(manual_map)}")

if not_found:
    print("\nNot found in DB (check spelling):")
    for x in not_found:
        print(" ", x)

# Check duplicates before trying constraint
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

# Final summary
cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code LIKE 'X%'")
print(f"\nRemaining X-coded (unresolved): {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code NOT LIKE 'X%'")
print(f"Properly coded districts: {cur.fetchone()[0]}")

conn.close()
print("Done")