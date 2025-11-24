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
        """Read inputs.csv with datetime column parsed."""
        df = pl.read_csv("data/input/inputs.csv", try_parse_dates=True)
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
        """Filter input data by selected project and add letter labels."""
        df = df_input()
        selected_project = input.project()

        if "project" in df.columns:
            df = df.filter(pl.col("project") == selected_project)

        # Add letter labels (A, B, C, ...)
        if not df.is_empty():
            letters = [chr(65 + i) for i in range(len(df))]  # A=65 in ASCII
            df = df.with_columns(pl.Series("label", letters))

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

        # Sort by datetime (required for group_by_dynamic)
        df = df.sort("dt")

        # Group by ISO week and count
        df = (
            df.group_by_dynamic("dt", every="1w", start_by="monday")
            .agg(pl.len().alias("count"))
            .rename({"dt": "week_start"})
        )

        return df

    @reactive.calc
    def annotations():
        """Create annotations from input data mapped to weeks."""
        df = filtered_input()

        if df.is_empty() or "datetime" not in df.columns:
            return pl.DataFrame()

        # Calculate Monday of the week for each datetime (as Date)
        df = df.with_columns(
            (pl.col("datetime") - pl.duration(days=pl.col("datetime").dt.weekday())).alias("week_start_date")
        )

        # Convert to Datetime to match weekly_counts format
        df = df.with_columns(
            pl.col("week_start_date").cast(pl.Datetime).alias("week_start")
        )

        # Select only label and week_start
        df = df.select(["label", "week_start"])

        return df

    @render.ui
    def events_chart():
        """Render Altair line chart of weekly event counts with annotations."""
        df_counts = weekly_counts()

        if df_counts.is_empty():
            return ui.p("No data available for selected filters.")

        # Base line chart
        line = (
            alt.Chart(df_counts)
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
        )

        # Get annotations
        df_annotations = annotations()

        if not df_annotations.is_empty():
            # Join annotations with counts to get y-position
            df_annotations_with_count = df_annotations.join(
                df_counts, on="week_start", how="left"
            )

            # Create annotation points with text
            points = (
                alt.Chart(df_annotations_with_count)
                .mark_point(size=400, filled=True, opacity=0.7, color="orange")
                .encode(
                    x=alt.X("week_start:T"),
                    y=alt.Y("count:Q"),
                    tooltip=[
                        alt.Tooltip("label:N", title="Label"),
                        alt.Tooltip("week_start:T", title="Week", format="%Y-%m-%d"),
                    ],
                )
            )

            text = (
                alt.Chart(df_annotations_with_count)
                .mark_text(fontSize=12, fontWeight="bold", color="white")
                .encode(
                    x=alt.X("week_start:T"),
                    y=alt.Y("count:Q"),
                    text="label:N",
                )
            )

            chart = (line + points + text).properties(
                width="container", height=400
            ).interactive()
        else:
            chart = line.properties(width="container", height=400).interactive()

        return ui.HTML(chart.to_html())

    @render.data_frame
    def input_table():
        """Render input data table with title case columns and label first."""
        df = filtered_input()

        if df.is_empty():
            return render.DataGrid(pl.DataFrame(), width="100%")

        # Move label column to first position
        if "label" in df.columns:
            other_cols = [col for col in df.columns if col != "label"]
            df = df.select(["label"] + other_cols)

        # Convert column names to title case
        df = df.rename({col: col.replace("_", " ").title() for col in df.columns})

        return render.DataGrid(df, width="100%")


app = App(app_ui, server)
