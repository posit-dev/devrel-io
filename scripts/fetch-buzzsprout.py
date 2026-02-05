#!/usr/bin/env python3
"""
Download Buzzsprout podcast download statistics for projects defined in config.toml.

Uses buzzsprout-headless (backfill-daily) to scrape per-episode daily downloads,
then aggregates into total downloads per date.
Outputs one JSONL file per project per day.
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

# Check if credentials exist before loading .env
user_in_env_before_dotenv = "BUZZSPROUT_USER" in os.environ
pass_in_env_before_dotenv = "BUZZSPROUT_PASS" in os.environ

# Load environment variables from .env file
load_dotenv()

from buzzsprout_headless.scrape_stats import cmd_backfill_daily

from utils import get_last_date_for_project

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


def run_buzzsprout_backfill(
    podcast_id: str,
    start_date: str,
    end_date: str,
    data_dir: str,
) -> bool:
    """
    Run buzzsprout-headless backfill-daily for a date range.

    Returns True on success, False on failure.
    """
    # Generate date list
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    if not dates:
        return False

    print(f"  Date range: {start_date} to {end_date}", file=sys.stderr)

    os.environ["BUZZSPROUT_PODCAST_ID"] = str(podcast_id)
    os.environ["BUZZSPROUT_DATA_DIR"] = data_dir

    asyncio.run(cmd_backfill_daily(dates, delay=1.0))
    return True


def read_and_aggregate(
    data_dir: str,
    podcast_id: str,
    project_id: str,
) -> Dict[str, List[Dict]]:
    """
    Read buzzsprout-headless output files and aggregate downloads by date.

    Returns a dict mapping date strings to lists of metric records.
    """
    base_path = Path(data_dir) / podcast_id
    grouped = {}

    if not base_path.exists():
        return grouped

    for date_dir in sorted(base_path.iterdir()):
        if not date_dir.is_dir():
            continue

        downloads_file = date_dir / "downloads-daily.jsonl"
        if not downloads_file.exists():
            continue

        date_str = date_dir.name
        total_downloads = 0
        episode_count = 0

        with open(downloads_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                total_downloads += int(record.get("downloads") or 0)
                episode_count += 1

        if episode_count > 0:
            grouped[date_str] = [
                {
                    "metric": "downloads",
                    "project_id": project_id,
                    "date": date_str,
                    "value": total_downloads,
                },
                {
                    "metric": "n_episodes",
                    "project_id": project_id,
                    "date": date_str,
                    "value": episode_count,
                },
            ]

    return grouped


def write_jsonl(
    metrics: List[Dict],
    project_id: str,
    date: str,
    output_dir: str,
):
    """Write metrics to JSONL file or stdout."""
    if output_dir == "-":
        for metric in metrics:
            print(json.dumps(metric))
    else:
        project_output_path = Path(output_dir) / project_id
        project_output_path.mkdir(parents=True, exist_ok=True)

        filename = project_output_path / f"{date}.jsonl"

        with open(filename, "w") as f:
            for metric in metrics:
                f.write(json.dumps(metric) + "\n")

        print(f"Wrote {len(metrics)} metrics to {filename}", file=sys.stderr)


def process_project(
    project_id: str,
    podcast_id: str,
    start_date: datetime,
    end_date: datetime,
    output_dir: str,
):
    """Process a single project."""
    print(f"\nProcessing {project_id} (podcast {podcast_id})...", file=sys.stderr)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    with tempfile.TemporaryDirectory() as tmpdir:
        success = run_buzzsprout_backfill(
            podcast_id, start_str, end_str, tmpdir
        )

        if not success:
            print(f"  Failed to fetch data for {project_id}", file=sys.stderr)
            return

        grouped = read_and_aggregate(tmpdir, podcast_id, project_id)

    if not grouped:
        print(f"  No data found for {project_id} in date range", file=sys.stderr)
        return

    print(f"  Found {len(grouped)} days of download data", file=sys.stderr)

    for date, date_metrics in grouped.items():
        write_jsonl(date_metrics, project_id, date, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Download Buzzsprout podcast statistics for projects in config.toml"
    )
    parser.add_argument(
        "--project",
        help="Project ID from config.toml (if not specified, process all projects with 'buzzsprout' field)",
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
        default="data/output/buzzsprout",
        help='Output directory (default: data/output/buzzsprout), use "-" for stdout',
    )

    args = parser.parse_args()

    # Check credentials
    user = os.environ.get("BUZZSPROUT_USER")
    password = os.environ.get("BUZZSPROUT_PASS")

    if not user or not password:
        print(
            "Error: BUZZSPROUT_USER and BUZZSPROUT_PASS must be set.\n"
            "Set them as environment variables or in a .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Show credential source
    if user_in_env_before_dotenv and pass_in_env_before_dotenv:
        print("Using BUZZSPROUT credentials from environment variables", file=sys.stderr)
    else:
        print("Using BUZZSPROUT credentials from .env file", file=sys.stderr)

    # Parse end_date
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
        # Only process projects with 'buzzsprout' field
        projects_to_process = {
            project_id: project_data
            for project_id, project_data in projects.items()
            if project_data.get("buzzsprout")
        }

        if not projects_to_process:
            print(
                "No projects with 'buzzsprout' field found in config.toml",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"Processing {len(projects_to_process)} projects with Buzzsprout configuration",
            file=sys.stderr,
        )

    # Process each project
    for project_id, project_data in projects_to_process.items():
        podcast_id = project_data.get("buzzsprout")

        if not podcast_id:
            print(
                f"Warning: No buzzsprout podcast ID for {project_id}, skipping",
                file=sys.stderr,
            )
            continue

        # Determine start_date for this project
        if not user_provided_start_date:
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
            podcast_id,
            project_start_date,
            end_date,
            args.output,
        )

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
