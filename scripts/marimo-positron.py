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
    df = pl.read_parquet("data/output/all.parquet")
    df
    return (df,)


@app.cell
def _(df, mo):
    _df = mo.sql(
        f"""
        SELECT project, date, SUM(value) OVER (PARTITION BY project ORDER BY date) AS 'stars' FROM df
        WHERE source = 'github' AND metric = 'star'
        """
    )
    return


@app.cell
def _(df):
    df
    return


@app.cell
def _(df, mo):
    _df = mo.sql(
        f"""
        SELECT * FROM df
        WHERE project = 'positron'
        AND source = 'dwh'
        """
    )
    return


@app.cell
def _():
    return


@app.cell
def _(df, mo):
    _df = mo.sql(
        f"""
        SELECT project, sum(value) AS stars FROM df
        WHERE source = 'github' AND metric = 'star'
        GROUP BY project
        ORDER BY stars DESC
        """
    )
    return


@app.cell
def _(df, mo):
    _df = mo.sql(
        f"""
        SELECT project, max(value) AS downloads FROM df
        WHERE source = 'openvsx' AND metric = 'total_downloads'
        GROUP BY project
        ORDER BY downloads DESC
        """
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
