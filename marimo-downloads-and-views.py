import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    return mo, pl


@app.cell
def _(pl):
    devrel_output = pl.read_parquet("data/output/all.parquet")
    return (devrel_output,)


@app.cell
def _(devrel_output, mo):
    df_downloads = mo.sql(
        f"""
        -- Filter to 2025 download metrics and aggregate to yearly totals
        -- Ordered by download count (highest first)
        SELECT 
            project,
            SUM(value) AS value
        FROM devrel_output
        WHERE YEAR(date) = 2025
          AND metric = 'downloads'
        GROUP BY project, source, metric, date_trunc('year', date)
        ORDER BY value DESC
        """
    )
    return (df_downloads,)


@app.cell
def _(df_downloads):
    df_downloads
    return


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    - [ ] Quarto
    - [x] Shiny
    - [x] ellmer
    - [x] chatlas
    - [x] ggplot2
    - [x] plotnine
    - [x] great-tables
    - [x] pointblank
    - [ ] querychat
    - [ ] tidyverse
    - [ ] orbital
    - [ ] dplyr
    """)
    return


if __name__ == "__main__":
    app.run()
