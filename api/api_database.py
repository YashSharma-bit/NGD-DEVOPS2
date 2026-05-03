"""
api/database.py
---------------
Async SQLAlchemy engine + session factory for FastAPI.
"""

from __future__ import annotations
import os
from collections.abc import AsyncGenerator
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

def get_postgres_url():
    user = os.getenv("POSTGRES_USER", "analyst")
    password = os.getenv("POSTGRES_PASSWORD", "yash123")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "india_dev_analytics")
    return "postgresql+asyncpg://" + user + ":" + password + "@" + host + ":" + port + "/" + db

def get_logger(name):
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    return logging.getLogger(name)

def get_config():
    return {}

engine = create_async_engine(
    get_postgres_url(),
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
            count = result.scalar()
            print("DB connected. Districts: " + str(count))
    except Exception as exc:
        print("DB connectivity check failed: " + str(exc))
