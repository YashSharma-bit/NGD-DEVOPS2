"""
scripts/download_data.py
------------------------
Downloads all data needed for the India Dev Analytics pipeline.

STRATEGY
--------
Census files (primary + housing) must be downloaded manually from GitHub
because government sites and raw GitHub links block automated requests.

This script handles ONLY what can be reliably automated:
  1. GADM shapefiles          — geodata.ucdavis.edu  (always works)
  2. India district shapefile — GitHub zip download  (always works)

Everything else is detected from data/raw/ and reported as OK or MISSING.

Usage
-----
    python scripts/download_data.py
    python scripts/download_data.py --check-only
"""

from __future__ import annotations

import sys
import zipfile
import shutil
from pathlib import Path

import click
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm import tqdm

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
RAW        = PROJECT_ROOT / "data" / "raw"
SHAPEFILES = PROJECT_ROOT / "data" / "shapefiles"
RAW.mkdir(parents=True, exist_ok=True)
SHAPEFILES.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Files the user MUST download manually from browser
# ─────────────────────────────────────────────────────────────

MANUAL_FILES = {
    "census_primary_abstract.csv": {
        "description": "Census 2011 district data — population, literacy, workers, sex ratio",
        "min_size_kb": 100,
        "manual_url":  "https://github.com/nishusharma1608/India-Census-2011-Analysis/blob/master/india-districts-census-2011.csv",
        "instruction": (
            "1. Open the URL above in your browser\n"
            "   2. Click the Download raw file button (down-arrow icon, top right)\n"
            "   3. Save the file\n"
            "   4. Rename it to:  census_primary_abstract.csv\n"
            "   5. Move it to:    data\\raw\\"
        ),
    },
    "census_houselisting.csv": {
        "description": "Census 2011 PCA full — housing, electrification, sanitation, assets",
        "min_size_kb": 100,
        "manual_url":  "https://github.com/pigshell/india-census-2011/blob/master/pca-full.csv",
        "instruction": (
            "1. Open the URL above in your browser\n"
            "   2. Click the Download raw file button (down-arrow icon, top right)\n"
            "   3. Save the file\n"
            "   4. Rename it to:  census_houselisting.csv\n"
            "   5. Move it to:    data\\raw\\"
        ),
    },
}


# ─────────────────────────────────────────────────────────────
# Files this script downloads automatically
# ─────────────────────────────────────────────────────────────

AUTO_DOWNLOADS = {
    "india_census_repo_zip": {
        "url":         "https://github.com/nishusharma1608/India-Census-2011-Analysis/archive/refs/heads/master.zip",
        "dest":        SHAPEFILES / "india_census_analysis.zip",
        "extract_to":  SHAPEFILES / "india_census_analysis",
        "description": "India Census 2011 Analysis repo — contains India shapefiles",
        "min_size_kb": 500,
    },
    "gadm_india": {
        "url":         "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_IND_shp.zip",
        "dest":        SHAPEFILES / "gadm41_IND.zip",
        "extract_to":  SHAPEFILES / "gadm41_IND",
        "description": "GADM 4.1 India district + state shapefiles (fallback)",
        "min_size_kb": 5000,
    },
}


