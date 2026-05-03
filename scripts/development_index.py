"""
analytics/development_index.py
-------------------------------
Computes the composite Development Index for all Indian districts.

Robustly handles partially missing indicator columns — works with
whatever data is actually present in districts_merged.parquet.

Usage
-----
    python analytics/development_index.py
    python analytics/development_index.py --push-db
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.config_loader import get_logger

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED    = PROJECT_ROOT / "data" / "processed"

CLUSTER_LABELS = [
    "Aspirational",
    "Developing",
    "Transitioning",
    "Growing",
    "Advanced",
    "Metro / High-Performance",
]

# All possible indicators and their weights
# Script will use only the ones that actually have data
ALL_INDICATORS = {
    "literacy_rate":              0.22,
    "female_literacy_rate":       0.12,
    "worker_participation_rate":  0.12,
    "hh_electricity_pct":         0.13,
    "hh_safe_drinking_water_pct": 0.12,
    "hh_latrine_pct":             0.10,
    "hh_banking_pct":             0.10,
    "hh_computer_internet_pct":   0.05,
    "hh_lpg_or_png_pct":          0.04,
}


# ─────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    # Try merged first, fall back to raw census
    for name in ["districts_merged", "census_primary_raw", "districts_geo"]:
        path = PROCESSED / f"{name}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            # Drop geometry column if present (from GeoDataFrame)
            if "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            logger.info(f"Loaded {len(df)} districts from {name}.parquet")
            return df
    raise FileNotFoundError(
        "No district data found in data/processed/. "
        "Run clean_transform.py first."
    )


# ─────────────────────────────────────────────────────────────
# Detect which indicator columns actually have data
# ─────────────────────────────────────────────────────────────

def detect_available_indicators(df: pd.DataFrame) -> dict[str, float]:
    """
    Returns {col: weight} for columns that exist AND have
    at least 50% non-null values.
    Weights are renormalised to sum to 1.
    """
    available = {}
    for col, weight in ALL_INDICATORS.items():
        if col not in df.columns:
            logger.warning(f"Indicator column missing entirely: {col}")
            continue
        non_null_pct = df[col].notna().mean()
        if non_null_pct < 0.1:
            logger.warning(
                f"Skipping {col} — only {non_null_pct*100:.1f}% non-null values"
            )
            continue
        available[col] = weight
        logger.info(f"Using {col} — {non_null_pct*100:.1f}% coverage")

    if not available:
        raise ValueError(
            "No indicator columns have sufficient data. "
            "Check that clean_transform.py ran correctly."
        )

    # Renormalise weights to sum to 1
    total = sum(available.values())
    available = {k: v / total for k, v in available.items()}

    logger.info(f"Using {len(available)} indicators: {list(available.keys())}")
    return available


# ─────────────────────────────────────────────────────────────
# Normalise
# ─────────────────────────────────────────────────────────────

def normalise(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Extract cols from df, fill missing values with column median,
    then MinMax scale to [0, 1].
    Returns a new DataFrame with same index, only the indicator cols.
    """
    feat = df[cols].copy()

    # Fill missing values with column median
    for col in cols:
        median = feat[col].median()
        if pd.isna(median):
            median = 0.0
        feat[col] = feat[col].fillna(median)

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(feat.values)
    return pd.DataFrame(scaled, columns=cols, index=feat.index)


# ─────────────────────────────────────────────────────────────
# Composite score
# ─────────────────────────────────────────────────────────────

