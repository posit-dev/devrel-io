#!/usr/bin/env python3
"""
Download GitHub stars for projects defined in config.toml.

Outputs one JSONL file per project per day containing stars from that date.
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


def fetch_stargazers(
    owner: str,
    repo: str,
    project_id: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """
    Fetch stargazers from GitHub API within the date range.

    Returns list of dicts with: project_id, github_repo, datetime, user
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
    headers = {
        "Accept": "application/vnd.github.v3.star+json",  # Get starred_at timestamps
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    stars = []
    page = 1
    per_page = 100
    github_repo = f"{owner}/{repo}"

    # Add one day to end_date to make it inclusive
    end_date_inclusive = end_date + timedelta(days=1)

    while True:
        params = {"page": page, "per_page": per_page}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"\nError fetching stars for {github_repo}:", file=sys.stderr)
            print(f"Status Code: {response.status_code}", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)

            # Print rate limit info if available
            if "X-RateLimit-Remaining" in response.headers:
                print(f"Rate Limit Remaining: {response.headers.get('X-RateLimit-Remaining')}", file=sys.stderr)
                print(f"Rate Limit Reset: {response.headers.get('X-RateLimit-Reset')}", file=sys.stderr)

            # Print response body for more details
            try:
                error_data = response.json()
                print(f"Response: {json.dumps(error_data, indent=2)}", file=sys.stderr)
            except:
                print(f"Response Text: {response.text}", file=sys.stderr)

            return stars

        data = response.json()

        if not data:
            # No more pages
            break

        for item in data:
            starred_at = datetime.fromisoformat(
                item["starred_at"].replace("Z", "+00:00")
            )

            # Since results are sorted by starred_at descending (newest first),
            # we can stop when we hit stars older than our start date
            if starred_at < start_date:
                return stars

            # Only include stars within our date range
            if start_date <= starred_at < end_date_inclusive:
                stars.append({
                    "project_id": project_id,
                    "github_repo": github_repo,
                    "datetime": item["starred_at"],
                    "user": item["user"]["login"],
                })

        page += 1

    return stars


def group_stars_by_date(stars: List[Dict]) -> Dict[str, List[Dict]]:
    """Group stars by date (YYYY-MM-DD)."""
    grouped = {}

    for star in stars:
        # Extract date from ISO timestamp
        dt = datetime.fromisoformat(star["datetime"].replace("Z", "+00:00"))
        date_key = dt.strftime("%Y-%m-%d")

        if date_key not in grouped:
            grouped[date_key] = []

        grouped[date_key].append(star)

    return grouped


def write_jsonl(
    stars: List[Dict],
    project_id: str,
    date: str,
    output_dir: str,
):
    """Write stars to JSONL file or stdout."""
    if output_dir == "-":
        # Write to stdout
        for star in stars:
            print(json.dumps(star))
    else:
        # Create subdirectory for project
        project_output_path = Path(output_dir) / project_id
        project_output_path.mkdir(parents=True, exist_ok=True)

        filename = project_output_path / f"{date}.jsonl"

        with open(filename, "w") as f:
            for star in stars:
                f.write(json.dumps(star) + "\n")

        print(f"Wrote {len(stars)} stars to {filename}", file=sys.stderr)


def process_project(
    project_id: str,
    github_repo: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
    output_dir: str,
):
    """Process a single project."""
    print(f"Processing {project_id} ({github_repo})...", file=sys.stderr)

    # Parse owner/repo
    try:
        owner, repo = github_repo.split("/")
    except ValueError:
        print(f"Invalid GitHub repo format: {github_repo}", file=sys.stderr)
        return

    # Fetch stars
    stars = fetch_stargazers(owner, repo, project_id, token, start_date, end_date)

    if not stars:
        print(f"No stars found for {project_id} in date range", file=sys.stderr)
        return

    # Group by date and write files
    grouped = group_stars_by_date(stars)

    for date, date_stars in grouped.items():
        write_jsonl(date_stars, project_id, date, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Download GitHub stars for projects in config.toml"
    )
    parser.add_argument(
        "--id",
        help="Project ID from config.toml (if not specified, process all projects)",
    )
    parser.add_argument(
        "--start-date",
        default=get_yesterday(),
        help="Start date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--end-date",
        default=get_yesterday(),
        help="End date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--output",
        default="data/output/github_stars",
        help='Output directory (default: data/output/github_stars), use "-" for stdout',
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )

    args = parser.parse_args()

    # Show token source for debugging
    if args.token:
        if os.environ.get("GITHUB_TOKEN") and args.token == os.environ.get("GITHUB_TOKEN"):
            print("Using GITHUB_TOKEN from .env file", file=sys.stderr)
        else:
            print("Using GITHUB_TOKEN from --token argument or environment", file=sys.stderr)
    else:
        print("No GITHUB_TOKEN provided (rate limited to 60 requests/hour)", file=sys.stderr)

    # Parse dates
    try:
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
    except ValueError as e:
        print(f"Error parsing dates: {e}", file=sys.stderr)
        sys.exit(1)

    if end_date < start_date:
        print("Error: end-date must be >= start-date", file=sys.stderr)
        sys.exit(1)

    # Load config
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
    if args.id:
        if args.id not in projects:
            print(f"Error: Project '{args.id}' not found in config.toml", file=sys.stderr)
            print(f"Available projects: {', '.join(projects.keys())}", file=sys.stderr)
            sys.exit(1)

        projects_to_process = {args.id: projects[args.id]}
    else:
        projects_to_process = projects

    # Process each project
    for project_id, project_data in projects_to_process.items():
        github_repo = project_data.get("github")

        if not github_repo:
            print(f"Warning: No github repo for {project_id}, skipping", file=sys.stderr)
            continue

        process_project(
            project_id,
            github_repo,
            args.token,
            start_date,
            end_date,
            args.output,
        )

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
