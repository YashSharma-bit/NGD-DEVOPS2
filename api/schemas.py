"""
api/schemas.py
--------------
Pydantic v2 response and request models for all API endpoints.
"""

from __future__ import annotations

from typing import Any, Optional
import datetime

from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────
# Shared base
# ─────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────
# Geography
# ─────────────────────────────────────────────────────────────

class Centroid(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None


# ─────────────────────────────────────────────────────────────
# Demographics
# ─────────────────────────────────────────────────────────────

class DemographicsOut(OrmBase):
    population_total: Optional[int] = None
    population_male: Optional[int] = None
    population_female: Optional[int] = None
    households: Optional[int] = None
    literacy_rate: Optional[float] = None
    female_literacy_rate: Optional[float] = None
    sex_ratio: Optional[float] = Field(None, description="Females per 1000 males")
    worker_participation_rate: Optional[float] = None
    sc_proportion: Optional[float] = Field(None, description="% Scheduled Caste")
    st_proportion: Optional[float] = Field(None, description="% Scheduled Tribe")
    agricultural_worker_pct: Optional[float] = None


class EconomicOut(OrmBase):
    hh_electricity_pct: Optional[float] = Field(None, description="% HH with electricity")
    hh_safe_drinking_water_pct: Optional[float] = None
    hh_latrine_pct: Optional[float] = None
    hh_lpg_or_png_pct: Optional[float] = None
    hh_banking_pct: Optional[float] = None
    hh_mobile_phone_pct: Optional[float] = None
    hh_computer_internet_pct: Optional[float] = None
    hh_car_jeep_van_pct: Optional[float] = None
    nightlight_mean: Optional[float] = None


class DevelopmentIndexOut(OrmBase):
    composite_score: Optional[float] = Field(None, description="Composite dev index 0–100")
    composite_rank: Optional[int] = Field(None, description="National rank (1 = most developed)")
    composite_percentile: Optional[float] = None
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None
    score_literacy_rate: Optional[float] = None
    score_electrification: Optional[float] = None
    score_water: Optional[float] = None
    score_sanitation: Optional[float] = None
    score_banking_access: Optional[float] = None
    computed_at: Optional[datetime.datetime] = None


# ─────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────

class StateSummary(OrmBase):
    id: int
    lgd_state_code: str
    state_name: str
    region: Optional[str] = None
    area_sq_km: Optional[float] = None
    centroid: Optional[Centroid] = None
    district_count: Optional[int] = None
    population_total: Optional[int] = None
    avg_literacy_rate: Optional[float] = None
    avg_dev_index: Optional[float] = None


class StateDetail(StateSummary):
    avg_electrification_pct: Optional[float] = None
    avg_safe_water_pct: Optional[float] = None
    avg_banking_pct: Optional[float] = None
    avg_female_literacy_rate: Optional[float] = None
    avg_sex_ratio: Optional[float] = None
    min_dev_index: Optional[float] = None
    max_dev_index: Optional[float] = None
    stddev_dev_index: Optional[float] = None


# ─────────────────────────────────────────────────────────────
# District
# ─────────────────────────────────────────────────────────────

class DistrictSummary(OrmBase):
    id: int
    lgd_district_code: str
    district_name: str
    state_name: Optional[str] = None
    lgd_state_code: Optional[str] = None
    area_sq_km: Optional[float] = None
    centroid: Optional[Centroid] = None
    composite_score: Optional[float] = None
    composite_rank: Optional[int] = None
    cluster_label: Optional[str] = None
    population_total: Optional[int] = None


class DistrictDetail(DistrictSummary):
    demographics: Optional[DemographicsOut] = None
    economic: Optional[EconomicOut] = None
    development_index: Optional[DevelopmentIndexOut] = None


# ─────────────────────────────────────────────────────────────
# City
# ─────────────────────────────────────────────────────────────

class CitySummary(OrmBase):
    id: int
    city_name: str
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    population_2011: Optional[int] = None
    city_class: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CityDetail(CitySummary):
    lgd_city_code: Optional[str] = None
    statutory_town: Optional[bool] = None
    ua_name: Optional[str] = None
    area_sq_km: Optional[float] = None
    district_dev_score: Optional[float] = None
    district_cluster: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Comparison
# ─────────────────────────────────────────────────────────────

class ComparisonIndicator(BaseModel):
    indicator: str
    unit: str
    entity_a_value: Optional[float] = None
    entity_b_value: Optional[float] = None
    difference: Optional[float] = None
    better_entity: Optional[str] = None


class CompareResponse(BaseModel):
    entity_a: str
    entity_b: str
    entity_type: str
    indicators: list[ComparisonIndicator]
    overall_dev_score_a: Optional[float] = None
    overall_dev_score_b: Optional[float] = None
    summary: str


# ─────────────────────────────────────────────────────────────
# Paginated list wrappers
# ─────────────────────────────────────────────────────────────

class PaginatedStates(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[StateSummary]


class PaginatedDistricts(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[DistrictSummary]


class PaginatedCities(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[CitySummary]


# ─────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    entity_type: str    # district | state | city
    entity_id: int
    name: str
    parent_name: Optional[str] = None
    code: Optional[str] = None
    centroid_lat: Optional[float] = None
    centroid_lon: Optional[float] = None
    composite_score: Optional[float] = None
    cluster_label: Optional[str] = None
    population_total: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


# ─────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db_districts: int
    db_states: int
    db_cities: int
    version: str = "1.0.0"
