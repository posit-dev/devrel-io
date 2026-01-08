#!/usr/bin/env python3

import polars as pl

OUTPUT = "data/output/all.parquet"

dfs = [
    pl.read_ndjson(f"data/output/{x}/*/*.jsonl", include_file_paths="source")
    .with_columns(pl.col("date").str.to_date())
    .unique(["project_id", "metric", "date", "source"])
    for x in ["cran", "plausible", "pypi"]
]

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
