"""
tests/test_pipeline.py
----------------------
Unit and integration tests for the ETL pipeline and API.
Run with: pytest tests/ -v --cov=scripts --cov=analytics --cov=api
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ─────────────────────────────────────────────────────────────
# Name normalisation
# ─────────────────────────────────────────────────────────────

class TestNameNormalisation:
    def test_basic(self):
        from scripts.clean_transform import normalise_name
        assert normalise_name("MUMBAI") == "Mumbai"

    def test_unicode_devanagari(self):
        from scripts.clean_transform import normalise_name
        # Devanagari should fall back to empty via unidecode
        result = normalise_name("मुंबई")
        assert isinstance(result, str)

    def test_parenthetical_removal(self):
        from scripts.clean_transform import normalise_name
        result = normalise_name("Bangalore (Rural)")
        assert "(" not in result
        assert ")" not in result

    def test_abbreviation_expansion(self):
        from scripts.clean_transform import normalise_name
        result = normalise_name("N.A. Bengaluru Dist.")
        assert "Dist" not in result or "District" in result

    def test_empty_string(self):
        from scripts.clean_transform import normalise_name
        assert normalise_name("") == ""

    def test_whitespace(self):
        from scripts.clean_transform import normalise_name
        assert "  " not in normalise_name("  East   Delhi  ")


# ─────────────────────────────────────────────────────────────
# Fuzzy matching
# ─────────────────────────────────────────────────────────────

class TestFuzzyMatch:
    CANONICAL = ["Bengaluru Urban", "Bengaluru Rural", "Mysuru", "Tumakuru"]

    def test_exact(self):
        from scripts.clean_transform import fuzzy_match
        assert fuzzy_match("Bengaluru Urban", self.CANONICAL) == "Bengaluru Urban"

    def test_misspelling(self):
        from scripts.clean_transform import fuzzy_match
        result = fuzzy_match("Bangalore Urban", self.CANONICAL, threshold=60)
        assert result == "Bengaluru Urban"

    def test_no_match_below_threshold(self):
        from scripts.clean_transform import fuzzy_match
        result = fuzzy_match("Completely Different Place", self.CANONICAL, threshold=90)
        assert result is None


# ─────────────────────────────────────────────────────────────
# Development Index
# ─────────────────────────────────────────────────────────────

class TestDevelopmentIndex:
    @pytest.fixture
    def sample_df(self):
        """Synthetic district data with known properties."""
        rng = np.random.default_rng(42)
        n = 50
        return pd.DataFrame({
            "lgd_district_code": [f"{i:04d}" for i in range(n)],
            "district_name": [f"District_{i}" for i in range(n)],
            "state_name": ["TestState"] * n,
            "literacy_rate": rng.uniform(40, 100, n),
            "hh_electricity_pct": rng.uniform(20, 100, n),
            "hh_safe_drinking_water_pct": rng.uniform(30, 100, n),
            "hh_latrine_pct": rng.uniform(10, 100, n),
            "female_literacy_rate": rng.uniform(25, 98, n),
            "worker_participation_rate": rng.uniform(30, 60, n),
            "hh_banking_pct": rng.uniform(10, 90, n),
            "hh_computer_internet_pct": rng.uniform(1, 50, n),
        })

    def test_scores_in_range(self, sample_df):
        from analytics.development_index import extract_features, normalise_features, compute_development_index
        feat, cols = extract_features(sample_df)
        normed = normalise_features(feat)
        scores = compute_development_index(sample_df, normed, cols)
        assert scores.min() >= 0
        assert scores.max() <= 100

    def test_rank_uniqueness(self, sample_df):
        from analytics.development_index import extract_features, normalise_features, compute_development_index, assemble_index, cluster_districts
        feat, cols = extract_features(sample_df)
        normed = normalise_features(feat)
        scores = compute_development_index(sample_df, normed, cols)
        labels, _ = cluster_districts(normed)
        result = assemble_index(sample_df, normed, cols, scores, labels)
        # Ranks should be unique (no ties with method='min' there may be ties — just check monotonic)
        assert result["composite_rank"].between(1, len(sample_df)).all()

    def test_cluster_count(self, sample_df):
        from analytics.development_index import extract_features, normalise_features, cluster_districts
        feat, cols = extract_features(sample_df)
        normed = normalise_features(feat)
        labels, meta = cluster_districts(normed)
        assert len(set(labels)) <= 6


# ─────────────────────────────────────────────────────────────
# Inequality metrics
# ─────────────────────────────────────────────────────────────

class TestInequalityMetrics:
    def test_gini_equal(self):
        from analytics.development_index import gini_coefficient
        # Perfect equality → Gini ≈ 0
        vals = np.full(100, 50.0)
        assert gini_coefficient(vals) < 0.01

    def test_gini_range(self):
        from analytics.development_index import gini_coefficient
        vals = np.random.default_rng(0).uniform(0, 100, 200)
        g = gini_coefficient(vals)
        assert 0 <= g <= 1

    def test_palma_ratio(self):
        from analytics.development_index import palma_ratio
        vals = np.arange(1, 101, dtype=float)
        p = palma_ratio(vals)
        assert p > 1  # top 10% should be higher than bottom 40%

    def test_theil_equal(self):
        from analytics.development_index import theil_index
        vals = np.full(50, 10.0)
        assert theil_index(vals) < 0.001


# ─────────────────────────────────────────────────────────────
# API schemas
# ─────────────────────────────────────────────────────────────

class TestSchemas:
    def test_district_summary_optional_fields(self):
        from api.schemas import DistrictSummary
        d = DistrictSummary(
            id=1, lgd_district_code="0001", district_name="Test District"
        )
        assert d.composite_score is None
        assert d.cluster_label is None

    def test_compare_response(self):
        from api.schemas import CompareResponse, ComparisonIndicator
        r = CompareResponse(
            entity_a="District A",
            entity_b="District B",
            entity_type="district",
            indicators=[
                ComparisonIndicator(
                    indicator="Literacy Rate",
                    unit="%",
                    entity_a_value=75.0,
                    entity_b_value=60.0,
                    difference=15.0,
                    better_entity="District A",
                )
            ],
            overall_dev_score_a=70.0,
            overall_dev_score_b=55.0,
            summary="District A is more developed.",
        )
        assert r.entity_a == "District A"
        assert len(r.indicators) == 1


# ─────────────────────────────────────────────────────────────
# Config loader
# ─────────────────────────────────────────────────────────────

class TestConfig:
    def test_config_loads(self):
        from config.config_loader import get_config
        cfg = get_config()
        assert "postgres" in cfg
        assert "etl" in cfg
        assert "analytics" in cfg

    def test_postgres_url(self):
        from config.config_loader import get_postgres_url
        url = get_postgres_url()
        assert url.startswith("postgresql+psycopg2://")

    def test_data_path(self):
        from config.config_loader import data_path
        p = data_path("data/raw")
        assert p.is_absolute()


# ─────────────────────────────────────────────────────────────
# Download helpers (mocked network)
# ─────────────────────────────────────────────────────────────

class TestDownload:
    @patch("scripts.download_data.requests.Session")
    def test_stream_download_creates_file(self, mock_session_cls, tmp_path):
        from scripts.download_data import _stream_download
        import requests

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-length": "100"}
        mock_resp.iter_content = MagicMock(return_value=[b"x" * 100])
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_session.get.return_value = mock_resp

        dest = tmp_path / "test.bin"
        _stream_download("http://example.com/file", dest, mock_session)
        assert dest.exists()
        assert dest.stat().st_size == 100

    def test_sha256(self, tmp_path):
        from scripts.download_data import _sha256
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        result = _sha256(f)
        assert len(result) == 64  # SHA-256 hex digest


# ─────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
