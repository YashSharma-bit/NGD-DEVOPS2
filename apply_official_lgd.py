"""
apply_official_lgd.py
---------------------
Applies 100% official LGD codes from the government Excel file.
Place this file in your project folder alongside lgd_official.xlsx

Run: python apply_official_lgd.py
"""

import csv
import os
import re
import zipfile
import xml.etree.ElementTree as ET
import math
from pathlib import Path

import psycopg2
import psycopg2.extras
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Step 1: Parse the official LGD Excel file ────────────────

LGD_FILE = "LGD_-_Local_Government_Directory__Government_of_India.xlsx"
if not os.path.exists(LGD_FILE):
    # Try alternate names
    for fname in os.listdir("."):
        if "LGD" in fname.upper() and fname.endswith(".xlsx"):
            LGD_FILE = fname
            break

print("Reading official LGD file: " + LGD_FILE)

with zipfile.ZipFile(LGD_FILE, 'r') as z:
    with z.open('xl/worksheets/sheet1.xml') as f:
        content = f.read().decode('utf-8')

root = ET.fromstring(content)
ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

lgd_data = []
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
            if is_elem is not None:
                t_elem = is_elem.find('ns:t', ns)
                val = t_elem.text if t_elem is not None else ''
            else:
                val = ''
        else:
            v_elem = cell.find('ns:v', ns)
            val = v_elem.text if v_elem is not None else ''
        cells[col] = str(val).strip() if val else ''

    if cells.get('D') and cells.get('E'):
        lgd_data.append({
            'state_code':        cells.get('B','').strip(),
            'state_name':        cells.get('C','').strip(),
            'lgd_district_code': cells.get('D','').strip(),
            'district_name':     cells.get('E','').strip(),
            'census_2011_code':  cells.get('J','').strip(),
        })

print("Parsed " + str(len(lgd_data)) + " districts from official LGD file")

# ── Step 2: Build lookup tables ──────────────────────────────

STATE_CODE_MAP = {
    "1":"JAMMU AND KASHMIR","2":"HIMACHAL PRADESH","3":"PUNJAB",
    "4":"CHANDIGARH","5":"UTTARAKHAND","6":"HARYANA","7":"NCT OF DELHI",
    "8":"RAJASTHAN","9":"UTTAR PRADESH","10":"BIHAR","11":"SIKKIM",
    "12":"ARUNACHAL PRADESH","13":"NAGALAND","14":"MANIPUR","15":"MIZORAM",
    "16":"TRIPURA","17":"MEGHALAYA","18":"ASSAM","19":"WEST BENGAL",
    "20":"JHARKHAND","21":"ORISSA","22":"CHHATTISGARH","23":"MADHYA PRADESH",
    "24":"GUJARAT","25":"DAMAN AND DIU","26":"DADRA AND NAGAR HAVELI",
    "27":"MAHARASHTRA","28":"ANDHRA PRADESH","29":"KARNATAKA","30":"GOA",
    "31":"LAKSHADWEEP","32":"KERALA","33":"TAMIL NADU","34":"PONDICHERRY",
    "35":"ANDAMAN AND NICOBAR ISLANDS",
}

def clean(s):
    s = str(s).upper().strip()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

by_census  = {}   # census_2011_code -> lgd_code
by_name_sc = {}   # (dist_name_upper, state_code) -> lgd_code
by_name_sn = {}   # (dist_name_upper, state_name_upper) -> lgd_code

for row in lgd_data:
    sc       = row['state_code'].strip()
    dc       = clean(row['district_name'])
    lgd_code = row['lgd_district_code'].strip()
    cen      = row['census_2011_code'].strip()
    sname    = STATE_CODE_MAP.get(sc, "")

    by_name_sc[(dc, sc)] = lgd_code
    if sname:
        by_name_sn[(dc, sname)] = lgd_code
    if cen:
        by_census[cen.zfill(4)] = lgd_code

print("Census code lookup: " + str(len(by_census)) + " entries")
print("Name lookup: " + str(len(by_name_sn)) + " entries")

# ── Step 3: Connect to DB ────────────────────────────────────

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST","localhost"),
    port=int(os.getenv("POSTGRES_PORT",5432)),
    dbname=os.getenv("POSTGRES_DB","india_dev_analytics"),
    user=os.getenv("POSTGRES_USER","analyst"),
    password=os.getenv("POSTGRES_PASSWORD","yash123")
)
conn.autocommit = False
cur = conn.cursor()

