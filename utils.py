"""
Utility functions shared across fetch scripts.
"""

import calendar
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_last_date_for_project(output_dir: str, project_id: str) -> Optional[str]:
    """
    Find the most recent date with data for a given project.

    Handles multiple file naming patterns:
    - Daily: YYYY-MM-DD.jsonl (e.g., 2026-01-08.jsonl)
    - Monthly: YYYY-MM.jsonl (e.g., 2025-12.jsonl)
    - Yearly: YYYY.jsonl (e.g., 2025.jsonl)

    Args:
        output_dir: Base output directory (e.g., "data/output/github")
        project_id: Project identifier

    Returns:
        Most recent date as YYYY-MM-DD string, or None if no data exists
    """
    project_path = Path(output_dir) / project_id

    if not project_path.exists():
        return None

    # Patterns for different file naming conventions
    daily_pattern = re.compile(r'(\d{4}-\d{2}-\d{2})\.jsonl$')
    monthly_pattern = re.compile(r'(\d{4}-\d{2})\.jsonl$')
    yearly_pattern = re.compile(r'(\d{4})\.jsonl$')

    dates = []

    for jsonl_file in project_path.glob("*.jsonl"):
        filename = jsonl_file.name

        # Try daily pattern (YYYY-MM-DD)
        match = daily_pattern.search(filename)
        if match:
            dates.append(match.group(1))
            continue

        # Try monthly pattern (YYYY-MM) - convert to last day of month
        match = monthly_pattern.search(filename)
        if match:
            year_month = match.group(1)
            year, month = map(int, year_month.split('-'))
            # Get last day of the month
            last_day = calendar.monthrange(year, month)[1]
            dates.append(f"{year:04d}-{month:02d}-{last_day:02d}")
            continue

        # Try yearly pattern (YYYY) - convert to last day of year
        match = yearly_pattern.search(filename)
        if match:
            year = match.group(1)
            dates.append(f"{year}-12-31")
            continue

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
