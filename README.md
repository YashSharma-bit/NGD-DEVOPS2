# India Regional Development Analytics System

> **Production-grade** data pipeline and analytics platform covering **all cities, districts, and states of India** — powered by Census 2011, LGD, PostGIS, Neo4j, and FastAPI.

---

## 📐 Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (Public / Open)                  │
│  Census 2011 · LGD · GADM/Datameet Shapefiles · SECC · VIIRS   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   ETL Pipeline      │  Python + GeoPandas
              │  download_data.py   │  ─ resumable streaming
              │  clean_transform.py │  ─ fuzzy name harmonisation
              │  geospatial_join.py │  ─ PostGIS-ready GeoParquet
              │  load_postgres.py   │  ─ batched upserts
              │  load_neo4j.py      │  ─ graph model
              └──────┬───────┬──────┘
                     │       │
        ┌────────────▼─┐  ┌──▼────────────┐
        │  PostgreSQL  │  │    Neo4j       │
        │  + PostGIS   │  │  Graph DB      │
        │  All tables  │  │  State→Dist→  │
        │  Spatial idx │  │  City + BORDR │
        └──────┬───────┘  └───────────────┘
               │
     ┌─────────▼──────────┐      ┌────────────────────┐
     │  Analytics Module  │      │   Visualisation    │
     │  • Dev Index       │      │  • Choropleth maps │
     │  • K-Means cluster │      │  • Cluster maps    │
     │  • Gini/Theil/CV   │      │  • Inequality heat │
     └─────────┬──────────┘      └────────────────────┘
               │
     ┌─────────▼──────────┐
     │   FastAPI (REST)   │
     │  /cities           │
     │  /districts        │
     │  /states           │
     │  /compare          │
     │  /top-developed    │
     │  /nearby           │
     └────────────────────┘
```

---

## 📦 Project Structure

```
india_dev_analytics/
├── config/
│   ├── settings.yaml          # Central configuration (all settings)
│   └── config_loader.py       # Env-var expansion, config access
│
├── scripts/                   # ETL Pipeline (5 stages)
│   ├── download_data.py       # Stage 1: Download all datasets
│   ├── clean_transform.py     # Stage 2: Clean, normalise, harmonise
│   ├── geospatial_join.py     # Stage 3: Spatial join → GeoParquet
│   ├── load_postgres.py       # Stage 4: PostGIS bulk load
│   └── load_neo4j.py          # Stage 5: Graph load
│
├── analytics/
│   ├── development_index.py   # Dev index, clustering, inequality
│   └── visualisation.py       # Choropleth, heatmap, scatter plots
│
├── api/
│   ├── main.py                # FastAPI app, middleware, lifespan
│   ├── database.py            # Async SQLAlchemy engine
│   ├── schemas.py             # Pydantic v2 request/response models
│   └── routers/
│       ├── districts.py       # /districts endpoints
│       ├── states.py          # /states endpoints
│       ├── cities.py          # /cities endpoints
│       ├── compare.py         # /compare endpoints
│       └── health.py          # /health
│
├── database/
│   ├── postgres/schema.sql    # PostGIS schema + triggers + mat views
│   └── neo4j/queries.cypher   # Reference Cypher queries
│
├── docker/
│   ├── docker-compose.yml     # Full stack: PG + Neo4j + Redis + API
│   ├── Dockerfile.api         # FastAPI container
│   └── Dockerfile.etl         # Pipeline runner container
│
├── data/
│   ├── raw/                   # Downloaded source files
│   ├── processed/             # Parquet / GeoParquet outputs
│   └── shapefiles/            # Extracted shapefiles
│
├── tests/
│   └── test_pipeline.py       # Pytest suite
│
├── notebooks/                 # Jupyter exploration notebooks
├── logs/                      # Pipeline + API log files
├── run_pipeline.py            # Master orchestrator CLI
├── requirements.txt
└── .env.example
```

---

## 🗂️ Data Sources

| Dataset | Source | URL | Level |
|---|---|---|---|
| **Census 2011 PCA** | Census of India | [censusindia.gov.in](https://censusindia.gov.in/nada/index.php/catalog/42584) | District |
| **Houselisting Census** | Census of India | [censusindia.gov.in](https://censusindia.gov.in/nada/index.php/catalog/42585) | District |
| **District Shapefiles** | Datameet / Census 2011 | [github.com/datameet/maps](https://github.com/datameet/maps/raw/master/Districts/Census_2011/2011_Dist.zip) | District |
| **State Shapefiles** | Datameet | [github.com/datameet/maps](https://github.com/datameet/maps/raw/master/States/Admin2.zip) | State |
| **Sub-district Shapefiles** | Datameet | [github.com/datameet/maps](https://github.com/datameet/maps/raw/master/SubDistricts/census_subdistrict_2011.zip) | Sub-district |
| **GADM 4.1 (fallback)** | UC Davis | [geodata.ucdavis.edu](https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_IND_shp.zip) | State/Dist/Sub |
| **LGD Master** | MoPR | [lgdirectory.gov.in](https://lgdirectory.gov.in) | All levels |
| **SECC 2011 Rural** | Datameet | [github.com/datameet/india-district-level-databases](https://raw.githubusercontent.com/datameet/india-district-level-databases/master/socio_economic/secc_rural_summary.csv) | District |
| **Nighttime Lights** | NASA VIIRS | [eogdata.mines.edu](https://eogdata.mines.edu/nighttime_light/annual/v22/) | Raster |

---

## ⚙️ Setup Instructions

### Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | ≥ 3.11 | Pipeline + API |
| PostgreSQL + PostGIS | ≥ 15 + ≥ 3.4 | Spatial database |
| Neo4j Community | ≥ 5.x | Graph database |
| Redis | ≥ 7.x | API cache |
| Docker + Compose | ≥ 24 | Optional container stack |
| GDAL | ≥ 3.6 | Geospatial processing |

---

### Option A: Docker (Recommended)

```bash
# 1. Clone / copy project
git clone <repo> india_dev_analytics
cd india_dev_analytics

