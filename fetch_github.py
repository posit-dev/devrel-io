#!/usr/bin/env python3
"""
Download GitHub events for projects defined in config.toml.

Supports: stars, forks, issues (opened/closed), PRs (opened/merged), and comments.
Outputs one JSONL file per project per day containing events from that date.
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

# Check if GITHUB_TOKEN exists before loading .env
token_in_env_before_dotenv = "GITHUB_TOKEN" in os.environ

# Load environment variables from .env file
load_dotenv()

# Supported event types
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


def handle_api_error(response: requests.Response, github_repo: str):
    """Print detailed API error information."""
    print(f"\nError fetching events for {github_repo}:", file=sys.stderr)
    print(f"Status Code: {response.status_code}", file=sys.stderr)

    # Print rate limit info if available
    if "X-RateLimit-Remaining" in response.headers:
        print(
            f"Rate Limit Remaining: {response.headers.get('X-RateLimit-Remaining')}",
            file=sys.stderr,
        )
        print(
            f"Rate Limit Reset: {response.headers.get('X-RateLimit-Reset')}",
            file=sys.stderr,
        )

    # Print response body for more details
    try:
        error_data = response.json()
        print(f"Response: {json.dumps(error_data, indent=2)}", file=sys.stderr)
    except (json.JSONDecodeError, ValueError):
        print(f"Response Text: {response.text}", file=sys.stderr)


def fetch_stars(
    owner: str,
    repo: str,
    project_id: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch star events from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
    headers = {
        "Accept": "application/vnd.github.v3.star+json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    events = []
    page = 1
    per_page = 100
    github_repo = f"{owner}/{repo}"
    end_date_inclusive = end_date + timedelta(days=1)

    while True:
        params = {"page": page, "per_page": per_page}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            handle_api_error(response, github_repo)
            return events

        data = response.json()
        if not data:
            break

        for item in data:
            starred_at = datetime.fromisoformat(
                item["starred_at"].replace("Z", "+00:00")
            )

            if starred_at < start_date:
                return events

            if start_date <= starred_at < end_date_inclusive:
                events.append(
                    {
                        "event_type": "star",
                        "project_id": project_id,
                        "github_repo": github_repo,
                        "datetime": item["starred_at"],
                        "user": item["user"]["login"],
                    }
                )

        page += 1

    return events


def fetch_forks(
    owner: str,
    repo: str,
    project_id: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch fork events from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    events = []
    page = 1
    per_page = 100
    github_repo = f"{owner}/{repo}"
    end_date_inclusive = end_date + timedelta(days=1)

    while True:
        params = {"sort": "newest", "page": page, "per_page": per_page}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            handle_api_error(response, github_repo)
            return events

        data = response.json()
        if not data:
            break

        for item in data:
            created_at = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )

            if created_at < start_date:
                return events

            if start_date <= created_at < end_date_inclusive:
                events.append(
                    {
                        "event_type": "fork",
                        "project_id": project_id,
                        "github_repo": github_repo,
                        "datetime": item["created_at"],
                        "user": item["owner"]["login"],
                    }
                )

        page += 1

    return events


def fetch_issues(
    owner: str,
    repo: str,
    project_id: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch issue_open and issue_close events from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    events = []
    page = 1
    per_page = 100
    github_repo = f"{owner}/{repo}"
    end_date_inclusive = end_date + timedelta(days=1)

    while True:
        params = {
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "page": page,
            "per_page": per_page,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            handle_api_error(response, github_repo)
            return events

        data = response.json()
        if not data:
            break

        for item in data:
            # Skip pull requests (issues API returns both issues and PRs)
            if "pull_request" in item:
                continue

            created_at = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )

            # Stop early if we've gone past our date range
            if created_at < start_date:
                return events

            # Issue opened event
            if start_date <= created_at < end_date_inclusive:
                events.append(
                    {
                        "event_type": "issue_open",
                        "project_id": project_id,
                        "github_repo": github_repo,
                        "datetime": item["created_at"],
                        "user": item["user"]["login"],
                    }
                )

            # Issue closed event
            if item["closed_at"]:
                closed_at = datetime.fromisoformat(
                    item["closed_at"].replace("Z", "+00:00")
                )
                if start_date <= closed_at < end_date_inclusive:
                    closed_by = item.get("closed_by", {})
                    events.append(
                        {
                            "event_type": "issue_close",
                            "project_id": project_id,
                            "github_repo": github_repo,
                            "datetime": item["closed_at"],
                            "user": closed_by.get("login", "unknown")
                            if closed_by
                            else "unknown",
                        }
                    )

        page += 1

    return events


def fetch_pulls(
    owner: str,
    repo: str,
    project_id: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch pr_open and pr_merge events from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    events = []
    page = 1
    per_page = 100
    github_repo = f"{owner}/{repo}"
    end_date_inclusive = end_date + timedelta(days=1)

    while True:
        params = {
            "state": "all",
            "sort": "created",
            "direction": "desc",
            "page": page,
            "per_page": per_page,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            handle_api_error(response, github_repo)
            return events

        data = response.json()
        if not data:
            break

        for item in data:
            created_at = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )

            # Stop early if we've gone past our date range
            if created_at < start_date:
                return events

            # PR opened event
            if start_date <= created_at < end_date_inclusive:
                events.append(
                    {
                        "event_type": "pr_open",
                        "project_id": project_id,
                        "github_repo": github_repo,
                        "datetime": item["created_at"],
                        "user": item["user"]["login"],
                    }
                )

            # PR merged event
            if item["merged_at"]:
                merged_at = datetime.fromisoformat(
                    item["merged_at"].replace("Z", "+00:00")
                )
                if start_date <= merged_at < end_date_inclusive:
                    merged_by = item.get("merged_by", {})
                    events.append(
                        {
                            "event_type": "pr_merge",
                            "project_id": project_id,
                            "github_repo": github_repo,
                            "datetime": item["merged_at"],
                            "user": merged_by.get("login", "unknown")
                            if merged_by
                            else "unknown",
                        }
                    )

        page += 1

    return events


def fetch_comments(
    owner: str,
    repo: str,
    project_id: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
) -> List[Dict]:
    """Fetch issue_comment and pr_comment events from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    events = []
    page = 1
    per_page = 100
    github_repo = f"{owner}/{repo}"
    end_date_inclusive = end_date + timedelta(days=1)

    while True:
        params = {
            "sort": "created",
            "direction": "desc",
            "page": page,
            "per_page": per_page,
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            handle_api_error(response, github_repo)
            return events

        data = response.json()
        if not data:
            break

        for item in data:
            created_at = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )

            # Stop early if we've gone past our date range
            if created_at < start_date:
                return events

            if start_date <= created_at < end_date_inclusive:
                # Determine if this is an issue comment or PR comment
                # The html_url contains /issues/ or /pull/ to distinguish
                html_url = item.get("html_url", "")
                event_type = "pr_comment" if "/pull/" in html_url else "issue_comment"

                events.append(
                    {
                        "event_type": event_type,
                        "project_id": project_id,
                        "github_repo": github_repo,
                        "datetime": item["created_at"],
                        "user": item["user"]["login"],
                    }
                )

        page += 1

    return events


