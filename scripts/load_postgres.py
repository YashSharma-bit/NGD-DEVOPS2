"""
scripts/load_postgres.py
------------------------
Stage 4 of the ETL pipeline.
Loads all processed Parquet files into PostgreSQL + PostGIS.

Uses psycopg2 directly for all inserts — no SQLAlchemy ORM,
no lambda issues, no pg_insert bugs. Simple and reliable.

Usage
-----
    python scripts/load_postgres.py
    python scripts/load_postgres.py --reset
"""

from __future__ import annotations

import sys
import json
from pathlib import Path

import click
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
import logging

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(h)
    return logger


load_dotenv()
logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED    = PROJECT_ROOT / "data" / "processed"
SCHEMA_SQL   = PROJECT_ROOT / "database" / "postgres" / "schema.sql"


# ─────────────────────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "india_dev_analytics"),
        user=os.getenv("POSTGRES_USER", "analyst"),
        password=os.getenv("POSTGRES_PASSWORD", "yash123"),
    )


def test_connection() -> bool:
    try:
        conn = get_conn()
        conn.close()
        logger.info("PostgreSQL connection OK")
        return True
    except Exception as exc:
        logger.error(f"PostgreSQL connection failed: {exc}")
        logger.error(
            "Fix: open psql -U postgres and run:\n"
            "  ALTER USER analyst WITH PASSWORD 'yash123';\n"
            "Also check your .env file has POSTGRES_PASSWORD=yash123"
        )
        return False


# ─────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────

def apply_schema() -> None:
    logger.info("Applying database schema ...")
    with open(SCHEMA_SQL, "r", encoding="utf-8") as fh:
        ddl = fh.read()

    conn = get_conn()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(ddl)
        logger.info("Schema applied")
    except Exception as exc:
        logger.error(f"Schema error: {exc}")
        raise
    finally:
        conn.close()


def reset_tables() -> None:
    logger.warning("Dropping and recreating all tables ...")
    drop_sql = """
        DROP TABLE IF EXISTS development_index CASCADE;
        DROP TABLE IF EXISTS economic_data     CASCADE;
        DROP TABLE IF EXISTS demographics      CASCADE;
        DROP TABLE IF EXISTS cities            CASCADE;
        DROP TABLE IF EXISTS subdistricts      CASCADE;
        DROP TABLE IF EXISTS districts         CASCADE;
        DROP TABLE IF EXISTS states            CASCADE;
        DROP MATERIALIZED VIEW IF EXISTS state_aggregates CASCADE;
    """
    conn = get_conn()
    try:
        conn.autocommit = True
        conn.cursor().execute(drop_sql)
        logger.info("Tables dropped")
    finally:
        conn.close()
    apply_schema()


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _clean(val):
    """Convert numpy/nan types to plain Python for psycopg2."""
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


def _clean_row(row: dict) -> dict:
    return {k: _clean(v) for k, v in row.items()}


def _batch_insert(conn, table: str, rows: list[dict], batch_size: int = 1000) -> int:
    """Insert rows into table using execute_values. Returns inserted count."""
    if not rows:
        return 0

    cols = list(rows[0].keys())
    col_str = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f'INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    total = 0
    cur = conn.cursor()
    for i in range(0, len(rows), batch_size):
        batch = rows[i: i + batch_size]
        values = [tuple(_clean(r[c]) for c in cols) for r in batch]
        psycopg2.extras.execute_batch(cur, sql, values, page_size=batch_size)
        total += len(batch)
    conn.commit()
    return total


# ─────────────────────────────────────────────────────────────
# States
# ─────────────────────────────────────────────────────────────