def compute_scores(normed: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    score = pd.Series(0.0, index=normed.index)
    for col, w in weights.items():
        score += normed[col] * w
    return (score * 100).round(3)


# ─────────────────────────────────────────────────────────────
# Clustering
# ─────────────────────────────────────────────────────────────

def cluster(normed: pd.DataFrame, k: int = 6) -> np.ndarray:
    km = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
    raw = km.fit_predict(normed.values)

    # Re-order clusters by mean score (0 = lowest development)
    means = km.cluster_centers_.mean(axis=1)
    order = np.argsort(means)
    remap  = {old: new for new, old in enumerate(order)}
    return np.array([remap[l] for l in raw])


# ─────────────────────────────────────────────────────────────
# Inequality metrics
# ─────────────────────────────────────────────────────────────

def gini(values: np.ndarray) -> float:
    v = np.sort(values[~np.isnan(values)])
    n = len(v)
    if n == 0 or v.sum() == 0:
        return 0.0
    cumsum = np.cumsum(v)
    return float((n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n)


def compute_inequality(scores: pd.Series, df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    state_col = "state_name" if "state_name" in df.columns else None
    if state_col:
        for state, grp in df.groupby(state_col):
            s = scores.loc[grp.index].dropna().values
            rows.append({
                "state_name":     state,
                "district_count": len(grp),
                "mean_dev_score": round(float(np.nanmean(s)), 3) if len(s) else None,
                "min_dev_score":  round(float(np.nanmin(s)), 3) if len(s) else None,
                "max_dev_score":  round(float(np.nanmax(s)), 3) if len(s) else None,
                "gini":           round(gini(s), 4) if len(s) > 1 else None,
            })
    return pd.DataFrame(rows).sort_values("gini", ascending=False)


# ─────────────────────────────────────────────────────────────
# Push to PostgreSQL
# ─────────────────────────────────────────────────────────────

def push_to_db(result: pd.DataFrame) -> None:
    import psycopg2
    import psycopg2.extras
    from dotenv import load_dotenv
    load_dotenv()

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "india_dev_analytics"),
        user=os.getenv("POSTGRES_USER", "analyst"),
        password=os.getenv("POSTGRES_PASSWORD", "yash123"),
    )

    try:
        cur = conn.cursor()

        # Get district id lookup
        cur.execute("SELECT lgd_district_code, id FROM districts")
        dist_map = {r[0]: r[1] for r in cur.fetchall()}

        rows = []
        for _, row in result.iterrows():
            code    = str(row.get("lgd_district_code", "")).zfill(4)
            dist_id = dist_map.get(code)
            if dist_id is None:
                continue

            def fv(col):
                v = row.get(col)
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return None
                return float(v)

            def iv(col):
                v = row.get(col)
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return None
                return int(v)

            rows.append((
                dist_id,
                fv("composite_score"),
                iv("composite_rank"),
                fv("composite_percentile"),
                iv("cluster_id"),
                str(row.get("cluster_label", "")),
            ))

        # Recreate table fresh
        cur.execute("DELETE FROM development_index")

        psycopg2.extras.execute_batch(
            cur,
            """
            INSERT INTO development_index
              (district_id, composite_score, composite_rank,
               composite_percentile, cluster_id, cluster_label)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (district_id) DO UPDATE SET
              composite_score      = EXCLUDED.composite_score,
              composite_rank       = EXCLUDED.composite_rank,
              composite_percentile = EXCLUDED.composite_percentile,
              cluster_id           = EXCLUDED.cluster_id,
              cluster_label        = EXCLUDED.cluster_label
            """,
            rows,
        )
        conn.commit()
        logger.success(f"Development index pushed to PostgreSQL: {len(rows)} rows")

        # Refresh materialised view
        conn.autocommit = True
        try:
            conn.cursor().execute("REFRESH MATERIALIZED VIEW state_aggregates")
            logger.success("Materialised view refreshed")
        except Exception as exc:
            logger.warning(f"Could not refresh view: {exc}")

    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

@click.command()
@click.option("--push-db", is_flag=True, default=False,
              help="Push results to PostgreSQL development_index table")
@click.option("--clusters", default=6, show_default=True,
              help="Number of K-Means clusters")
def main(push_db: bool, clusters: int):
    """Compute composite development index for all Indian districts."""

    print("\n" + "=" * 55)
    print("  India Dev Analytics — Development Index")
    print("=" * 55 + "\n")

    # Load data
    df = load_data()

    # Detect which indicators are usable
    weights = detect_available_indicators(df)
    cols    = list(weights.keys())

    print(f"\n  Indicators available : {len(cols)}")
    for c, w in weights.items():
        coverage = df[c].notna().mean() * 100
        print(f"    {c:35s}  weight={w:.3f}  coverage={coverage:.0f}%")

    # Normalise
    normed = normalise(df, cols)

    # Composite score
    scores = compute_scores(normed, weights)

    # Clustering
    k = min(clusters, len(df))
    labels = cluster(normed, k=k)

    # Build result DataFrame
    id_cols = [c for c in ["lgd_district_code", "district_name", "state_name"]
               if c in df.columns]
    result = df[id_cols].copy()
    result["composite_score"]      = scores.values
    result["composite_rank"]       = scores.rank(ascending=False, method="min").astype(int)
    result["composite_percentile"] = (scores.rank(pct=True) * 100).round(2)
    result["cluster_id"]           = labels
    result["cluster_label"]        = [
        CLUSTER_LABELS[min(l, len(CLUSTER_LABELS) - 1)] for l in labels
    ]

    # Save to parquet
    out = PROCESSED / "development_index.parquet"
    result.to_parquet(out, index=False, engine="pyarrow", compression="snappy")
    logger.success(f"Saved: {out}")

    # Inequality
    inequality = compute_inequality(scores, df)
    ineq_out = PROCESSED / "state_inequality.parquet"
    inequality.to_parquet(ineq_out, index=False)

    # Print summary
    print("\n" + "=" * 55)
    print("  TOP 10 MOST DEVELOPED DISTRICTS")
    print("=" * 55)
    top = result.nsmallest(10, "composite_rank")[
        ["district_name", "state_name", "composite_score", "cluster_label"]
    ] if "district_name" in result.columns else result.nsmallest(10, "composite_rank")
    print(top.to_string(index=False))

    print("\n" + "=" * 55)
    print("  BOTTOM 10 LEAST DEVELOPED DISTRICTS")
    print("=" * 55)
    bot = result.nlargest(10, "composite_rank")[
        ["district_name", "state_name", "composite_score", "cluster_label"]
    ] if "district_name" in result.columns else result.nlargest(10, "composite_rank")
    print(bot.to_string(index=False))

    print("\n" + "=" * 55)
    print("  CLUSTER DISTRIBUTION")
    print("=" * 55)
    for label, count in result["cluster_label"].value_counts().sort_index().items():
        print(f"  {label:30s}: {count} districts")

    arr = scores.dropna().values
    print(f"\n  Score range : {arr.min():.1f} — {arr.max():.1f}")
    print(f"  Mean score  : {arr.mean():.1f}")
    print(f"  Gini (national): {gini(arr):.4f}")

    if push_db:
        push_to_db(result)

    print("\n  Output → data/processed/development_index.parquet")
    print("\n  Next steps:")
    print("    python analytics\\visualisation.py --format both")
    print("    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
    print()


if __name__ == "__main__":
    main()
