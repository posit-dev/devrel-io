#!/usr/bin/env python3
"""
Shiny app for visualizing DevRel I/O data.
"""

import tomllib
from pathlib import Path

import plotly.graph_objects as go
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
            selected="great-tables",
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
    ui.output_ui("input_table"),
    title="DevRel I/O Dashboard",
)


def server(input: Inputs, output: Outputs, session: Session):
    # Reactive value to track hovered label
    hovered_label = reactive.value(None)

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
            pl.col("datetime").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ")
        )

        # Sort by datetime (required for group_by_dynamic)
        df = df.sort("datetime")

        # Group by ISO week and count
        df = df.group_by_dynamic("datetime", every="1w", start_by="monday").agg(
            pl.len().alias("count")
        )

        return df

    @reactive.calc
    def annotations():
        """Create annotations from input data mapped to weeks."""
        df = filtered_input()

        if df.is_empty() or "datetime" not in df.columns:
            return pl.DataFrame()

        # Calculate Monday of the week for each datetime (as Date)
        # df = df.with_columns(
        #     (pl.col("datetime") - pl.duration(days=pl.col("datetime").dt.weekday())).alias("week_start_date")
        # )
        #
        # # Convert to Datetime to match weekly_counts format
        # df = df.with_columns(
        #     pl.col("week_start_date").cast(pl.Datetime).alias("week_start")
        # )

        # Select only label and week_start
        df = df.select(["label", "datetime"])

        return df

    @render.ui
    def events_chart():
        """Render Plotly line chart of weekly event counts with annotations."""
        df_counts = weekly_counts()

        if df_counts.is_empty():
            return ui.p("No data available for selected filters.")

        # Create Plotly figure
        fig = go.Figure()

        # Add line trace for event counts
        fig.add_trace(
            go.Scatter(
                x=df_counts["datetime"],
                y=df_counts["count"],
                mode="lines+markers",
                name="Events",
                line=dict(color="steelblue"),
                hovertemplate="<b>Week:</b> %{x|%Y-%m-%d}<br><b>Events:</b> %{y}<extra></extra>",
            )
        )

        # Get annotations
        df_annotations = annotations()

        if not df_annotations.is_empty():
            # Get y-axis range to position annotations at bottom
            y_min = 0
            y_range = df_counts["count"].max() - y_min if not df_counts.is_empty() else 100
            annotation_y = y_min + y_range * 0.05  # 5% from bottom

            # Add annotation markers
            fig.add_trace(
                go.Scatter(
                    x=df_annotations["datetime"],
                    y=[annotation_y] * len(df_annotations),
                    mode="markers+text",
                    name="Annotations",
                    text=df_annotations["label"],
                    textposition="middle center",
                    textfont=dict(color="white", size=12),
                    marker=dict(size=20, color="orange", opacity=0.7),
                    hovertemplate="<b>Label:</b> %{text}<br><b>Date:</b> %{x|%Y-%m-%d}<extra></extra>",
                    customdata=df_annotations["label"],
                )
            )

        # Update layout
        fig.update_layout(
            xaxis_title="Week Starting",
            yaxis_title="Event Count",
            height=400,
            hovermode="closest",
            showlegend=False,
            margin=dict(l=50, r=50, t=30, b=50),
        )

        # Add event listener for hover using JavaScript callback
        chart_html = fig.to_html(include_plotlyjs="cdn", div_id="events_chart_div")

        # Add JavaScript to handle hover events
        js_code = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            var chartDiv = document.getElementById('events_chart_div');
            if (chartDiv) {
                chartDiv.on('plotly_hover', function(data) {
                    if (data.points[0].data.name === 'Annotations') {
                        var label = data.points[0].customdata;
                        Shiny.setInputValue('hovered_label', label);
                    }
                });
                chartDiv.on('plotly_unhover', function() {
                    Shiny.setInputValue('hovered_label', null);
                });
            }
        });
        </script>
        """

        return ui.HTML(chart_html + js_code)

    @render.ui
    def input_table():
        """Render input data table with title case columns and highlight hovered row."""
        df = filtered_input()

        if df.is_empty():
            return ui.p("No data available.")

        # Move label column to first position
        if "label" in df.columns:
            other_cols = [col for col in df.columns if col != "label"]
            df = df.select(["label"] + other_cols)

        # Get hovered label from input
        hovered = input.hovered_label()

        # Build HTML table
        html = '<div style="overflow-x: auto;"><table class="table table-striped table-hover">'

        # Header
        html += "<thead><tr>"
        for col in df.columns:
            display_name = col.replace("_", " ").title()
            html += f"<th>{display_name}</th>"
        html += "</tr></thead>"

        # Body
        html += "<tbody>"
        for row in df.iter_rows(named=True):
            # Highlight row if it matches hovered label
            row_class = ' class="table-warning"' if hovered and row.get("label") == hovered else ""
            html += f"<tr{row_class}>"
            for col in df.columns:
                val = row[col]
                if val is None:
                    html += "<td></td>"
                else:
                    html += f"<td>{val}</td>"
            html += "</tr>"
        html += "</tbody></table></div>"

        # Add CSS for highlighting
        css = """
        <style>
        .table-warning {
            background-color: #fff3cd !important;
            font-weight: bold;
        }
        </style>
        """

        return ui.HTML(css + html)


app = App(app_ui, server)
