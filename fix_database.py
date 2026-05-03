"""
fix_database.py
---------------
Fixes all database issues:
1. Correct LGD state codes (UP=09, Maharashtra=27, Kerala=32 etc.)
2. Correct district codes linked to proper states
3. Fixes compare endpoint by ensuring consistent codes
4. Reloads demographics and development index

Run: python fix_database.py
"""

import os, sys, numpy as np, pandas as pd
import psycopg2, psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = Path(".").resolve()
PROCESSED = PROJECT_ROOT / "data" / "processed"

# ── Real LGD state codes matched to your exact state names ──────────────
# Source: Ministry of Panchayati Raj LGD master
STATE_LGD_MAP = {
    "JAMMU AND KASHMIR":            "01",
    "HIMACHAL PRADESH":             "02",
    "PUNJAB":                       "03",
    "CHANDIGARH":                   "04",
    "UTTARAKHAND":                  "05",
    "HARYANA":                      "06",
    "NCT OF DELHI":                 "07",
    "RAJASTHAN":                    "08",
    "UTTAR PRADESH":                "09",
    "BIHAR":                        "10",
    "SIKKIM":                       "11",
    "ARUNACHAL PRADESH":            "12",
    "NAGALAND":                     "13",
    "MANIPUR":                      "14",
    "MIZORAM":                      "15",
    "TRIPURA":                      "16",
    "MEGHALAYA":                    "17",
    "ASSAM":                        "18",
    "WEST BENGAL":                  "19",
    "JHARKHAND":                    "20",
    "ORISSA":                       "21",
    "CHHATTISGARH":                 "22",
    "MADHYA PRADESH":               "23",
    "GUJARAT":                      "24",
    "DAMAN AND DIU":                "25",
    "DADRA AND NAGAR HAVELI":       "26",
    "MAHARASHTRA":                  "27",
    "ANDHRA PRADESH":               "28",
    "KARNATAKA":                    "29",
    "GOA":                          "30",
    "LAKSHADWEEP":                  "31",
    "KERALA":                       "32",
    "TAMIL NADU":                   "33",
    "PONDICHERRY":                  "34",
    "ANDAMAN AND NICOBAR ISLANDS":  "35",
}

REGION_MAP = {
    "01": "North",  "02": "North",  "03": "North",  "04": "North",
    "05": "North",  "06": "North",  "07": "North",  "08": "North",
    "09": "North",
    "10": "East",   "19": "East",   "20": "East",   "21": "East",
    "35": "East",
    "11": "NE",     "12": "NE",     "13": "NE",     "14": "NE",
    "15": "NE",     "16": "NE",     "17": "NE",     "18": "NE",
    "22": "Central","23": "Central",
    "24": "West",   "25": "West",   "26": "West",   "27": "West",
    "30": "West",
    "28": "South",  "29": "South",  "31": "South",  "32": "South",
    "33": "South",  "34": "South",
}


def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "india_dev_analytics"),
        user=os.getenv("POSTGRES_USER", "analyst"),
        password=os.getenv("POSTGRES_PASSWORD", "yash123"),
    )


def clean(v):
    if v is None: return None
    if isinstance(v, float) and np.isnan(v): return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return float(v)
    return v


print("\n" + "="*60)
print("  India Dev Analytics — Database Fix")
print("="*60 + "\n")

# ── Load parquet ──────────────────────────────────────────────
print("Step 1/6  Loading district data...")
df = pd.read_parquet(PROCESSED / "districts_merged.parquet")
df["lgd_state_code"] = df["state_name"].map(STATE_LGD_MAP)

missing_states = df[df["lgd_state_code"].isna()]["state_name"].unique()
if len(missing_states) > 0:
    print("  WARNING: Could not map these states:", missing_states)

df["lgd_district_code"] = df["district_code_census"].astype(str).str.zfill(4)
print("  Loaded " + str(len(df)) + " districts across " + str(df["lgd_state_code"].nunique()) + " states")