cur.execute("""
    SELECT d.id, d.district_name, d.census_district_code,
           d.lgd_district_code, s.state_name, s.lgd_state_code
    FROM districts d
    JOIN states s ON s.id = d.state_id
    ORDER BY s.lgd_state_code, d.district_name
""")
districts = cur.fetchall()
print("\nDistricts in DB: " + str(len(districts)))

# ── Step 4: Match each district to official LGD code ─────────

updates = []
not_found = []

for dist_id, dist_name, census_code, current_lgd, state_name, our_state_code in districts:
    lgd_sc   = str(int(our_state_code))
    dist_cl  = clean(dist_name)
    state_cl = clean(state_name)
    new_code = None

    # Method 1: Census 2011 code (most accurate)
    if census_code:
        new_code = by_census.get(str(census_code).zfill(4))

    # Method 2: District name + state code
    if not new_code:
        new_code = by_name_sc.get((dist_cl, lgd_sc))

    # Method 3: District name + state name
    if not new_code:
        new_code = by_name_sn.get((dist_cl, state_cl))

    # Method 4: Partial match within same state
    if not new_code:
        for (kd, ks), v in by_name_sc.items():
            if ks == lgd_sc and (kd in dist_cl or dist_cl in kd):
                new_code = v
                break

    if new_code:
        updates.append((dist_id, str(new_code).zfill(4), current_lgd))
    else:
        not_found.append(dist_name + " | " + state_name)

print("Matched: " + str(len(updates)) + " / " + str(len(districts)))
if not_found:
    print("Not matched (" + str(len(not_found)) + "):")
    for d in not_found[:20]:
        print("  - " + d)

# ── Step 5: Apply updates ─────────────────────────────────────

print("\nApplying updates...")

# First set temp codes to avoid unique constraint conflicts
for dist_id, new_code, old_code in updates:
    try:
        cur.execute("UPDATE districts SET lgd_district_code=%s WHERE id=%s",
                   ("TMP" + str(dist_id), dist_id))
    except:
        conn.rollback()
conn.commit()

# Now set real LGD codes
applied = 0
for dist_id, new_code, old_code in updates:
    try:
        cur.execute("UPDATE districts SET lgd_district_code=%s WHERE id=%s",
                   (new_code, dist_id))
        applied += 1
    except Exception as e:
        conn.rollback()
        print("  Skip conflict: " + str(e)[:60])
conn.commit()
print("Applied: " + str(applied) + " official LGD codes")

# ── Step 6: Relink development index ─────────────────────────

print("\nRelinking development index...")
cur.execute("SELECT lgd_district_code, id FROM districts")
dist_map = {r[0]: r[1] for r in cur.fetchall()}

idx_path = Path("data/processed/development_index.parquet")
if idx_path.exists():
    idx = pd.read_parquet(idx_path)
    cur.execute("DELETE FROM development_index")
    conn.commit()
    rows = []
    for _, row in idx.iterrows():
        old_census = str(row.get("lgd_district_code","")).zfill(4)
        new_lgd    = by_census.get(old_census)
        new_padded = str(new_lgd).zfill(4) if new_lgd else old_census
        dist_id    = dist_map.get(new_padded) or dist_map.get(old_census)
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
        """INSERT INTO development_index
             (district_id,composite_score,composite_rank,
              composite_percentile,cluster_id,cluster_label)
           VALUES (%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        rows
    )
    conn.commit()
    print("Dev index relinked: " + str(len(rows)) + " rows")

# ── Step 7: Refresh view ──────────────────────────────────────

try:
    conn.autocommit = True
    conn.cursor().execute("REFRESH MATERIALIZED VIEW state_aggregates")
    print("View refreshed")
except Exception as e:
    print("View: " + str(e))

conn.close()

# ── Step 8: Print verification ────────────────────────────────

print("\n" + "="*60)
print("  OFFICIAL LGD CODES APPLIED FROM GOVERNMENT FILE")
print("="*60)
print("\nVerification — run these in your API:")
print("  /districts/state/32  → all Kerala districts with correct codes")
print("  /districts/state/27  → all Maharashtra districts")
print("  /districts/state/33  → all Tamil Nadu districts")
print()
print("Key codes from official LGD file:")
for row in lgd_data:
    name = row['district_name'].strip()
    code = row['lgd_district_code'].strip()
    sc   = row['state_code'].strip()
    if name in ["Ernakulam","Wayanad","Pune","Mumbai City","Chennai",
                "Bangalore Urban","Kolkata","Lucknow","Jaipur","Patna"]:
        sname = STATE_CODE_MAP.get(sc, sc)
        print("  " + name + " (" + sname + ") = " + str(code).zfill(4))
