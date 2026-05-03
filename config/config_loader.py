"""
config/config_loader.py
-----------------------
Simplified config loader that works without YAML dependency issues.
"""

from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_config() -> dict:
    return {
        "postgres": {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": os.getenv("POSTGRES_PORT", "5432"),
            "database": os.getenv("POSTGRES_DB", "india_dev_analytics"),
            "user": os.getenv("POSTGRES_USER", "analyst"),
            "password": os.getenv("POSTGRES_PASSWORD", "yash123"),
            "pool_size": 5,
            "max_overflow": 10,
        },
        "neo4j": {
            "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", "yash1234"),
            "max_connection_pool_size": 50,
        },
        "etl": {
            "batch_size": 5000,
            "fuzzy_match_threshold": 85,
        },
        "analytics": {
            "development_index": {
                "weights": {
                    "literacy_rate": 0.25,
                    "female_literacy_rate": 0.15,
                    "worker_participation_rate": 0.15,
                    "hh_electricity_pct": 0.15,
                    "hh_safe_drinking_water_pct": 0.10,
                    "hh_latrine_pct": 0.10,
                    "hh_banking_pct": 0.05,
                    "hh_computer_internet_pct": 0.05,
                },
                "normalization": "min_max",
            },
            "clustering": {
                "n_clusters": 6,
                "random_state": 42,
            },
        },
        "api": {
            "host": "0.0.0.0",
            "port": 8000,
            "cors_origins": ["*"],
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "file": "logs/pipeline.log",
            "max_bytes": 10485760,
            "backup_count": 5,
        },
    }


def get_postgres_url(async_driver: bool = False) -> str:
    cfg = get_config()["postgres"]
    driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg2"
    return (
        driver + "://" + cfg["user"] + ":" + cfg["password"]
        + "@" + cfg["host"] + ":" + str(cfg["port"]) + "/" + cfg["database"]
    )


def get_neo4j_config() -> dict:
    return get_config()["neo4j"]


def data_path(relative: str) -> Path:
    return PROJECT_ROOT / relative


def get_logger(name: str):
    import logging
    import sys
    cfg = get_config()["logging"]
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(cfg["level"])
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(cfg["format"]))
        logger.addHandler(handler)
        try:
            fh = logging.FileHandler(str(PROJECT_ROOT / cfg["file"]), encoding="utf-8")
            fh.setFormatter(logging.Formatter(cfg["format"]))
            logger.addHandler(fh)
        except Exception:
            pass
    return logger
