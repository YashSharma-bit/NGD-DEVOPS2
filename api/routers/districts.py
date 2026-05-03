"""
api/routers/districts.py
------------------------
Endpoints:
  GET /districts                → paginated list of all districts
  GET /districts/{code}         → full profile for one district
  GET /districts/search         → fuzzy search across districts
  GET /districts/top-developed  → top N by composite dev index
  GET /districts/least-developed→ bottom N
  GET /districts/by-cluster/{cluster} → districts in a cluster
  GET /districts/state/{state_code}   → districts of a state
  GET /districts/nearby         → districts near a lat/lon
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas import (
    DistrictDetail,
    DistrictSummary,
    DemographicsOut,
    EconomicOut,
    DevelopmentIndexOut,
    PaginatedDistricts,
    SearchResponse,
    SearchResult,
    Centroid,
)
from config.config_loader import get_logger

logger = get_logger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ─────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────

DISTRICT_SUMMARY_SQL = """
    SELECT
        d.id,
        d.lgd_district_code,
        d.district_name,
        s.state_name,
        s.lgd_state_code,
        d.area_sq_km,
        d.centroid_lat,
        d.centroid_lon,
        di.composite_score,
        di.composite_rank,
        di.cluster_label,
        dem.population_total
    FROM districts d
    LEFT JOIN states s           ON s.id = d.state_id
    LEFT JOIN development_index di ON di.district_id = d.id
    LEFT JOIN demographics dem   ON dem.district_id = d.id
"""


def _row_to_summary(row) -> DistrictSummary:
    return DistrictSummary(
        id=row.id,
        lgd_district_code=row.lgd_district_code,
        district_name=row.district_name,
        state_name=row.state_name,
        lgd_state_code=row.lgd_state_code,
        area_sq_km=row.area_sq_km,
        centroid=Centroid(lat=row.centroid_lat, lon=row.centroid_lon),
        composite_score=row.composite_score,
        composite_rank=row.composite_rank,
        cluster_label=row.cluster_label,
        population_total=row.population_total,
    )


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedDistricts, summary="List all districts")
async def list_districts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200),
    state_code: Optional[str] = Query(None, description="Filter by LGD state code"),
    cluster: Optional[str] = Query(None, description="Filter by cluster label"),
    sort_by: str = Query("composite_rank", description="Sort field: composite_rank | population_total | district_name"),
    order: str = Query("asc", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a paginated list of all districts in India.
    No hardcoded list — fully dynamic from the database.
    """
    allowed_sort = {"composite_rank", "population_total", "district_name", "composite_score"}
    if sort_by not in allowed_sort:
        sort_by = "composite_rank"
    order_sql = "ASC" if order.lower() == "asc" else "DESC"

    filters = []
    params: dict = {"offset": (page - 1) * page_size, "limit": page_size}

    if state_code:
        filters.append("s.lgd_state_code = :state_code")
        params["state_code"] = state_code
    if cluster:
        filters.append("di.cluster_label ILIKE :cluster")
        params["cluster"] = f"%{cluster}%"

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_sql = f"""
        SELECT COUNT(*) FROM districts d
        LEFT JOIN states s ON s.id = d.state_id
        LEFT JOIN development_index di ON di.district_id = d.id
        {where}
    """
    data_sql = f"""
        {DISTRICT_SUMMARY_SQL}
        {where}
        ORDER BY {sort_by} {order_sql} NULLS LAST
        OFFSET :offset LIMIT :limit
    """

    async with db as session:
        total = (await session.execute(text(count_sql), params)).scalar()
        rows = (await session.execute(text(data_sql), params)).fetchall()

    return PaginatedDistricts(
        total=total,
        page=page,
        page_size=page_size,
        results=[_row_to_summary(r) for r in rows],
    )


