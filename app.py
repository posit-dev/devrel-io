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
project_colors = {pid: config["projects"][pid].get("hex_color", "#808080") for pid in projects}

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

# Plausible metrics
PLAUSIBLE_METRICS = ["pageviews", "visitors", "visits"]

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
            selected=["star"],
        ),
        ui.h4("Plausible"),
        ui.input_checkbox_group(
            "plausible_metrics",
            None,
            choices={m: m.title() for m in PLAUSIBLE_METRICS},
            selected=[],
        ),
        ui.h4("Period"),
        ui.input_select(
            "period",
            None,
            choices={
                "all": "All",
                "last_7_days": "Last 7 days",
                "last_month": "Last month",
                "custom": "Custom"
            },
            selected="all",
        ),
        ui.output_ui("date_pickers"),
        ui.h4("Settings"),
        ui.input_select(
            "aggregation",
            "Aggregation",
            choices={"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"},
            selected="weekly",
        ),
        ui.input_switch("cumulative", "Cumulative Counts", value=False),
        ui.input_switch("stack_metrics", "Stack Metrics", value=False),
    ),
    ui.h2("Input"),
    ui.output_data_frame("input_table"),
    ui.h2("Output"),
    ui.output_ui("events_chart"),
    title="DevRel I/O Dashboard",
)