def load_states() -> dict[str, int]:
    """Load states from lgd_districts.parquet. Returns {lgd_state_code: state_id}."""
    path = PROCESSED / "lgd_districts.parquet"
    if not path.exists():
        logger.warning("lgd_districts.parquet not found — creating minimal states from census")
        path = PROCESSED / "census_primary_raw.parquet"
        if not path.exists():
            logger.error("No source for states data")
            return {}

    df = pd.read_parquet(path)
    logger.info(f"Loading states from {path.name} ...")

    # Build unique states list
    state_cols = {}
    if "state_name" in df.columns:
        state_cols["state_name"] = "state_name"
    if "state_name_norm" in df.columns:
        state_cols["state_name_norm"] = "state_name_norm"
    if "lgd_state_code" in df.columns:
        state_cols["lgd_state_code"] = "lgd_state_code"

    if "state_name" not in df.columns:
        logger.error("state_name column not found")
        return {}

    # Deduplicate states
    state_df = df[list(state_cols.values())].drop_duplicates("state_name").copy()

    if "lgd_state_code" not in state_df.columns:
        # Generate codes from index
        state_df = state_df.reset_index(drop=True)
        state_df["lgd_state_code"] = [f"{i+1:02d}" for i in range(len(state_df))]

    region_map = {
        "Rajasthan": "North", "Punjab": "North", "Haryana": "North",
        "Delhi": "North", "Himachal Pradesh": "North",
        "Jammu And Kashmir": "North", "Uttarakhand": "North",
        "Uttar Pradesh": "North", "Chandigarh": "North",
        "Maharashtra": "West", "Gujarat": "West", "Goa": "West",
        "Daman And Diu": "West", "Dadra And Nagar Haveli": "West",
        "Karnataka": "South", "Kerala": "South", "Tamil Nadu": "South",
        "Andhra Pradesh": "South", "Telangana": "South",
        "Puducherry": "South", "Lakshadweep": "South",
        "West Bengal": "East", "Odisha": "East", "Bihar": "East",
        "Jharkhand": "East", "Andaman And Nicobar Islands": "East",
        "Assam": "NE", "Arunachal Pradesh": "NE", "Manipur": "NE",
        "Meghalaya": "NE", "Mizoram": "NE", "Nagaland": "NE",
        "Sikkim": "NE", "Tripura": "NE",
        "Madhya Pradesh": "Central", "Chhattisgarh": "Central",
    }

    rows = []
    for _, row in state_df.iterrows():
        name = str(row.get("state_name", "")).strip()
        norm = str(row.get("state_name_norm", name)).strip()
        code = str(row.get("lgd_state_code", "00")).strip().zfill(2)
        rows.append({
            "lgd_state_code":   code,
            "state_name":       name,
            "state_name_norm":  norm,
            "region":           region_map.get(norm, region_map.get(name, "Other")),
        })

    conn = get_conn()
    try:
        inserted = _batch_insert(conn, "states", rows)
        logger.info(f"States loaded: {inserted} rows")

        cur = conn.cursor()
        cur.execute("SELECT lgd_state_code, id FROM states")
        lookup = {row[0]: row[1] for row in cur.fetchall()}
        return lookup
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# Districts
# ─────────────────────────────────────────────────────────────

def load_districts(state_lookup: dict[str, int]) -> dict[str, int]:
    """Load districts. Returns {lgd_district_code: district_id}."""
    path = PROCESSED / "districts_merged.parquet"
    if not path.exists():
        path = PROCESSED / "census_primary_raw.parquet"
    if not path.exists():
        logger.error("No district data found in processed/")
        return {}

    df = pd.read_parquet(path)
    logger.info(f"Loading {len(df)} districts ...")

    # Build state name → state_id mapping
    conn_temp = get_conn()
    cur = conn_temp.cursor()
    cur.execute("SELECT state_name_norm, lgd_state_code, id FROM states")
    state_rows = cur.fetchall()
    conn_temp.close()

    state_norm_to_id  = {r[0]: r[2] for r in state_rows}
    state_code_to_id  = {r[1]: r[2] for r in state_rows}

    rows = []
    seen_codes = set()
    for _, row in df.iterrows():
        code = str(row.get("lgd_district_code", "")).strip().zfill(4)
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)

        name      = str(row.get("district_name", "")).strip()
        name_norm = str(row.get("district_name_norm", name)).strip()
        state_norm = str(row.get("state_name_norm", "")).strip()
        state_code = str(row.get("lgd_state_code", "")).strip().zfill(2)

        # Resolve state_id
        state_id = (
            state_norm_to_id.get(state_norm)
            or state_code_to_id.get(state_code)
        )

        rows.append({
            "lgd_district_code":    code,
            "census_district_code": str(row.get("district_code_census", code)).strip(),
            "state_id":             state_id,
            "district_name":        name,
            "district_name_norm":   name_norm,
        })

    conn = get_conn()
    try:
        inserted = _batch_insert(conn, "districts", rows)
        logger.info(f"Districts loaded: {inserted} rows")

        cur = conn.cursor()
        cur.execute("SELECT lgd_district_code, id FROM districts")
        lookup = {row[0]: row[1] for row in cur.fetchall()}
        return lookup
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# Demographics
# ─────────────────────────────────────────────────────────────

def load_demographics(district_lookup: dict[str, int]) -> None:
    path = PROCESSED / "districts_merged.parquet"
    if not path.exists():
        path = PROCESSED / "census_primary_raw.parquet"
    if not path.exists():
        logger.warning("No data for demographics")
        return

    df = pd.read_parquet(path)
    logger.info(f"Loading demographics for {len(df)} districts ...")

    DEMO_COLS = [
        "population_total", "population_male", "population_female",
        "households", "literates_total", "literates_male", "literates_female",
        "literacy_rate", "female_literacy_rate", "sex_ratio", "child_sex_ratio",
        "workers_total", "workers_male", "workers_female",
        "main_workers_total", "marginal_workers_total", "non_workers_total",
        "worker_participation_rate",
        "cultivators_total", "agri_labourers_total",
        "household_industry_workers", "other_workers_total",
        "scheduled_caste_total", "scheduled_tribe_total",
        "sc_proportion", "st_proportion",
    ]

    rows = []
    seen = set()
    for _, row in df.iterrows():
        code    = str(row.get("lgd_district_code", "")).strip().zfill(4)
        dist_id = district_lookup.get(code)
        if dist_id is None or dist_id in seen:
            continue
        seen.add(dist_id)

        rec = {"district_id": dist_id, "census_year": 2011}
        for col in DEMO_COLS:
            rec[col] = _clean(row.get(col))
        rows.append(rec)

    conn = get_conn()
    try:
        inserted = _batch_insert(conn, "demographics", rows)
        logger.info(f"Demographics loaded: {inserted} rows")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# Economic data
