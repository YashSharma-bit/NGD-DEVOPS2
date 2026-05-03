#!/usr/bin/env python3
"""
scripts/fix_district_codes.py

Fixes two issues found in your lgd_districts.parquet:
  1. Column names differ from what pipeline scripts expect
       Your file          →  Pipeline canonical name
       lgd_district_code  →  district_lgd_code   (and kept as alias)
       lgd_state_code     →  state_lgd_code       (and kept as alias)
       district_code_census → district_census_code

  2. lgd_district_code is stored as zero-padded STRING "0001"
     but should be INTEGER 1 for joins/comparisons,
     while also preserving the zero-padded string for display.

This script:
  - Adds canonical columns alongside originals (no data loss)
  - Converts codes to correct integer type
  - Adds a display column (lgd_district_code_str) with zero-padded strings
  - Re-saves ALL processed parquet files with consistent column names
  - Prints a before/after report

Usage:
    python scripts/fix_district_codes.py
    python scripts/fix_district_codes.py --dry-run   # show changes without saving
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DIR

# ── Column alias map: your actual names → canonical names scripts expect ───────
# We ADD canonical columns, keeping originals so nothing breaks.
COLUMN_RENAMES = {
    # District code
    "lgd_district_code":   "district_lgd_code",
    # State code
    "lgd_state_code":      "state_lgd_code",
    # Census code
    "district_code_census": "district_census_code",
    # Normalised names (keep both)
    "district_name_norm":  "district_name_canonical",
    "state_name_norm":     "state_name_canonical",
}

# Files to patch (order matters — lgd_districts first as others may derive from it)
TARGET_FILES = [
    "lgd_districts.parquet",
    "lgd_states.parquet",
    "master_districts.parquet",
    "analytics_districts.parquet",
    "geo_districts_tabular.csv",
]


def fix_codes(df: pd.DataFrame, fname: str, dry_run: bool) -> pd.DataFrame:
    df = df.copy()
    changes = []

    # ── Step 1: Add canonical column aliases ──────────────────────────────────
    for old_col, new_col in COLUMN_RENAMES.items():
        if old_col in df.columns and new_col not in df.columns:
            df[new_col] = df[old_col]
            changes.append(f"  + Added '{new_col}' as alias of '{old_col}'")

    # ── Step 2: Fix district_lgd_code — must be INTEGER ──────────────────────
    for code_col in ["district_lgd_code", "lgd_district_code"]:
        if code_col in df.columns:
            original_dtype = df[code_col].dtype
            # Strip leading zeros and convert to int
            df[code_col] = (
                df[code_col]
                .astype(str)
                .str.strip()
                .str.lstrip("0")          # remove leading zeros
                .replace("", "0")         # "0000" → "" → back to "0"
                .pipe(pd.to_numeric, errors="coerce")
                .astype("Int64")          # nullable integer
            )
            changes.append(
                f"  ✓ '{code_col}': {original_dtype} → Int64 "
                f"(e.g. '0001' → 1)"
            )

    # ── Step 3: Add zero-padded display string (4 digits) ─────────────────────
    if "district_lgd_code" in df.columns and "district_lgd_code_str" not in df.columns:
        df["district_lgd_code_str"] = (
            df["district_lgd_code"]
            .astype("Int64")
            .astype(str)
            .str.replace("<NA>", "")
            .str.zfill(4)
        )
        changes.append("  + Added 'district_lgd_code_str' (zero-padded, e.g. '0001')")

    # ── Step 4: Fix state_lgd_code — must be INTEGER ─────────────────────────
    for code_col in ["state_lgd_code", "lgd_state_code"]:
        if code_col in df.columns:
            df[code_col] = pd.to_numeric(df[code_col], errors="coerce").astype("Int64")
            changes.append(f"  ✓ '{code_col}' → Int64")

    # ── Step 5: Fix census code — must be INTEGER ─────────────────────────────
    for code_col in ["district_census_code", "district_code_census"]:
        if code_col in df.columns:
            df[code_col] = pd.to_numeric(df[code_col], errors="coerce").astype("Int64")
            changes.append(f"  ✓ '{code_col}' → Int64")

    # ── Step 6: Normalise state_name to title case ────────────────────────────
    # Your data has "JAMMU AND KASHMIR" (all caps) — normalise to "Jammu And Kashmir"
    for col in ["state_name", "state_name_norm", "state_name_canonical"]:
        if col in df.columns and df[col].dtype == object:
            before = df[col].iloc[0] if len(df) else ""
            df[col] = df[col].str.strip().str.title()
            after = df[col].iloc[0] if len(df) else ""
            if before != after:
                changes.append(f"  ✓ '{col}': title-cased ('{before}' → '{after}')")

    if changes:
        print(f"\n[{fname}]")
        for c in changes:
            print(c)
    else:
        print(f"\n[{fname}] — no changes needed")

    return df


def patch_file(path: Path, dry_run: bool) -> None:
    if not path.exists():
        print(f"\n[{path.name}] — NOT FOUND, skipping")
        return

    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, low_memory=False)

    print(f"\nBefore [{path.name}]: {list(df.columns)}")
    df_fixed = fix_codes(df, path.name, dry_run)
    print(f"After  [{path.name}]: {list(df_fixed.columns)}")

    if not dry_run:
        if path.suffix == ".parquet":
            df_fixed.to_parquet(path, index=False)
        else:
            df_fixed.to_csv(path, index=False)
        print(f"  → Saved: {path}")


def verify(path: Path) -> None:
    """Print sample rows to confirm codes look correct after patch."""
    if not path.exists():
        return
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, nrows=20)

    code_cols = [c for c in df.columns if "code" in c.lower() or "lgd" in c.lower()]
    name_cols = [c for c in ["district_name", "state_name"] if c in df.columns]
    show_cols = name_cols + code_cols

    print(f"\n=== Verification: {path.name} ===")
    print(df[show_cols].head(10).to_string(index=False))

    # Check for any remaining string codes that look like "0001"
    for col in code_cols:
        if df[col].dtype == object:
            sample = df[col].dropna().head(3).tolist()
            print(f"  ⚠ '{col}' is still string dtype. Sample: {sample}")
        else:
            mn, mx = df[col].min(), df[col].max()
            print(f"  ✓ '{col}' dtype={df[col].dtype}, range=[{mn}, {mx}]")


def main():
    parser = argparse.ArgumentParser(description="Fix district code columns in processed parquets")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN — no files will be modified ===")

    print(f"Processing files in: {PROCESSED_DIR}\n")

    for fname in TARGET_FILES:
        patch_file(PROCESSED_DIR / fname, args.dry_run)

    if not args.dry_run:
        print("\n=== Verification (sample rows after fix) ===")
        verify(PROCESSED_DIR / "lgd_districts.parquet")

    print("\n=== Done ===")
    if args.dry_run:
        print("Re-run without --dry-run to apply changes.")
    else:
        print("All processed files patched. Re-run your pipeline stages as needed.")
        print("\nQuick check:")
        print("  python -c \"import pandas as pd; df=pd.read_parquet('data/processed/lgd_districts.parquet'); print(df[['district_lgd_code','district_lgd_code_str','district_name','state_name']].head(10))\"")


if __name__ == "__main__":
    main()
