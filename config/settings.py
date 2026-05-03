"""
config/settings.py
------------------
Exposes typed config objects consumed by pipeline scripts.

Usage (in scripts):
    from config.settings import neo4j as neo4j_cfg, PROCESSED_DIR, etl
"""

from __future__ import annotations
from pathlib import Path
from config.config_loader import get_config, PROJECT_ROOT

_cfg = get_config()

# ── Paths ──────────────────────────────────────────────────────────────────
DATA_DIR      = PROJECT_ROOT / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR      = PROJECT_ROOT / "logs"

# Create dirs if missing so scripts never crash on first run
for _d in (RAW_DIR, PROCESSED_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Simple namespace (dot-access config objects) ───────────────────────────
class _Namespace:
    def __init__(self, d: dict):
        for k, v in d.items():
            setattr(self, k, _Namespace(v) if isinstance(v, dict) else v)

    def __repr__(self):
        return f"_Namespace({vars(self)})"


# ── Exported config objects ────────────────────────────────────────────────
_neo4j_cfg = {**_cfg["neo4j"], "database": _cfg["neo4j"].get("database", "neo4j")}
neo4j    = _Namespace(_neo4j_cfg)       # .uri  .user  .password  .database  .max_connection_pool_size
postgres = _Namespace(_cfg["postgres"]) # .host .port  .database  .user  .password
etl      = _Namespace(_cfg["etl"])      # .batch_size  .fuzzy_match_threshold
analytics = _Namespace(_cfg["analytics"])
api      = _Namespace(_cfg["api"])
