#!/usr/bin/env python3
"""
Download Open VSX extension statistics for projects defined in config.toml.

Fetches daily snapshot metrics from Open VSX API.
Outputs one JSONL file per project per day containing metrics from that date.
"""

import argparse
import json
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()


def load_config(config_path: str = "config.toml") -> Dict:
    """Load configuration from TOML file."""
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_yesterday() -> str:
    """Get yesterday's date in YYYY-MM-DD format."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def handle_api_error(response: requests.Response, extension_id: str):
    """Print detailed API error information."""
    print(f"\nError fetching data for {extension_id}:", file=sys.stderr)
    print(f"Status Code: {response.status_code}", file=sys.stderr)

    # Print response body for more details
    try:
        error_data = response.json()
        print(f"Response: {json.dumps(error_data, indent=2)}", file=sys.stderr)
    except (json.JSONDecodeError, ValueError):
        print(f"Response Text: {response.text}", file=sys.stderr)


def fetch_openvsx_metrics(
    extension_id: str,
    project_id: str,
    date: str,
) -> List[Dict]:
    """
    Fetch extension metrics from Open VSX API.

    Args:
        extension_id: Extension ID in format "namespace/extension" (e.g., "quarto/quarto")
        project_id: Project identifier from config.toml
        date: Date string in YYYY-MM-DD format

    Returns:
        List of metric dicts with keys: metric, project_id, date, value
    """
    # Split extension_id into namespace and extension
    parts = extension_id.split("/")
    if len(parts) != 2:
        print(f"Error: Invalid extension_id format: {extension_id}", file=sys.stderr)
        print(f"Expected format: namespace/extension", file=sys.stderr)
        return []

    namespace, extension = parts
    url = f"https://open-vsx.org/api/{namespace}/{extension}"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        handle_api_error(response, extension_id)
        return []

    data = response.json()

    # Extract metrics
    metrics = []

    # Total downloads
    download_count = data.get("downloadCount", 0)
    metrics.append({
        "metric": "total_downloads",
        "project_id": project_id,
        "date": date,
        "value": download_count,
    })

    # Average rating
    average_rating = data.get("averageRating")
    if average_rating is not None:
        metrics.append({
            "metric": "rating",
            "project_id": project_id,
            "date": date,
            "value": average_rating,
        })

    # Review count
    review_count = data.get("reviewCount", 0)
    metrics.append({
        "metric": "reviews",
        "project_id": project_id,
        "date": date,
        "value": review_count,
    })

    return metrics


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
    extension_id: str,
    date: str,
    output_dir: str,
):
    """Process a single project."""
    print(f"\nProcessing {project_id} ({extension_id})...", file=sys.stderr)

    metrics = fetch_openvsx_metrics(extension_id, project_id, date)

    if not metrics:
        print(f"  No data found for {project_id}", file=sys.stderr)
        return

    print(f"  Found {len(metrics)} metrics", file=sys.stderr)

    # Write to file
    write_jsonl(metrics, project_id, date, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Download Open VSX extension metrics for projects in config.toml"
    )
    parser.add_argument(
        "--project",
        help="Project ID from config.toml (if not specified, process all projects with 'openvsx' field)",
    )
    parser.add_argument(
        "--output",
        default="data/output/openvsx",
        help='Output directory (default: data/output/openvsx), use "-" for stdout',
    )

    args = parser.parse_args()

    # Use yesterday's date for snapshot
    date = get_yesterday()
    print(f"Fetching Open VSX metrics for date: {date}", file=sys.stderr)

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

    # Filter projects based on --project argument
    if args.project:
        # Single project mode
        if args.project not in projects:
            print(
                f"Error: Project '{args.project}' not found in config.toml",
                file=sys.stderr,
            )
            print(f"Available projects: {', '.join(projects.keys())}", file=sys.stderr)
            sys.exit(1)

        projects_to_process = {args.project: projects[args.project]}
    else:
        # All projects mode - only process projects with 'openvsx' field
        projects_to_process = {
            project_id: project_data
            for project_id, project_data in projects.items()
            if project_data.get("openvsx")
        }

        if not projects_to_process:
            print(
                "No projects with 'openvsx' field found in config.toml",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"Processing {len(projects_to_process)} projects with Open VSX configuration",
            file=sys.stderr,
        )

    # Process each project
    for project_id, project_data in projects_to_process.items():
        extension_id = project_data.get("openvsx")

        if not extension_id:
            print(
                f"Warning: No openvsx extension ID for {project_id}, skipping",
                file=sys.stderr,
            )
            continue

        process_project(project_id, extension_id, date, args.output)

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
