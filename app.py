#!/usr/bin/env python3
"""
Shiny app for visualizing DevRel I/O data.
"""

import tomllib
from pathlib import Path

import altair as alt
import polars as pl
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

# Load config to get projects
with open("config.toml", "rb") as f:
    config = tomllib.load(f)

projects = list(config["projects"].keys())
project_names = {pid: config["projects"][pid]["name"] for pid in projects}

# Event types for checkboxes
EVENT_TYPES = [
    "star",
    "fork",
    "issue_open",
    "issue_close",
    "pr_open",
    "pr_merge",
    "issue_comment",
    "pr_comment",
]

# Create UI
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select(
            "project",
            "Select Project",
            choices={pid: project_names[pid] for pid in projects},
            selected=projects[0],
        ),
        ui.h4("GitHub Events"),
        ui.input_checkbox_group(
            "event_types",
            None,
            choices={et: et.replace("_", " ").title() for et in EVENT_TYPES},
            selected=EVENT_TYPES,
        ),
    ),
    ui.h2("Event Counts Per Week"),
    ui.output_ui("events_chart"),
    ui.h2("Input Data"),
    ui.output_data_frame("input_table"),
    title="DevRel I/O Dashboard",
)


def server(input: Inputs, output: Outputs, session: Session):
    @reactive.calc
    def df_input():
        """Read inputs.csv."""
        df = pl.read_csv("data/input/inputs.csv")
        return df

    @reactive.calc
    def df_output():
        """Read all GitHub events JSONL files (excluding archive)."""
        # Read all JSONL files except those in archive directories
        jsonl_files = []
        for path in Path("data/output/github").rglob("*.jsonl"):
            if "archive" not in path.parts:
                jsonl_files.append(str(path))

        if not jsonl_files:
            return pl.DataFrame()

        df = pl.read_ndjson(jsonl_files)
        return df

    @reactive.calc
    def filtered_input():
        """Filter input data by selected project."""
        df = df_input()
        selected_project = input.project()

        if "project" in df.columns:
            df = df.filter(pl.col("project") == selected_project)

        return df

    @reactive.calc
    def filtered_output():
        """Filter output data by selected project and event types."""
        df = df_output()

        if df.is_empty():
            return df

        selected_project = input.project()
        selected_events = list(input.event_types())

        # Filter by project
        if "project_id" in df.columns:
            df = df.filter(pl.col("project_id") == selected_project)

        # Filter by event types
        if selected_events and "event_type" in df.columns:
            df = df.filter(pl.col("event_type").is_in(selected_events))

        return df

    @reactive.calc
    def weekly_counts():
        """Aggregate events by ISO week."""
        df = filtered_output()

        if df.is_empty():
            return pl.DataFrame()

        # Convert datetime string to datetime and extract week
        df = df.with_columns(
            pl.col("datetime")
            .str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ")
            .alias("dt")
        )

        # Group by ISO week and count
        df = (
            df.group_by_dynamic("dt", every="1w", start_by="monday")
            .agg(pl.len().alias("count"))
            .rename({"dt": "week_start"})
        )

        return df

    @render.ui
    def events_chart():
        """Render Altair line chart of weekly event counts."""
        df = weekly_counts()

        if df.is_empty():
            return ui.p("No data available for selected filters.")

        chart = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "week_start:T",
                    title="Week Starting",
                    axis=alt.Axis(format="%Y-%m-%d"),
                ),
                y=alt.Y("count:Q", title="Event Count"),
                tooltip=[
                    alt.Tooltip("week_start:T", title="Week", format="%Y-%m-%d"),
                    alt.Tooltip("count:Q", title="Events"),
                ],
            )
            .properties(width="container", height=400)
            .interactive()
        )

        return ui.HTML(chart.to_html())

    @render.data_frame
    def input_table():
        """Render input data table with title case columns."""
        df = filtered_input()

        # Convert column names to title case
        df = df.rename({col: col.replace("_", " ").title() for col in df.columns})

        return render.DataGrid(df, width="100%")


app = App(app_ui, server)