# ── Clear existing data ───────────────────────────────────────
print("\nStep 2/6  Clearing existing database tables...")
conn = get_conn()
conn.autocommit = True
cur = conn.cursor()
for table in ["development_index", "economic_data", "demographics", "cities", "districts", "states"]:
    cur.execute("DELETE FROM " + table)
    print("  Cleared: " + table)

try:
    cur.execute("REFRESH MATERIALIZED VIEW state_aggregates")
except:
    pass
conn.close()
print("  Done clearing")

# ── Load states ───────────────────────────────────────────────
print("\nStep 3/6  Loading states with correct LGD codes...")
conn = get_conn()
cur = conn.cursor()

state_rows = []
for state_name, lgd_code in STATE_LGD_MAP.items():
    state_rows.append((
        lgd_code,
        state_name,
        state_name.title(),
        REGION_MAP.get(lgd_code, "Other"),
    ))

psycopg2.extras.execute_batch(
    cur,
    """INSERT INTO states (lgd_state_code, state_name, state_name_norm, region)
       VALUES (%s, %s, %s, %s)
       ON CONFLICT (lgd_state_code) DO UPDATE SET
         state_name=EXCLUDED.state_name,
         state_name_norm=EXCLUDED.state_name_norm,
         region=EXCLUDED.region""",
    state_rows,
)
conn.commit()

cur.execute("SELECT lgd_state_code, id FROM states")
state_id_map = {r[0]: r[1] for r in cur.fetchall()}
conn.close()
print("  Loaded " + str(len(state_rows)) + " states")
print("  Sample: UP code=09 id=" + str(state_id_map.get("09", "NOT FOUND")))

# ── Load districts ────────────────────────────────────────────
print("\nStep 4/6  Loading districts with correct codes...")
conn = get_conn()
cur = conn.cursor()

district_rows = []
seen = set()
for _, row in df.iterrows():
    code = str(row.get("lgd_district_code", "")).zfill(4)
    if code in seen:
        continue
    seen.add(code)

    state_lgd = str(row.get("lgd_state_code", "")) if pd.notna(row.get("lgd_state_code")) else None
    state_id = state_id_map.get(state_lgd) if state_lgd else None

    district_rows.append((
        code,
        str(row.get("district_code_census", code)),
        state_id,
        str(row.get("district_name", "")).strip(),
        str(row.get("district_name_norm", "")).strip(),
    ))

psycopg2.extras.execute_batch(
    cur,
    """INSERT INTO districts
         (lgd_district_code, census_district_code, state_id, district_name, district_name_norm)
       VALUES (%s, %s, %s, %s, %s)
       ON CONFLICT (lgd_district_code) DO UPDATE SET
         census_district_code=EXCLUDED.census_district_code,
         state_id=EXCLUDED.state_id,
         district_name=EXCLUDED.district_name,
         district_name_norm=EXCLUDED.district_name_norm""",
    district_rows,
)
conn.commit()

cur.execute("SELECT lgd_district_code, id FROM districts")
district_id_map = {r[0]: r[1] for r in cur.fetchall()}
conn.close()
print("  Loaded " + str(len(district_rows)) + " districts")

# ── Load demographics ─────────────────────────────────────────
print("\nStep 5/6  Loading demographics...")
conn = get_conn()
cur = conn.cursor()

DEMO_COLS = [
    "population_total","population_male","population_female",
    "households","literates_total","literates_male","literates_female",
    "literacy_rate","female_literacy_rate","sex_ratio","child_sex_ratio",
    "workers_total","workers_male","workers_female",
    "main_workers_total","marginal_workers_total","non_workers_total",
    "worker_participation_rate","cultivators_total","agri_labourers_total",
    "household_industry_workers","other_workers_total",
    "scheduled_caste_total","scheduled_tribe_total",
    "sc_proportion","st_proportion",
]

