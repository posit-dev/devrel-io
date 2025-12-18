#!/usr/bin/env python3
"""
Shiny app for visualizing DevRel I/O data.
"""

import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import altair as alt
import polars as pl
from itables.widget import ITable
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shinywidgets import output_widget, reactive_read, render_widget

# Load config to get projects
try:
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)

    projects = list(config["projects"].keys())
    project_names = {pid: config["projects"][pid]["name"] for pid in projects}
    project_colors = {
        pid: config["projects"][pid].get("hex_color", "#808080") for pid in projects
    }
except FileNotFoundError:
    print("Error: config.toml not found", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error loading config.toml: {e}", file=sys.stderr)
    sys.exit(1)

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

# Chart configuration constants
CHART_HEIGHT = 400
ANNOTATION_OFFSET = 440  # pixels (CHART_HEIGHT + 40)

# Line patterns for different metric types
LINE_PATTERNS = {
    "GitHub": [1, 0],  # solid
    "Plausible": [5, 2],  # dashed
    "PyPI": [2, 2],  # dotted
}

# Aggregation intervals
AGGREGATION_INTERVALS = {
    "daily": "1d",
    "weekly": "1w",
    "monthly": "1mo",
}

# Font sizes
FONT_SIZE_AXIS_LABEL = 14
FONT_SIZE_AXIS_TITLE = 16
FONT_SIZE_ANNOTATION = 14

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
        ui.h4("PyPI"),
        ui.input_checkbox_group(
            "pypi_metrics",
            None,
            choices={"downloads": "Downloads"},
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
                "custom": "Custom",
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
    ui.h2("Output"),
    ui.output_ui("events_chart"),
    ui.h2("Input"),
    output_widget("input_table"),
    title="DevRel I/O Dashboard",
)


# Helper functions
def read_metric_data(directory: str) -> pl.DataFrame:
    """Read all JSONL files from a directory (excluding archive subdirectories)."""
    try:
        jsonl_files = []
        for path in Path(f"data/output/{directory}").rglob("*.jsonl"):
            if "archive" not in path.parts:
                jsonl_files.append(str(path))

        if not jsonl_files:
            return pl.DataFrame()

        return pl.read_ndjson(jsonl_files)
    except Exception as e:
        print(f"Error reading {directory} data: {e}", file=sys.stderr)
        return pl.DataFrame()


def filter_by_date_range(
    df: pl.DataFrame,
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    date_column: str = "date",
) -> pl.DataFrame:
    """Filter dataframe by date range."""
    if not start_date or not end_date or date_column not in df.columns:
        return df

    df = df.with_columns(
        pl.col(date_column)
        .str.strptime(
            pl.Datetime, "%Y-%m-%d" if date_column == "date" else "%Y-%m-%dT%H:%M:%SZ"
        )
        .dt.replace_time_zone("UTC")
    )
    df = df.filter(
        (pl.col(date_column) >= start_date) & (pl.col(date_column) <= end_date)
    )

    # Convert back to string for consistency
    format_str = "%Y-%m-%d" if date_column == "date" else "%Y-%m-%dT%H:%M:%SZ"
    df = df.with_columns(
        pl.col(date_column).dt.convert_time_zone("UTC").dt.strftime(format_str)
    )

    return df


def aggregate_metric_data(
    df: pl.DataFrame,
    metric_label: str,
    aggregation: str,
    group_by_project_only: bool = True,
) -> pl.DataFrame:
    """Aggregate metric data by time period."""
    if df.is_empty():
        return pl.DataFrame()

    # Determine aggregation interval
    interval = AGGREGATION_INTERVALS[aggregation]

    # Group by project and time period
    group_by_kwargs = {
        "every": interval,
        "group_by": "project_id",
        "label": "right",
    }

    if aggregation == "weekly":
        group_by_kwargs["start_by"] = "monday"

    df_agg = df.group_by_dynamic("datetime", **group_by_kwargs).agg(
        pl.len().alias("count")
        if metric_label == "GitHub"
        else pl.sum("count").cast(pl.Int64).alias("count")
    )

    # Add metric_type column
    df_agg = df_agg.with_columns(pl.lit(metric_label).alias("metric_type"))

    return df_agg


def filter_metric_data(
    df: pl.DataFrame,
    selected_projects: List[str],
    selected_metrics: List[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    date_column: str = "datetime",
    metric_column: str = "event_type",
    date_format: str = "%Y-%m-%dT%H:%M:%SZ",
) -> pl.DataFrame:
    """Generic function to filter metric data by projects, metrics, and date range."""
    if df.is_empty():
        return df

    # If no projects selected, return empty DataFrame
    if not selected_projects:
        return pl.DataFrame()

    # If no metrics selected, return empty DataFrame
    if not selected_metrics:
        return pl.DataFrame()

    # Filter by projects
    if "project_id" in df.columns:
        df = df.filter(pl.col("project_id").is_in(selected_projects))

    # Filter by metric column (event_type for GitHub, metric for others)
    if metric_column in df.columns:
        df = df.filter(pl.col(metric_column).is_in(selected_metrics))

    # Filter by date range
    if start_date and end_date and date_column in df.columns:
        df = df.with_columns(
            pl.col(date_column)
            .str.strptime(pl.Datetime, date_format)
            .dt.replace_time_zone("UTC")
        )
        df = df.filter(
            (pl.col(date_column) >= start_date) & (pl.col(date_column) <= end_date)
        )
        # Convert back to string for consistency
        df = df.with_columns(
            pl.col(date_column).dt.convert_time_zone("UTC").dt.strftime(date_format)
        )

    return df


def aggregate_single_metric(
    df: pl.DataFrame,
    metric_label: str,
    aggregation: str,
    date_column: str = "datetime",
    date_format: str = "%Y-%m-%dT%H:%M:%SZ",
    has_value_column: bool = False,
) -> pl.DataFrame:
    """Aggregate a single metric type by time period."""
    if df.is_empty():
        return pl.DataFrame()

    # Convert date string to datetime
    df = df.with_columns(pl.col(date_column).str.strptime(pl.Datetime, date_format))

    # Rename date column to datetime for consistency
    if date_column != "datetime":
        df = df.rename({date_column: "datetime"})

    # Rename value to count if needed
    if has_value_column:
        df = df.rename({"value": "count"})

    # Sort by project and datetime
    df = df.sort(["project_id", "datetime"])

    # Determine aggregation interval
    interval = AGGREGATION_INTERVALS[aggregation]

    # Group by project and time period
    group_by_kwargs = {
        "every": interval,
        "group_by": "project_id",
        "label": "right",
    }

    if aggregation == "weekly":
        group_by_kwargs["start_by"] = "monday"

    # Aggregate based on whether we're counting events or summing values
    if has_value_column:
        df_agg = df.group_by_dynamic("datetime", **group_by_kwargs).agg(
            pl.sum("count").cast(pl.Int64).alias("count")
        )
    else:
        df_agg = df.group_by_dynamic("datetime", **group_by_kwargs).agg(
            pl.len().alias("count")
        )
        df_agg = df_agg.with_columns(pl.col("count").cast(pl.Int64))

    # Add metric_type column
    df_agg = df_agg.with_columns(pl.lit(metric_label).alias("metric_type"))

    return df_agg


def combine_and_transform_metrics(
    dataframes: List[pl.DataFrame],
    stack_metrics: bool,
    cumulative: bool,
) -> pl.DataFrame:
    """Combine metric dataframes and apply stacking/cumulative transformations."""
    if len(dataframes) == 0:
        return pl.DataFrame()

    # Combine all dataframes
    df_combined = pl.concat(dataframes)

    # Apply stacking if enabled
    if stack_metrics:
        # Sum all metrics per project and time period
        df_combined = (
            df_combined.group_by(["project_id", "datetime"])
            .agg(pl.sum("count").alias("count"))
            .sort(["project_id", "datetime"])
        )
    else:
        # Keep metrics separate, sort for display
        df_combined = df_combined.sort(["project_id", "metric_type", "datetime"])

    # Apply cumulative sum if enabled
    if cumulative:
        if stack_metrics:
            # Cumulative sum per project
            df_combined = df_combined.with_columns(
                pl.col("count").cum_sum().over("project_id").alias("count")
            )
        else:
            # Cumulative sum per project and metric type
            df_combined = df_combined.with_columns(
                pl.col("count")
                .cum_sum()
                .over(["project_id", "metric_type"])
                .alias("count")
            )

    return df_combined


def add_project_metadata(df: pl.DataFrame) -> pl.DataFrame:
    """Add hex_color and project_name columns to dataframe."""
    if df.is_empty():
        return df

    df = df.with_columns(
        [
            pl.col("project_id")
            .map_elements(
                lambda pid: project_colors.get(pid, "#808080"),
                return_dtype=pl.Utf8,
            )
            .alias("hex_color"),
            pl.col("project_id")
            .map_elements(lambda pid: project_names.get(pid, pid), return_dtype=pl.Utf8)
            .alias("project_name"),
        ]
    )

    return df


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
    def date_range() -> Tuple[Optional[datetime], Optional[datetime]]:
        """Calculate the date range based on period selection."""
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
                start_date = datetime.combine(start, datetime.min.time()).replace(
                    tzinfo=timezone.utc
                )
                end_date = datetime.combine(end, datetime.max.time()).replace(
                    tzinfo=timezone.utc
                )
                return start_date, end_date

        return None, None

    @reactive.calc
    def df_input() -> pl.DataFrame:
        """Read inputs.csv with datetime column parsed."""
        try:
            df = pl.read_csv("data/input/inputs.csv", try_parse_dates=True)
            return df
        except FileNotFoundError:
            print("Warning: data/input/inputs.csv not found", file=sys.stderr)
            return pl.DataFrame()
        except Exception as e:
            print(f"Error reading inputs.csv: {e}", file=sys.stderr)
            return pl.DataFrame()

    @reactive.calc
    def df_output() -> pl.DataFrame:
        """Read all GitHub events JSONL files (excluding archive)."""
        return read_metric_data("github")

    @reactive.calc
    def df_plausible() -> pl.DataFrame:
        """Read all Plausible JSONL files (excluding archive)."""
        return read_metric_data("plausible")

    @reactive.calc
    def df_pypi() -> pl.DataFrame:
        """Read all PyPI JSONL files (excluding archive)."""
        return read_metric_data("pypi")

    @reactive.calc
    def filtered_input() -> pl.DataFrame:
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
    def filtered_output() -> pl.DataFrame:
        """Filter output data by selected projects, event types, and date range."""
        df = df_output()
        selected_projects = list(input.project())
        selected_events = list(input.event_types())
        start_date, end_date = date_range()

        return filter_metric_data(
            df,
            selected_projects,
            selected_events,
            start_date,
            end_date,
            date_column="datetime",
            metric_column="event_type",
            date_format="%Y-%m-%dT%H:%M:%SZ",
        )

    @reactive.calc
    def filtered_plausible() -> pl.DataFrame:
        """Filter Plausible data by selected projects, metrics, and date range."""
        df = df_plausible()
        selected_projects = list(input.project())
        selected_metrics = list(input.plausible_metrics())
        start_date, end_date = date_range()

        return filter_metric_data(
            df,
            selected_projects,
            selected_metrics,
            start_date,
            end_date,
            date_column="date",
            metric_column="metric",
            date_format="%Y-%m-%d",
        )

    @reactive.calc
    def filtered_pypi() -> pl.DataFrame:
        """Filter PyPI data by selected projects, metrics, and date range."""
        df = df_pypi()
        selected_projects = list(input.project())
        selected_metrics = list(input.pypi_metrics())
        start_date, end_date = date_range()

        return filter_metric_data(
            df,
            selected_projects,
            selected_metrics,
            start_date,
            end_date,
            date_column="date",
            metric_column="metric",
            date_format="%Y-%m-%d",
        )

    @reactive.calc
    def aggregated_counts() -> pl.DataFrame:
        """Aggregate events and metrics by time period, with optional stacking and cumulative sum."""
        aggregation = input.aggregation()

        # Process GitHub events
        df_github_agg = aggregate_single_metric(
            filtered_output(),
            metric_label="GitHub",
            aggregation=aggregation,
            date_column="datetime",
            date_format="%Y-%m-%dT%H:%M:%SZ",
            has_value_column=False,
        )

        # Process Plausible data
        df_plaus_agg = aggregate_single_metric(
            filtered_plausible(),
            metric_label="Plausible",
            aggregation=aggregation,
            date_column="date",
            date_format="%Y-%m-%d",
            has_value_column=True,
        )

        # Process PyPI data
        df_pypi_agg = aggregate_single_metric(
            filtered_pypi(),
            metric_label="PyPI",
            aggregation=aggregation,
            date_column="date",
            date_format="%Y-%m-%d",
            has_value_column=True,
        )

        # Combine all non-empty dataframes
        dataframes = []
        for df in [df_github_agg, df_plaus_agg, df_pypi_agg]:
            if not df.is_empty():
                dataframes.append(
                    df.select(["project_id", "datetime", "metric_type", "count"])
                )

        # Combine and apply transformations
        df_combined = combine_and_transform_metrics(
            dataframes, input.stack_metrics(), input.cumulative()
        )

        # Add project metadata
        df_combined = add_project_metadata(df_combined)

        return df_combined

    @reactive.calc
    def selected_table_rows() -> List[int]:
        """Get the list of selected row indices from the input table."""
        try:
            selected = reactive_read(input_table.widget, "selected_rows")
            return selected if selected else []
        except Exception:
            return []

    @reactive.calc
    def annotations() -> pl.DataFrame:
        """Create annotations from input data with project information."""
        df = filtered_input()

        if df.is_empty() or "datetime" not in df.columns:
            return pl.DataFrame()

        # Select label, datetime, project, and title
        columns_to_select = ["label", "datetime", "project"]
        if "title" in df.columns:
            columns_to_select.append("title")
        df = df.select(columns_to_select)

        # Add selected column based on table selection
        selected_rows = selected_table_rows()
        df = df.with_columns(
            pl.Series("selected", [i in selected_rows for i in range(len(df))])
        )

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
            base = alt.Chart(df_counts).encode(
                color=alt.Color(
                    "project_id:N",
                    title="Project",
                    scale=alt.Scale(domain=color_domain, range=color_range),
                    legend=None,
                )
            )

            line = base.mark_line(point=True).encode(
                x=alt.X(
                    "datetime:T",
                    title=None,
                    axis=alt.Axis(format="%Y-%m-%d"),
                ),
                y=alt.Y("count:Q", title="Count (Stacked)"),
                tooltip=[
                    alt.Tooltip("project_id:N", title="Project"),
                    alt.Tooltip("datetime:T", title=period_label, format="%Y-%m-%d"),
                    alt.Tooltip("count:Q", title="Count"),
                ],
            )

            # Get last visible point for each project (responds to zoom)
            last_point = (
                base.mark_circle(size=100)
                .encode(
                    x=alt.X("last_date['datetime']:T"), y=alt.Y("last_date['count']:Q")
                )
                .transform_filter(zoom)  # Filter to visible range
                .transform_aggregate(
                    last_date="argmax(datetime)", groupby=["project_id", "project_name"]
                )
            )

            # Add project name labels at fixed x position
            project_labels = last_point.mark_text(
                align="left", fontSize=FONT_SIZE_ANNOTATION, clip=False, dx=10
            ).encode(
                text=alt.Text("project_name:N"),
                x=alt.value("width"),  # Position at right edge
                y=alt.Y("last_date['count']:Q"),
            )

            line = line + last_point + project_labels
        else:
            # Not stacked: color by project, line type by metric (solid=GitHub, dashed=Plausible)
            # Add combined label column for display using project name
            df_counts = df_counts.with_columns(
                (pl.col("project_name") + " (" + pl.col("metric_type") + ")").alias(
                    "label"
                )
            )

            base = alt.Chart(df_counts).encode(
                color=alt.Color(
                    "project_id:N",
                    title="Project",
                    scale=alt.Scale(domain=color_domain, range=color_range),
                    legend=None,
                ),
                strokeDash=alt.StrokeDash(
                    "metric_type:N",
                    title="Metric",
                    scale=alt.Scale(
                        domain=["GitHub", "Plausible", "PyPI"],
                        range=[
                            LINE_PATTERNS["GitHub"],
                            LINE_PATTERNS["Plausible"],
                            LINE_PATTERNS["PyPI"],
                        ],
                    ),
                    legend=None,
                ),
            )

            line = base.mark_line(point=True).encode(
                x=alt.X(
                    "datetime:T",
                    title=None,
                    axis=alt.Axis(format="%Y-%m-%d"),
                ),
                y=alt.Y("count:Q", title="Count"),
                tooltip=[
                    alt.Tooltip("project_id:N", title="Project"),
                    alt.Tooltip("metric_type:N", title="Metric"),
                    alt.Tooltip("datetime:T", title=period_label, format="%Y-%m-%d"),
                    alt.Tooltip("count:Q", title="Count"),
                ],
            )

            # Get last visible point for each project+metric combination (responds to zoom)
            last_point = (
                base.mark_circle(size=100)
                .encode(
                    x=alt.X("last_date['datetime']:T"), y=alt.Y("last_date['count']:Q")
                )
                .transform_filter(zoom)  # Filter to visible range
                .transform_aggregate(
                    last_date="argmax(datetime)",
                    groupby=["project_id", "metric_type", "label"],
                )
            )

            # Add "Project (Metric)" labels at fixed x position
            line_labels = last_point.mark_text(
                align="left", fontSize=FONT_SIZE_ANNOTATION, clip=False, dx=10
            ).encode(
                text=alt.Text("label:N"),
                x=alt.value("width"),  # Position at right edge
                y=alt.Y("last_date['count']:Q"),
            )

            line = line + line_labels

        # Get annotations
        df_annotations = annotations()

        if not df_annotations.is_empty():
            # Create annotation points below x-axis, colored by project
            # Filter to only show annotations within visible x-axis range
            # Build tooltip list dynamically based on available columns
            tooltip_list = [
                alt.Tooltip("label:N", title="Label"),
                alt.Tooltip("project:N", title="Project"),
                alt.Tooltip("datetime:T", title="Date", format="%Y-%m-%d"),
            ]
            if "title" in df_annotations.columns:
                tooltip_list.append(alt.Tooltip("title:N", title="Title"))

            points = (
                alt.Chart(df_annotations)
                .mark_point(filled=True, clip=False)
                .encode(
                    x=alt.X("datetime:T"),
                    y=alt.value(ANNOTATION_OFFSET),
                    color=alt.Color("project:N", title="Project", legend=None),
                    size=alt.condition(
                        "datum.selected",
                        alt.value(600),  # Larger size for selected
                        alt.value(400),  # Normal size for unselected
                    ),
                    opacity=alt.condition(
                        "datum.selected",
                        alt.value(1.0),  # Full opacity for selected
                        alt.value(0.5),  # Reduced opacity for unselected
                    ),
                    strokeWidth=alt.condition(
                        "datum.selected",
                        alt.value(3),  # Thick stroke for selected
                        alt.value(0),  # No stroke for unselected
                    ),
                    stroke=alt.value("black"),  # Black stroke color
                    tooltip=tooltip_list,
                )
                .transform_filter(zoom)  # Only show annotations in visible range
            )

            text = (
                alt.Chart(df_annotations)
                .mark_text(
                    fontSize=FONT_SIZE_ANNOTATION,
                    fontWeight="bold",
                    color="white",
                    clip=False,
                )
                .encode(
                    x=alt.X("datetime:T"),
                    y=alt.value(ANNOTATION_OFFSET),
                    text="label:N",
                    opacity=alt.condition(
                        "datum.selected",
                        alt.value(1.0),  # Full opacity for selected
                        alt.value(0.7),  # Slightly reduced for unselected
                    ),
                )
                .transform_filter(zoom)  # Only show annotations in visible range
            )

            chart = line + points + text
        else:
            chart = line

        # Apply zoom and configuration
        chart = (
            chart.add_selection(zoom)
            .properties(width="container", height=CHART_HEIGHT)
            .configure_axis(
                labelFontSize=FONT_SIZE_AXIS_LABEL, titleFontSize=FONT_SIZE_AXIS_TITLE
            )
            .configure_view(
                clip=False  # Allow labels to extend beyond plot area
            )
        )

        return ui.HTML(chart.to_html())

    @render_widget
    def input_table():
        """Render input data table with title case columns and label first."""
        df = filtered_input()

        if df.is_empty():
            # Return empty ITable
            return ITable(pl.DataFrame())

        # Move label column to first position
        if "label" in df.columns:
            other_cols = [col for col in df.columns if col != "label"]
            df = df.select(["label"] + other_cols)

        df = df.with_columns(pl.col("datetime").dt.date()).rename({"datetime": "date"})

        # Convert column names to title case
        df = df.rename({col: col.replace("_", " ").title() for col in df.columns})

        # Return ITable widget with Polars DataFrame
        return ITable(
            df, show_dtypes=False, paging=False, scrollY="350px", scrollCollapse=True
        )


app = App(app_ui, server)