# ─────────────────────────────────────────────────────────────

def load_economic(district_lookup: dict[str, int]) -> None:
    path = PROCESSED / "districts_merged.parquet"
    if not path.exists():
        path = PROCESSED / "census_primary_raw.parquet"
    if not path.exists():
        logger.warning("No data for economic_data")
        return

    df = pd.read_parquet(path)
    logger.info(f"Loading economic data for {len(df)} districts ...")

    ECON_COLS = [
        "households",
        "hh_electricity", "hh_electricity_pct",
        "hh_safe_drinking_water_pct",
        "hh_latrine", "hh_latrine_pct",
        "hh_lpg_or_png", "hh_lpg_or_png_pct",
        "hh_banking", "hh_banking_pct",
        "hh_tv", "hh_tv_pct",
        "hh_mobile_phone", "hh_mobile_phone_pct",
        "hh_computer_internet", "hh_computer_internet_pct",
        "hh_bicycle",
        "hh_scooter_motorcycle",
        "hh_car_jeep_van", "hh_car_jeep_van_pct",
    ]

    # Map to DB column names
    DB_COL_MAP = {
        "households": "total_households",
    }

    rows = []
    seen = set()
    for _, row in df.iterrows():
        code    = str(row.get("lgd_district_code", "")).strip().zfill(4)
        dist_id = district_lookup.get(code)
        if dist_id is None or dist_id in seen:
            continue
        seen.add(dist_id)

        rec = {"district_id": dist_id, "data_year": 2011}
        for col in ECON_COLS:
            if col in row.index:
                db_col = DB_COL_MAP.get(col, col)
                rec[db_col] = _clean(row.get(col))
        rows.append(rec)

    conn = get_conn()
    try:
        inserted = _batch_insert(conn, "economic_data", rows)
        logger.info(f"Economic data loaded: {inserted} rows")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# Refresh materialised views
# ─────────────────────────────────────────────────────────────

def refresh_views() -> None:
    logger.info("Refreshing materialised views ...")
    conn = get_conn()
    try:
        conn.autocommit = True
        conn.cursor().execute("REFRESH MATERIALIZED VIEW state_aggregates")
        logger.info("Materialised views refreshed")
    except Exception as exc:
        logger.warning(f"Could not refresh views (may be empty): {exc}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

@click.command()
@click.option("--reset", is_flag=True, default=False,
              help="Drop all tables and recreate schema before loading")
@click.option("--table", default="all",
              type=click.Choice(["states", "districts", "demographics", "economic", "all"]),
              help="Load only a specific table")
def main(reset: bool, table: str):
    """Load processed Parquet data into PostgreSQL."""

    print("\n" + "=" * 50)
    print("  India Dev Analytics — Load PostgreSQL")
    print("=" * 50 + "\n")

    # Test connection first
    if not test_connection():
        sys.exit(1)

    if reset:
        reset_tables()
    else:
        apply_schema()

    state_lookup:    dict[str, int] = {}
    district_lookup: dict[str, int] = {}

    # ── States ───────────────────────────────────────────────
    if table in ("states", "all"):
        state_lookup = load_states()

    # ── Districts ────────────────────────────────────────────
    if table in ("districts", "all"):
        if not state_lookup:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("SELECT lgd_state_code, id FROM states")
            state_lookup = {r[0]: r[1] for r in cur.fetchall()}
            conn.close()
        district_lookup = load_districts(state_lookup)

    # ── Demographics ─────────────────────────────────────────
    if table in ("demographics", "all"):
        if not district_lookup:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("SELECT lgd_district_code, id FROM districts")
            district_lookup = {r[0]: r[1] for r in cur.fetchall()}
            conn.close()
        load_demographics(district_lookup)

    # ── Economic ─────────────────────────────────────────────
    if table in ("economic", "all"):
        if not district_lookup:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("SELECT lgd_district_code, id FROM districts")
            district_lookup = {r[0]: r[1] for r in cur.fetchall()}
            conn.close()
        load_economic(district_lookup)

    # ── Refresh views ─────────────────────────────────────────
    if table == "all":
        refresh_views()

    # ── Summary ───────────────────────────────────────────────
    print()
    conn = get_conn()
    cur  = conn.cursor()
    for t in ["states", "districts", "demographics", "economic_data"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"  {t:20s}: {count} rows")
        except Exception:
            print(f"  {t:20s}: (table not found)")
    conn.close()

    print()
    print("  load_postgres.py complete.")
    print()
    print("  Next step:")
    print("    python analytics\\development_index.py --push-db")
    print()


if __name__ == "__main__":
    main()
