"""
scripts/clean_transform.py
--------------------------
Built on verified column names from your actual files:

census_primary_abstract.csv  (118 columns)
  First 6: District code, State name, District name,
           Population, Male, Female

census_houselisting.csv  (91 columns)
  First 6: State, District, Level, Name, TRU, TRU1

Outputs
-------
  data/processed/lgd_districts.parquet
  data/processed/census_primary_raw.parquet
  data/processed/houselisting_raw.parquet
  data/processed/districts_merged.parquet   ← main output

Usage
-----
    python scripts/clean_transform.py
    python scripts/clean_transform.py --csv
    python scripts/clean_transform.py --debug
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import click
import numpy as np
import pandas as pd

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


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW       = PROJECT_ROOT / "data" / "raw"
PROCESSED = PROJECT_ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Name normalisation
# ─────────────────────────────────────────────────────────────

_REMOVE_PAREN = re.compile(r"\(.*?\)")
_MULTI_SPACE  = re.compile(r"\s+")


def normalise_name(name) -> str:
    if not isinstance(name, str) or not name.strip():
        return ""
    try:
        from unidecode import unidecode
        s = unidecode(name)
    except Exception:
        s = name
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = _REMOVE_PAREN.sub("", s).strip().title()
    s = _MULTI_SPACE.sub(" ", s).strip()
    return s


# ─────────────────────────────────────────────────────────────
# Loader 1 — census_primary_abstract.csv
# Verified columns: District code, State name, District name,
#                   Population, Male, Female … 118 total
# ─────────────────────────────────────────────────────────────

PRIMARY_RENAME = {
    "District code":            "district_code_census",
    "State name":               "state_name",
    "District name":            "district_name",
    "Population":               "population_total",
    "Male":                     "population_male",
    "Female":                   "population_female",
    "Literate":                 "literates_total",
    "Male_Literate":            "literates_male",
    "Female_Literate":          "literates_female",
    "Households":               "households",
    "Workers":                  "workers_total",
    "Male_Workers":             "workers_male",
    "Female_Workers":           "workers_female",
    "Main_Workers":             "main_workers_total",
    "Marginal_Workers":         "marginal_workers_total",
    "Non_Workers":              "non_workers_total",
    "Cultivator_Workers":       "cultivators_total",
    "Agricultural_Workers":     "agri_labourers_total",
    "Household_Workers":        "household_industry_workers",
    "Other_Workers":            "other_workers_total",
    "Sex_Ratio":                "sex_ratio",
    "Child_Sex_Ratio":          "child_sex_ratio",
    "Scheduled_Caste":          "scheduled_caste_total",
    "Scheduled_Tribe":          "scheduled_tribe_total",
    "Households_with_Electricity":                            "hh_electricity",
    "Households_with_Internet":                               "hh_computer_internet",
    "Households_with_Mobile_Phone":                           "hh_mobile_phone",
    "Households_with_Telephone_Mobile_Phone_Mobile_only":     "hh_mobile_only",
    "Households_with_Scooter_Motorcycle_Moped":               "hh_scooter_motorcycle",
    "Households_with_Car_Jeep_Van":                           "hh_car_jeep_van",
    "Households_with_Bicycle":                                "hh_bicycle",
    "Households_with_Television":                             "hh_tv",
    "Households_with_Radio_Transistor":                       "hh_radio",
    "Households_with_Banking_Service":                        "hh_banking",
    "Households_with_Tap_Water":                              "hh_tap_water",
    "Households_with_Treated_Tap_Water":                      "hh_treated_water",
    "Households_with_Latrine_facility":                       "hh_latrine",
    "Households_with_LPG_PNG":                                "hh_lpg_or_png",
    "Area":                     "area_sq_km",
}


def load_census_primary() -> pd.DataFrame:
    path = RAW / "census_primary_abstract.csv"
    if not path.exists():
        logger.error(f"Missing: {path}")
        return pd.DataFrame()

    logger.info("Loading census_primary_abstract.csv ...")
    df = pd.read_csv(path, dtype=str, encoding="utf-8", low_memory=False)
    logger.info(f"  Raw shape: {df.shape}")

    # Apply renames for known columns only
    df = df.rename(columns={k: v for k, v in PRIMARY_RENAME.items() if k in df.columns})

    # Validate required columns
    for required in ["state_name", "district_name"]:
        if required not in df.columns:
            logger.error(
                f"Column '{required}' not found after rename. "
                f"Run --debug to see all column names."
            )
            return pd.DataFrame()

    # Drop blank district rows
    df = df[df["district_name"].str.strip().astype(bool)].copy()

    # Convert all non-identifier columns to numeric
    id_cols = {"district_code_census", "state_name", "district_name"}
    for col in df.columns:
        if col not in id_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Derived rates ────────────────────────────────────────
    pop  = df.get("population_total",  pd.Series(np.nan, index=df.index))
    hh   = df.get("households",        pd.Series(np.nan, index=df.index))
    popf = df.get("population_female", pd.Series(np.nan, index=df.index))

    def rate(num_col: str, denom: pd.Series, scale: float = 100) -> pd.Series:
        num = df.get(num_col, pd.Series(np.nan, index=df.index))
        return np.where(denom > 0, (num / denom * scale).round(2), np.nan)

    df["literacy_rate"]             = rate("literates_total",          pop)
    df["female_literacy_rate"]      = rate("literates_female",         popf)
    df["worker_participation_rate"] = rate("workers_total",            pop)
    df["sc_proportion"]             = rate("scheduled_caste_total",    pop)
    df["st_proportion"]             = rate("scheduled_tribe_total",    pop)
    df["hh_electricity_pct"]        = rate("hh_electricity",           hh)
    df["hh_banking_pct"]            = rate("hh_banking",               hh)
    df["hh_computer_internet_pct"]  = rate("hh_computer_internet",     hh)
    df["hh_latrine_pct"]            = rate("hh_latrine",               hh)
    df["hh_safe_drinking_water_pct"]= rate("hh_tap_water",             hh)
    df["hh_lpg_or_png_pct"]         = rate("hh_lpg_or_png",            hh)
    df["hh_mobile_phone_pct"]       = rate("hh_mobile_phone",          hh)
    df["hh_tv_pct"]                 = rate("hh_tv",                    hh)
    df["hh_car_jeep_van_pct"]       = rate("hh_car_jeep_van",          hh)

    # ── Normalised names & codes ─────────────────────────────
    df["district_name_norm"] = df["district_name"].apply(normalise_name)
    df["state_name_norm"]    = df["state_name"].apply(normalise_name)

    if "district_code_census" not in df.columns:
        df["district_code_census"] = range(len(df))
    df["lgd_district_code"] = df["district_code_census"].astype(str).str.strip().str.zfill(4)

    logger.info(f"Census primary: {len(df)} districts, {len(df.columns)} columns")
    return df


# ─────────────────────────────────────────────────────────────
# Loader 2 — census_houselisting.csv
# Verified columns: State, District, Level, Name, TRU, TRU1
#                   … 91 total
# ─────────────────────────────────────────────────────────────

HOUSELISTING_RENAME = {
    "State":                    "state_name",
    "District":                 "district_name",
    "Level":                    "level",
    "Name":                     "name",
    "TRU":                      "tru",
    # Common PCA column patterns in this dataset
    "No_HH":                    "total_households",
    "TOT_P":                    "population_total",
    "TOT_M":                    "population_male",
    "TOT_F":                    "population_female",
    "P_LIT":                    "literates_total",
    "M_LIT":                    "literates_male",
    "F_LIT":                    "literates_female",
    "TOT_WORK_P":               "workers_total",
    "MAIN_CL_P":                "cultivators_total",
    "MAIN_AL_P":                "agri_labourers_total",
    "SC_P":                     "scheduled_caste_total",
    "ST_P":                     "scheduled_tribe_total",
}


def load_houselisting() -> pd.DataFrame:
    path = RAW / "census_houselisting.csv"
    if not path.exists():
        logger.warning("census_houselisting.csv not found — skipping")
        return pd.DataFrame()

    logger.info("Loading census_houselisting.csv ...")
    df = pd.read_csv(path, dtype=str, encoding="utf-8", low_memory=False)
    logger.info(f"  Raw shape: {df.shape}")
    logger.info(f"  Columns: {list(df.columns)[:10]}")

    # Apply renames
    df = df.rename(columns={k: v for k, v in HOUSELISTING_RENAME.items() if k in df.columns})

    # Filter to district-level Total rows only
    if "level" in df.columns:
        df = df[df["level"].str.strip().str.upper() == "DISTRICT"]
    elif "Level" in df.columns:
        df = df[df["Level"].str.strip().str.upper() == "DISTRICT"]

    if "tru" in df.columns:
        df = df[df["tru"].str.strip().str.upper() == "T"]
    elif "TRU" in df.columns:
        df = df[df["TRU"].str.strip().str.upper() == "T"]

    logger.info(f"  After filter (district + total): {len(df)} rows")

    # Resolve district_name
    if "district_name" not in df.columns:
        for candidate in ["District", "DISTRICT", "name", "Name"]:
            if candidate in df.columns:
                df = df.rename(columns={candidate: "district_name"})
                break

    if "district_name" not in df.columns:
        logger.warning("Could not identify district_name column in houselisting — skipping")
        return pd.DataFrame()

    # Convert numerics
    id_cols = {"state_name", "district_name", "level", "name", "tru", "Level", "TRU"}
    for col in df.columns:
        if col not in id_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["district_name_norm"] = df["district_name"].apply(normalise_name)

    # Build district code from State + District columns if available
    state_code_col = next((c for c in df.columns if "state" in c.lower() and "code" in c.lower()), None)
    dist_code_col  = next((c for c in df.columns if "district" in c.lower() and "code" in c.lower()), None)

    if dist_code_col:
        df["lgd_district_code"] = df[dist_code_col].astype(str).str.zfill(4)
    else:
        # Build a synthetic code: state_num * 100 + district_num
        if "State" in df.columns or "state_name" in df.columns:
            sc = df.get("State", df.get("state_name", pd.Series(["00"] * len(df))))
            df["lgd_district_code"] = (
                sc.astype(str).str.zfill(2)
                + df.groupby(sc.values).cumcount().add(1).astype(str).str.zfill(3)
            )
        else:
            df["lgd_district_code"] = [f"{i:04d}" for i in range(len(df))]

    logger.info(f"Houselisting: {len(df)} district rows, {len(df.columns)} columns")
    return df


# ─────────────────────────────────────────────────────────────
# LGD lookup from census data
# ─────────────────────────────────────────────────────────────

def build_lgd_lookup(census: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["lgd_district_code", "district_code_census",
                        "district_name", "district_name_norm",
                        "state_name", "state_name_norm"] if c in census.columns]
    lgd = census[cols].drop_duplicates("lgd_district_code").copy()

    # Assign a numeric state code
    if "state_name_norm" in lgd.columns:
        state_ids = {s: f"{i+1:02d}" for i, s in enumerate(sorted(lgd["state_name_norm"].unique()))}
        lgd["lgd_state_code"] = lgd["state_name_norm"].map(state_ids)
    else:
        lgd["lgd_state_code"] = "00"

    logger.info(f"LGD lookup: {len(lgd)} districts, {lgd['lgd_state_code'].nunique()} states")
    return lgd


# ─────────────────────────────────────────────────────────────
# Merge
# ─────────────────────────────────────────────────────────────

def merge_datasets(census: pd.DataFrame, houselisting: pd.DataFrame) -> pd.DataFrame:
    if census.empty:
        return pd.DataFrame()

    if houselisting.empty:
        logger.warning("Houselisting empty — using census-only data")
        return census

    logger.info("Merging census + houselisting ...")

    # Extra columns from houselisting not already in census
    exclude = set(census.columns) | {"level", "name", "tru", "Level", "TRU", "Name"}
    extra   = [c for c in houselisting.columns if c not in exclude] + ["lgd_district_code"]
    extra   = list(dict.fromkeys(extra))

    hl_sub = houselisting[extra].drop_duplicates("lgd_district_code")

    merged = census.merge(hl_sub, on="lgd_district_code", how="left", suffixes=("", "_hl"))
    logger.info(f"Merged: {len(merged)} districts, {len(merged.columns)} columns")
    return merged


# ─────────────────────────────────────────────────────────────
# Writers
# ─────────────────────────────────────────────────────────────

def write_parquet(df: pd.DataFrame, name: str) -> None:
    out = PROCESSED / f"{name}.parquet"
    df.to_parquet(out, index=False, engine="pyarrow", compression="snappy")
    logger.info(f"Saved: {out}  ({len(df)} rows, {len(df.columns)} cols)")


def write_csv_copy(df: pd.DataFrame, name: str) -> None:
    out = PROCESSED / f"{name}.csv"
    df.to_csv(out, index=False, encoding="utf-8")
    logger.info(f"CSV copy: {out}")


# ─────────────────────────────────────────────────────────────
# Debug helper
# ─────────────────────────────────────────────────────────────

def debug_file(path: Path) -> None:
    df = pd.read_csv(path, nrows=3, dtype=str)
    print(f"\n{'='*60}")
    print(f"File   : {path.name}")
    print(f"Shape  : {df.shape}")
    print(f"Columns ({len(df.columns)}):")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:3d}.  {col!r}")
    print(f"\nRow 1:")
    for col in df.columns[:20]:
        print(f"  {col!r:45s} = {df.iloc[0][col]!r}")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

@click.command()
@click.option("--csv", "write_csv_flag", is_flag=True, default=False,
              help="Also write CSV copies of the Parquet output files")
@click.option("--debug", is_flag=True, default=False,
              help="Print all column names from raw CSV files and exit")
def main(write_csv_flag: bool, debug: bool):
    """Clean and transform raw census CSV files into Parquet datasets."""

    if debug:
        for fname in ["census_primary_abstract.csv", "census_houselisting.csv"]:
            p = RAW / fname
            if p.exists():
                debug_file(p)
            else:
                print(f"\nMISSING: {p}")
        return

    # ── Load ─────────────────────────────────────────────────
    census      = load_census_primary()
    houselisting = load_houselisting()

    if census.empty:
        logger.error(
            "Census primary failed to load.\n"
            "Make sure data/raw/census_primary_abstract.csv exists and is not empty.\n"
            "Run: python scripts\\download_data.py"
        )
        sys.exit(1)

    # ── Save individual cleaned files ────────────────────────
    lgd = build_lgd_lookup(census)
    write_parquet(lgd,    "lgd_districts")
    write_parquet(census, "census_primary_raw")
    if not houselisting.empty:
        write_parquet(houselisting, "houselisting_raw")

    # ── Merge and save ───────────────────────────────────────
    merged = merge_datasets(census, houselisting)
    if merged.empty:
        logger.error("Merge produced empty result")
        sys.exit(1)

    write_parquet(merged, "districts_merged")
    if write_csv_flag:
        write_csv_copy(merged, "districts_merged")

    # ── Summary ──────────────────────────────────────────────
    print()
    print("=" * 55)
    print("  CLEAN & TRANSFORM — COMPLETE")
    print("=" * 55)
    print(f"  Districts          : {len(merged)}")
    print(f"  States / UTs       : {merged['state_name'].nunique() if 'state_name' in merged.columns else 'N/A'}")
    print(f"  Total columns      : {len(merged.columns)}")

    for col, label in [
        ("literacy_rate",             "Literacy rate (avg)"),
        ("population_total",          "Total population   "),
        ("hh_electricity_pct",        "Electrification pct"),
    ]:
        if col in merged.columns:
            s = merged[col].dropna()
            if col == "population_total":
                print(f"  {label}: {s.sum()/1e6:.1f} M across {len(s)} districts")
            else:
                print(f"  {label}: avg {s.mean():.1f}%  (min {s.min():.1f}% — max {s.max():.1f}%)")

    print("=" * 55)
    print()
    print("  Output → data/processed/districts_merged.parquet")
    print()
    print("  Next step:")
    print("    python scripts\\geospatial_join.py")
    print()


if __name__ == "__main__":
    main()
