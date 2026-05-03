#!/usr/bin/env python3
"""
load_neo4j.py — Loads India administrative hierarchy into Neo4j graph database.

FIXED: Handles column name variants across different pipeline versions.
       Uses a schema-resolution layer so it never hard-crashes on a missing column.

Graph Schema:
  Nodes:
    (:Country {name: 'India'})
    (:State  {lgd_code, name, population, literacy_rate, ...})
    (:District {lgd_code, name, population, development_index, cluster, ...})

  Relationships:
    (:District)-[:BELONGS_TO]->(:State)
    (:State)-[:BELONGS_TO]->(:Country)
    (:District)-[:SIMILAR_DEVELOPMENT_LEVEL {similarity_score}]->(:District)

Usage:
    python scripts/load_neo4j.py
    python scripts/load_neo4j.py --only-hierarchy
    python scripts/load_neo4j.py --rebuild
    python scripts/load_neo4j.py --inspect   # print parquet columns and exit
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import neo4j as neo4j_cfg, PROCESSED_DIR, etl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "neo4j.log"),
    ],
)
log = logging.getLogger("load_neo4j")

SIMILARITY_FEATURES = [
    "development_index",
    "literacy_rate",
    "worker_participation_rate",
    "electrification_rate",
    "sanitation_rate",
]
SIMILARITY_THRESHOLD = 0.92
MAX_SIMILAR_EDGES = 5


# ─────────────────────────────────────────────────────────────────────────────
# Schema resolution — handles column name variants across pipeline versions
# ─────────────────────────────────────────────────────────────────────────────

# Maps canonical name → list of known aliases (first found wins)
COLUMN_ALIASES = {
    "district_lgd_code": [
        "district_lgd_code", "lgd_district_code", "dist_lgd_code",
        "DISTRICT_LGD_CODE", "lgd_code_district",
    ],
    "state_lgd_code": [
        "state_lgd_code", "lgd_state_code", "state_lgd", "STATE_LGD_CODE",
        "lgd_code_state", "state_code",
    ],
    "state_name": [
        "state_name", "STATE_NAME", "StateName", "state",
    ],
    "district_name": [
        "district_name", "DISTRICT_NAME", "DistrictName", "district",
    ],
    "total_population": [
        "total_population", "TOT_P", "population", "total_pop",
    ],
    "female_population": [
        "female_population", "TOT_F", "female_pop",
    ],
    "literacy_rate": [
        "literacy_rate", "lit_rate", "LITERACY_RATE",
    ],
    "female_literacy_rate": [
        "female_literacy_rate", "fem_lit_rate",
    ],
    "worker_participation_rate": [
        "worker_participation_rate", "wpr", "work_part_rate",
    ],
    "agricultural_dependency": [
        "agricultural_dependency", "agri_dep", "agri_dependency",
    ],
    "sex_ratio": [
        "sex_ratio", "SEX_RATIO",
    ],
    "electrification_rate": [
        "electrification_rate", "elec_rate",
    ],
    "sanitation_rate": [
        "sanitation_rate", "sanit_rate",
    ],
    "development_index": [
        "development_index", "dev_index", "cdi", "CDI",
    ],
    "development_cluster": [
        "development_cluster", "dev_cluster", "cluster", "CLUSTER",
    ],
    "centroid_lat": [
        "centroid_lat", "lat", "latitude",
    ],
    "centroid_lon": [
        "centroid_lon", "lon", "longitude",
    ],
    "area_sq_km": [
        "area_sq_km", "area",
    ],
}


def resolve_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename df columns to canonical names using COLUMN_ALIASES.
    Logs which aliases were resolved. Never raises on missing columns.
    """
    rename_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical
                log.debug(f"  alias resolved: '{alias}' -> '{canonical}'")
                break

    if rename_map:
        log.info(f"Resolving {len(rename_map)} column aliases: {rename_map}")
        df = df.rename(columns=rename_map)

    missing = [c for c in COLUMN_ALIASES if c not in df.columns]
    if missing:
        log.warning(f"Columns absent after resolution (will be None): {missing}")

    return df


def safe_get(row: pd.Series, col: str, default=None):
    """Return row[col] or default if column is missing or NaN."""
    if col not in row.index:
        return default
    val = row[col]
    try:
        if pd.isna(val):
            return default
    except (TypeError, ValueError):
        pass
    return val