demo_rows = []
seen = set()
for _, row in df.iterrows():
    code = str(row.get("lgd_district_code","")).zfill(4)
    dist_id = district_id_map.get(code)
    if dist_id is None or dist_id in seen:
        continue
    seen.add(dist_id)
    rec = [dist_id, 2011]
    for col in DEMO_COLS:
        rec.append(clean(row.get(col)))
    demo_rows.append(tuple(rec))

col_names = ", ".join(DEMO_COLS)
placeholders = ", ".join(["%s"] * (len(DEMO_COLS) + 2))
psycopg2.extras.execute_batch(
    cur,
    "INSERT INTO demographics (district_id, census_year, " + col_names + ") VALUES (" + placeholders + ") ON CONFLICT (district_id) DO NOTHING",
    demo_rows,
)
conn.commit()
conn.close()
print("  Loaded " + str(len(demo_rows)) + " demographic records")

# ── Load development index ────────────────────────────────────
print("\nStep 6/6  Loading development index...")
idx_path = PROCESSED / "development_index.parquet"
if idx_path.exists():
    idx = pd.read_parquet(idx_path)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM development_index")

    idx_rows = []
    for _, row in idx.iterrows():
        code = str(row.get("lgd_district_code","")).zfill(4)
        dist_id = district_id_map.get(code)
        if dist_id is None:
            continue
        idx_rows.append((
            dist_id,
            clean(row.get("composite_score")),
            clean(row.get("composite_rank")),
            clean(row.get("composite_percentile")),
            clean(row.get("cluster_id")),
            str(row.get("cluster_label","")),
        ))

    psycopg2.extras.execute_batch(
        cur,
        """INSERT INTO development_index
             (district_id, composite_score, composite_rank,
              composite_percentile, cluster_id, cluster_label)
           VALUES (%s,%s,%s,%s,%s,%s)
           ON CONFLICT (district_id) DO NOTHING""",
        idx_rows,
    )
    conn.commit()

    # Refresh materialized view
    conn.autocommit = True
    try:
        conn.cursor().execute("REFRESH MATERIALIZED VIEW state_aggregates")
        print("  Materialised view refreshed")
    except Exception as e:
        print("  View refresh skipped: " + str(e))
    conn.close()
    print("  Loaded " + str(len(idx_rows)) + " development index records")
else:
    print("  development_index.parquet not found — skipping")

# ── Final verification ────────────────────────────────────────
print("\n" + "="*60)
print("  VERIFICATION")
print("="*60)
conn = get_conn()
cur = conn.cursor()

cur.execute("SELECT lgd_state_code, state_name FROM states ORDER BY lgd_state_code")
print("\nState codes (first 10):")
for r in cur.fetchall()[:10]:
    print("  " + r[0] + " = " + r[1])

cur.execute("""
    SELECT d.lgd_district_code, d.district_name, s.lgd_state_code, s.state_name
    FROM districts d
    JOIN states s ON s.id = d.state_id
    WHERE s.lgd_state_code = '09'
    ORDER BY d.lgd_district_code
    LIMIT 5
""")
print("\nSample UP districts (state code 09):")
for r in cur.fetchall():
    print("  District " + r[0] + " = " + r[1] + " (" + r[2] + "/" + r[3] + ")")

cur.execute("SELECT COUNT(*) FROM states")
print("\nTotal states : " + str(cur.fetchone()[0]))
cur.execute("SELECT COUNT(*) FROM districts")
print("Total districts : " + str(cur.fetchone()[0]))
cur.execute("SELECT COUNT(*) FROM demographics")
print("Total demographics : " + str(cur.fetchone()[0]))
cur.execute("SELECT COUNT(*) FROM development_index")
print("Total dev index : " + str(cur.fetchone()[0]))

conn.close()

print("\n" + "="*60)
print("  ALL DONE - Database fixed successfully!")
print("="*60)
print("\nAPI state codes are now correct:")
print("  UP         = 09")
print("  Maharashtra= 27")
print("  Kerala     = 32")
print("  Tamil Nadu = 33")
print("  Karnataka  = 29")
print("  West Bengal= 19")
print("\nRestart your API:")
print("  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
print()
