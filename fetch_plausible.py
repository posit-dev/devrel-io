#!/usr/bin/env python3
"""
Download Plausible analytics data for projects defined in config.toml.

Fetches daily counts for pageviews, visitors, and visits.
Outputs one JSONL file per project per day containing metrics from that date.
"""

import argparse
import json
import os
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from utils import get_last_date_for_project

# Check if PLAUSIBLE_KEY exists before loading .env
key_in_env_before_dotenv = "PLAUSIBLE_KEY" in os.environ

# Load environment variables from .env file
load_dotenv()

# Metrics to fetch from Plausible
METRICS = ["pageviews", "visitors", "visits"]


def load_config(config_path: str = "config.toml") -> Dict:
    """Load configuration from TOML file."""
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format to datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def get_yesterday() -> str:
    """Get yesterday's date in YYYY-MM-DD format."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def handle_api_error(response: requests.Response, site_id: str):
    """Print detailed API error information."""
    print(f"\nError fetching data for {site_id}:", file=sys.stderr)
    print(f"Status Code: {response.status_code}", file=sys.stderr)

    # Print response body for more details
    try:
        error_data = response.json()
        print(f"Response: {json.dumps(error_data, indent=2)}", file=sys.stderr)
    except (json.JSONDecodeError, ValueError):
        print(f"Response Text: {response.text}", file=sys.stderr)


def fetch_plausible_data(
    site_id: str,
    project_id: str,
    api_key: str,
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch analytics data from Plausible API."""
    url = "https://plausible.io/api/v2/query"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Calculate date range in days
    delta = end_date - start_date
    days = delta.days + 1  # +1 to include end date

    payload = {
        "site_id": site_id,
        "metrics": METRICS,
        "date_range": [
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        ],
        "dimensions": ["time:day"],
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        handle_api_error(response, site_id)
        return []

    data = response.json()
    results = data.get("results", [])

    # Transform results into our desired format
    # Each result has: {"metrics": [pageviews, visitors, visits], "dimensions": ["YYYY-MM-DD"]}
    metrics_data = []

    for result in results:
        date = result["dimensions"][0]
        metric_values = result["metrics"]

        # Create one entry per metric
        for i, metric_name in enumerate(METRICS):
            metrics_data.append(
                {
                    "metric": metric_name,
                    "project_id": project_id,
                    "date": date,
                    "value": metric_values[i],
                }
            )

    return metrics_data


def group_metrics_by_date(metrics: List[Dict]) -> Dict[str, List[Dict]]:
    """Group metrics by date (YYYY-MM-DD)."""
    grouped = {}

    for metric_entry in metrics:
        date_key = metric_entry["date"]

        if date_key not in grouped:
            grouped[date_key] = []

        grouped[date_key].append(metric_entry)

    return grouped


def write_jsonl(
    metrics: List[Dict],
    project_id: str,
    date: str,
    output_dir: str,
):
    """Write metrics to JSONL file or stdout."""
    if output_dir == "-":
        # Write to stdout
        for metric in metrics:
            print(json.dumps(metric))
    else:
        # Create subdirectory for project
        project_output_path = Path(output_dir) / project_id
        project_output_path.mkdir(parents=True, exist_ok=True)

        filename = project_output_path / f"{date}.jsonl"

        # Overwrite file to avoid duplicates on re-runs
        with open(filename, "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")

        print(f"Wrote {len(metrics)} metrics to {filename}", file=sys.stderr)


def process_project(
    project_id: str,
    site_id: str,
    api_key: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: str,
):
    """Process a single project."""
    print(f"\nProcessing {project_id} ({site_id})...", file=sys.stderr)

    metrics_data = fetch_plausible_data(
        site_id, project_id, api_key, start_date, end_date
    )

    if not metrics_data:
        print(f"  No data found for {project_id} in date range", file=sys.stderr)
        return

    print(f"  Found {len(metrics_data)} total metrics", file=sys.stderr)

    # Group by date and write files
    grouped = group_metrics_by_date(metrics_data)

    for date, date_metrics in grouped.items():
        write_jsonl(date_metrics, project_id, date, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Download Plausible analytics data for projects in config.toml"
    )
    parser.add_argument(
        "--project",
        help="Project ID from config.toml (if not specified, process all projects)",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date in YYYY-MM-DD format (default: auto-detect from last data file, or 2000-01-01 for new projects)",
    )
    parser.add_argument(
        "--end-date",
        default=get_yesterday(),
        help="End date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--output",
        default="data/output/plausible",
        help='Output directory (default: data/output/plausible), use "-" for stdout',
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("PLAUSIBLE_KEY"),
        help="Plausible API key (or set PLAUSIBLE_KEY env var)",
    )

    args = parser.parse_args()

    # Determine and show API key source
    if args.api_key:
        # Check if --api-key was explicitly provided in command line
        if "--api-key" in sys.argv:
            print("Using PLAUSIBLE_KEY from --api-key argument", file=sys.stderr)
        # Check if it was set in environment before loading .env
        elif key_in_env_before_dotenv:
            print("Using PLAUSIBLE_KEY from environment variable", file=sys.stderr)
        # Otherwise it must be from .env file
        else:
            print("Using PLAUSIBLE_KEY from .env file", file=sys.stderr)
    else:
        print("Error: No PLAUSIBLE_KEY provided", file=sys.stderr)
        print(
            "Set PLAUSIBLE_KEY environment variable or use --api-key argument",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse end_date (always required or has default)
    try:
        end_date = parse_date(args.end_date)
    except ValueError as e:
        print(f"Error parsing end date: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse start_date if provided by user
    user_provided_start_date = args.start_date
    if user_provided_start_date:
        try:
            start_date = parse_date(user_provided_start_date)
        except ValueError as e:
            print(f"Error parsing start date: {e}", file=sys.stderr)
            sys.exit(1)

        if end_date < start_date:
            print("Error: end-date must be >= start-date", file=sys.stderr)
            sys.exit(1)

    # Load config for projects
    try:
        config = load_config()
    except FileNotFoundError:
        print("Error: config.toml not found", file=sys.stderr)
        sys.exit(1)

    projects = config.get("projects", {})

    if not projects:
        print("Error: No projects found in config.toml", file=sys.stderr)
        sys.exit(1)

    # Filter by project ID if specified
    if args.project:
        if args.project not in projects:
            print(
                f"Error: Project '{args.project}' not found in config.toml",
                file=sys.stderr,
            )
            print(f"Available projects: {', '.join(projects.keys())}", file=sys.stderr)
            sys.exit(1)

        projects_to_process = {args.project: projects[args.project]}
    else:
        projects_to_process = projects

    # Process each project
    for project_id, project_data in projects_to_process.items():
        site_id = project_data.get("plausible")

        if not site_id:
            print(
                f"Warning: No plausible site ID for {project_id}, skipping",
                file=sys.stderr,
            )
            continue

        # Determine start_date for this project
        if not user_provided_start_date:
            # Auto-detect start date
            last_date = get_last_date_for_project(args.output, project_id)
            if last_date:
                project_start_date = parse_date(last_date) + timedelta(days=1)
                print(
                    f"Auto-detected start date for {project_id}: {project_start_date.strftime('%Y-%m-%d')}",
                    file=sys.stderr,
                )
            else:
                project_start_date = parse_date("2000-01-01")
                print(
                    f"No existing data for {project_id}, starting from 2000-01-01",
                    file=sys.stderr,
                )

            # Validate dates
            if end_date < project_start_date:
                print(
                    f"Warning: Skipping {project_id} - end-date is before start-date",
                    file=sys.stderr,
                )
                continue
        else:
            project_start_date = start_date

        process_project(
            project_id,
            site_id,
            args.api_key,
            project_start_date,
            end_date,
            args.output,
        )

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
