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
        ui.input_selectize(
            "project",
            "Select Project(s)",
            choices={pid: project_names[pid] for pid in projects},
            selected=["great-tables"],
            multiple=True,
        ),
        ui.h4("GitHub Events"),
        ui.input_checkbox_group(
            "event_types",
            None,
            choices={et: et.replace("_", " ").title() for et in EVENT_TYPES},
            selected=EVENT_TYPES,
        ),
        ui.input_switch("cumulative", "Cumulative Counts", value=False),
    ),
    ui.h2("Output"),
    ui.output_ui("events_chart"),
    ui.h2("Input"),
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
        """Filter input data by selected projects, sort by datetime, and add letter labels."""
        df = df_input()
        selected_projects = list(input.project())

        if "project" in df.columns and selected_projects:
            df = df.filter(pl.col("project").is_in(selected_projects))

        # Sort by datetime before assigning labels
        if not df.is_empty() and "datetime" in df.columns:
            df = df.sort("datetime")

        # Add letter labels (A, B, C, ...)
        if not df.is_empty():
            letters = [chr(65 + i) for i in range(len(df))]  # A=65 in ASCII
            df = df.with_columns(pl.Series("label", letters))

        return df

    @reactive.calc
    def filtered_output():
        """Filter output data by selected projects and event types."""
        df = df_output()

        if df.is_empty():
            return df

        selected_projects = list(input.project())
        selected_events = list(input.event_types())

        # Filter by projects
        if "project_id" in df.columns and selected_projects:
            df = df.filter(pl.col("project_id").is_in(selected_projects))

        # Filter by event types
        if selected_events and "event_type" in df.columns:
            df = df.filter(pl.col("event_type").is_in(selected_events))

        return df

    @reactive.calc
    def weekly_counts():
        """Aggregate events by ISO week and project, optionally cumulative."""
        df = filtered_output()

        if df.is_empty():
            return pl.DataFrame()

        # Convert datetime string to datetime
        df = df.with_columns(
            pl.col("datetime").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ")
        )

        # Sort by project and datetime (required for group_by_dynamic)
        df = df.sort(["project_id", "datetime"])

        # Group by project and ISO week, count events
        df = df.group_by_dynamic(
            "datetime",
            every="1w",
            start_by="monday",
            group_by="project_id",
            label="right",
        ).agg(pl.len().alias("count"))

        # Apply cumulative sum if enabled
        if input.cumulative():
            df = df.with_columns(
                pl.col("count").cum_sum().over("project_id").alias("count")
            )

        return df

    @reactive.calc
    def annotations():
        """Create annotations from input data with project information."""
        df = filtered_input()

        if df.is_empty() or "datetime" not in df.columns:
            return pl.DataFrame()

        # Select label, datetime, and project
        df = df.select(["label", "datetime", "project"])

        return df

    @render.ui
    def events_chart():
        """Render Altair line chart of weekly event counts with colored annotations."""
        df_counts = weekly_counts()

        if df_counts.is_empty():
            return ui.p("No data available for selected filters.")

        # Base line chart with color by project
        line = (
            alt.Chart(df_counts)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "datetime:T",
                    title="Week Starting",
                    axis=alt.Axis(format="%Y-%m-%d"),
                ),
                y=alt.Y("count:Q", title="Event Count"),
                color=alt.Color(
                    "project_id:N", title="Project", legend=alt.Legend(orient="right")
                ),
                tooltip=[
                    alt.Tooltip("project_id:N", title="Project"),
                    alt.Tooltip("datetime:T", title="Week", format="%Y-%m-%d"),
                    alt.Tooltip("count:Q", title="Events"),
                ],
            )
        )

        # Get annotations
        df_annotations = annotations()

        if not df_annotations.is_empty():
            # Create annotation points with text, colored by project
            points = (
                alt.Chart(df_annotations)
                .mark_point(size=400, filled=True, opacity=0.7)
                .encode(
                    x=alt.X("datetime:T"),
                    y=alt.value(50),
                    color=alt.Color("project:N", title="Project", legend=None),
                    tooltip=[
                        alt.Tooltip("label:N", title="Label"),
                        alt.Tooltip("project:N", title="Project"),
                        alt.Tooltip("datetime:T", title="Date", format="%Y-%m-%d"),
                    ],
                )
            )

            text = (
                alt.Chart(df_annotations)
                .mark_text(fontSize=12, fontWeight="bold", color="white")
                .encode(
                    x=alt.X("datetime:T"),
                    y=alt.value(50),
                    text="label:N",
                )
            )

            chart = (
                (line + points + text)
                .properties(width="container", height=400)
                .interactive()
            )
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
