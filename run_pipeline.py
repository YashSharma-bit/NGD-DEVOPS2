#!/usr/bin/env python3
"""
run_pipeline.py
---------------
Master orchestrator for the full ETL pipeline.
Runs all stages in sequence with error handling and timing.

Usage
-----
    python run_pipeline.py [--stages STAGES] [--skip STAGES] [--force-download]

    --stages  Comma-separated list: download,clean,geo,postgres,analytics,neo4j,viz
    --skip    Skip specific stages
    --force-download  Re-download even if files exist
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config.config_loader import get_logger

logger = get_logger("pipeline")
console = Console()

STAGES = [
    ("download",   "scripts/download_data.py",              "Download raw datasets"),
    ("clean",      "scripts/clean_transform.py",            "Clean & transform data"),
    ("geo",        "scripts/geospatial_join.py",            "Geospatial join"),
    ("postgres",   "scripts/load_postgres.py",              "Load PostgreSQL + PostGIS"),
    ("analytics",  "analytics/development_index.py",        "Compute development index"),
    ("neo4j",      "scripts/load_neo4j.py",                 "Load Neo4j graph"),
    ("viz",        "analytics/visualisation.py",            "Generate visualisations"),
]


def run_stage(name: str, script: str, extra_args: list[str] = []) -> tuple[bool, float]:
    project_root = Path(__file__).parent
    cmd = [sys.executable, str(project_root / script)] + extra_args
    console.print(f"\n[bold cyan]▶ Stage: {name.upper()}[/bold cyan]  ({script})")

    start = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(project_root))
    elapsed = time.perf_counter() - start

    if result.returncode == 0:
        console.print(f"[green]✓ {name} completed in {elapsed:.1f}s[/green]")
        return True, elapsed
    else:
        console.print(f"[red]✗ {name} FAILED (exit {result.returncode}) after {elapsed:.1f}s[/red]")
        return False, elapsed


@click.command()
@click.option("--stages", default="all", help="Comma-separated stages or 'all'")
@click.option("--skip", default="", help="Comma-separated stages to skip")
@click.option("--force-download", is_flag=True, default=False)
@click.option("--push-db", is_flag=True, default=True, help="Push analytics results to PostgreSQL")
@click.option("--fail-fast", is_flag=True, default=True, help="Stop on first failure")
def main(stages: str, skip: str, force_download: bool, push_db: bool, fail_fast: bool):
    """Run the complete India Regional Development Analytics ETL pipeline."""
    console.print(
        "\n[bold white on blue]  India Regional Development Analytics — ETL Pipeline  [/bold white on blue]\n"
    )

    skip_set = set(s.strip() for s in skip.split(",") if s.strip())
    if stages.strip().lower() == "all":
        stage_list = [(n, s, d) for n, s, d in STAGES if n not in skip_set]
    else:
        requested = set(s.strip() for s in stages.split(","))
        stage_list = [(n, s, d) for n, s, d in STAGES if n in requested and n not in skip_set]

    if not stage_list:
        console.print("[yellow]No stages to run.[/yellow]")
        return

    results: list[dict] = []

    for name, script, description in stage_list:
        extra: list[str] = []
        if name == "download" and force_download:
            extra.append("--force")
        if name == "analytics" and push_db:
            extra.append("--push-db")

        ok, elapsed = run_stage(name, script, extra)
        results.append({"stage": name, "description": description,
                        "status": "✓ OK" if ok else "✗ FAIL",
                        "time": f"{elapsed:.1f}s"})

        if not ok and fail_fast:
            console.print("[red bold]Pipeline aborted due to failure.[/red bold]")
            break

    # Summary table
    table = Table(title="\nPipeline Summary", box=box.ROUNDED)
    table.add_column("Stage", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Status", justify="center")
    table.add_column("Time", justify="right")

    for r in results:
        style = "green" if "OK" in r["status"] else "red"
        table.add_row(r["stage"], r["description"],
                      f"[{style}]{r['status']}[/{style}]", r["time"])

    console.print(table)

    failed = sum(1 for r in results if "FAIL" in r["status"])
    if failed == 0:
        console.print("\n[bold green]All pipeline stages completed successfully! 🎉[/bold green]")
        console.print("  API:         http://localhost:8000/docs")
        console.print("  Neo4j:       http://localhost:7474")
        console.print("  PostgreSQL:  localhost:5432/india_dev_analytics")
    else:
        console.print(f"\n[bold red]{failed} stage(s) failed. Check logs/pipeline.log[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
