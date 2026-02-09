#!/usr/bin/env python3

import polars as pl

OUTPUT = "data/input.parquet"

# Read both CSV files
df_inputs = pl.read_csv("data/input/inputs.csv")
df_blogs = pl.read_csv("data/input/blogs.csv")

# Verify schemas match
print("inputs.csv schema:", df_inputs.schema)
print("blogs.csv schema:", df_blogs.schema)

if df_inputs.schema != df_blogs.schema:
    raise ValueError("Schemas do not match between inputs.csv and blogs.csv")

# Concatenate the dataframes
df_all = pl.concat([df_inputs, df_blogs], how="vertical")

# Convert datetime column to date
df_all = df_all.with_columns(
    pl.col("datetime").str.to_datetime().dt.date().alias("date")
).select(
    "date",
    "project",
    "type",
    "title",
    "author",
    "url",
    "notes"
)

print(f"\nCombined dataframe:")
print(f"  Rows: {len(df_all)}")
print(f"  Schema: {df_all.schema}")
print(f"\nWriting to {OUTPUT}")

# Write to parquet
df_all.write_parquet(OUTPUT)

print("Done!")
