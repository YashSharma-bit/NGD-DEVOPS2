"""
api/routers/cities.py

Fixes applied:
  - list_cities: state_code and district_code filters now auto zero-pad
    (state 9 → 09, district 515 → 0515).
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.schemas import CityDetail, CitySummary, PaginatedCities
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


def _pad_state(value: str) -> str:
    s = value.strip()
    return s.zfill(2) if s.isdigit() else s


def _pad_district(value: str) -> str:
    s = value.strip()
    return s.zfill(4) if s.isdigit() else s


CITY_SQL = """
    SELECT
        c.id, c.city_name, c.lgd_city_code,
        d.district_name, s.state_name,
        c.population_2011, c.city_class,
        c.latitude, c.longitude,
        c.statutory_town, c.ua_name, c.area_sq_km,
        di.composite_score  AS district_dev_score,
        di.cluster_label    AS district_cluster
    FROM cities c
    JOIN districts d        ON d.id = c.district_id
    JOIN states s           ON s.id = d.state_id
    LEFT JOIN development_index di ON di.district_id = d.id
"""


def _row_to_city(row, detail: bool = False):
    base = dict(
        id=row.id,
        city_name=row.city_name,
        district_name=row.district_name,
        state_name=row.state_name,
        population_2011=row.population_2011,
        city_class=row.city_class,
        latitude=row.latitude,
        longitude=row.longitude,
    )
    if detail:
        base.update(
            lgd_city_code=row.lgd_city_code,
            statutory_town=row.statutory_town,
            ua_name=row.ua_name,
            area_sq_km=row.area_sq_km,
            district_dev_score=row.district_dev_score,
            district_cluster=row.district_cluster,
        )
        return CityDetail(**base)
    return CitySummary(**base)


@router.get("", response_model=PaginatedCities, summary="List all cities")
async def list_cities(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    state_code: Optional[str] = Query(None, description="LGD state code (e.g. 9 or 09)"),
    district_code: Optional[str] = Query(None, description="LGD district code (e.g. 515 or 0515)"),
    city_class: Optional[str] = Query(None, description="I | II | III | IV | V | VI"),
    min_population: Optional[int] = Query(None),
    sort_by: str = Query("population_2011", description="population_2011 | city_name"),
    db: AsyncSession = Depends(get_db),
):
    filters, params = [], {"offset": (page - 1) * page_size, "limit": page_size}

    if state_code:
        filters.append("s.lgd_state_code = :state_code")
        params["state_code"] = _pad_state(state_code)
    if district_code:
        filters.append("d.lgd_district_code = :district_code")
        params["district_code"] = _pad_district(district_code)
    if city_class:
        filters.append("c.city_class = :city_class")
        params["city_class"] = city_class
    if min_population:
        filters.append("c.population_2011 >= :min_pop")
        params["min_pop"] = min_population

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    order_col = sort_by if sort_by in {"population_2011", "city_name"} else "population_2011"

    count_sql = f"""
        SELECT COUNT(*) FROM cities c
        JOIN districts d ON d.id = c.district_id
        JOIN states s    ON s.id = d.state_id
        {where}
    """
    data_sql = f"{CITY_SQL} {where} ORDER BY {order_col} DESC NULLS LAST OFFSET :offset LIMIT :limit"

    async with db as session:
        total = (await session.execute(text(count_sql), params)).scalar()
        rows  = (await session.execute(text(data_sql),  params)).fetchall()

    return PaginatedCities(total=total, page=page, page_size=page_size,
                           results=[_row_to_city(r) for r in rows])


@router.get("/{city_id}", response_model=CityDetail, summary="City detail")
async def city_detail(city_id: int, db: AsyncSession = Depends(get_db)):
    sql = f"{CITY_SQL} WHERE c.id = :cid LIMIT 1"
    async with db as session:
        row = (await session.execute(text(sql), {"cid": city_id})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"City id={city_id} not found")
    return _row_to_city(row, detail=True)
