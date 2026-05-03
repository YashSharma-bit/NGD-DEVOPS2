"""
api/routers/states.py
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.schemas import StateDetail, StateSummary, PaginatedStates, Centroid
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
router = APIRouter()

# ─────────────────────────────────────────────────────────────
# LGD ↔ Census 2011 state code mapping
#
# The shapefiles loaded into the DB may have used Census 2011 codes
# OR GADM codes instead of true LGD codes. This map covers all known
# aliases so that queries like /states/09 and /states/9 and
# /states/Uttar Pradesh all resolve correctly regardless of what
# was stored.
#
# LGD code  : Census 2011 code  (where they differ)
# ─────────────────────────────────────────────────────────────
_LGD_TO_CENSUS: dict[str, str] = {
    "01": "01",  # Jammu & Kashmir
    "02": "02",  # Himachal Pradesh
    "03": "03",  # Punjab
    "04": "04",  # Chandigarh
    "05": "05",  # Uttarakhand
    "06": "06",  # Haryana
    "07": "07",  # Delhi
    "08": "08",  # Rajasthan
    "09": "09",  # Uttar Pradesh
    "10": "10",  # Bihar
    "11": "11",  # Sikkim
    "12": "12",  # Arunachal Pradesh
    "13": "13",  # Nagaland
    "14": "14",  # Manipur
    "15": "15",  # Mizoram
    "16": "16",  # Tripura
    "17": "17",  # Meghalaya
    "18": "18",  # Assam
    "19": "19",  # West Bengal
    "20": "20",  # Jharkhand
    "21": "21",  # Odisha
    "22": "22",  # Chhattisgarh
    "23": "23",  # Madhya Pradesh
    "24": "24",  # Gujarat
    "25": "25",  # Daman & Diu
    "26": "26",  # Dadra & Nagar Haveli
    "27": "27",  # Maharashtra
    "28": "28",  # Andhra Pradesh (pre-bifurcation / residual)
    "29": "29",  # Karnataka
    "30": "30",  # Goa
    "31": "31",  # Lakshadweep
    "32": "32",  # Kerala
    "33": "33",  # Tamil Nadu
    "34": "34",  # Puducherry
    "35": "35",  # Andaman & Nicobar
    "36": "36",  # Telangana  (created 2014 — may be absent in 2011 census data)
    "37": "37",  # Andhra Pradesh (post-bifurcation)
    "38": "38",  # Ladakh      (created 2019 — absent in 2011 data)
}

# Reverse map: census code → LGD code (same for most, kept for completeness)
_CENSUS_TO_LGD: dict[str, str] = {v: k for k, v in _LGD_TO_CENSUS.items()}

# All known aliases for each canonical LGD code
# Format:  lgd_code → [alias1, alias2, ...]
# Add extra aliases here if your shapefile used GADM / other codes.
_EXTRA_ALIASES: dict[str, list[str]] = {
    # Example: GADM used '1' for J&K instead of '01'
    # "01": ["1"],
}


def _normalize_state_code(value: str) -> list[str]:
    """
    Return a list of all code variants to try against the DB,
    covering LGD, Census-2011, and zero/non-zero-padded forms.
    Non-numeric values (state names) return an empty list so the
    caller falls back to name matching only.
    """
    stripped = value.strip()
    if not stripped.isdigit():
        return []

    padded   = stripped.zfill(2)   # e.g. '09'
    unpadded = stripped.lstrip("0") or "0"  # e.g. '9'

    candidates = {padded, unpadded}

    # Add Census alias if different from LGD
    census = _LGD_TO_CENSUS.get(padded)
    if census:
        candidates.add(census)
        candidates.add(census.lstrip("0") or "0")

    # Add LGD alias for census input
    lgd = _CENSUS_TO_LGD.get(padded)
    if lgd:
        candidates.add(lgd)
        candidates.add(lgd.lstrip("0") or "0")

    # Extra shapefile aliases
    for aliases in _EXTRA_ALIASES.get(padded, []):
        candidates.add(aliases)

    return list(candidates)


STATE_SQL = """
    SELECT
        s.id, s.lgd_state_code, s.state_name, s.region,
        s.area_sq_km, s.centroid_lat, s.centroid_lon,
        sa.district_count, sa.population_total,
        sa.avg_literacy_rate, sa.avg_dev_index,
        sa.avg_electrification_pct, sa.avg_safe_water_pct,
        sa.avg_banking_pct, sa.avg_female_literacy_rate,
        sa.avg_sex_ratio, sa.min_dev_index,
        sa.max_dev_index, sa.stddev_dev_index
    FROM states s
    LEFT JOIN state_aggregates sa ON sa.state_id = s.id
