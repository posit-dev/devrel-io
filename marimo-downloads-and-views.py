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
        """,
        output=False
    )
    return (df_downloads,)


@app.cell
def _(df_downloads):
    df_downloads
    return


@app.cell
def _():
    return


@app.cell
def _(devrel_output, mo):
    df_monthly = mo.sql(
        f"""
        SELECT 
            project,
            source,
            metric,
            DATE_TRUNC('month', date) AS month,
            SUM(value) AS value
        FROM devrel_output
        GROUP BY project, source, metric, DATE_TRUNC('month', date)
        ORDER BY month DESC, project, metric
        """
    )
    return (df_monthly,)


@app.cell
def _(df_monthly, mo):
    df_stars = mo.sql(
        f"""
        SELECT 
            project,
            month,
            value
        FROM df_monthly
        WHERE metric = 'star'
        ORDER BY month
        """
    )
    return (df_stars,)


@app.cell(hide_code=True)
def _(df_stars, mo):
    project_dropdown = mo.ui.dropdown(
        options=df_stars['project'].unique().sort().to_list(),
        value=df_stars['project'].unique().sort().to_list()[0],
        label="Select Project"
    )

    project_dropdown
    return (project_dropdown,)


@app.cell
def _(df_stars, pl, project_dropdown):
    import altair as alt

    df_stars_filtered = df_stars.filter(pl.col('project') == project_dropdown.value)

    chart_stars_filtered = alt.Chart(df_stars_filtered).mark_line(point=True).encode(
        x=alt.X('month:T', title='Month'),
        y=alt.Y('value:Q', title='Stars'),
        tooltip=['project:N', 'month:T', alt.Tooltip('value:Q', format=',')]
    ).properties(
        title=f'GitHub Stars Over Time - {project_dropdown.value}',
        width=800,
        height=400
    ).interactive()

    chart_stars_filtered
    return (alt,)


@app.cell
def _(df_stars, pl):
    df_stars_cumulative = df_stars.sort('month').sort("project", "month").with_columns(
        pl.col('value').cum_sum().over('project').alias('cumulative_stars')
    )

    df_stars_cumulative
    return (df_stars_cumulative,)


@app.cell
def _(alt, df_stars_cumulative):
    df_stars_filtered_cumulative = df_stars_cumulative #.filter(pl.col('project') == project_dropdown.value)

    chart_stars_cumulative = alt.Chart(df_stars_filtered_cumulative).mark_line(point=True).encode(
        x=alt.X('month:T', title='Month'),
        y=alt.Y('cumulative_stars:Q', title='Cumulative Stars'),
        color='project:N',
        tooltip=['project:N', 'month:T', alt.Tooltip('cumulative_stars:Q', format=',')]
    ).properties(
        title=f'Cumulative GitHub Stars Over Time',
        width=800,
        height=400
    ).interactive()

    chart_stars_cumulative
    return


@app.cell
def _():
    return


@app.cell
def _(alt, df_stars_cumulative, pl, project_dropdown):
    df_stars_filtered_cumulative_sorted = df_stars_cumulative

    # Get the order of projects by their maximum cumulative stars
    project_order = (
        df_stars_cumulative
        .group_by('project')
        .agg(pl.col('cumulative_stars').max().alias('max_stars'))
        .sort('max_stars', descending=True)
        ['project']
        .to_list()
    )

    chart_stars_cumulative_sorted = alt.Chart(df_stars_filtered_cumulative_sorted).mark_line(point=True).encode(
        x=alt.X('month:T', title='Month'),
        y=alt.Y('cumulative_stars:Q', title='Cumulative Stars'),
        color=alt.Color('project:N', sort=project_order, title='Project'),
        tooltip=['project:N', 'month:T', alt.Tooltip('cumulative_stars:Q', format=',')]
    ).properties(
        title=f'Cumulative GitHub Stars Over Time - {project_dropdown.value}',
        width=800,
        height=400
    ).interactive()

    chart_stars_cumulative_sorted
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