# ─────────────────────────────────────────────────────────────
# Download helpers
# ─────────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(4),
)
def _download(url: str, dest: Path, min_size_kb: int = 10) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = dest.stat().st_size if dest.exists() else 0
    headers = {"User-Agent": "Mozilla/5.0 IndiaDevAnalytics/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=180)
        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 404:
            logger.error(f"404 Not Found: {url}")
            return False
        if "text/html" in content_type and min_size_kb > 50:
            logger.error(f"Server returned an HTML page instead of a file: {url}")
            return False
        resp.raise_for_status()
    except requests.HTTPError as exc:
        logger.error(f"HTTP error: {exc}")
        return False

    total = int(resp.headers.get("content-length", 0)) + existing
    mode = "ab" if existing and resp.status_code == 206 else "wb"

    with open(dest, mode) as fh, tqdm(
        total=total, initial=existing,
        unit="B", unit_scale=True, unit_divisor=1024,
        desc=dest.name, leave=False,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            if chunk:
                fh.write(chunk)
                bar.update(len(chunk))

    actual_kb = dest.stat().st_size / 1024
    if actual_kb < min_size_kb:
        logger.error(f"File too small after download: {actual_kb:.0f} KB (expected ≥ {min_size_kb} KB)")
        dest.unlink(missing_ok=True)
        return False
    return True


def _extract(zip_path: Path, extract_to: Path) -> None:
    extract_to.mkdir(parents=True, exist_ok=True)
    logger.info(f"Extracting {zip_path.name} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    logger.info(f"Extracted to {extract_to}")


def setup_shapefiles_from_repo() -> None:
    """Copy India_SHP folder from the downloaded census repo zip."""
    repo_dir = SHAPEFILES / "india_census_analysis"
    if not repo_dir.exists():
        return

    shp_dirs = [p.parent for p in repo_dir.rglob("*.shp")]
    if not shp_dirs:
        logger.warning("No .shp files found inside the downloaded repo zip")
        return

    src = shp_dirs[0]
    dst = SHAPEFILES / "india_shp"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    shp_files = list(dst.rglob("*.shp"))
    logger.info(f"Shapefiles set up at {dst} — found {len(shp_files)} .shp file(s)")


# ─────────────────────────────────────────────────────────────
# Check manual files
# ─────────────────────────────────────────────────────────────

def check_manual_files() -> tuple[list[str], list[str]]:
    ok, missing = [], []
    for filename, meta in MANUAL_FILES.items():
        path = RAW / filename
        if path.exists():
            size_kb = path.stat().st_size / 1024
            if size_kb >= meta["min_size_kb"]:
                ok.append(filename)
                logger.info(f"[OK] {filename}  ({size_kb:.0f} KB)")
            else:
                missing.append(filename)
                logger.error(
                    f"[TOO SMALL] {filename} is {size_kb:.0f} KB "
                    f"— expected at least {meta['min_size_kb']} KB. "
                    f"Delete it and re-download."
                )
        else:
            missing.append(filename)
    return ok, missing


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

@click.command()
@click.option("--check-only", is_flag=True, default=False,
              help="Only check which files exist, do not download anything")
@click.option("--force", is_flag=True, default=False,
              help="Re-download shapefiles even if they already exist")
@click.option("--skip-gadm", is_flag=True, default=False,
              help="Skip the large GADM download (~150 MB). Use if internet is slow.")
def main(check_only: bool, force: bool, skip_gadm: bool):
    """Download and verify all pipeline data files."""

    print("\n" + "=" * 62)
    print("  India Dev Analytics — Data Downloader")
    print("=" * 62 + "\n")

    # ── 1. Check manually downloaded files ───────────────────
    print("Step 1/3  Checking manually-downloaded census files ...\n")
    ok_files, missing_files = check_manual_files()

    if missing_files:
        print("\n" + "!" * 62)
        print("  ACTION REQUIRED — download these files in your browser:")
        print("!" * 62)
        for filename in missing_files:
            meta = MANUAL_FILES[filename]
            print(f"\n  ► {filename}")
            print(f"    Description : {meta['description']}")
            print(f"    Download URL: {meta['manual_url']}")
            print(f"    Steps       : {meta['instruction']}")
        print("\n  Once downloaded, re-run:  python scripts\\download_data.py\n")
        if check_only:
            sys.exit(1)
    else:
        print("  All census files present.\n")

    if check_only:
        return

    # ── 2. Auto-download shapefiles ───────────────────────────
    print("Step 2/3  Downloading shapefiles automatically ...\n")

    for key, meta in AUTO_DOWNLOADS.items():
        if skip_gadm and key == "gadm_india":
            print(f"  [SKIP] {key} (--skip-gadm flag set)")
            continue

        dest: Path      = meta["dest"]
        extract_to: Path = meta["extract_to"]

        # Already extracted?
        if extract_to.exists() and any(extract_to.rglob("*.shp")) and not force:
            logger.info(f"[SKIP] {key} already extracted at {extract_to}")
            continue

        # Already downloaded but not extracted?
        if dest.exists() and dest.stat().st_size / 1024 >= meta["min_size_kb"] and not force:
            logger.info(f"[SKIP download] {dest.name} already present — extracting only")
            _extract(dest, extract_to)
            continue

        logger.info(f"[DOWNLOAD] {meta['description']}")
        ok = _download(meta["url"], dest, meta["min_size_kb"])
        if ok:
            _extract(dest, extract_to)
        else:
            logger.warning(
                f"Auto-download failed for {key}. "
                f"Pipeline will still work if census CSV files are present."
            )

    setup_shapefiles_from_repo()

    # ── 3. Final status report ────────────────────────────────
    print("\nStep 3/3  Final status check ...\n")
    ok_files, missing_files = check_manual_files()

    shp_ok  = (SHAPEFILES / "india_shp").exists() and any((SHAPEFILES / "india_shp").rglob("*.shp"))
    gadm_ok = (SHAPEFILES / "gadm41_IND").exists() and any((SHAPEFILES / "gadm41_IND").rglob("*.shp"))

    rows = [
        ("census_primary_abstract.csv", "census_primary_abstract.csv" in ok_files),
        ("census_houselisting.csv",     "census_houselisting.csv"     in ok_files),
        ("India shapefiles",            shp_ok),
        ("GADM shapefiles (fallback)",  gadm_ok),
    ]
    for name, status in rows:
        icon = "✓" if status else "✗"
        print(f"  {icon}  {name}")

    print()
    if missing_files:
        print("  Some census files are missing — see instructions above.\n")
        sys.exit(1)
    else:
        print("  All required files are present.\n")
        print("  Next step:  python scripts\\clean_transform.py\n")


if __name__ == "__main__":
    main()