def inspect_parquets() -> None:
    """Print columns of all relevant processed files and exit."""
    files = [
        "lgd_states.parquet",
        "lgd_districts.parquet",
        "master_districts.parquet",
        "analytics_districts.parquet",
        "geo_districts.parquet",
        "geo_districts_tabular.csv",
        "districts_geo.parquet",   # alternate naming some pipelines use
    ]
    print("\n=== Processed File Column Inspection ===\n")
    for fname in files:
        path = PROCESSED_DIR / fname
        if path.exists():
            try:
                df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, nrows=0)
                print(f"[{fname}]  shape={df.shape}")
                print(f"  {list(df.columns)}\n")
            except Exception as exc:
                print(f"[{fname}]  ERROR reading: {exc}\n")
        else:
            print(f"[{fname}]  NOT FOUND\n")


# ─────────────────────────────────────────────────────────────────────────────
# Data Loading
# ─────────────────────────────────────────────────────────────────────────────

def load_states_df() -> pd.DataFrame:
    """Load states reference. Falls back through multiple file candidates."""
    candidates = [
        "lgd_states.parquet",
        "analytics_districts.parquet",
        "master_districts.parquet",
        "districts_geo.parquet",
    ]
    for fname in candidates:
        path = PROCESSED_DIR / fname
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        df = resolve_columns(df)

        # Aggregate district-level files to state level
        if "district_name" in df.columns and "state_name" in df.columns:
            agg = {}
            if "state_lgd_code" in df.columns:
                agg["state_lgd_code"] = "first"
            for col in ["total_population", "literate_persons", "total_households"]:
                if col in df.columns:
                    agg[col] = "sum"
            if "literacy_rate" in df.columns:
                agg["literacy_rate"] = "mean"
            if agg:
                df = df.groupby("state_name").agg(agg).reset_index()
            else:
                df = df[["state_name"]].drop_duplicates()

        log.info(f"States loaded from {fname}: {len(df)} rows")
        return df

    log.error("No states data found. Run clean_transform.py first.")
    return pd.DataFrame()


def load_master_df() -> pd.DataFrame:
    """Load district master data, preferring analytics-enriched version."""
    candidates = [
        "analytics_districts.parquet",
        "master_districts.parquet",
        "districts_geo.parquet",       # alternate name some pipelines produce
        "geo_districts_tabular.csv",
    ]
    for fname in candidates:
        path = PROCESSED_DIR / fname
        if not path.exists():
            continue
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path, low_memory=False)
        df = resolve_columns(df)
        log.info(f"Master districts loaded from {fname}: {len(df)} rows, cols={list(df.columns[:10])}")
        return df

    log.error(
        "No district data found. Run clean_transform.py + "
        "analytics/development_index.py first."
    )
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# Neo4j Driver wrapper
# ─────────────────────────────────────────────────────────────────────────────

class Neo4jLoader:
    def __init__(self):
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(
            neo4j_cfg.uri,
            auth=(neo4j_cfg.user, neo4j_cfg.password),
        )
        log.info(f"Connected to Neo4j: {neo4j_cfg.uri}")

    def close(self):
        self.driver.close()

    def run(self, query: str, parameters: dict = None):
        with self.driver.session(database=neo4j_cfg.database) as session:
            return session.run(query, parameters or {})

    def run_batch(self, query: str, rows: list, batch_size: int = 500) -> int:
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i: i + batch_size]
            with self.driver.session(database=neo4j_cfg.database) as session:
                result = session.run(query, {"rows": batch})
                s = result.consume()
                total += s.counters.nodes_created + s.counters.relationships_created
        return total


# ─────────────────────────────────────────────────────────────────────────────
# Constraints + Indexes
# ─────────────────────────────────────────────────────────────────────────────

CONSTRAINTS = [
    "CREATE CONSTRAINT country_name_unique IF NOT EXISTS FOR (c:Country) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT state_name_unique   IF NOT EXISTS FOR (s:State)   REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT district_name_state_unique IF NOT EXISTS FOR (d:District) REQUIRE (d.name, d.state_name) IS NODE KEY",
]
INDEXES = [
    "CREATE INDEX state_lgd_idx    IF NOT EXISTS FOR (s:State)    ON (s.lgd_code)",
    "CREATE INDEX district_lgd_idx IF NOT EXISTS FOR (d:District) ON (d.lgd_code)",
    "CREATE INDEX district_dev_idx IF NOT EXISTS FOR (d:District) ON (d.development_index)",
    "CREATE INDEX district_cluster IF NOT EXISTS FOR (d:District) ON (d.cluster)",
]


