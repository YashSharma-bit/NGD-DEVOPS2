import psycopg2, os, zipfile, re, xml.etree.ElementTree as ET
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(host='localhost', port=5432, dbname='india_dev_analytics', user='analyst', password='yash123')
conn.autocommit = True
cur = conn.cursor()

# First check how many temp codes exist
cur.execute("SELECT COUNT(*) FROM districts WHERE lgd_district_code LIKE 'T%'")
print('Temp codes in DB:', cur.fetchone()[0])

# Find LGD file
lgd_file = None
for f in os.listdir('.'):
    if 'lgd' in f.lower() and f.endswith('.xlsx'):
        lgd_file = f
        break
print('LGD file:', lgd_file)

# Parse Excel
with zipfile.ZipFile(lgd_file, 'r') as z:
    with z.open('xl/worksheets/sheet1.xml') as f:
        content = f.read().decode('utf-8')

root = ET.fromstring(content)
ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def cn(s):
    s = str(s).upper().strip()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

by_name_sc = {}
for row in root.findall('.//ns:row', ns):
    row_num = int(row.get('r', 0))
    if row_num == 1: continue
    cells = {}
    for cell in row.findall('ns:c', ns):
        ref = cell.get('r', '')
        col = re.sub(r'\d', '', ref)
        t = cell.get('t', '')
        if t == 'inlineStr':
            is_elem = cell.find('ns:is', ns)
            val = ''
            if is_elem is not None:
                t_elem = is_elem.find('ns:t', ns)
                val = t_elem.text if t_elem is not None else ''
        else:
            v_elem = cell.find('ns:v', ns)
            val = v_elem.text if v_elem is not None else ''
        cells[col] = str(val).strip() if val else ''
    if cells.get('D') and cells.get('E'):
        sc = str(int(cells['B'])) if cells.get('B','').isdigit() else cells.get('B','')
        by_name_sc[(cn(cells['E']), sc)] = cells['D']

# Get all districts including temp-coded ones
cur.execute('SELECT d.id, d.district_name, d.lgd_district_code, s.lgd_state_code FROM districts d JOIN states s ON s.id=d.state_id')
districts = cur.fetchall()

# First completely drop the unique constraint temporarily
try:
    cur.execute('ALTER TABLE districts DROP CONSTRAINT IF EXISTS districts_lgd_district_code_key')
    print('Dropped unique constraint')
except Exception as e:
    print('Could not drop constraint:', str(e)[:50])

# Now update all districts with real codes
updated = 0
not_found = []
for dist_id, dist_name, current_code, state_code in districts:
    lgd_sc = str(int(state_code))
    dist_cl = cn(dist_name)
    new_code = by_name_sc.get((dist_cl, lgd_sc))
    if not new_code:
        for (kn, ks), v in by_name_sc.items():
            if ks == lgd_sc and (kn in dist_cl or dist_cl in kn):
                new_code = v
                break
    if new_code:
        cur.execute('UPDATE districts SET lgd_district_code=%s WHERE id=%s', (str(new_code).zfill(4), dist_id))
        updated += 1
    else:
        cur.execute('UPDATE districts SET lgd_district_code=%s WHERE id=%s', ('X'+str(dist_id).zfill(5), dist_id))
        not_found.append(dist_name)

print('Updated:', updated)
print('Not matched:', len(not_found))

# Re-add unique constraint
try:
    cur.execute('ALTER TABLE districts ADD CONSTRAINT districts_lgd_district_code_key UNIQUE (lgd_district_code)')
    print('Re-added unique constraint')
except Exception as e:
    print('Constraint issue:', str(e)[:80])

# Verify
cur.execute("""
    SELECT d.lgd_district_code, d.district_name, s.state_name
    FROM districts d JOIN states s ON s.id=d.state_id
    WHERE d.district_name IN ('Ernakulam','Wayanad','Pune','Chennai','Lucknow','Dibang Valley','Kolkata','Patna')
    ORDER BY d.district_name
""")
print('\nVerification:')
for r in cur.fetchall():
    print('  ' + r[0] + ' | ' + r[1] + ' | ' + r[2])

conn.close()
print('Done')