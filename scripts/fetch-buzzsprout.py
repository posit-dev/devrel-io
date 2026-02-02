#!/usr/bin/env python3
"""
Download Buzzsprout podcast metrics for projects defined in config.toml.

Fetches daily snapshot of per-episode play counts (raw ELT style).
Outputs one JSONL file per project per day containing episode-level metrics.
Aggregation to total_plays happens in output-to-parquet.py.
"""

import argparse
import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Check if BUZZSPROUT_API_KEY exists before loading .env
key_in_env_before_dotenv = "BUZZSPROUT_API_KEY" in os.environ

# Load environment variables from .env file
load_dotenv()


def load_config(config_path: str = "config.toml") -> Dict:
    """Load configuration from TOML file."""
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_today() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def handle_api_error(response: requests.Response, podcast_id: str):
    """Print detailed API error information."""
    print(f"\nError fetching data for podcast {podcast_id}:", file=sys.stderr)
    print(f"Status Code: {response.status_code}", file=sys.stderr)

    try:
        error_data = response.json()
        print(f"Response: {json.dumps(error_data, indent=2)}", file=sys.stderr)
    except (json.JSONDecodeError, ValueError):
        print(f"Response Text: {response.text}", file=sys.stderr)


def fetch_buzzsprout_data(podcast_id: str, api_key: str) -> Optional[List[Dict]]:
    """
    Fetch episodes data from Buzzsprout API.

    Returns None on error (to distinguish from empty list).
    """
    url = f"https://www.buzzsprout.com/api/{podcast_id}/episodes.json"
    headers = {
        "Authorization": f"Token token={api_key}",
        "User-Agent": "devrel-io/1.0 (podcast metrics collector)",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Check if we got a response (connection errors won't have one)
        if response is not None:
            handle_api_error(response, podcast_id)
        else:
            print(f"\nError fetching data for podcast {podcast_id}:", file=sys.stderr)
            print(f"Request failed: {e}", file=sys.stderr)
        return None

    return response.json()


def extract_episode_metrics(
    episodes: List[Dict], project_id: str, date: str
) -> List[Dict]:
    """
    Extract per-episode metrics from episodes data.

    Returns one record per episode with play count and metadata.
    """
    metrics = []

    for ep in episodes:
        # Skip unpublished episodes (drafts/scheduled)
        if not ep.get("published_at"):
            continue

        metrics.append(
            {
                "metric": "episode_plays",
                "project_id": project_id,
                "date": date,
                "value": ep.get("total_plays") or 0,
                "episode_id": ep.get("id"),
                "episode_number": ep.get("episode_number"),
                "episode_title": ep.get("title"),
            }
        )

    return metrics


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
    api_key: str,
    date: str,
    output_dir: str,
) -> bool:
    """
    Process a single project.

    Returns True on success, False on failure.
    """
    print(f"\nProcessing {project_id} (podcast {podcast_id})...", file=sys.stderr)

    episodes = fetch_buzzsprout_data(podcast_id, api_key)

    if episodes is None:
        print(f"  Failed to fetch data for {project_id}", file=sys.stderr)
        return False

    if not episodes:
        print(f"  No episodes found for {project_id}", file=sys.stderr)
        return True  # Empty is valid, not an error

    print(f"  Found {len(episodes)} episodes", file=sys.stderr)

    metrics = extract_episode_metrics(episodes, project_id, date)
    write_jsonl(metrics, project_id, date, output_dir)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download Buzzsprout podcast metrics for projects in config.toml"
    )
    parser.add_argument(
        "--project",
        help="Project ID from config.toml (if not specified, process all projects)",
    )
    parser.add_argument(
        "--date",
        default=get_today(),
        help="Date for the snapshot in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--output",
        default="data/output/buzzsprout",
        help='Output directory (default: data/output/buzzsprout), use "-" for stdout',
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("BUZZSPROUT_API_KEY"),
        help="Buzzsprout API key (or set BUZZSPROUT_API_KEY env var)",
    )

    args = parser.parse_args()

    # Determine and show API key source
    if args.api_key:
        if "--api-key" in sys.argv:
            print("Using BUZZSPROUT_API_KEY from --api-key argument", file=sys.stderr)
        elif key_in_env_before_dotenv:
            print("Using BUZZSPROUT_API_KEY from environment variable", file=sys.stderr)
        else:
            print("Using BUZZSPROUT_API_KEY from .env file", file=sys.stderr)
    else:
        print("Error: No BUZZSPROUT_API_KEY provided", file=sys.stderr)
        print(
            "Set BUZZSPROUT_API_KEY environment variable or use --api-key argument",
            file=sys.stderr,
        )
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

    # Track failures
    had_failures = False

    # Process each project
    for project_id, project_data in projects_to_process.items():
        podcast_id = project_data.get("buzzsprout")

        if not podcast_id:
            print(
                f"Warning: No buzzsprout podcast ID for {project_id}, skipping",
                file=sys.stderr,
            )
            continue

        success = process_project(
            project_id,
            podcast_id,
            args.api_key,
            args.date,
            args.output,
        )
        if not success:
            had_failures = True

    if had_failures:
        print("\nCompleted with errors!", file=sys.stderr)
        sys.exit(1)

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