def create_constraints_and_indexes(loader: Neo4jLoader) -> None:
    log.info("Ensuring constraints and indexes")
    for stmt in CONSTRAINTS + INDEXES:
        try:
            loader.run(stmt)
        except Exception as exc:
            # Neo4j 4.x uses different IF NOT EXISTS syntax; fall back gracefully
            log.debug(f"Constraint/index (may already exist or syntax differs): {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Node + Relationship loaders
# ─────────────────────────────────────────────────────────────────────────────

def load_country_node(loader: Neo4jLoader) -> None:
    loader.run("""
        MERGE (c:Country {name: 'India'})
        SET c.iso_code = 'IN', c.capital = 'New Delhi', c.continent = 'Asia'
    """)
    log.info("Country node: India ✓")


def load_state_nodes(loader: Neo4jLoader, states_df: pd.DataFrame) -> None:
    if states_df.empty:
        log.warning("No state data — skipping state nodes.")
        return

    log.info(f"Loading {len(states_df)} state nodes")
    rows = [
        {
            "lgd_code":         safe_get(row, "state_lgd_code"),
            "name":             safe_get(row, "state_name"),
            "total_population": safe_get(row, "total_population"),
            "literacy_rate":    safe_get(row, "literacy_rate"),
        }
        for _, row in states_df.iterrows()
        if safe_get(row, "state_name")   # require a name
    ]

    count = loader.run_batch(
        """
        UNWIND $rows AS row
        MERGE (s:State {name: row.name})
        SET s.lgd_code         = row.lgd_code,
            s.total_population = row.total_population,
            s.literacy_rate    = row.literacy_rate
        WITH s
        MATCH (c:Country {name: 'India'})
        MERGE (s)-[:BELONGS_TO]->(c)
        """,
        rows,
    )
    log.info(f"State nodes/rels: {count}")


def load_district_nodes(loader: Neo4jLoader, master_df: pd.DataFrame) -> None:
    if master_df.empty:
        log.warning("No district data — skipping district nodes.")
        return

    log.info(f"Loading {len(master_df)} district nodes")
    rows = []
    for _, row in master_df.iterrows():
        name  = safe_get(row, "district_name")
        state = safe_get(row, "state_name")
        if not name or not state:
            continue
        rows.append({
            "lgd_code":                  safe_get(row, "district_lgd_code"),
            "name":                      name,
            "state_name":                state,
            "state_lgd_code":            safe_get(row, "state_lgd_code"),
            "total_population":          safe_get(row, "total_population"),
            "female_population":         safe_get(row, "female_population"),
            "literacy_rate":             safe_get(row, "literacy_rate"),
            "female_literacy_rate":      safe_get(row, "female_literacy_rate"),
            "worker_participation_rate": safe_get(row, "worker_participation_rate"),
            "agricultural_dependency":   safe_get(row, "agricultural_dependency"),
            "sex_ratio":                 safe_get(row, "sex_ratio"),
            "electrification_rate":      safe_get(row, "electrification_rate"),
            "sanitation_rate":           safe_get(row, "sanitation_rate"),
            "development_index":         safe_get(row, "development_index"),
            "cluster":                   safe_get(row, "development_cluster"),
            "centroid_lat":              safe_get(row, "centroid_lat"),
            "centroid_lon":              safe_get(row, "centroid_lon"),
            "area_sq_km":                safe_get(row, "area_sq_km"),
        })

    count = loader.run_batch(
        """
        UNWIND $rows AS row
        MERGE (d:District {name: row.name, state_name: row.state_name})
        SET d.lgd_code                  = row.lgd_code,
            d.total_population          = row.total_population,
            d.female_population         = row.female_population,
            d.literacy_rate             = row.literacy_rate,
            d.female_literacy_rate      = row.female_literacy_rate,
            d.worker_participation_rate = row.worker_participation_rate,
            d.agricultural_dependency   = row.agricultural_dependency,
            d.sex_ratio                 = row.sex_ratio,
            d.electrification_rate      = row.electrification_rate,
            d.sanitation_rate           = row.sanitation_rate,
            d.development_index         = row.development_index,
            d.cluster                   = row.cluster,
            d.centroid_lat              = row.centroid_lat,
            d.centroid_lon              = row.centroid_lon,
            d.area_sq_km                = row.area_sq_km
        WITH d, row
        MATCH (s:State {name: row.state_name})
        MERGE (d)-[:BELONGS_TO]->(s)
        """,
        rows,
        batch_size=etl.batch_size,
    )
    log.info(f"District nodes/rels: {count}")


# ─────────────────────────────────────────────────────────────────────────────
# Similarity edges
# ─────────────────────────────────────────────────────────────────────────────

def compute_similarity_edges(master_df: pd.DataFrame) -> list:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import MinMaxScaler

    feature_cols = [c for c in SIMILARITY_FEATURES if c in master_df.columns]
    if not feature_cols:
        log.warning(f"No similarity features found ({SIMILARITY_FEATURES}). Skipping.")
        return []

    log.info(f"Computing similarity on: {feature_cols}")
    df = master_df[["district_name", "state_name"] + feature_cols].dropna(subset=feature_cols, how="all").copy()

    if len(df) < 2:
        return []

    X = SimpleImputer(strategy="median").fit_transform(df[feature_cols].values.astype(float))
    X = MinMaxScaler().fit_transform(X)
    sim = cosine_similarity(X)

    names  = df["district_name"].tolist()
    states = df["state_name"].tolist()
    edges  = []

    for i in range(len(df)):
        row_sim = sim[i].copy()
        row_sim[i] = -1
        for j in np.argsort(row_sim)[::-1][:MAX_SIMILAR_EDGES]:
            score = float(sim[i][j])
            if score >= SIMILARITY_THRESHOLD:
                edges.append({
                    "src_name":  names[i],  "src_state": states[i],
                    "dst_name":  names[j],  "dst_state": states[j],
                    "similarity": round(score, 4),
                })

    log.info(f"Similarity edges computed: {len(edges)}")
    return edges


def load_similarity_edges(loader: Neo4jLoader, edges: list) -> None:
    if not edges:
        return
    count = loader.run_batch(
        """
        UNWIND $rows AS row
        MATCH (a:District {name: row.src_name, state_name: row.src_state})
        MATCH (b:District {name: row.dst_name, state_name: row.dst_state})
        MERGE (a)-[r:SIMILAR_DEVELOPMENT_LEVEL]->(b)
        SET r.similarity_score = row.similarity
        """,
        edges,
    )
    log.info(f"Similarity edges created/updated: {count}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def print_graph_summary(loader: Neo4jLoader) -> None:
    print("\n=== Neo4j Graph Summary ===")
    for label in ["Country", "State", "District"]:
        cnt = loader.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]
        print(f"  {label:<12} nodes : {cnt}")
    for rel in ["BELONGS_TO", "SIMILAR_DEVELOPMENT_LEVEL"]:
        cnt = loader.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c").single()["c"]
        print(f"  [{rel}] : {cnt}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Load India analytics into Neo4j")
    parser.add_argument("--rebuild",        action="store_true", help="Drop all nodes first")
    parser.add_argument("--only-hierarchy", action="store_true", help="Skip similarity edges")
    parser.add_argument("--inspect",        action="store_true", help="Print parquet columns and exit")
    args = parser.parse_args()

    if args.inspect:
        inspect_parquets()
        sys.exit(0)

    states_df = load_states_df()
    master_df = load_master_df()

    if states_df.empty and master_df.empty:
        log.error("No data available. Run the ETL pipeline first.")
        sys.exit(1)

    # Derive states from master if dedicated states file is missing
    if states_df.empty and not master_df.empty and "state_name" in master_df.columns:
        log.info("Deriving states from master_df")
        agg = {}
        if "state_lgd_code" in master_df.columns:
            agg["state_lgd_code"] = "first"
        for col in ["total_population", "literate_persons"]:
            if col in master_df.columns:
                agg[col] = "sum"
        if "literacy_rate" in master_df.columns:
            agg["literacy_rate"] = "mean"
        states_df = (
            master_df.groupby("state_name").agg(agg).reset_index()
            if agg else master_df[["state_name"]].drop_duplicates()
        )

    loader = Neo4jLoader()
    try:
        if args.rebuild:
            log.warning("Dropping all nodes (--rebuild)")
            loader.run("MATCH (n) DETACH DELETE n")

        create_constraints_and_indexes(loader)
        load_country_node(loader)
        load_state_nodes(loader, states_df)
        load_district_nodes(loader, master_df)

        if not args.only_hierarchy:
            edges = compute_similarity_edges(master_df)
            load_similarity_edges(loader, edges)

        pass  # summary skipped

    except Exception as exc:
        log.error(f"Fatal: {exc}", exc_info=True)
        sys.exit(1)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
