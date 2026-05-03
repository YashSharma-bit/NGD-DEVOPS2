"""
api/routers/compare.py
----------------------
GET /compare?d1=&d2=            district comparison (LGD code OR name)
GET /compare/districts?d1=&d2=  explicit district comparison
GET /compare/states?s1=&s2=     state comparison (LGD code OR name)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas import CompareResponse, ComparisonIndicator
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
# SQL
# ─────────────────────────────────────────────────────────────

DISTRICT_PROFILE_SQL = """
    SELECT
        d.district_name         AS name,
        s.state_name,
        dem.literacy_rate,
        dem.female_literacy_rate,
        dem.sex_ratio,
        dem.worker_participation_rate,
        dem.population_total,
        eco.hh_electricity_pct,
        eco.hh_safe_drinking_water_pct,
        eco.hh_latrine_pct,
        eco.hh_banking_pct,
        eco.hh_mobile_phone_pct,
        eco.hh_computer_internet_pct,
        eco.nightlight_mean,
        di.composite_score,
        di.composite_rank,
        di.cluster_label
    FROM districts d
    LEFT JOIN states s             ON s.id = d.state_id
    LEFT JOIN demographics dem     ON dem.district_id = d.id
    LEFT JOIN economic_data eco    ON eco.district_id = d.id
    LEFT JOIN development_index di ON di.district_id = d.id
    WHERE
        d.lgd_district_code = :code
        OR LOWER(d.district_name)      = LOWER(:raw)
        OR LOWER(d.district_name_norm) = LOWER(:raw)
    LIMIT 1
"""

STATE_PROFILE_SQL = """
    SELECT
        s.state_name            AS name,
        sa.avg_literacy_rate    AS literacy_rate,
        sa.avg_female_literacy_rate AS female_literacy_rate,
        sa.avg_sex_ratio        AS sex_ratio,
        sa.avg_electrification_pct AS hh_electricity_pct,
        sa.avg_safe_water_pct   AS hh_safe_drinking_water_pct,
        sa.avg_banking_pct      AS hh_banking_pct,
        sa.avg_dev_index        AS composite_score,
        sa.population_total
    FROM states s
    LEFT JOIN state_aggregates sa ON sa.state_id = s.id
    WHERE
        s.lgd_state_code = :code
        OR LOWER(s.state_name)      = LOWER(:raw)
        OR LOWER(s.state_name_norm) = LOWER(:raw)
    LIMIT 1