@router.get("/search", response_model=SearchResponse, summary="Search districts, states, cities")
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across districts, states, and cities.
    Prioritises exact matches, then prefix matches, then fuzzy (pg_trgm).
    """
    sql = """
        SELECT
            entity_type, entity_id, name, parent_name, code,
            centroid_lat, centroid_lon, composite_score,
            cluster_label, population_total,
            similarity(name, :q) AS sim
        FROM search_index
        WHERE name ILIKE :ilike_start
           OR name ILIKE :ilike
           OR name % :q
        ORDER BY
            CASE WHEN LOWER(name) = LOWER(:q)            THEN 0 ELSE 1 END,
            CASE WHEN LOWER(name) LIKE LOWER(:q_start)   THEN 0 ELSE 1 END,
            sim DESC,
            population_total DESC NULLS LAST
        LIMIT :limit
    """
    params = {
        "q": q,
        "ilike": f"%{q}%",
        "ilike_start": f"{q}%",
        "q_start": f"{q}%",
        "limit": limit,
    }

    async with db as session:
        rows = (await session.execute(text(sql), params)).fetchall()

    results = [
        SearchResult(
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            name=r.name,
            parent_name=r.parent_name,
            code=r.code,
            centroid_lat=r.centroid_lat,
            centroid_lon=r.centroid_lon,
            composite_score=r.composite_score,
            cluster_label=r.cluster_label,
            population_total=r.population_total,
        )
        for r in rows
    ]
    return SearchResponse(query=q, total=len(results), results=results)


@router.get("/top-developed", response_model=list[DistrictSummary], summary="Top N most developed districts")
async def top_developed(
    n: int = Query(20, ge=1, le=200, description="Number of results"),
    state_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = ["di.composite_rank IS NOT NULL"]
    params: dict = {"limit": n}
    if state_code:
        filters.append("s.lgd_state_code = :state_code")
        params["state_code"] = state_code

    sql = f"""
        {DISTRICT_SUMMARY_SQL}
        WHERE {" AND ".join(filters)}
        ORDER BY di.composite_rank ASC
        LIMIT :limit
    """
    async with db as session:
        rows = (await session.execute(text(sql), params)).fetchall()
    return [_row_to_summary(r) for r in rows]


@router.get("/least-developed", response_model=list[DistrictSummary], summary="Bottom N least developed districts")
async def least_developed(
    n: int = Query(20, ge=1, le=200),
    state_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = ["di.composite_rank IS NOT NULL"]
    params: dict = {"limit": n}
    if state_code:
        filters.append("s.lgd_state_code = :state_code")
        params["state_code"] = state_code

    sql = f"""
        {DISTRICT_SUMMARY_SQL}
        WHERE {" AND ".join(filters)}
        ORDER BY di.composite_rank DESC
        LIMIT :limit
    """
    async with db as session:
        rows = (await session.execute(text(sql), params)).fetchall()
    return [_row_to_summary(r) for r in rows]


@router.get("/by-cluster/{cluster_label}", response_model=PaginatedDistricts, summary="Districts by development cluster")
async def by_cluster(
    cluster_label: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    params = {
        "cluster": cluster_label,
        "offset": (page - 1) * page_size,
        "limit": page_size,
    }
    count_sql = """
        SELECT COUNT(*) FROM districts d
        JOIN development_index di ON di.district_id = d.id
        WHERE di.cluster_label ILIKE :cluster
    """
    data_sql = f"""
        {DISTRICT_SUMMARY_SQL}
        WHERE di.cluster_label ILIKE :cluster
        ORDER BY di.composite_rank ASC NULLS LAST
        OFFSET :offset LIMIT :limit
    """
    async with db as session:
        total = (await session.execute(text(count_sql), params)).scalar()
        rows = (await session.execute(text(data_sql), params)).fetchall()

    return PaginatedDistricts(
        total=total, page=page, page_size=page_size,
        results=[_row_to_summary(r) for r in rows],
    )


@router.get("/state/{state_code}", response_model=list[DistrictSummary], summary="All districts in a state")
async def districts_by_state(
    state_code: str,
    sort_by: str = Query("composite_rank", description="composite_rank | population_total | district_name"),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"composite_rank", "population_total", "district_name"}
    if sort_by not in allowed:
        sort_by = "composite_rank"

    sql = f"""
        {DISTRICT_SUMMARY_SQL}
        WHERE s.lgd_state_code = :state_code
        ORDER BY {sort_by} ASC NULLS LAST
    """
    async with db as session:
        rows = (await session.execute(text(sql), {"state_code": state_code})).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"State '{state_code}' not found or has no districts")
    return [_row_to_summary(r) for r in rows]


@router.get("/nearby", response_model=list[DistrictSummary], summary="Districts near a coordinate")
async def nearby_districts(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(150.0, description="Search radius in km"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns districts whose centroid falls within radius_km of the given point.
    Uses PostGIS ST_DWithin for spatial query.
    """
    sql = f"""
        {DISTRICT_SUMMARY_SQL}
        WHERE ST_DWithin(
            d.geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius_m
        )
        ORDER BY ST_Distance(
            d.geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        ) ASC
        LIMIT :limit
    """
    params = {"lat": lat, "lon": lon, "radius_m": radius_km * 1000, "limit": limit}
    async with db as session:
        rows = (await session.execute(text(sql), params)).fetchall()
    return [_row_to_summary(r) for r in rows]


@router.get("/{district_code}", response_model=DistrictDetail, summary="Full district profile")
async def district_detail(
    district_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the complete development profile for a district identified by
    its LGD district code (e.g. '0573').
    """
    district_sql = f"""
        {DISTRICT_SUMMARY_SQL}
        WHERE d.lgd_district_code = :code
        LIMIT 1
    """
    demo_sql = """
        SELECT * FROM demographics WHERE district_id = :dist_id LIMIT 1
    """
    econ_sql = """
        SELECT * FROM economic_data WHERE district_id = :dist_id LIMIT 1
    """
    idx_sql = """
        SELECT * FROM development_index WHERE district_id = :dist_id LIMIT 1
    """

    async with db as session:
        row = (await session.execute(text(district_sql), {"code": district_code})).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"District '{district_code}' not found")

        dist_id = row.id
        demo_row = (await session.execute(text(demo_sql), {"dist_id": dist_id})).fetchone()
        econ_row = (await session.execute(text(econ_sql), {"dist_id": dist_id})).fetchone()
        idx_row = (await session.execute(text(idx_sql), {"dist_id": dist_id})).fetchone()

    def safe_map(row_, schema_cls):
        if row_ is None:
            return None
        return schema_cls(**{k: getattr(row_, k, None) for k in schema_cls.model_fields})

    return DistrictDetail(
        id=row.id,
        lgd_district_code=row.lgd_district_code,
        district_name=row.district_name,
        state_name=row.state_name,
        lgd_state_code=row.lgd_state_code,
        area_sq_km=row.area_sq_km,
        centroid=Centroid(lat=row.centroid_lat, lon=row.centroid_lon),
        composite_score=row.composite_score,
        composite_rank=row.composite_rank,
        cluster_label=row.cluster_label,
        population_total=row.population_total,
        demographics=safe_map(demo_row, DemographicsOut),
        economic=safe_map(econ_row, EconomicOut),
        development_index=safe_map(idx_row, DevelopmentIndexOut),
    )
