import os, sys, numpy as np, pandas as pd
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
import click

PROJECT_ROOT = Path(".").resolve()
PROCESSED = PROJECT_ROOT / "data" / "processed"

CLUSTER_LABELS = [
    "Aspirational",
    "Developing", 
    "Transitioning",
    "Growing",
    "Advanced",
    "Metro / High-Performance"
]

ALL_INDICATORS = {
    "literacy_rate": 0.25,
    "female_literacy_rate": 0.15,
    "worker_participation_rate": 0.15,
    "hh_electricity_pct": 0.15,
    "hh_safe_drinking_water_pct": 0.10,
    "hh_latrine_pct": 0.10,
    "hh_banking_pct": 0.05,
    "hh_computer_internet_pct": 0.05,
}

def gini(values):
    v = np.sort(values[~np.isnan(values)])
    n = len(v)
    if n == 0 or v.sum() == 0:
        return 0.0
    cumsum = np.cumsum(v)
    return float((n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n)

@click.command()
@click.option("--push-db", is_flag=True, default=False)
@click.option("--clusters", default=6)
def main(push_db, clusters):
    print("\n" + "="*55)
    print("  India Dev Analytics - Development Index")
    print("="*55 + "\n")

    # Load data
    df = None
    for name in ["districts_merged", "census_primary_raw"]:
        p = PROCESSED / (name + ".parquet")
        if p.exists():
            df = pd.read_parquet(p)
            if "geometry" in df.columns:
                df = df.drop(columns=["geometry"])
            print("Loaded " + str(len(df)) + " districts from " + name + ".parquet")
            break

    if df is None:
        print("ERROR: No data found in data/processed/")
        sys.exit(1)

    # Find which indicators actually have data
    available = {}
    for col, w in ALL_INDICATORS.items():
        if col in df.columns and df[col].notna().mean() >= 0.1:
            coverage = round(df[col].notna().mean() * 100)
            available[col] = w
            print("  OK   : " + col + " (" + str(coverage) + "% data)")
        else:
            print("  SKIP : " + col + " (no data)")

    if not available:
        print("ERROR: No indicators have data. Check clean_transform.py ran correctly.")
        sys.exit(1)

    # Renormalise weights to sum to 1
    total = sum(available.values())
    available = {k: v/total for k, v in available.items()}
    cols = list(available.keys())
    print("\nUsing " + str(len(cols)) + " indicators for scoring")

    # Extract features and fill missing with median
    feat = df[cols].copy()
    for col in cols:
        median_val = feat[col].median()
        if pd.isna(median_val):
            median_val = 0.0
        feat[col] = feat[col].fillna(median_val)

    # MinMax scale to 0-1
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(feat.values)
    normed = pd.DataFrame(scaled, columns=cols, index=feat.index)

    # Weighted composite score 0-100
    scores = pd.Series(0.0, index=normed.index)
    for col, w in available.items():
        scores = scores + normed[col] * w
    scores = (scores * 100).round(3)

    # KMeans clustering
    k = min(clusters, len(df))
    km = KMeans(n_clusters=k, random_state=42, n_init=20, max_iter=500)
    raw_labels = km.fit_predict(normed.values)

    # Reorder clusters: 0 = least developed, 5 = most developed
    means = km.cluster_centers_.mean(axis=1)
    order = np.argsort(means)
    remap = {old: new for new, old in enumerate(order)}
    labels = np.array([remap[l] for l in raw_labels])

    # Build result DataFrame
    id_cols = [c for c in ["lgd_district_code", "district_name", "state_name"] if c in df.columns]
    result = df[id_cols].copy()
    result["composite_score"] = scores.values
    result["composite_rank"] = scores.rank(ascending=False, method="min").astype(int)
    result["composite_percentile"] = (scores.rank(pct=True) * 100).round(2)
    result["cluster_id"] = labels
    result["cluster_label"] = [CLUSTER_LABELS[min(l, len(CLUSTER_LABELS)-1)] for l in labels]

    # Save
    out = PROCESSED / "development_index.parquet"
    result.to_parquet(str(out), index=False)
    print("\nSaved: " + str(out))

    # Print top 10
    show_cols = [c for c in ["district_name", "state_name", "composite_score", "cluster_label"] if c in result.columns]
    print("\n" + "="*55)
    print("  TOP 10 MOST DEVELOPED DISTRICTS")
    print("="*55)
    print(result.nsmallest(10, "composite_rank")[show_cols].to_string(index=False))

    print("\n" + "="*55)
    print("  BOTTOM 10 LEAST DEVELOPED DISTRICTS")
    print("="*55)
    print(result.nlargest(10, "composite_rank")[show_cols].to_string(index=False))

    print("\n" + "="*55)
    print("  CLUSTER DISTRIBUTION")
    print("="*55)
    for label, count in result["cluster_label"].value_counts().sort_index().items():
        print("  " + str(label) + ": " + str(count) + " districts")

    arr = scores.dropna().values
    print("\n  Total districts  : " + str(len(result)))
    print("  Score range      : " + str(round(float(arr.min()), 1)) + " to " + str(round(float(arr.max()), 1)))
    print("  National Gini    : " + str(round(gini(arr), 4)))

    if push_db:
        print("\nPushing to PostgreSQL...")
        try:
            from dotenv import load_dotenv
            import psycopg2
            import psycopg2.extras
            load_dotenv()

            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                dbname=os.getenv("POSTGRES_DB", "india_dev_analytics"),
                user=os.getenv("POSTGRES_USER", "analyst"),
                password=os.getenv("POSTGRES_PASSWORD", "yash123"),
            )
            cur = conn.cursor()
            cur.execute("SELECT lgd_district_code, id FROM districts")
            dist_map = {r[0]: r[1] for r in cur.fetchall()}

            rows = []
            for _, row in result.iterrows():
                code = str(row.get("lgd_district_code", "")).zfill(4)
                dist_id = dist_map.get(code)
                if dist_id is None:
                    continue

                def clean(v):
                    if v is None:
                        return None
                    if isinstance(v, float) and np.isnan(v):
                        return None
                    return v

                rows.append((
                    dist_id,
                    clean(float(row["composite_score"])),
                    clean(int(row["composite_rank"])),
                    clean(float(row["composite_percentile"])),
                    clean(int(row["cluster_id"])),
                    str(row["cluster_label"]),
                ))

            cur.execute("DELETE FROM development_index")
            psycopg2.extras.execute_batch(
                cur,
                "INSERT INTO development_index (district_id, composite_score, composite_rank, composite_percentile, cluster_id, cluster_label) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (district_id) DO NOTHING",
                rows,
            )
            conn.commit()
            conn.close()
            print("Pushed " + str(len(rows)) + " rows to PostgreSQL")

        except Exception as e:
            print("DB push failed: " + str(e))

    print("\n" + "="*55)
    print("  COMPLETE")
    print("="*55)
    print("\nNext steps:")
    print("  python analytics\\visualisation.py --format html")
    print("  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
    print()

if __name__ == "__main__":
    main()
