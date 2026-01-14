#!/usr/bin/env python3
"""
Install Plausible site for a project and generate HTML tracking snippet.

Checks if a Plausible site exists for a project, creates it if not,
and prints the HTML snippet to install on the website.
"""

import argparse
import os
import sys
import tomllib
from typing import Dict, Optional

import requests
from dotenv import load_dotenv


def load_config(config_path: str = "config.toml") -> Dict:
    """Load configuration from TOML file."""
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_plausible_site(domain: str, api_key: str) -> Optional[Dict]:
    """
    Check if a Plausible site exists.

    Returns:
        Site data dict if exists, None if doesn't exist
    """
    url = f"https://plausible.io/api/v1/sites/{domain}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error checking site: {e}", file=sys.stderr)
        sys.exit(1)


def generate_html_snippet(tracker_id: str) -> str:
    """Generate the HTML tracking snippet."""
    return (
        f'<script async src="https://plausible.io/js/{tracker_id}.js"></script>'
        "<script>window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)},"
        "plausible.init=plausible.init||function(i){plausible.o=i||{}}; plausible.init()</script>"
    )


def process_project(project_id: str, domain: str, api_key: str, timezone: str) -> str:
    """
    Process a single project: check/create site and return HTML snippet.

    Returns:
        HTML snippet for the project
    """

    # Check if site exists
    site_data = get_plausible_site(domain, api_key)

    if site_data:
        tracker_id = site_data["tracker_script_configuration"]["id"]
        # Generate HTML snippet
        html_snippet = generate_html_snippet(tracker_id)
        return html_snippet
    else:
        print(f"Site doesn't exist: {domain}", file=sys.stderr)
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Install Plausible site for a project and generate HTML tracking snippet"
    )
    parser.add_argument(
        "--project",
        help="Project ID from config.toml (if not specified, process all projects with 'plausible' field)",
    )
    parser.add_argument(
        "--api-key",
        help="Plausible API key (default: from PLAUSIBLE_KEY environment variable)",
    )
    parser.add_argument(
        "--timezone",
        default="America/New_York",
        help="Timezone for new site (default: America/New_York)",
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = args.api_key or os.environ.get("PLAUSIBLE_KEY")
    if not api_key:
        print("Error: No PLAUSIBLE_KEY provided", file=sys.stderr)
        print(
            "Set PLAUSIBLE_KEY environment variable or use --api-key", file=sys.stderr
        )
        sys.exit(1)

    # Load config
    try:
        config = load_config()
    except FileNotFoundError:
        print("Error: config.toml not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading config.toml: {e}", file=sys.stderr)
        sys.exit(1)

    # Get all projects
    projects = config.get("projects", {})

    # Filter projects based on --project argument
    if args.project:
        # Single project mode
        if args.project not in projects:
            print(
                f"Error: Project '{args.project}' not found in config.toml",
                file=sys.stderr,
            )
            sys.exit(1)

        projects_to_process = {args.project: projects[args.project]}
    else:
        # All projects mode - only process projects with 'plausible' field
        projects_to_process = {
            project_id: project_data
            for project_id, project_data in projects.items()
            if project_data.get("plausible")
        }

        if not projects_to_process:
            print(
                "No projects with 'plausible' field found in config.toml",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"Processing {len(projects_to_process)} projects with Plausible configuration",
            file=sys.stderr,
        )

    # Process each project
    snippets = []
    for project_id, project_data in projects_to_process.items():
        domain = project_data.get("plausible")
        if not domain:
            print(
                f"Warning: Skipping {project_id} - no 'plausible' field",
                file=sys.stderr,
            )
            continue

        try:
            snippet = process_project(project_id, domain, api_key, args.timezone)
            snippets.append((project_id, domain, snippet))
        except Exception as e:
            print(f"Error processing {project_id}: {e}", file=sys.stderr)
            continue

    for project_id, domain, snippet in snippets:
        if snippet:
            print(f"# {project_id} ({domain})")
            print(snippet)
            print()


if __name__ == "__main__":
    main()