def group_events_by_date(events: List[Dict]) -> Dict[str, List[Dict]]:
    """Group events by date (YYYY-MM-DD)."""
    grouped = {}

    for event in events:
        dt = datetime.fromisoformat(event["datetime"].replace("Z", "+00:00"))
        date_key = dt.strftime("%Y-%m-%d")

        if date_key not in grouped:
            grouped[date_key] = []

        grouped[date_key].append(event)

    return grouped


def write_jsonl(
    events: List[Dict],
    project_id: str,
    date: str,
    output_dir: str,
):
    """Write events to JSONL file or stdout."""
    if output_dir == "-":
        # Write to stdout
        for event in events:
            print(json.dumps(event))
    else:
        # Create subdirectory for project
        project_output_path = Path(output_dir) / project_id
        project_output_path.mkdir(parents=True, exist_ok=True)

        filename = project_output_path / f"{date}.jsonl"

        # Overwrite file to avoid duplicates on re-runs
        with open(filename, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        print(f"Wrote {len(events)} events to {filename}", file=sys.stderr)


def process_project(
    project_id: str,
    github_repo: str,
    token: Optional[str],
    start_date: datetime,
    end_date: datetime,
    output_dir: str,
    event_types: List[str],
):
    """Process a single project."""
    print(f"\nProcessing {project_id} ({github_repo})...", file=sys.stderr)

    # Parse owner/repo
    try:
        owner, repo = github_repo.split("/")
    except ValueError:
        print(f"Invalid GitHub repo format: {github_repo}", file=sys.stderr)
        return

    all_events = []

    # Fetch requested event types
    if "star" in event_types:
        print("  Fetching stars...", file=sys.stderr)
        all_events.extend(
            fetch_stars(owner, repo, project_id, token, start_date, end_date)
        )

    if "fork" in event_types:
        print("  Fetching forks...", file=sys.stderr)
        all_events.extend(
            fetch_forks(owner, repo, project_id, token, start_date, end_date)
        )

    if "issue_open" in event_types or "issue_close" in event_types:
        print("  Fetching issues...", file=sys.stderr)
        issue_events = fetch_issues(
            owner, repo, project_id, token, start_date, end_date
        )
        # Filter to only requested types
        filtered_events = [e for e in issue_events if e["event_type"] in event_types]
        all_events.extend(filtered_events)

    if "pr_open" in event_types or "pr_merge" in event_types:
        print("  Fetching pull requests...", file=sys.stderr)
        pr_events = fetch_pulls(owner, repo, project_id, token, start_date, end_date)
        # Filter to only requested types
        filtered_events = [e for e in pr_events if e["event_type"] in event_types]
        all_events.extend(filtered_events)

    if "issue_comment" in event_types or "pr_comment" in event_types:
        print("  Fetching comments...", file=sys.stderr)
        comment_events = fetch_comments(
            owner, repo, project_id, token, start_date, end_date
        )
        # Filter to only requested types
        filtered_events = [e for e in comment_events if e["event_type"] in event_types]
        all_events.extend(filtered_events)

    if not all_events:
        print(f"  No events found for {project_id} in date range", file=sys.stderr)
        return

    print(f"  Found {len(all_events)} total events", file=sys.stderr)

    # Group by date and write files
    grouped = group_events_by_date(all_events)

    for date, date_events in grouped.items():
        write_jsonl(date_events, project_id, date, output_dir)


def parse_github_repo(repo_str: str) -> str:
    """Parse GitHub repository from URL or owner/repo format."""
    if repo_str.startswith("http://") or repo_str.startswith("https://"):
        # Extract owner/repo from URL
        # Example: https://github.com/owner/repo -> owner/repo
        parts = repo_str.rstrip("/").split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        else:
            raise ValueError(f"Invalid GitHub URL: {repo_str}")
    else:
        # Assume it's already in owner/repo format
        if "/" not in repo_str:
            raise ValueError(
                f"Invalid repository format: {repo_str}. Use 'owner/repo' or full URL"
            )
        return repo_str


def main():
    parser = argparse.ArgumentParser(
        description="Download GitHub events for projects in config.toml"
    )
    parser.add_argument(
        "--project",
        help="Project ID from config.toml (if not specified, process all projects)",
    )
    parser.add_argument(
        "--repo",
        help="GitHub repository (owner/repo or full URL). Use this for arbitrary repos not in config.toml",
    )
    parser.add_argument(
        "--event-type",
        help=f"Comma-separated event types to fetch (default: all). Options: {', '.join(EVENT_TYPES)}",
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
        default="data/output/github",
        help='Output directory (default: data/output/github), use "-" for stdout',
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )

    args = parser.parse_args()

    # Parse event types
    if args.event_type:
        event_types = [et.strip() for et in args.event_type.split(",")]
        # Validate event types
        invalid_types = [et for et in event_types if et not in EVENT_TYPES]
        if invalid_types:
            print(
                f"Error: Invalid event types: {', '.join(invalid_types)}",
                file=sys.stderr,
            )
            print(f"Valid types: {', '.join(EVENT_TYPES)}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default to all event types
        event_types = EVENT_TYPES

    print(f"Fetching event types: {', '.join(event_types)}", file=sys.stderr)

    # Determine and show token source
    if args.token:
        # Check if --token was explicitly provided in command line
        if "--token" in sys.argv:
            print("Using GITHUB_TOKEN from --token argument", file=sys.stderr)
        # Check if it was set in environment before loading .env
        elif token_in_env_before_dotenv:
            print("Using GITHUB_TOKEN from environment variable", file=sys.stderr)
        # Otherwise it must be from .env file
        else:
            print("Using GITHUB_TOKEN from .env file", file=sys.stderr)
    else:
        print(
            "No GITHUB_TOKEN provided (rate limited to 60 requests/hour)",
            file=sys.stderr,
        )

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

    # Check for mutually exclusive arguments
    if args.project and args.repo:
        print("Error: --project and --repo are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    # Handle --repo (arbitrary repository)
    if args.repo:
        try:
            github_repo = parse_github_repo(args.repo)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Use repo name as project_id for output directory
        project_id = github_repo.replace("/", "-")

        # Determine start_date for this repo
        if not user_provided_start_date:
            # Auto-detect start date
            last_date = get_last_date_for_project(args.output, project_id)
            if last_date:
                start_date = parse_date(last_date) + timedelta(days=1)
                print(
                    f"Auto-detected start date for {project_id}: {start_date.strftime('%Y-%m-%d')}",
                    file=sys.stderr,
                )
            else:
                start_date = parse_date("2000-01-01")
                print(
                    f"No existing data for {project_id}, starting from 2000-01-01",
                    file=sys.stderr,
                )

            # Validate dates
            if end_date < start_date:
                print("Error: end-date is before auto-detected start-date", file=sys.stderr)
                sys.exit(1)

        process_project(
            project_id,
            github_repo,
            args.token,
            start_date,
            end_date,
            args.output,
            event_types,
        )
    else:
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
                print(
                    f"Available projects: {', '.join(projects.keys())}", file=sys.stderr
                )
                sys.exit(1)

            projects_to_process = {args.project: projects[args.project]}
        else:
            projects_to_process = projects

        # Process each project
        for project_id, project_data in projects_to_process.items():
            github_repo = project_data.get("github")

            if not github_repo:
                print(
                    f"Warning: No github repo for {project_id}, skipping",
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
                github_repo,
                args.token,
                project_start_date,
                end_date,
                args.output,
                event_types,
            )

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
