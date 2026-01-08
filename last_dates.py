#!/usr/bin/env python3

import polars as pl

df = pl.read_parquet("data/output/all.parquet")

df = df.group_by("project", "source").agg(pl.col("date").max())
df = df.sort("date")

print(df)
