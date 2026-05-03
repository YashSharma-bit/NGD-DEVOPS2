-- ============================================================
-- India Regional Development Analytics System
-- PostgreSQL + PostGIS Schema
-- ============================================================
-- Run as: psql -U analyst -d india_dev_analytics -f schema.sql
-- Prerequisites: CREATE EXTENSION postgis; (done below)
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;          -- fuzzy text search
CREATE EXTENSION IF NOT EXISTS btree_gin;        -- composite index support
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────
-- Core administrative hierarchy
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS states (
    id                      SERIAL PRIMARY KEY,
    lgd_state_code          VARCHAR(3) UNIQUE NOT NULL,
    census_state_code       VARCHAR(3),
    state_name              VARCHAR(100) NOT NULL,
    state_name_norm         VARCHAR(100),
    state_name_local        VARCHAR(200),         -- name in local language
    iso_code                VARCHAR(10),           -- e.g. IN-KA for Karnataka
    region                  VARCHAR(50),           -- North / South / East / West / Central / NE
    area_sq_km              NUMERIC(12, 2),
    centroid_lat            NUMERIC(10, 6),
    centroid_lon            NUMERIC(10, 6),
    geometry                GEOMETRY(MultiPolygon, 4326),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_states_geom ON states USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_states_name ON states USING GIN(state_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_states_lgd ON states (lgd_state_code);


CREATE TABLE IF NOT EXISTS districts (
    id                      SERIAL PRIMARY KEY,
    lgd_district_code       VARCHAR(6) UNIQUE NOT NULL,
    census_district_code    VARCHAR(6),
    state_id                INTEGER REFERENCES states(id) ON DELETE CASCADE,
    district_name           VARCHAR(150) NOT NULL,
    district_name_norm      VARCHAR(150),
    district_name_local     VARCHAR(300),
    district_hq             VARCHAR(150),         -- headquarter city
    area_sq_km              NUMERIC(12, 2),
    centroid_lat            NUMERIC(10, 6),
    centroid_lon            NUMERIC(10, 6),
    geometry                GEOMETRY(MultiPolygon, 4326),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_districts_geom ON districts USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_districts_name ON districts USING GIN(district_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_districts_state ON districts (state_id);
CREATE INDEX IF NOT EXISTS idx_districts_lgd ON districts (lgd_district_code);


CREATE TABLE IF NOT EXISTS subdistricts (
    id                      SERIAL PRIMARY KEY,
    lgd_subdistrict_code    VARCHAR(8) UNIQUE NOT NULL,
    census_subdistrict_code VARCHAR(8),
    district_id             INTEGER REFERENCES districts(id) ON DELETE CASCADE,
    subdistrict_name        VARCHAR(150) NOT NULL,
    subdistrict_name_norm   VARCHAR(150),
    subdistrict_type        VARCHAR(50),           -- Tehsil / Taluka / Block / Mandal etc.
    area_sq_km              NUMERIC(12, 2),
    centroid_lat            NUMERIC(10, 6),
    centroid_lon            NUMERIC(10, 6),
    geometry                GEOMETRY(MultiPolygon, 4326),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subdist_geom ON subdistricts USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_subdist_district ON subdistricts (district_id);


CREATE TABLE IF NOT EXISTS cities (
    id                      SERIAL PRIMARY KEY,
    lgd_city_code           VARCHAR(10),
    census_town_code        VARCHAR(10),
    district_id             INTEGER REFERENCES districts(id),
    subdistrict_id          INTEGER REFERENCES subdistricts(id),
    city_name               VARCHAR(200) NOT NULL,
    city_name_norm          VARCHAR(200),
    city_name_local         VARCHAR(400),
    city_class              VARCHAR(10),           -- Class I … Class VI (Census classification)
    statutory_town          BOOLEAN DEFAULT TRUE,
    census_town             BOOLEAN DEFAULT FALSE,
    ua_name                 VARCHAR(200),          -- Urban Agglomeration name if applicable
    population_2011         INTEGER,
    area_sq_km              NUMERIC(10, 4),
    latitude                NUMERIC(10, 6),
    longitude               NUMERIC(10, 6),
    geometry                GEOMETRY(Point, 4326),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cities_geom ON cities USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_cities_name ON cities USING GIN(city_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_cities_district ON cities (district_id);


-- ─────────────────────────────────────────────────────────────
-- Demographics (Census 2011 Primary Census Abstract)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS demographics (
    id                          SERIAL PRIMARY KEY,
    district_id                 INTEGER REFERENCES districts(id) ON DELETE CASCADE UNIQUE,
    census_year                 SMALLINT DEFAULT 2011,

    -- Population
    population_total            INTEGER,
    population_male             INTEGER,
    population_female           INTEGER,
    households                  INTEGER,
    population_density          NUMERIC(10, 2),   -- per sq km
    decadal_growth_rate         NUMERIC(6, 2),    -- 2001→2011 %

    -- Literacy
    literates_total             INTEGER,
    literates_male              INTEGER,
    literates_female            INTEGER,
    literacy_rate               NUMERIC(5, 2),
    male_literacy_rate          NUMERIC(5, 2),
    female_literacy_rate        NUMERIC(5, 2),

    -- Gender
    sex_ratio                   NUMERIC(6, 1),    -- females per 1000 males
    child_sex_ratio             NUMERIC(6, 1),    -- 0–6 years

    -- Work participation
    workers_total               INTEGER,
    workers_male                INTEGER,
    workers_female              INTEGER,
    main_workers_total          INTEGER,
    marginal_workers_total      INTEGER,
    non_workers_total           INTEGER,
    worker_participation_rate   NUMERIC(5, 2),
    female_worker_participation NUMERIC(5, 2),

    -- Occupational distribution
    cultivators_total           INTEGER,
    agri_labourers_total        INTEGER,
    household_industry_workers  INTEGER,
    other_workers_total         INTEGER,
    agricultural_worker_pct     NUMERIC(5, 2),

    -- Social groups
    scheduled_caste_total       INTEGER,
    scheduled_tribe_total       INTEGER,
    sc_proportion               NUMERIC(5, 2),
    st_proportion               NUMERIC(5, 2),

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_district ON demographics (district_id);


-- ─────────────────────────────────────────────────────────────
-- Economic & infrastructure data (Houselisting + SECC)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS economic_data (
    id                          SERIAL PRIMARY KEY,
    district_id                 INTEGER REFERENCES districts(id) ON DELETE CASCADE UNIQUE,
    data_year                   SMALLINT DEFAULT 2011,

    -- Household amenities
    total_households            INTEGER,
    hh_electricity              INTEGER,
    hh_electricity_pct          NUMERIC(5, 2),
    hh_safe_drinking_water      INTEGER,
    hh_safe_drinking_water_pct  NUMERIC(5, 2),
    hh_latrine                  INTEGER,
    hh_latrine_pct              NUMERIC(5, 2),
    hh_open_defecation          INTEGER,
    hh_open_defecation_pct      NUMERIC(5, 2),
    hh_lpg_or_png               INTEGER,
    hh_lpg_or_png_pct           NUMERIC(5, 2),
    hh_banking                  INTEGER,
    hh_banking_pct              NUMERIC(5, 2),

    -- Consumer durables
    hh_tv                       INTEGER,
    hh_tv_pct                   NUMERIC(5, 2),
    hh_mobile_phone             INTEGER,
    hh_mobile_phone_pct         NUMERIC(5, 2),
    hh_computer_internet        INTEGER,
    hh_computer_internet_pct    NUMERIC(5, 2),
    hh_bicycle                  INTEGER,
    hh_bicycle_pct              NUMERIC(5, 2),
    hh_scooter_motorcycle       INTEGER,
    hh_scooter_motorcycle_pct   NUMERIC(5, 2),
    hh_car_jeep_van             INTEGER,
    hh_car_jeep_van_pct         NUMERIC(5, 2),

    -- SECC deprivation indicators (rural)
    secc_deprived_hh_pct        NUMERIC(5, 2),
    secc_no_adult_member_pct    NUMERIC(5, 2),
    secc_begging_scavenging_pct NUMERIC(5, 2),

    -- Nighttime lights proxy
    nightlight_mean             NUMERIC(10, 4),
    nightlight_max              NUMERIC(10, 4),

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_econ_district ON economic_data (district_id);


-- ─────────────────────────────────────────────────────────────
-- Development Index (computed by analytics module)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS development_index (
    id                      SERIAL PRIMARY KEY,
    district_id             INTEGER REFERENCES districts(id) ON DELETE CASCADE UNIQUE,
    computed_at             TIMESTAMPTZ DEFAULT NOW(),
    model_version           VARCHAR(20) DEFAULT '1.0',

    -- Composite index (0–100)
    composite_score         NUMERIC(6, 3),
    composite_rank          INTEGER,
    composite_percentile    NUMERIC(5, 2),

    -- Component scores (0–1 normalised)
    score_literacy          NUMERIC(6, 4),
    score_electrification   NUMERIC(6, 4),
    score_water             NUMERIC(6, 4),
    score_sanitation        NUMERIC(6, 4),
    score_female_literacy   NUMERIC(6, 4),
    score_worker_participation NUMERIC(6, 4),
    score_banking           NUMERIC(6, 4),
    score_internet          NUMERIC(6, 4),
    score_road_access       NUMERIC(6, 4),

    -- Clustering
    cluster_id              SMALLINT,
    cluster_label           VARCHAR(50),           -- e.g. "Aspirational", "Developing"

    -- Inequality metrics
    gini_local              NUMERIC(6, 4),         -- within-district inequality proxy

    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devindex_district ON development_index (district_id);
CREATE INDEX IF NOT EXISTS idx_devindex_rank ON development_index (composite_rank);
CREATE INDEX IF NOT EXISTS idx_devindex_cluster ON development_index (cluster_id);


-- ─────────────────────────────────────────────────────────────
-- State-level aggregates (materialised view)
-- ─────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS state_aggregates AS
SELECT
    s.id                                                    AS state_id,
    s.lgd_state_code,
    s.state_name,
    COUNT(d.id)                                             AS district_count,
    SUM(dem.population_total)                               AS population_total,
    AVG(dem.literacy_rate)::NUMERIC(5,2)                    AS avg_literacy_rate,
    AVG(dem.female_literacy_rate)::NUMERIC(5,2)             AS avg_female_literacy_rate,
    AVG(dem.sex_ratio)::NUMERIC(6,1)                        AS avg_sex_ratio,
    AVG(eco.hh_electricity_pct)::NUMERIC(5,2)               AS avg_electrification_pct,
    AVG(eco.hh_safe_drinking_water_pct)::NUMERIC(5,2)       AS avg_safe_water_pct,
    AVG(eco.hh_banking_pct)::NUMERIC(5,2)                   AS avg_banking_pct,
    AVG(di.composite_score)::NUMERIC(6,3)                   AS avg_dev_index,
    MIN(di.composite_score)::NUMERIC(6,3)                   AS min_dev_index,
    MAX(di.composite_score)::NUMERIC(6,3)                   AS max_dev_index,
    STDDEV(di.composite_score)::NUMERIC(6,4)                AS stddev_dev_index,
    NOW()                                                   AS refreshed_at
FROM states s
LEFT JOIN districts d        ON d.state_id = s.id
LEFT JOIN demographics dem   ON dem.district_id = d.id
LEFT JOIN economic_data eco  ON eco.district_id = d.id
LEFT JOIN development_index di ON di.district_id = d.id
GROUP BY s.id, s.lgd_state_code, s.state_name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_state_agg_state ON state_aggregates (state_id);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_state_aggregates()
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY state_aggregates;
END;
$$;


-- ─────────────────────────────────────────────────────────────
-- Full-text search view
-- ─────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW search_index AS
SELECT
    'district'          AS entity_type,
    d.id                AS entity_id,
    d.district_name     AS name,
    s.state_name        AS parent_name,
    d.lgd_district_code AS code,
    d.centroid_lat,
    d.centroid_lon,
    di.composite_score,
    di.cluster_label,
    dem.population_total
FROM districts d
JOIN states s           ON s.id = d.state_id
LEFT JOIN development_index di ON di.district_id = d.id
LEFT JOIN demographics dem     ON dem.district_id = d.id

UNION ALL

SELECT
    'state'             AS entity_type,
    s.id                AS entity_id,
    s.state_name        AS name,
    'India'             AS parent_name,
    s.lgd_state_code    AS code,
    s.centroid_lat,
    s.centroid_lon,
    sa.avg_dev_index    AS composite_score,
    NULL                AS cluster_label,
    sa.population_total
FROM states s
LEFT JOIN state_aggregates sa ON sa.state_id = s.id

UNION ALL

SELECT
    'city'              AS entity_type,
    c.id                AS entity_id,
    c.city_name         AS name,
    d.district_name     AS parent_name,
    c.lgd_city_code     AS code,
    c.latitude          AS centroid_lat,
    c.longitude         AS centroid_lon,
    NULL                AS composite_score,
    NULL                AS cluster_label,
    c.population_2011   AS population_total
FROM cities c
JOIN districts d ON d.id = c.district_id;


-- ─────────────────────────────────────────────────────────────
-- Auto-update timestamps
-- ─────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['states','districts','subdistricts','cities','demographics','economic_data']
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_updated_%1$s ON %1$s;
             CREATE TRIGGER trg_updated_%1$s
             BEFORE UPDATE ON %1$s
             FOR EACH ROW EXECUTE FUNCTION update_updated_at();', t
        );
    END LOOP;
END;
$$;
