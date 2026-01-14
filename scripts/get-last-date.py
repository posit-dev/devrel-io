#!/usr/bin/env python3
"""
CLI tool to find the most recent date with data for a given project.

Uses the get_last_date_for_project function from utils.py to determine
when data was last fetched for a project, which is useful for determining
the starting point for incremental data fetching.
"""

import argparse
import sys

from utils import get_last_date_for_project


def main():
    parser = argparse.ArgumentParser(
        description="Find the most recent date with data for a given project"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Base output directory (e.g., data/output/github)",
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Project identifier (e.g., great-tables, positron)",
    )

    args = parser.parse_args()

    # Find the last date
    last_date = get_last_date_for_project(args.output_dir, args.project_id)

    if last_date:
        print(last_date)
        sys.exit(0)
    else:
        print(
            f"No data found for project '{args.project_id}' in '{args.output_dir}'",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
