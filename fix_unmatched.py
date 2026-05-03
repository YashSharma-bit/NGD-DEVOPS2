import psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
conn.autocommit = True
cur = conn.cursor()

# Manual mapping: (district_name_in_db, state_name_in_db) -> lgd_district_code
manual_map = {
    # Telangana districts (stored as Andhra Pradesh in old data)
    ('Adilabad', 'ANDHRA PRADESH'): '0519',
    ('Anantapur', 'ANDHRA PRADESH'): '0516',
    ('Hyderabad', 'ANDHRA PRADESH'): '0520',
    ('Karimnagar', 'ANDHRA PRADESH'): '0521',
    ('Khammam', 'ANDHRA PRADESH'): '0522',
    ('Mahbubnagar', 'ANDHRA PRADESH'): '0523',
    ('Medak', 'ANDHRA PRADESH'): '0524',
    ('Nalgonda', 'ANDHRA PRADESH'): '0525',
    ('Nizamabad', 'ANDHRA PRADESH'): '0526',
    ('Rangareddy', 'ANDHRA PRADESH'): '0527',
    ('Warangal', 'ANDHRA PRADESH'): '0528',

    # Assam
    ('Karimganj', 'ASSAM'): '0110',
    ('Morigaon', 'ASSAM'): '0115',

    # Bihar
    ('Purba Champaran', 'BIHAR'): '0213',

    # Chhattisgarh
    ('Koriya', 'CHHATTISGARH'): '0407',

    # Dadra & Daman & Diu
    ('Dadra AND Nagar Haveli', 'DADRA AND NAGAR HAVELI'): '0626',
    ('Daman', 'DAMAN AND DIU'): '0627',
    ('Diu', 'DAMAN AND DIU'): '0628',

    # Gujarat
    ('Ahmadabad', 'GUJARAT'): '0469',
    ('Dohad', 'GUJARAT'): '0474',

    # Haryana
    ('Gurgaon', 'HARYANA'): '0648',
    ('Mewat', 'HARYANA'): '0651',

    # Himachal Pradesh
    ('Lahul AND Spiti', 'HIMACHAL PRADESH'): '0582',

    # J&K
    ('Badgam', 'JAMMU AND KASHMIR'): '0001',
    ('Bandipore', 'JAMMU AND KASHMIR'): '0002',
    ('Baramula', 'JAMMU AND KASHMIR'): '0003',
    ('Kargil', 'JAMMU AND KASHMIR'): '0004',
    ('Leh(Ladakh)', 'JAMMU AND KASHMIR'): '0005',
    ('Punch', 'JAMMU AND KASHMIR'): '0006',
    ('Shupiyan', 'JAMMU AND KASHMIR'): '0007',

    # Jharkhand
    ('Kodarma', 'JHARKHAND'): '0388',
    ('Pashchimi Singhbhum', 'JHARKHAND'): '0389',
    ('Purbi Singhbhum', 'JHARKHAND'): '0390',
    ('Sahibganj', 'JHARKHAND'): '0391',

    # Karnataka (renamed districts)
    ('Bangalore', 'KARNATAKA'): '0572',
    ('Bangalore Rural', 'KARNATAKA'): '0573',
    ('Belgaum', 'KARNATAKA'): '0557',
    ('Bellary', 'KARNATAKA'): '0561',
    ('Bijapur', 'KARNATAKA'): '0563',
    ('Chikmagalur', 'KARNATAKA'): '0566',
    ('Gulbarga', 'KARNATAKA'): '0569',
    ('Mysore', 'KARNATAKA'): '0576',
    ('Ramanagara', 'KARNATAKA'): '0579',
    ('Shimoga', 'KARNATAKA'): '0580',
    ('Tumkur', 'KARNATAKA'): '0581',

    # Madhya Pradesh
    ('Hoshangabad', 'MADHYA PRADESH'): '0435',

    # Maharashtra
    ('Ahmadnagar', 'MAHARASHTRA'): '0495',
    ('Aurangabad', 'MAHARASHTRA'): '0497',
    ('Bid', 'MAHARASHTRA'): '0498',
    ('Buldana', 'MAHARASHTRA'): '0499',
    ('Gondiya', 'MAHARASHTRA'): '0502',
    ('Osmanabad', 'MAHARASHTRA'): '0507',
    ('Raigarh', 'MAHARASHTRA'): '0508',

    # Meghalaya
    ('Ribhoi', 'MEGHALAYA'): '0276',

    # Mizoram
    ('Saiha', 'MIZORAM'): '0285',

    # Odisha (stored as Orissa)
    ('Anugul', 'ORISSA'): '0327',
    ('Baleshwar', 'ORISSA'): '0328',
    ('Baudh', 'ORISSA'): '0329',
    ('Debagarh', 'ORISSA'): '0330',
    ('Jajapur', 'ORISSA'): '0331',
    ('Kendujhar', 'ORISSA'): '0332',
    ('Nabarangapur', 'ORISSA'): '0333',
    ('Subarnapur', 'ORISSA'): '0334',

    # Puducherry
    ('Mahe', 'PONDICHERRY'): '0637',
    ('PONDICHERRY', 'PONDICHERRY'): '0638',
    ('Yanam', 'PONDICHERRY'): '0639',

    # Punjab
    ('Firozpur', 'PUNJAB'): '0601',
    ('Sahibzada Ajit Singh Nagar', 'PUNJAB'): '0608',

    # Rajasthan
    ('Chittaurgarh', 'RAJASTHAN'): '0693',
    ('Dhaulpur', 'RAJASTHAN'): '0694',

    # Sikkim
    ('East District', 'SIKKIM'): '0294',
    ('North  District', 'SIKKIM'): '0295',
    ('South District', 'SIKKIM'): '0296',
    ('West District', 'SIKKIM'): '0297',

    # Uttar Pradesh (renamed)
    ('Allahabad', 'UTTAR PRADESH'): '0155',
    ('Faizabad', 'UTTAR PRADESH'): '0158',
    ('Jyotiba Phule Nagar', 'UTTAR PRADESH'): '0164',
    ('Kanshiram Nagar', 'UTTAR PRADESH'): '0166',
    ('Mahamaya Nagar', 'UTTAR PRADESH'): '0168',
    ('Sant Ravidas Nagar (Bhadohi)', 'UTTAR PRADESH'): '0175',

    # Uttarakhand
    ('Hardwar', 'UTTARAKHAND'): '0200',

    # West Bengal
    ('Barddhaman', 'WEST BENGAL'): '0316',
    ('Darjiling', 'WEST BENGAL'): '0317',
    ('Haora', 'WEST BENGAL'): '0318',
    ('Hugli', 'WEST BENGAL'): '0319',
    ('Koch Bihar', 'WEST BENGAL'): '0320',
    ('North Twenty Four Parganas', 'WEST BENGAL'): '0321',
    ('Puruliya', 'WEST BENGAL'): '0322',
    ('South Twenty Four Parganas', 'WEST BENGAL'): '0323',
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

print(f"Updated: {updated}")
if not_found:
    print("Still not found:")
    for x in not_found:
        print(" ", x)

# Re-add unique constraint
try:
    cur.execute('ALTER TABLE districts ADD CONSTRAINT districts_lgd_district_code_key UNIQUE (lgd_district_code)')
    print('Unique constraint added successfully')
except Exception as e:
    print('Constraint issue:', str(e)[:120])
    # Show remaining duplicates
    cur.execute("""
        SELECT lgd_district_code, COUNT(*), array_agg(district_name)
        FROM districts GROUP BY lgd_district_code HAVING COUNT(*) > 1
    """)
    rows = cur.fetchall()
    if rows:
        print("Remaining duplicates:")
        for r in rows:
            print(f"  {r[0]} | {r[2]}")

conn.close()
print('Done')