# 2. Configure environment
cp .env.example .env
nano .env   # fill in passwords

# 3. Start databases + API
docker compose -f docker/docker-compose.yml up -d postgres neo4j redis

# 4. Wait for databases to be ready (~30 seconds), then run ETL
docker compose -f docker/docker-compose.yml --profile etl up etl

# 5. Start the API
docker compose -f docker/docker-compose.yml up -d api

# 6. Verify
curl http://localhost:8000/health
open http://localhost:8000/docs
```

---

### Option B: Local Python Environment

#### 1. System dependencies

```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y \
    python3.11 python3.11-venv \
    gdal-bin libgdal-dev libpq-dev \
    postgresql-15 postgresql-15-postgis-3 \
    redis-server

# macOS (Homebrew)
brew install python@3.11 gdal postgresql@15 postgis redis
```

#### 2. Python virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. PostgreSQL setup

```bash
# Create database and enable PostGIS
sudo -u postgres psql << 'EOF'
CREATE DATABASE india_dev_analytics;
CREATE USER analyst WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE india_dev_analytics TO analyst;
\c india_dev_analytics
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION pg_trgm;
CREATE EXTENSION btree_gin;
CREATE EXTENSION "uuid-ossp";
GRANT ALL ON ALL TABLES IN SCHEMA public TO analyst;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO analyst;
EOF
```

#### 4. Neo4j setup

```bash
# Download Neo4j Community 5.x
wget https://dist.neo4j.org/neo4j-community-5.19.0-unix.tar.gz
tar -xf neo4j-community-5.19.0-unix.tar.gz
cd neo4j-community-5.19.0

# Set password
bin/neo4j-admin dbms set-initial-password your_neo4j_password

# Start
bin/neo4j start

# Verify
curl http://localhost:7474
```

#### 5. Configure environment

```bash
cp .env.example .env
# Edit .env with your database credentials
nano .env
```

---

## 🚀 Execution Guide

### Stage-by-stage execution

#### Stage 1: Download data

```bash
# Download all configured datasets
python scripts/download_data.py

# Download only shapefiles
python scripts/download_data.py --source shapefiles_district

# Force re-download
python scripts/download_data.py --force

