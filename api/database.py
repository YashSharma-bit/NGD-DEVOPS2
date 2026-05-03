from __future__ import annotations
import os
import sys
import logging
from collections.abc import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

load_dotenv()

def _get_url():
    u = os.getenv("POSTGRES_USER", "analyst")
    p = os.getenv("POSTGRES_PASSWORD", "yash123")
    h = os.getenv("POSTGRES_HOST", "localhost")
    pt = os.getenv("POSTGRES_PORT", "5432")
    d = os.getenv("POSTGRES_DB", "india_dev_analytics")
    return "postgresql+asyncpg://" + u + ":" + p + "@" + h + ":" + pt + "/" + d

engine = create_async_engine(
    _get_url(),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def create_tables() -> None:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM districts"))
            print("DB connected. Districts: " + str(result.scalar()))
    except Exception as exc:
        print("DB check failed: " + str(exc))