def server(input: Inputs, output: Outputs, session: Session):
    @render.ui
    def date_pickers():
        """Show date pickers only when Custom period is selected."""
        if input.period() == "custom":
            from datetime import date, timedelta
            today = date.today()
            month_ago = today - timedelta(days=30)
            return ui.TagList(
                ui.input_date("start_date", "Start Date", value=month_ago),
                ui.input_date("end_date", "End Date", value=today),
            )
        return ui.TagList()

    @reactive.calc
    def date_range():
        """Calculate the date range based on period selection."""
        from datetime import datetime, timedelta, timezone

        period = input.period()

        if period == "all":
            return None, None  # No filtering
        elif period == "last_7_days":
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)
            return start_date, end_date
        elif period == "last_month":
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30)
            return start_date, end_date
        elif period == "custom":
            # Convert date inputs to datetime
            start = input.start_date()
            end = input.end_date()
            if start and end:
                start_date = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
                end_date = datetime.combine(end, datetime.max.time()).replace(tzinfo=timezone.utc)
                return start_date, end_date

        return None, None

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
    def df_plausible():
        """Read all Plausible JSONL files (excluding archive)."""
        jsonl_files = []
        for path in Path("data/output/plausible").rglob("*.jsonl"):
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
        """Filter output data by selected projects, event types, and date range."""
        df = df_output()

        if df.is_empty():
            return df

        selected_projects = list(input.project())
        selected_events = list(input.event_types())

        # If no projects selected, return empty DataFrame
        if not selected_projects:
            return pl.DataFrame()

        # If no events selected, return empty DataFrame
        if not selected_events:
            return pl.DataFrame()

        # Filter by projects
        if "project_id" in df.columns:
            df = df.filter(pl.col("project_id").is_in(selected_projects))

        # Filter by event types
        if "event_type" in df.columns:
            df = df.filter(pl.col("event_type").is_in(selected_events))

        # Filter by date range
        start_date, end_date = date_range()
        if start_date and end_date and "datetime" in df.columns:
            df = df.with_columns(
                pl.col("datetime").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ").dt.replace_time_zone("UTC")
            )
            df = df.filter(
                (pl.col("datetime") >= start_date) & (pl.col("datetime") <= end_date)
            )
            # Convert back to string for consistency
            df = df.with_columns(
                pl.col("datetime").dt.convert_time_zone("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            )

        return df

    @reactive.calc
    def filtered_plausible():
        """Filter Plausible data by selected projects, metrics, and date range."""
        df = df_plausible()

        if df.is_empty():
            return df

        selected_projects = list(input.project())
        selected_metrics = list(input.plausible_metrics())

        # If no projects selected, return empty DataFrame
        if not selected_projects:
            return pl.DataFrame()

        # If no metrics selected, return empty DataFrame
        if not selected_metrics:
            return pl.DataFrame()

        # Filter by projects
        if "project_id" in df.columns:
            df = df.filter(pl.col("project_id").is_in(selected_projects))

        # Filter by selected metrics
        if "metric" in df.columns:
            df = df.filter(pl.col("metric").is_in(selected_metrics))

        # Filter by date range
        start_date, end_date = date_range()
        if start_date and end_date and "date" in df.columns:
            df = df.with_columns(
                pl.col("date").str.strptime(pl.Datetime, "%Y-%m-%d").dt.replace_time_zone("UTC")
            )
            df = df.filter(
                (pl.col("date") >= start_date) & (pl.col("date") <= end_date)
            )
            # Convert back to string for consistency
            df = df.with_columns(
                pl.col("date").dt.convert_time_zone("UTC").dt.strftime("%Y-%m-%d")
            )

        return df

    @reactive.calc
    def aggregated_counts():
        """Aggregate events and metrics by time period, with optional stacking and cumulative sum."""
        # Process GitHub events
        df_github = filtered_output()
        df_github_agg = pl.DataFrame()

        if not df_github.is_empty():
            # Convert datetime string to datetime
            df_github = df_github.with_columns(
                pl.col("datetime").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ")
            )

            # Sort by project and datetime
            df_github = df_github.sort(["project_id", "datetime"])

            # Determine aggregation interval
            aggregation_map = {
                "daily": "1d",
                "weekly": "1w",
                "monthly": "1mo",
            }
            interval = aggregation_map[input.aggregation()]

            # Group by project and time period (sum all GitHub events together)
            group_by_kwargs = {
                "every": interval,
                "group_by": "project_id",
                "label": "right",
            }

            if input.aggregation() == "weekly":
                group_by_kwargs["start_by"] = "monday"

            df_github_agg = df_github.group_by_dynamic("datetime", **group_by_kwargs).agg(
                pl.len().alias("count")
            )

            # Add metric_type column labeled as "GitHub" and cast count to Int64
            df_github_agg = df_github_agg.with_columns([
                pl.lit("GitHub").alias("metric_type"),
                pl.col("count").cast(pl.Int64)
            ])

        # Process Plausible data
        df_plaus = filtered_plausible()
        df_plaus_agg = pl.DataFrame()

        if not df_plaus.is_empty():
            # Convert date string to datetime
            df_plaus = df_plaus.with_columns(
                pl.col("date").str.strptime(pl.Datetime, "%Y-%m-%d")
            ).rename({"date": "datetime"})

            # Rename value to count for consistency
            df_plaus = df_plaus.rename({"value": "count"})

            # Sort by project and datetime
            df_plaus = df_plaus.sort(["project_id", "datetime"])

            # Determine aggregation interval
            aggregation_map = {
                "daily": "1d",
                "weekly": "1w",
                "monthly": "1mo",
            }
            interval = aggregation_map[input.aggregation()]

            # Group by project and time period (sum all Plausible metrics together)
            group_by_kwargs = {
                "every": interval,
                "group_by": "project_id",
                "label": "right",
            }

            if input.aggregation() == "weekly":
                group_by_kwargs["start_by"] = "monday"

            df_plaus_agg = df_plaus.group_by_dynamic("datetime", **group_by_kwargs).agg(
                pl.sum("count").cast(pl.Int64).alias("count")
            )

            # Add metric_type column labeled as "Plausible"
            df_plaus_agg = df_plaus_agg.with_columns(
                pl.lit("Plausible").alias("metric_type")
            )

        # Combine GitHub and Plausible data
        if not df_github_agg.is_empty() and not df_plaus_agg.is_empty():
            # Ensure both dataframes have the same column order
            df_github_agg = df_github_agg.select(["project_id", "datetime", "metric_type", "count"])
            df_plaus_agg = df_plaus_agg.select(["project_id", "datetime", "metric_type", "count"])
            df_combined = pl.concat([df_github_agg, df_plaus_agg])
        elif not df_github_agg.is_empty():
            df_combined = df_github_agg.select(["project_id", "datetime", "metric_type", "count"])
        elif not df_plaus_agg.is_empty():
            df_combined = df_plaus_agg.select(["project_id", "datetime", "metric_type", "count"])
        else:
            return pl.DataFrame()

        # Apply stacking if enabled
        if input.stack_metrics():
            # Sum all metrics per project and time period
            df_combined = df_combined.group_by(["project_id", "datetime"]).agg(
                pl.sum("count").alias("count")
            ).sort(["project_id", "datetime"])
        else:
            # Keep metrics separate, sort for display
            df_combined = df_combined.sort(["project_id", "metric_type", "datetime"])

        # Apply cumulative sum if enabled
        if input.cumulative():
            if input.stack_metrics():
                # Cumulative sum per project
                df_combined = df_combined.with_columns(
                    pl.col("count").cum_sum().over("project_id").alias("count")
                )
            else:
                # Cumulative sum per project and metric type
                df_combined = df_combined.with_columns(
                    pl.col("count").cum_sum().over(["project_id", "metric_type"]).alias("count")
                )

        # Add hex_color column based on project_id
        if not df_combined.is_empty():
            df_combined = df_combined.with_columns(
                pl.col("project_id").map_elements(
                    lambda pid: project_colors.get(pid, "#808080"),
                    return_dtype=pl.Utf8
                ).alias("hex_color")
            )

        return df_combined

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
        """Render Altair line chart of aggregated event counts with colored annotations."""
        df_counts = aggregated_counts()

        if df_counts.is_empty():
            return ui.p("No data available for selected filters.")

        # Determine axis title and tooltip based on aggregation level
        aggregation = input.aggregation()
        period_labels = {
            "daily": "Day",
            "weekly": "Week",
            "monthly": "Month",
        }
        period_label = period_labels[aggregation]

        # Create zoom selection for x-axis (time) only
        zoom = alt.selection_interval(bind="scales", encodings=["x"])

        # Create color scale using hex colors from config, only for selected projects
        selected_project_ids = df_counts["project_id"].unique().to_list()
        color_domain = [pid for pid in selected_project_ids]
        color_range = [project_colors.get(pid, "#808080") for pid in color_domain]

        # Build line chart based on stacking mode
        if input.stack_metrics():
            # Stacked: color by project, solid lines
            line = (
                alt.Chart(df_counts)
                .mark_line(point=True)
                .encode(
                    x=alt.X(
                        "datetime:T",
                        title=f"{period_label} Ending",
                        axis=alt.Axis(format="%Y-%m-%d"),
                    ),
                    y=alt.Y("count:Q", title="Count (Stacked)"),
                    color=alt.Color(
                        "project_id:N",
                        title="Project",
                        scale=alt.Scale(domain=color_domain, range=color_range),
                        legend=alt.Legend(orient="right")
                    ),
                    tooltip=[
                        alt.Tooltip("project_id:N", title="Project"),
                        alt.Tooltip("datetime:T", title=period_label, format="%Y-%m-%d"),
                        alt.Tooltip("count:Q", title="Count"),
                    ],
                )
            )
        else:
            # Not stacked: color by project, line type by metric (solid=GitHub, dashed=Plausible)
            line = (
                alt.Chart(df_counts)
                .mark_line(point=True)
                .encode(
                    x=alt.X(
                        "datetime:T",
                        title=f"{period_label} Ending",
                        axis=alt.Axis(format="%Y-%m-%d"),
                    ),
                    y=alt.Y("count:Q", title="Count"),
                    color=alt.Color(
                        "project_id:N",
                        title="Project",
                        scale=alt.Scale(domain=color_domain, range=color_range),
                        legend=alt.Legend(orient="right")
                    ),
                    strokeDash=alt.StrokeDash(
                        "metric_type:N",
                        title="Metric",
                        scale=alt.Scale(
                            domain=["GitHub", "Plausible"],
                            range=[[1, 0], [5, 2]]  # solid for GitHub, dashed for Plausible
                        ),
                        legend=alt.Legend(orient="right")
                    ),
                    tooltip=[
                        alt.Tooltip("project_id:N", title="Project"),
                        alt.Tooltip("metric_type:N", title="Metric"),
                        alt.Tooltip("datetime:T", title=period_label, format="%Y-%m-%d"),
                        alt.Tooltip("count:Q", title="Count"),
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
                .mark_text(fontSize=14, fontWeight="bold", color="white")
                .encode(
                    x=alt.X("datetime:T"),
                    y=alt.value(50),
                    text="label:N",
                )
            )

            chart = (
                (line + points + text)
                .add_selection(zoom)
                .properties(width="container", height=400)
                .configure_axis(
                    labelFontSize=14,
                    titleFontSize=16
                )
                .configure_legend(
                    labelFontSize=14,
                    titleFontSize=16
                )
            )
        else:
            chart = (
                line.add_selection(zoom)
                .properties(width="container", height=400)
                .configure_axis(
                    labelFontSize=14,
                    titleFontSize=16
                )
                .configure_legend(
                    labelFontSize=14,
                    titleFontSize=16
                )
            )

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
