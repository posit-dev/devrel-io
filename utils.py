"""
Utility functions shared across fetch scripts.
"""

import re
from pathlib import Path
from typing import Optional


def get_last_date_for_project(output_dir: str, project_id: str) -> Optional[str]:
    """
    Find the most recent date with data for a given project.

    Args:
        output_dir: Base output directory (e.g., "data/output/github")
        project_id: Project identifier

    Returns:
        Most recent date as YYYY-MM-DD string, or None if no data exists
    """
    project_path = Path(output_dir) / project_id

    if not project_path.exists():
        return None

    # Find all .jsonl files in project directory (excluding archive subdirectories)
    date_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})\.jsonl$')
    dates = []

    for jsonl_file in project_path.glob("*.jsonl"):
        match = date_pattern.search(jsonl_file.name)
        if match:
            dates.append(match.group(1))

    if not dates:
        return None

    # Return the most recent date
    return max(dates)


def get_last_date_for_analytics(
    output_dir: str, prefix: str = "supported-by-posit_ga"
) -> Optional[str]:
    """
    Find the most recent date with analytics data.

    This is used for flat directory structures (like Google Analytics)
    where files are named with a prefix and date.

    Args:
        output_dir: Output directory (e.g., "data/output/google_analytics")
        prefix: Filename prefix (default: "supported-by-posit_ga")

    Returns:
        Most recent date as YYYY-MM-DD string, or None if no data exists
    """
    output_path = Path(output_dir)

    if not output_path.exists():
        return None

    # Find all .jsonl files matching the pattern prefix_YYYY-MM-DD.jsonl
    date_pattern = re.compile(rf'{re.escape(prefix)}_(\d{{4}}-\d{{2}}-\d{{2}})\.jsonl$')
    dates = []

    for jsonl_file in output_path.glob("*.jsonl"):
        match = date_pattern.search(jsonl_file.name)
        if match:
            dates.append(match.group(1))

    if not dates:
        return None

    # Return the most recent date
    return max(dates)