# Include supplementary sources (SECC, LGD, budget data)
python scripts/download_data.py --include-supplementary
```

**Expected outputs:**
```
data/raw/census_primary_abstract.xlsx     (~50 MB)
data/raw/census_houselisting.xlsx         (~80 MB)
data/raw/lgd_districts.xlsx               (~2 MB)
data/raw/lgd_subdistricts.xlsx            (~10 MB)
data/shapefiles/districts_2011.zip        (~30 MB)
data/shapefiles/states.zip                (~5 MB)
data/raw/secc_rural.csv                   (~8 MB)
```

---

#### Stage 2: Clean and transform

```bash
# Run all cleaning stages
python scripts/clean_transform.py

# Run specific stage
python scripts/clean_transform.py --stage census_primary
python scripts/clean_transform.py --stage lgd
python scripts/clean_transform.py --stage merge --csv

# Expected outputs:
# data/processed/lgd_districts.parquet
# data/processed/census_primary_raw.parquet
# data/processed/houselisting_raw.parquet
# data/processed/districts_merged.parquet   ← merged tabular dataset
```

---

#### Stage 3: Geospatial join

```bash
python scripts/geospatial_join.py

# Specific level
python scripts/geospatial_join.py --level districts
python scripts/geospatial_join.py --level states

# Expected outputs:
# data/processed/states_geo.parquet
# data/processed/districts_geo.parquet      ← geometry + census data
# data/processed/subdistricts_geo.parquet
```

---

#### Stage 4: Load PostgreSQL

```bash
python scripts/load_postgres.py

# Specific tables
python scripts/load_postgres.py --table states
python scripts/load_postgres.py --table districts
python scripts/load_postgres.py --table demographics

# Reset all tables and reload
python scripts/load_postgres.py --reset

# Expected: ~640 districts, 36 states/UTs, 4000+ cities loaded
```

---

#### Stage 5 (Analytics): Compute development index

```bash
python analytics/development_index.py

# Also push to PostgreSQL
python analytics/development_index.py --push-db

# Expected outputs:
# data/processed/development_index.parquet
# data/processed/state_inequality.parquet
# Console: Top/bottom 10 districts printed
```

---

#### Stage 6: Load Neo4j

```bash
python scripts/load_neo4j.py

# Specific mode
python scripts/load_neo4j.py --mode hierarchy
python scripts/load_neo4j.py --mode borders
python scripts/load_neo4j.py --mode similarity

# Expected graph:
# ~36 State nodes, ~640 District nodes, ~4000+ City nodes
# ~1200+ BORDERS relationships
```

---

#### Stage 7: Generate visualisations

```bash
python analytics/visualisation.py

# HTML only (interactive)
python analytics/visualisation.py --format html

# Custom output directory
python analytics/visualisation.py --output-dir /var/www/html/maps

# Expected outputs:
# data/processed/viz/choropleth_development_index.png
# data/processed/viz/choropleth_interactive.html
# data/processed/viz/cluster_map.png
# data/processed/viz/state_inequality_heatmap.png
# data/processed/viz/scatter_dev_vs_population.html
```

---

### Run the full pipeline in one command

```bash
python run_pipeline.py

# Skip download if data already exists
python run_pipeline.py --stages clean,geo,postgres,analytics,neo4j,viz

# Skip visualisation
python run_pipeline.py --skip viz
```

---

### Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Development mode (auto-reload)
uvicorn api.main:app --reload --port 8000
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | System info + endpoint map |
| `GET` | `/health` | Health check + row counts |
| `GET` | `/states` | All states (paginated) |
| `GET` | `/states/{code}` | State detail + aggregates |
| `GET` | `/districts` | All districts (paginated, filterable) |
| `GET` | `/districts/{code}` | Full district profile |
| `GET` | `/districts/search?q=` | Fuzzy search (pg_trgm) |
| `GET` | `/districts/top-developed?n=20` | Top N districts |
| `GET` | `/districts/least-developed?n=20` | Bottom N districts |
| `GET` | `/districts/by-cluster/{label}` | Districts by cluster |
| `GET` | `/districts/state/{state_code}` | Districts in a state |
| `GET` | `/districts/nearby?lat=&lon=&radius_km=` | Spatial proximity |
| `GET` | `/cities` | All cities (dynamic, no hardcoding) |
| `GET` | `/cities/{id}` | City detail |
| `GET` | `/compare?d1=&d2=` | Compare two districts |
| `GET` | `/compare/states?s1=&s2=` | Compare two states |

**Interactive docs:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

### Example API calls

```bash
# List all districts in Karnataka
curl "http://localhost:8000/districts/state/29"

