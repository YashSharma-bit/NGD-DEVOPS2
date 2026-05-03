"""
api/routers/health.py
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_db
from api.schemas import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse, summary="API health check")
async def health_check(db: AsyncSession = Depends(get_db)):
    async with db as session:
        try:
            districts = (await session.execute(text("SELECT COUNT(*) FROM districts"))).scalar()
            states = (await session.execute(text("SELECT COUNT(*) FROM states"))).scalar()
            cities = (await session.execute(text("SELECT COUNT(*) FROM cities"))).scalar()
            status = "healthy"
        except Exception:
            districts = states = cities = 0
            status = "degraded"

    return HealthResponse(
        status=status,
        db_districts=districts or 0,
        db_states=states or 0,
        db_cities=cities or 0,
    )
