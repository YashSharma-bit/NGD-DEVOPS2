"""
scripts/geospatial_join.py
--------------------------
Stage 3 of the ETL pipeline.
Loads shapefiles for Indian administrative boundaries,
joins them with the cleaned tabular data, and produces
GeoParquet files ready for PostGIS loading.

Shapefile priority
------------------
1. Datameet Census 2011-aligned shapefiles (preferred)
2. GADM 4.1 (fallback)

Outputs
-------
data/processed/states_geo.parquet
data/processed/districts_geo.parquet
data/processed/subdistricts_geo.parquet

Usage
-----
    python scripts/geospatial_join.py [--level LEVEL]

    --level  states | districts | subdistricts | all (default)
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import click
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.validation import make_valid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging as _log, re as _re, unicodedata as _ud

def get_config():
    return {"etl": {"batch_size": 5000, "fuzzy_match_threshold": 85}}

def get_logger(name):
    lg = _log.getLogger(name)
    if not lg.handlers:
        lg.setLevel(_log.INFO)
        h = _log.StreamHandler()
        h.setFormatter(_log.Formatter("%(levelname)s: %(message)s"))
        lg.addHandler(h)
    return lg

def normalise_name(name):
    if not isinstance(name, str) or not name.strip(): return ""
    try:
        from unidecode import unidecode
        s = unidecode(name)
    except: s = name
    s = _ud.normalize("NFKD", s).encode("ascii","ignore").decode()
    s = _re.sub(r"\(.*?\)", "", s).strip().title()
    s = _re.sub(r"\s+", " ", s).strip()
    return s

def fuzzy_match(raw, candidates, threshold=80):
    if not raw or not candidates: return None
    from rapidfuzz import process as fp, fuzz
    result = fp.extractOne(raw, candidates, scorer=fuzz.token_sort_ratio)
    return result[0] if result and result[1] >= threshold else None

logger = get_logger(__name__)
CFG = get_config()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "data" / "raw"
SHAPEFILES = PROJECT_ROOT / "data" / "shapefiles"
PROCESSED = PROJECT_ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)
TARGET_CRS = "EPSG:4326"  # WGS-84 for PostGIS


# ─────────────────────────────────────────────────────────────
# Shapefile loading helpers
# ─────────────────────────────────────────────────────────────

def _find_shp(directory: Path, keyword: str) -> Path | None:
    """Find first .shp file containing keyword in its name."""
    for p in directory.rglob("*.shp"):
        if keyword.lower() in p.stem.lower():
            return p
    # fallback: any .shp in directory
    candidates = list(directory.rglob("*.shp"))
    return candidates[0] if candidates else None


def _ensure_extracted(zip_path: Path, extract_dir: Path) -> None:
    if not zip_path.exists():
        raise FileNotFoundError(f"Shapefile zip not found: {zip_path}")
    if not extract_dir.exists() or not any(extract_dir.rglob("*.shp")):
        logger.info(f"Extracting {zip_path.name} …")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)


def load_datameet_districts() -> gpd.GeoDataFrame | None:
    """Load Datameet Census 2011 district shapefiles."""
    zip_path = SHAPEFILES / "districts_2011.zip"
    extract_dir = SHAPEFILES / "districts_2011"
    try:
        _ensure_extracted(zip_path, extract_dir)
        shp = _find_shp(extract_dir, "dist")
        if shp is None:
            shp = _find_shp(extract_dir, "")
        if shp is None:
            return None
        logger.info(f"Loading district shapefile: {shp}")
        gdf = gpd.read_file(shp)
        return gdf
    except Exception as exc:
        logger.warning(f"Datameet district load failed: {exc}")
        return None


def load_gadm_level(level: int) -> gpd.GeoDataFrame | None:
    """Load GADM 4.1 at the given admin level (0=country, 1=state, 2=district, 3=subdistrict)."""
    zip_path = SHAPEFILES / "gadm41_IND.zip"
    extract_dir = SHAPEFILES / "gadm41_IND"
    try:
        _ensure_extracted(zip_path, extract_dir)
        shp = _find_shp(extract_dir, f"IND_{level}")
        if shp is None:
            # Try GeoPackage
            gpkg_files = list(extract_dir.rglob("*.gpkg"))
            if gpkg_files:
                gdf = gpd.read_file(gpkg_files[0], layer=f"ADM_ADM_{level}")
                return gdf
        if shp is None:
            return None
        logger.info(f"Loading GADM level {level}: {shp}")
        return gpd.read_file(shp)
    except Exception as exc:
        logger.warning(f"GADM level {level} load failed: {exc}")
        return None


def load_state_shapefile() -> gpd.GeoDataFrame | None:
    zip_path = SHAPEFILES / "states.zip"
    extract_dir = SHAPEFILES / "states"
    try:
        _ensure_extracted(zip_path, extract_dir)
        shp = _find_shp(extract_dir, "state") or _find_shp(extract_dir, "admin")
        if shp:
            return gpd.read_file(shp)
    except Exception as exc:
        logger.warning(f"State shapefile load failed: {exc}")
    return load_gadm_level(1)


def load_subdistrict_shapefile() -> gpd.GeoDataFrame | None:
    zip_path = SHAPEFILES / "subdistricts_2011.zip"
    extract_dir = SHAPEFILES / "subdistricts_2011"
    try:
        _ensure_extracted(zip_path, extract_dir)
        shp = _find_shp(extract_dir, "subdist") or _find_shp(extract_dir, "")
        if shp:
            return gpd.read_file(shp)
    except Exception as exc:
        logger.warning(f"Subdistrict shapefile load failed: {exc}")
    return load_gadm_level(3)


# ─────────────────────────────────────────────────────────────
# GeoDataFrame normalisation
# ─────────────────────────────────────────────────────────────

# Possible attribute names for district names across shapefiles
DISTRICT_NAME_CANDIDATES = [
    "DISTRICT", "DIST_NAME", "DISTNAME", "NAME_2", "District",
    "district", "dist_name", "dtname", "Dist_Name",
]
STATE_NAME_CANDIDATES = [
    "STATE", "ST_NAME", "STATENAME", "NAME_1", "State",
    "state", "st_name", "stname", "State_Name",
]
STATE_CODE_CANDIDATES = ["ST_CODE", "STATE_CODE", "STCODE", "CC_1", "HASC_1"]
DISTRICT_CODE_CANDIDATES = ["DIST_CODE", "DT_CODE", "DTCODE", "CC_2"]


def _pick_col(gdf: gpd.GeoDataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in gdf.columns:
            return c
    return None


def normalise_geodataframe(
    gdf: gpd.GeoDataFrame,
    level: str,
) -> gpd.GeoDataFrame:
    """
    Standardise column names and geometry for a given admin level GeoDataFrame.
    level: 'state' | 'district' | 'subdistrict'
    """
    logger.info(f"Normalising {level} GeoDataFrame ({len(gdf)} features) …")

    # Reproject to WGS-84
    if gdf.crs is None:
        gdf = gdf.set_crs(TARGET_CRS)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(TARGET_CRS)

    # Repair invalid geometries
    gdf["geometry"] = gdf["geometry"].apply(lambda g: make_valid(g) if g and not g.is_valid else g)
    gdf = gdf[~gdf["geometry"].is_empty].copy()

    # Rename columns
    rename = {}
    if level in ("district", "subdistrict"):
        c = _pick_col(gdf, DISTRICT_NAME_CANDIDATES)
        if c:
            rename[c] = "district_name_shp"
        c = _pick_col(gdf, DISTRICT_CODE_CANDIDATES)
        if c:
            rename[c] = "district_code_shp"

    c = _pick_col(gdf, STATE_NAME_CANDIDATES)
    if c:
        rename[c] = "state_name_shp"
    c = _pick_col(gdf, STATE_CODE_CANDIDATES)
    if c:
        rename[c] = "state_code_shp"

    gdf = gdf.rename(columns=rename)

    # Normalised name columns for joining
    if "district_name_shp" in gdf.columns:
        gdf["district_name_norm"] = gdf["district_name_shp"].apply(normalise_name)
    if "state_name_shp" in gdf.columns:
        gdf["state_name_norm"] = gdf["state_name_shp"].apply(normalise_name)

    # Compute centroid in WGS-84
    gdf["centroid_lon"] = gdf["geometry"].centroid.x.round(6)
    gdf["centroid_lat"] = gdf["geometry"].centroid.y.round(6)
    gdf["area_sq_km"] = (
        gdf["geometry"]
        .to_crs("EPSG:32644")  # UTM Zone 44N — approximate for India
        .area
        / 1e6
    ).round(2)

    return gdf


# ─────────────────────────────────────────────────────────────
# Spatial join: tabular data → shapefile
# ─────────────────────────────────────────────────────────────

def join_tabular_to_geo(
    gdf: gpd.GeoDataFrame,
    tabular: pd.DataFrame,
    geo_level: str,
) -> gpd.GeoDataFrame:
    """
    Join tabular census data onto the GeoDataFrame using normalised district names.
    Uses fuzzy matching for unresolved districts.
    """
    if tabular.empty:
        logger.warning("Tabular dataset empty — returning geometry-only GeoDataFrame")
        return gdf

    logger.info(f"Joining tabular data ({len(tabular)} rows) → {geo_level} GDF ({len(gdf)} features)")

    tab_district_norm = tabular["district_name_norm"].tolist()
    geo_district_norm = gdf["district_name_norm"].tolist() if "district_name_norm" in gdf.columns else []

    if not geo_district_norm:
        logger.warning("No district_name_norm in GeoDataFrame — cannot join")
        return gdf

    # Build index: geo normalised name → row index
    geo_idx: dict[str, int] = {name: i for i, name in enumerate(geo_district_norm)}

    matched_rows: list[int | None] = []
    for dist in tab_district_norm:
        if dist in geo_idx:
            matched_rows.append(geo_idx[dist])
        else:
            m = fuzzy_match(dist, list(geo_idx.keys()))
            matched_rows.append(geo_idx[m] if m else None)

    tabular = tabular.copy()
    tabular["_geo_row"] = matched_rows

    # Add geometry and spatial columns from gdf
    gdf = gdf.reset_index(drop=True)
    geo_cols = ["geometry", "centroid_lon", "centroid_lat", "area_sq_km",
                "district_name_shp", "state_name_shp",
                "district_code_shp", "state_code_shp"]
    geo_cols = [c for c in geo_cols if c in gdf.columns]
    geo_sub = gdf[geo_cols].copy()
    geo_sub["_geo_row"] = geo_sub.index

    merged = tabular.merge(geo_sub, on="_geo_row", how="left")
    merged = merged.drop(columns=["_geo_row"])

    # Convert to GeoDataFrame
    merged_gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=TARGET_CRS)

    matched = merged_gdf["geometry"].notna().sum()
    logger.info(f"Join complete: {matched}/{len(merged_gdf)} districts have geometry")
    return merged_gdf


# ─────────────────────────────────────────────────────────────
# Nighttime lights raster extraction (optional)
# ─────────────────────────────────────────────────────────────

def extract_nighttime_lights(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute mean nighttime radiance for each district polygon
    using the VIIRS annual composite raster.
    """
    import gzip
    import shutil

    raster_gz = PROJECT_ROOT / "data" / "raw" / "nighttime_lights_2022.tif.gz"
    raster_tif = PROJECT_ROOT / "data" / "raw" / "nighttime_lights_2022.tif"

    if not raster_gz.exists() and not raster_tif.exists():
        logger.info("Nighttime lights raster not available — skipping")
        return gdf

    if not raster_tif.exists() and raster_gz.exists():
        logger.info("Decompressing nighttime lights raster …")
        with gzip.open(raster_gz, "rb") as f_in, open(raster_tif, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    logger.info("Extracting nighttime light statistics per district …")
    try:
        from rasterstats import zonal_stats

        stats = zonal_stats(
            gdf,
            str(raster_tif),
            stats=["mean", "max"],
            geojson_out=False,
            nodata=-9999,
        )
        gdf["nightlight_mean"] = [s["mean"] for s in stats]
        gdf["nightlight_max"] = [s["max"] for s in stats]
        logger.info("Nighttime light stats extracted")
    except Exception as exc:
        logger.warning(f"Nighttime light extraction failed: {exc}")

    return gdf


# ─────────────────────────────────────────────────────────────
# GeoParquet writer
# ─────────────────────────────────────────────────────────────

def write_geoparquet(gdf: gpd.GeoDataFrame, name: str) -> None:
    out = PROCESSED / f"{name}.parquet"
    gdf.to_parquet(out, engine="pyarrow", compression="snappy")
    logger.info(f"GeoParquet written: {out} ({len(gdf)} features)")


# ─────────────────────────────────────────────────────────────
# Per-level processing
# ─────────────────────────────────────────────────────────────

def process_states() -> None:
    gdf = load_state_shapefile()
    if gdf is None:
        logger.error("Could not load state shapefile from any source")
        return
    gdf = normalise_geodataframe(gdf, "state")
    write_geoparquet(gdf, "states_geo")


def process_districts() -> None:
    tabular_path = PROCESSED / "districts_merged.parquet"
    tabular = pd.read_parquet(tabular_path) if tabular_path.exists() else pd.DataFrame()

    gdf = load_datameet_districts()
    if gdf is None:
        logger.warning("Datameet shapefiles unavailable — falling back to GADM L2")
        gdf = load_gadm_level(2)
    if gdf is None:
        logger.error("No district shapefile source available")
        return

    gdf = normalise_geodataframe(gdf, "district")
    if not tabular.empty:
        gdf = join_tabular_to_geo(gdf, tabular, "district")
    gdf = extract_nighttime_lights(gdf)
    write_geoparquet(gdf, "districts_geo")


def process_subdistricts() -> None:
    gdf = load_subdistrict_shapefile()
    if gdf is None:
        logger.warning("No subdistrict shapefile available")
        return
    gdf = normalise_geodataframe(gdf, "subdistrict")
    write_geoparquet(gdf, "subdistricts_geo")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

@click.command()
@click.option(
    "--level",
    default="all",
    type=click.Choice(["states", "districts", "subdistricts", "all"]),
    help="Which administrative level to process",
)
def main(level: str):
    """Run geospatial join stage of the ETL pipeline."""
    if level in ("states", "all"):
        process_states()
    if level in ("districts", "all"):
        process_districts()
    if level in ("subdistricts", "all"):
        process_subdistricts()
    logger.info("geospatial_join.py complete.")


if __name__ == "__main__":
    main()
