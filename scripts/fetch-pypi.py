#!/usr/bin/env python3
"""
Download PyPI download statistics for projects defined in config.toml.

Fetches daily download counts from pypistats.org.
Outputs one JSONL file per project per day containing download counts from that date.
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

# Load environment variables from .env file
load_dotenv()


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


def handle_api_error(response: requests.Response, package_name: str):
    """Print detailed API error information."""
    print(f"\nError fetching data for {package_name}:", file=sys.stderr)
    print(f"Status Code: {response.status_code}", file=sys.stderr)

    # Print response body for more details
    try:
        error_data = response.json()
        print(f"Response: {json.dumps(error_data, indent=2)}", file=sys.stderr)
    except (json.JSONDecodeError, ValueError):
        print(f"Response Text: {response.text}", file=sys.stderr)


def fetch_pypi_downloads(
    package_name: str,
    project_id: str,
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch download statistics from pypistats.org API."""
    url = f"https://pypistats.org/api/packages/{package_name}/overall"

    try:
        response = requests.get(url, params={"mirrors": "false"})
        response.raise_for_status()
    except requests.exceptions.RequestException:
        handle_api_error(response, package_name)
        return []

    data = response.json()

    # The API returns: {"data": [{"category": "with_mirrors/without_mirrors", "date": "YYYY-MM-DD", "downloads": 123}], ...}
    download_data = data.get("data", [])

    # Filter for date range and without_mirrors category
    downloads = []
    for entry in download_data:
        # Skip entries with mirrors included
        if entry.get("category") == "with_mirrors":
            continue

        date_str = entry.get("date")
        if not date_str:
            continue

        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        # Check if date is in our range
        if start_date <= entry_date <= end_date:
            downloads.append({
                "metric": "downloads",
                "project_id": project_id,
                "date": date_str,
                "value": entry.get("downloads", 0),
            })

    return downloads


def group_downloads_by_date(downloads: List[Dict]) -> Dict[str, List[Dict]]:
    """Group downloads by date (YYYY-MM-DD)."""
    grouped = {}

    for download_entry in downloads:
        date_key = download_entry["date"]

        if date_key not in grouped:
            grouped[date_key] = []

        grouped[date_key].append(download_entry)

    return grouped


def write_jsonl(
    downloads: List[Dict],
    project_id: str,
    date: str,
    output_dir: str,
):
    """Write downloads to JSONL file or stdout."""
    if output_dir == "-":
        # Write to stdout
        for download in downloads:
            print(json.dumps(download))
    else:
        # Create subdirectory for project
        project_output_path = Path(output_dir) / project_id
        project_output_path.mkdir(parents=True, exist_ok=True)

        filename = project_output_path / f"{date}.jsonl"

        # Overwrite file to avoid duplicates on re-runs
        with open(filename, "w") as f:
            for download in downloads:
                f.write(json.dumps(download) + "\n")

        print(f"Wrote {len(downloads)} entries to {filename}", file=sys.stderr)


def process_project(
    project_id: str,
    package_name: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: str,
):
    """Process a single project."""
    print(f"\nProcessing {project_id} ({package_name})...", file=sys.stderr)

    downloads = fetch_pypi_downloads(
        package_name, project_id, start_date, end_date
    )

    if not downloads:
        print(f"  No data found for {project_id} in date range", file=sys.stderr)
        return

    print(f"  Found {len(downloads)} days of download data", file=sys.stderr)

    # Group by date and write files
    grouped = group_downloads_by_date(downloads)

    for date, date_downloads in grouped.items():
        write_jsonl(date_downloads, project_id, date, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Download PyPI download statistics for projects in config.toml"
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
        default="data/output/pypi",
        help='Output directory (default: data/output/pypi), use "-" for stdout',
    )

    args = parser.parse_args()

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
        package_name = project_data.get("pypi")

        if not package_name:
            print(
                f"Warning: No pypi package name for {project_id}, skipping",
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
            package_name,
            project_start_date,
            end_date,
            args.output,
        )

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