"""


def _row_to_state(row, detail: bool = False):
    base = dict(
        id=row.id,
        lgd_state_code=row.lgd_state_code,
        state_name=row.state_name,
        region=row.region,
        area_sq_km=row.area_sq_km,
        centroid=Centroid(lat=row.centroid_lat, lon=row.centroid_lon),
        district_count=row.district_count,
        population_total=row.population_total,
        avg_literacy_rate=row.avg_literacy_rate,
        avg_dev_index=row.avg_dev_index,
    )
    if detail:
        base.update(
            avg_electrification_pct=row.avg_electrification_pct,
            avg_safe_water_pct=row.avg_safe_water_pct,
            avg_banking_pct=row.avg_banking_pct,
            avg_female_literacy_rate=row.avg_female_literacy_rate,
            avg_sex_ratio=row.avg_sex_ratio,
            min_dev_index=row.min_dev_index,
            max_dev_index=row.max_dev_index,
            stddev_dev_index=row.stddev_dev_index,
        )
        return StateDetail(**base)
    return StateSummary(**base)


@router.get("", response_model=PaginatedStates, summary="List all states")
async def list_states(
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=40),
    region: Optional[str] = Query(None, description="Filter: North|South|East|West|Central|NE"),
    sort_by: str = Query("state_name", description="state_name | avg_dev_index | population_total"),
    db: AsyncSession = Depends(get_db),
):
    filters, params = [], {"offset": (page - 1) * page_size, "limit": page_size}
    if region:
        filters.append("s.region ILIKE :region")
        params["region"] = region

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    order_col = sort_by if sort_by in {"state_name", "avg_dev_index", "population_total"} else "state_name"

    count_sql = f"SELECT COUNT(*) FROM states s {where}"
    data_sql  = f"{STATE_SQL} {where} ORDER BY {order_col} ASC NULLS LAST OFFSET :offset LIMIT :limit"

    async with db as session:
        total = (await session.execute(text(count_sql), params)).scalar()
        rows  = (await session.execute(text(data_sql),  params)).fetchall()

    return PaginatedStates(
        total=total, page=page, page_size=page_size,
        results=[_row_to_state(r) for r in rows],
    )


@router.get("/{state_code}", response_model=StateDetail, summary="State detail")
async def state_detail(state_code: str, db: AsyncSession = Depends(get_db)):
    """
    Accepts any of:
    - LGD state code:      09, 9
    - Census 2011 code:    09  (same for most states)
    - State name:          Uttar Pradesh
    - Normalised name:     uttar pradesh
    """
    code_variants = _normalize_state_code(state_code)
    raw = state_code.strip()

    if code_variants:
        # Build  WHERE lgd_state_code IN (:c0, :c1, ...)  OR name match
        in_params = {f"c{i}": v for i, v in enumerate(code_variants)}
        in_clause = ", ".join(f":c{i}" for i in range(len(code_variants)))
        sql = f"""
            {STATE_SQL}
            WHERE s.lgd_state_code IN ({in_clause})
               OR LOWER(s.state_name)      = LOWER(:raw)
               OR LOWER(s.state_name_norm) = LOWER(:raw)
            LIMIT 1
        """
        params = {**in_params, "raw": raw}
    else:
        # Name-only lookup
        sql = f"""
            {STATE_SQL}
            WHERE LOWER(s.state_name)      = LOWER(:raw)
               OR LOWER(s.state_name_norm) = LOWER(:raw)
            LIMIT 1
        """
        params = {"raw": raw}

    async with db as session:
        row = (await session.execute(text(sql), params)).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=(
                f"State '{state_code}' not found. "
                "Use LGD/Census code (e.g. '09') or full state name (e.g. 'Uttar Pradesh')."
            ),
        )
    return _row_to_state(row, detail=True)
