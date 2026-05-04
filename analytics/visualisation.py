"""
analytics/visualisation.py
--------------------------
Generates:
1. Choropleth map — district-level development index
2. State-level heatmap — inequality
3. Cluster map — district clusters
4. Interactive Plotly maps (HTML output)

Usage
-----
    python analytics/visualisation.py [--output-dir PATH] [--format FORMAT]

    --format  html | png | both (default: html)
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # non-interactive backend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
import logging

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(h)
    return logger


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"

CLUSTER_COLOR_MAP = {
    "Aspirational": "#d73027",
    "Developing": "#fc8d59",
    "Transitioning": "#fee090",
    "Growing": "#e0f3f8",
    "Advanced": "#91bfdb",
    "Metro / High-Performance": "#4575b4",
}


# ─────────────────────────────────────────────────────────────
# Data loader
# ─────────────────────────────────────────────────────────────

def load_geo_with_index() -> gpd.GeoDataFrame:
    geo_path = PROCESSED / "districts_geo.parquet"
    idx_path = PROCESSED / "development_index.parquet"

    if not geo_path.exists():
        raise FileNotFoundError("districts_geo.parquet not found")

    gdf = gpd.read_parquet(geo_path)

    if idx_path.exists():
        idx = pd.read_parquet(idx_path)
        gdf = gdf.merge(
            idx[["lgd_district_code", "composite_score", "composite_rank",
                  "cluster_id", "cluster_label", "composite_percentile"]],
            on="lgd_district_code",
            how="left",
        )

    return gdf


# ─────────────────────────────────────────────────────────────
# 1. Choropleth — Development Index
# ─────────────────────────────────────────────────────────────

def plot_choropleth_static(gdf: gpd.GeoDataFrame, output_dir: Path) -> None:
    """Static matplotlib choropleth of composite development index."""
    import mapclassify

    if "composite_score" not in gdf.columns or gdf["composite_score"].isna().all():
        logger.warning("No composite_score — skipping static choropleth")
        return

    fig, ax = plt.subplots(1, 1, figsize=(18, 20))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#0f3460")

    # Classification — Quantiles
    gdf_plot = gdf.dropna(subset=["composite_score"]).copy()
    scheme = mapclassify.Quantiles(gdf_plot["composite_score"], k=7)

    gdf_plot.plot(
        column="composite_score",
        ax=ax,
        legend=True,
        scheme="Quantiles",
        k=7,
        cmap="RdYlGn",
        missing_kwds={"color": "lightgrey", "label": "No data"},
        legend_kwds={
            "title": "Development Index",
            "title_fontsize": 11,
            "fontsize": 9,
            "loc": "lower left",
            "framealpha": 0.85,
        },
        linewidth=0.2,
        edgecolor="white",
    )

    ax.set_title(
        " Regional Development Index — District Level (Census 2011)",
        fontsize=16,
        fontweight="bold",
        color="white",
        pad=20,
    )
    ax.set_xlabel("Longitude", color="white")
    ax.set_ylabel("Latitude", color="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("white")

    ax.annotate(
        "Source: Census of India 2011 | LGD | Datameet Shapefiles\n"
        "Development index = weighted composite of literacy, electrification,\n"
        "water access, sanitation, banking, internet, worker participation",
        xy=(0.01, 0.01),
        xycoords="axes fraction",
        fontsize=7,
        color="lightgrey",
        va="bottom",
    )

    out = output_dir / "choropleth_development_index.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    logger.info(f"Static choropleth saved: {out}")


def plot_choropleth_interactive(gdf: gpd.GeoDataFrame, output_dir: Path) -> None:
    """Plotly interactive choropleth."""
    import plotly.express as px
    import json

    if "composite_score" not in gdf.columns:
        logger.warning("No composite_score — skipping interactive choropleth")
        return

    gdf_plot = gdf.dropna(subset=["composite_score"]).copy()
    gdf_plot["district_label"] = (
        gdf_plot["district_name"].fillna("Unknown")
        + ", "
        + gdf_plot.get("state_name", pd.Series("")).fillna("")
    )

    geojson = json.loads(gdf_plot.to_json())

    fig = px.choropleth_mapbox(
        gdf_plot,
        geojson=geojson,
        locations=gdf_plot.index,
        color="composite_score",
        color_continuous_scale="RdYlGn",
        mapbox_style="carto-positron",
        zoom=4,
        center={"lat": 22.5, "lon": 82.0},
        opacity=0.75,
        labels={"composite_score": "Dev Index"},
        hover_data={
            "district_label": True,
            "composite_score": ":.2f",
            "composite_rank": True,
            "cluster_label": True,
        },
        title="India District Development Index — Interactive Map",
    )
    fig.update_layout(
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title="Dev Index",
            tickfont=dict(size=10),
        ),
    )

    out = output_dir / "choropleth_interactive.html"
    fig.write_html(str(out))
    logger.info(f"Interactive choropleth saved: {out}")


# ─────────────────────────────────────────────────────────────
# 2. Cluster map
# ─────────────────────────────────────────────────────────────

def plot_cluster_map(gdf: gpd.GeoDataFrame, output_dir: Path) -> None:
    """Colour districts by development cluster."""
    if "cluster_label" not in gdf.columns:
        logger.warning("No cluster_label — skipping cluster map")
        return

    fig, ax = plt.subplots(figsize=(18, 20))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#0f3460")

    for cluster, color in CLUSTER_COLOR_MAP.items():
        subset = gdf[gdf["cluster_label"] == cluster]
        if subset.empty:
            continue
        subset.plot(ax=ax, color=color, linewidth=0.2, edgecolor="white", label=cluster)

    # No-data
    gdf[gdf["cluster_label"].isna()].plot(
        ax=ax, color="lightgrey", linewidth=0.2, edgecolor="white", label="No data"
    )

    ax.set_title(
        "India District Development Clusters",
        fontsize=16, fontweight="bold", color="white", pad=20
    )
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("white")

    legend = ax.legend(
        title="Cluster",
        loc="lower left",
        framealpha=0.85,
        fontsize=9,
        title_fontsize=10,
    )
    legend.get_title().set_color("black")

    out = output_dir / "cluster_map.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    logger.info(f"Cluster map saved: {out}")


# ─────────────────────────────────────────────────────────────
# 3. State heatmap — inequality
# ─────────────────────────────────────────────────────────────

def plot_inequality_heatmap(output_dir: Path) -> None:
    """Heatmap of within-state inequality metrics."""
    path = PROCESSED / "state_inequality.parquet"
    if not path.exists():
        logger.warning("state_inequality.parquet not found — skipping heatmap")
        return

    df = pd.read_parquet(path).sort_values("gini", ascending=False)

    metrics = [c for c in ["gini", "theil", "cv", "palma"] if c in df.columns]
    if not metrics:
        return

    data = df.set_index("state_name")[metrics]

    fig, ax = plt.subplots(figsize=(10, max(12, len(df) * 0.4)))
    import matplotlib.colors as mcolors

    im = ax.imshow(data.values, aspect="auto", cmap="RdYlGn_r", interpolation="nearest")
    plt.colorbar(im, ax=ax, shrink=0.6, label="Metric value (higher = more unequal)")

    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([m.upper() for m in metrics], fontsize=11)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["state_name"].tolist(), fontsize=9)

    # Annotate cells
    for i in range(len(df)):
        for j, m in enumerate(metrics):
            val = data.iloc[i, j]
            ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                    fontsize=7, color="black" if 0.3 < (val if not np.isnan(val) else 0) < 0.7 else "white")

    ax.set_title("Regional Inequality within States — India Districts", fontsize=14, pad=15)
    ax.set_xlabel("Inequality Metric")

    out = output_dir / "state_inequality_heatmap.png"
    plt.tight_layout()
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Inequality heatmap saved: {out}")


# ─────────────────────────────────────────────────────────────
# 4. Scatter: development score vs population
# ─────────────────────────────────────────────────────────────

def plot_scatter_dev_population(gdf: gpd.GeoDataFrame, output_dir: Path) -> None:
    import plotly.graph_objects as go

    if "composite_score" not in gdf.columns or "population_total" not in gdf.columns:
        logger.warning("Skipping scatter plot — missing columns")
        return

    df = pd.DataFrame(gdf[[
        "district_name", "state_name", "composite_score",
        "population_total", "cluster_label", "literacy_rate",
    ]]).dropna(subset=["composite_score", "population_total"])

    fig = go.Figure()
    for cluster, color in CLUSTER_COLOR_MAP.items():
        sub = df[df["cluster_label"] == cluster]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["population_total"] / 1e6,
            y=sub["composite_score"],
            mode="markers",
            name=cluster,
            marker=dict(color=color, size=6, opacity=0.7),
            text=sub["district_name"] + ", " + sub.get("state_name", ""),
            hovertemplate="<b>%{text}</b><br>Pop: %{x:.2f}M<br>Dev: %{y:.1f}<extra></extra>",
        ))

    fig.update_layout(
        title="Development Score vs Population by Cluster",
        xaxis_title="Population (millions)",
        yaxis_title="Development Index",
        legend_title="Cluster",
        hovermode="closest",
    )

    out = output_dir / "scatter_dev_vs_population.html"
    fig.write_html(str(out))
    logger.info(f"Scatter plot saved: {out}")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

@click.command()
@click.option("--output-dir", default="data/processed/viz", help="Output directory for visualisations")
@click.option(
    "--format",
    "fmt",
    default="both",
    type=click.Choice(["html", "png", "both"]),
)
def main(output_dir: str, fmt: str):
    """Generate all visualisations."""
    out = PROJECT_ROOT / output_dir
    out.mkdir(parents=True, exist_ok=True)

    gdf = load_geo_with_index()
    logger.info(f"Loaded {len(gdf)} districts for visualisation")

    if fmt in ("png", "both"):
        plot_choropleth_static(gdf, out)
        plot_cluster_map(gdf, out)
        plot_inequality_heatmap(out)

    if fmt in ("html", "both"):
        plot_choropleth_interactive(gdf, out)
        plot_scatter_dev_population(gdf, out)

    logger.info(f"All visualisations written to {out}")


if __name__ == "__main__":
    main()