"""

INDICATORS = [
    ("literacy_rate",               "Literacy Rate",              "%"),
    ("female_literacy_rate",        "Female Literacy Rate",       "%"),
    ("sex_ratio",                   "Sex Ratio",                  "F per 1000 M"),
    ("worker_participation_rate",   "Worker Participation Rate",  "%"),
    ("hh_electricity_pct",          "Electrification Rate",       "% HH"),
    ("hh_safe_drinking_water_pct",  "Safe Drinking Water",        "% HH"),
    ("hh_latrine_pct",              "Toilet Access",              "% HH"),
    ("hh_banking_pct",              "Banking Access",             "% HH"),
    ("hh_mobile_phone_pct",         "Mobile Phone Ownership",     "% HH"),
    ("hh_computer_internet_pct",    "Internet Access",            "% HH"),
    ("nightlight_mean",             "Nighttime Radiance (proxy)", "nW/cm²/sr"),
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _normalize_district_code(value: str) -> str:
    """
    LGD district codes are stored zero-padded to 4 digits (e.g. '0515').
    Accept bare integers like '515' or '9' and pad them automatically.
    Non-numeric values (district names) are returned as-is.
    """
    stripped = value.strip()
    if stripped.isdigit():
        return stripped.zfill(4)
    return stripped


def _normalize_state_code(value: str) -> str:
    """
    LGD state codes are stored zero-padded to 2 digits (e.g. '09').
    Accept bare integers like '9' and pad them automatically.
    Non-numeric values (state names) are returned as-is.
    """
    stripped = value.strip()
    if stripped.isdigit():
        return stripped.zfill(2)
    return stripped


def _build_comparison(
    row_a, row_b, name_a: str, name_b: str, entity_type: str
) -> CompareResponse:
    indicators = []
    for col, label, unit in INDICATORS:
        va = getattr(row_a, col, None)
        vb = getattr(row_b, col, None)
        diff = (
            round(float(va) - float(vb), 3)
            if (va is not None and vb is not None)
            else None
        )
        better = None
        if diff is not None:
            if col == "sex_ratio":
                better = name_a if float(va) > float(vb) else name_b
            else:
                better = name_a if diff > 0 else name_b
        indicators.append(
            ComparisonIndicator(
                indicator=label,
                unit=unit,
                entity_a_value=round(float(va), 2) if va is not None else None,
                entity_b_value=round(float(vb), 2) if vb is not None else None,
                difference=diff,
                better_entity=better,
            )
        )

    score_a = getattr(row_a, "composite_score", None)
    score_b = getattr(row_b, "composite_score", None)
    if score_a is not None and score_b is not None:
        sa, sb = float(score_a), float(score_b)
        if sa > sb:
            summary = f"{name_a} is more developed than {name_b} (score {sa:.1f} vs {sb:.1f})"
        elif sb > sa:
            summary = f"{name_b} is more developed than {name_a} (score {sb:.1f} vs {sa:.1f})"
        else:
            summary = f"{name_a} and {name_b} have equal development scores."
    else:
        summary = "Development score comparison unavailable for one or both entities."

    return CompareResponse(
        entity_a=name_a,
        entity_b=name_b,
        entity_type=entity_type,
        indicators=indicators,
        overall_dev_score_a=float(score_a) if score_a is not None else None,
        overall_dev_score_b=float(score_b) if score_b is not None else None,
        summary=summary,
    )


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=CompareResponse,
    summary="Compare two districts by LGD code or name",
)
async def compare_districts(
    d1: str = Query(..., description="LGD district code (e.g. 515 or 0515) or district name"),
    d2: str = Query(..., description="LGD district code (e.g. 230 or 0230) or district name"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two districts. Accepts:
    - LGD district codes (with or without zero-padding): 515, 0515
    - District names: Kanpur, Patna
    """
    code_a = _normalize_district_code(d1)
    code_b = _normalize_district_code(d2)

    async with db as session:
        row_a = (
            await session.execute(
                text(DISTRICT_PROFILE_SQL), {"code": code_a, "raw": d1.strip()}
            )
        ).fetchone()
        row_b = (
            await session.execute(
                text(DISTRICT_PROFILE_SQL), {"code": code_b, "raw": d2.strip()}
            )
        ).fetchone()

    if not row_a:
        raise HTTPException(
            status_code=404,
            detail=f"District '{d1}' not found. Use LGD code (e.g. '0515') or district name.",
        )
    if not row_b:
        raise HTTPException(
            status_code=404,
            detail=f"District '{d2}' not found. Use LGD code (e.g. '0230') or district name.",
        )

    name_a = f"{row_a.name}, {row_a.state_name}"
    name_b = f"{row_b.name}, {row_b.state_name}"
    return _build_comparison(row_a, row_b, name_a, name_b, "district")


@router.get(
    "/districts",
    response_model=CompareResponse,
    summary="Compare two districts (explicit endpoint)",
)
async def compare_districts_explicit(
    d1: str = Query(..., description="LGD district code or name"),
    d2: str = Query(..., description="LGD district code or name"),
    db: AsyncSession = Depends(get_db),
):
    """Alias for GET /compare — explicit /districts path."""
    return await compare_districts(d1=d1, d2=d2, db=db)


@router.get(
    "/states",
    response_model=CompareResponse,
    summary="Compare two states by LGD code or name",
)
async def compare_states(
    s1: str = Query(..., description="LGD state code (e.g. 9 or 09) or state name"),
    s2: str = Query(..., description="LGD state code (e.g. 10) or state name"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two states. Accepts:
    - LGD state codes (with or without zero-padding): 9, 09
    - State names: Uttar Pradesh, Bihar
    """
    code_a = _normalize_state_code(s1)
    code_b = _normalize_state_code(s2)

    async with db as session:
        row_a = (
            await session.execute(
                text(STATE_PROFILE_SQL), {"code": code_a, "raw": s1.strip()}
            )
        ).fetchone()
        row_b = (
            await session.execute(
                text(STATE_PROFILE_SQL), {"code": code_b, "raw": s2.strip()}
            )
        ).fetchone()

    if not row_a:
        raise HTTPException(
            status_code=404,
            detail=f"State '{s1}' not found. Use LGD code (e.g. '09') or state name.",
        )
    if not row_b:
        raise HTTPException(
            status_code=404,
            detail=f"State '{s2}' not found. Use LGD code (e.g. '10') or state name.",
        )

    return _build_comparison(row_a, row_b, row_a.name, row_b.name, "state")
