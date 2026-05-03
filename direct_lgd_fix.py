import os, zipfile, re, xml.etree.ElementTree as ET
import psycopg2, psycopg2.extras
from dotenv import load_dotenv
load_dotenv()

# Find LGD file
lgd_file = None
for f in os.listdir('.'):
    if 'lgd' in f.lower() and f.endswith('.xlsx'):
        lgd_file = f
        break
print("Using file: " + str(lgd_file))

# Parse Excel
with zipfile.ZipFile(lgd_file, 'r') as z:
    with z.open('xl/worksheets/sheet1.xml') as f:
        content = f.read().decode('utf-8')

root = ET.fromstring(content)
ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

lgd_rows = []
for row in root.findall('.//ns:row', ns):
    row_num = int(row.get('r', 0))
    if row_num == 1:
        continue
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
        lgd_rows.append({
            'state_code': cells.get('B','').strip(),
            'lgd_code':   cells.get('D','').strip(),
            'name':       cells.get('E','').strip(),
            'census_j':   cells.get('J','').strip(),
        })

print("Parsed " + str(len(lgd_rows)) + " rows from Excel")

# Build lookups
def cn(s):
    s = str(s).upper().strip()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# Our DB state codes (01-35) map to LGD state codes (1-35)
by_name_sc = {}  # (clean_dist_name, lgd_state_code_no_leading_zero) -> lgd_district_code
by_census_j = {} # census_j_code_padded -> lgd_district_code

for r in lgd_rows:
    sc = str(int(r['state_code'])) if r['state_code'].isdigit() else r['state_code']
    name_clean = cn(r['name'])
    lgd_code = r['lgd_code']
    cj = r['census_j'].strip()

    by_name_sc[(name_clean, sc)] = lgd_code
    if cj and cj != '000' and cj != '0':
        by_census_j[cj.zfill(4)] = lgd_code

print("Name+state lookup: " + str(len(by_name_sc)) + " entries")

# Connect DB
conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST","localhost"),
    port=5432,
    dbname=os.getenv("POSTGRES_DB","india_dev_analytics"),
    user=os.getenv("POSTGRES_USER","analyst"),
    password=os.getenv("POSTGRES_PASSWORD","yash123")
)
conn.autocommit = False
cur = conn.cursor()

cur.execute("""
    SELECT d.id, d.district_name, d.lgd_district_code,
           s.lgd_state_code, s.state_name
    FROM districts d
    JOIN states s ON s.id = d.state_id
    ORDER BY s.lgd_state_code, d.district_name
""")
districts = cur.fetchall()
print("Districts in DB: " + str(len(districts)))

# Match each district
updates = []
not_found = []

for dist_id, dist_name, current_code, our_state_code, state_name in districts:
    lgd_sc = str(int(our_state_code))
    dist_cl = cn(dist_name)
    new_code = None

    # Try exact name + state code match
    new_code = by_name_sc.get((dist_cl, lgd_sc))

    # Try partial match
    if not new_code:
        for (kn, ks), v in by_name_sc.items():
            if ks == lgd_sc:
                if kn in dist_cl or dist_cl in kn:
                    new_code = v
                    break

    # Try removing common suffixes
    if not new_code:
        simplified = re.sub(r'\s*(DISTRICT|RURAL|URBAN|NAGAR)\s*$', '', dist_cl).strip()
        new_code = by_name_sc.get((simplified, lgd_sc))

    if new_code:
        updates.append((dist_id, str(new_code).zfill(4), current_code, dist_name))
    else:
        not_found.append(dist_name + " (" + state_name + ")")

print("Matched: " + str(len(updates)))
print("Not matched: " + str(len(not_found)))
if not_found:
    for d in not_found[:15]:
        print("  - " + d)

# Apply - first set temp codes
print("\nSetting temp codes...")
for dist_id, new_code, old_code, name in updates:
    try:
        cur.execute("UPDATE districts SET lgd_district_code=%s WHERE id=%s", ("T"+str(dist_id), dist_id))
    except:
        conn.rollback()
conn.commit()

# Set real codes
applied = 0
skipped = []
for dist_id, new_code, old_code, name in updates:
    try:
        cur.execute("UPDATE districts SET lgd_district_code=%s WHERE id=%s", (new_code, dist_id))
        applied += 1
    except Exception as e:
        conn.rollback()
        skipped.append(name + " -> " + new_code + " (conflict)")
conn.commit()

print("Applied: " + str(applied))
if skipped:
    print("Skipped (conflicts):")
    for s in skipped[:10]:
        print("  " + s)

# Relink dev index using name matching
print("\nRelinking development index...")
cur.execute("SELECT lgd_district_code, id, district_name FROM districts")
dist_rows = cur.fetchall()
dist_map_code = {r[0]: r[1] for r in dist_rows}
dist_map_name = {cn(r[2]): r[1] for r in dist_rows}

import pandas as pd, math
from pathlib import Path
idx_path = Path("data/processed/development_index.parquet")
if idx_path.exists():
    idx = pd.read_parquet(idx_path)
    cur.execute("DELETE FROM development_index")
    conn.commit()
    rows = []
    for _, row in idx.iterrows():
        # Try by district name first (most reliable after code changes)
        dname = cn(str(row.get("district_name","")))
        dist_id = dist_map_name.get(dname)
        if dist_id is None:
            old_code = str(row.get("lgd_district_code","")).zfill(4)
            dist_id = dist_map_code.get(old_code)
        if dist_id is None:
            continue
        def c(v):
            if v is None: return None
            if isinstance(v, float) and math.isnan(v): return None
            return v
        rows.append((dist_id, c(row.get("composite_score")),
                    c(row.get("composite_rank")), c(row.get("composite_percentile")),
                    c(row.get("cluster_id")), str(row.get("cluster_label",""))))
    psycopg2.extras.execute_batch(
        cur,
        "INSERT INTO development_index (district_id,composite_score,composite_rank,composite_percentile,cluster_id,cluster_label) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        rows
    )
    conn.commit()
    print("Dev index relinked: " + str(len(rows)) + " rows")

try:
    conn.autocommit = True
    conn.cursor().execute("REFRESH MATERIALIZED VIEW state_aggregates")
    print("View refreshed")
except Exception as e:
    print("View: " + str(e))

conn.close()

# Verify
print("\n" + "="*55)
print("VERIFICATION")
print("="*55)
conn2 = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST","localhost"), port=5432,
    dbname=os.getenv("POSTGRES_DB","india_dev_analytics"),
    user=os.getenv("POSTGRES_USER","analyst"),
    password=os.getenv("POSTGRES_PASSWORD","yash123")
)
cur2 = conn2.cursor()
cur2.execute("""
    SELECT d.lgd_district_code, d.district_name, s.state_name
    FROM districts d JOIN states s ON s.id=d.state_id
    WHERE d.district_name IN
      ('Ernakulam','Wayanad','Pune','Mumbai City','Chennai',
       'Lucknow','Bangalore Urban','Kolkata','Patna','Jaipur',
       'Dibang Valley','South Andamans','Nicobars')
    ORDER BY d.district_name
""")
print("\nKey district codes after update:")
for r in cur2.fetchall():
    print("  " + r[0] + " | " + r[1] + " | " + r[2])
conn2.close()

print("\nDONE. Restart your API:")
print("uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")