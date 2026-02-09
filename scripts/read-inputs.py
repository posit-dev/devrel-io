#!/usr/bin/env python3

import polars as pl

# Configure Polars to show all rows
pl.Config.set_tbl_rows(-1)

# Read the input parquet file
df = pl.read_parquet("data/input.parquet")

print(f"Total entries: {len(df)}")
print(f"\nEntries per project:")
print(
    df.group_by("project")
    .agg(pl.len().alias("count"))
    .sort("count", descending=True)
)

print(f"\nEntries by type:")
print(
    df.group_by("type")
    .agg(pl.len().alias("count"))
    .sort("count", descending=True)
)