# Search for Wayanad
curl "http://localhost:8000/districts/search?q=wayanad"

# Top 10 most developed districts in India
curl "http://localhost:8000/districts/top-developed?n=10"

# Compare Ernakulam vs Wayanad
curl "http://localhost:8000/compare?d1=0698&d2=0699"

# Districts near Bengaluru (150 km)
curl "http://localhost:8000/districts/nearby?lat=12.97&lon=77.59&radius_km=150"

# All cities with population > 1 million
curl "http://localhost:8000/cities?min_population=1000000"

# Aspirational cluster districts
curl "http://localhost:8000/districts/by-cluster/Aspirational"
```

---

## 📊 Development Index

The composite development index aggregates 8 indicators into a single 0–100 score:

| Indicator | Source | Weight |
|---|---|---|
| Literacy Rate | Census 2011 PCA | 20% |
| Electrification Rate (% HH) | Houselisting Census | 15% |
| Safe Drinking Water (% HH) | Houselisting Census | 15% |
| Toilet Access (% HH) | Houselisting Census | 10% |
| Female Literacy Rate | Census 2011 PCA | 10% |
| Worker Participation Rate | Census 2011 PCA | 10% |
| Banking Access (% HH) | Houselisting Census | 10% |
| Internet Access (% HH) | Houselisting Census | 5% |
| Road/Motorable Access | Houselisting Census | 5% |

**Normalisation:** Min-Max (configurable: min_max / zscore / robust)  
**Clustering:** K-Means, k=6 clusters:

| Cluster | Description |
|---|---|
| 0 — Aspirational | Lowest development, requires highest policy priority |
| 1 — Developing | Below national average across most indicators |
| 2 — Transitioning | Mixed performance, improving |
| 3 — Growing | Above average, progressing well |
| 4 — Advanced | High development, minimal deprivation |
| 5 — Metro/High-Performance | Top tier: major urban centres |

---

## 🔧 Configuration

All settings are in `config/settings.yaml`. Key knobs:

```yaml
analytics:
  development_index:
    weights:           # Adjust indicator weights (must sum to 1)
      literacy_rate: 0.20
    normalization: "min_max"   # or zscore or robust

  clustering:
    n_clusters: 6              # Increase for finer granularity
    algorithm: "kmeans"

etl:
  fuzzy_match_threshold: 85   # Lower = more permissive name matching
  batch_size: 5000            # Rows per DB insert batch
```

---

## 🧪 Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=scripts --cov=analytics --cov=api --cov-report=html

# Specific test class
pytest tests/test_pipeline.py::TestDevelopmentIndex -v
```

---

## 🩺 Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `FileNotFoundError: districts_geo.parquet` | Stages run out of order | Run stages 1→2→3 first |
| District name mismatches | Census ≠ LGD names | Lower `fuzzy_match_threshold` to 75 |
| PostGIS geometry error | Wrong SRID | Ensure CRS = EPSG:4326 in geospatial_join.py |
| Neo4j auth error | Wrong password | Check `NEO4J_PASSWORD` in `.env` |
| `GDAL not found` | Missing system GDAL | `sudo apt-get install gdal-bin libgdal-dev` |
| API `422 Unprocessable Entity` | Schema mismatch | Check `api/schemas.py` field names vs DB columns |
| Download timeout | Slow/unstable connection | Increase `request_timeout` in settings.yaml |

---

## 📝 Notes on District Name Harmonisation

India's Census 2011, LGD, and shapefiles use different district name spellings (e.g. `Bangalore`, `Bengaluru`, `Bengalūru`). This system uses:

1. **Unicode → ASCII normalisation** via `unidecode`
2. **Title-casing and abbreviation expansion** (Dist. → District)
3. **rapidfuzz token_sort_ratio** fuzzy matching (default threshold: 85)
4. **State-scoped matching** — only compare districts within the same state to avoid false positives

Unmatched districts are logged with `logger.warning()` so you can manually inspect and add aliases.

---

## 📄 Licence

Data: Open Government Data (OGD) — Government of India  
Code: MIT


Auto trigger test