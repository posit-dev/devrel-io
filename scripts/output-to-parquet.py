#!/usr/bin/env python3

from pathlib import Path

import polars as pl

OUTPUT = "data/output/all.parquet"

# Sources to include (skip if no data files exist)
# Note: buzzsprout handled separately due to per-episode aggregation
SOURCES = ["cran", "openvsx", "plausible", "pypi"]

dfs = []
for source in SOURCES:
    source_path = Path(f"data/output/{source}")
    if not source_path.exists() or not list(source_path.glob("*/*.jsonl")):
        continue
    dfs.append(
        pl.read_ndjson(f"data/output/{source}/*/*.jsonl", include_file_paths="source")
        .with_columns(pl.col("date").str.to_date())
        .unique(["project_id", "metric", "date", "source"])
    )

# Buzzsprout: aggregate per-episode data to total_plays and episode_count
buzzsprout_path = Path("data/output/buzzsprout")
if buzzsprout_path.exists() and list(buzzsprout_path.glob("*/*.jsonl")):
    buzzsprout_raw = pl.read_ndjson(
        "data/output/buzzsprout/*/*.jsonl", include_file_paths="source"
    ).with_columns(pl.col("date").str.to_date())

    # Aggregate: sum plays → total_plays, count episodes → episode_count
    buzzsprout_agg = buzzsprout_raw.group_by("project_id", "date", "source").agg(
        pl.col("value").sum().alias("total_plays"),
        pl.len().alias("episode_count"),
    )

    # Unpivot to standard format (one row per metric)
    dfs.append(
        buzzsprout_agg.unpivot(
            index=["project_id", "date", "source"],
            on=["total_plays", "episode_count"],
            variable_name="metric",
            value_name="value",
        )
    )

dfs.append(
    pl.read_ndjson("data/output/github/*/*.jsonl", include_file_paths="source")
    .group_by(
        pl.col("event_type").alias("metric"),
        pl.col("project_id"),
        pl.col("datetime")
        .str.to_datetime("%Y-%m-%dT%H:%M:%SZ")
        .dt.date()
        .alias("date"),
        pl.col("source"),
    )
    .agg(pl.len().alias("value"))
)

df_all = (
    pl.concat(dfs, how="diagonal_relaxed")
    .with_columns(
        pl.col("project_id").alias("project"),
        pl.col("source").str.split("/").list.get(2),
    )
    .select("project", "source", "metric", "date", "value")
).sort("project", "source", "metric", "date")


print(f"Writing {len(df_all)} rows to {OUTPUT}")

df_all.write_parquet(OUTPUT)
