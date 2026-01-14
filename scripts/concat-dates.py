#!/usr/bin/env python3
"""
Concatenate daily JSONL files into monthly files, and monthly files into yearly files.

Only processes complete months (when current date is past the last day of the month)
and complete years (when current date is past December 31 of the year).
"""

import argparse
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict
from calendar import monthrange


def parse_filename(filename):
    """
    Parse filename to extract prefix, date components, and suffix.

    Returns:
        tuple: (prefix, year, month, day, suffix, date_type)
        date_type is 'daily', 'monthly', 'yearly', or None
    """
    # Pattern: optional prefix_YYYY-MM-DD.suffix or YYYY-MM-DD.suffix
    # Also handles: prefix_YYYY-MM.suffix or YYYY-MM.suffix
    # Also handles: prefix_YYYY.suffix or YYYY.suffix
    pattern = r"^(?:(.+?)_)?(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(\..+)$"
    match = re.match(pattern, filename)

    if not match:
        return None

    prefix, year, month, day, suffix = match.groups()
    # Use empty string as prefix if none provided
    prefix = prefix if prefix else ""
    year = int(year)
    month = int(month) if month else None
    day = int(day) if day else None

    if day is not None:
        date_type = "daily"
    elif month is not None:
        date_type = "monthly"
    else:
        date_type = "yearly"

    return (prefix, year, month, day, suffix, date_type)


def is_month_complete(year, month, today=None):
    """Check if a given year-month is complete (all days have passed)."""
    if today is None:
        today = date.today()

    # Get the last day of the month
    last_day = monthrange(year, month)[1]
    last_date_of_month = date(year, month, last_day)

    return today > last_date_of_month


def is_year_complete(year, today=None):
    """Check if a given year is complete (passed December 31)."""
    if today is None:
        today = date.today()

    last_date_of_year = date(year, 12, 31)

    return today > last_date_of_year


def group_files_by_period(file_paths):
    """
    Group files by their prefix, date type, and time period.

    Returns:
        dict: Structure organizing files for aggregation
    """
    # Structure: {prefix: {suffix: {'daily': {(year, month): [files]}, 'monthly': {year: [files]}}}}
    groups = defaultdict(
        lambda: defaultdict(
            lambda: {"daily": defaultdict(list), "monthly": defaultdict(list)}
        )
    )

    for file_path in file_paths:
        parsed = parse_filename(file_path.name)
        if not parsed:
            print(
                f"Skipping file with unrecognized format: {file_path}", file=sys.stderr
            )
            continue

        prefix, year, month, day, suffix, date_type = parsed

        if date_type == "daily":
            groups[prefix][suffix]["daily"][(year, month)].append(file_path)
        elif date_type == "monthly":
            groups[prefix][suffix]["monthly"][year].append(file_path)
        elif date_type == "yearly":
            # Yearly files are final, don't aggregate further
            pass

    return groups


def sort_files_chronologically(files):
    """Sort files by their date components."""

    def get_sort_key(file_path):
        parsed = parse_filename(file_path.name)
        if not parsed:
            return (9999, 99, 99)  # Put unparseable files at the end
        _, year, month, day, _, _ = parsed
        return (year, month or 0, day or 0)

    return sorted(files, key=get_sort_key)


def get_sort_key_from_line(line):
    """Extract date/datetime from JSONL line for sorting."""
    try:
        import json
        obj = json.loads(line)
        # Try different date fields (datetime for events, date for metrics)
        if "datetime" in obj:
            return obj["datetime"]
        elif "date" in obj:
            return obj["date"]
        elif "day" in obj:
            return obj["day"]
        else:
            return ""  # Lines without dates go to the beginning
    except:
        return ""  # Unparseable lines go to the beginning


def get_unique_key(obj):
    """Extract unique key from a JSONL record for deduplication.

    For metrics: (project_id, metric, date)
    For events: (project_id, event_type, datetime, user)
    """
    # Try event format first (has datetime and user)
    if "datetime" in obj and "user" in obj:
        return (
            obj.get("project_id", ""),
            obj.get("event_type", ""),
            obj.get("datetime", ""),
            obj.get("user", "")
        )
    # Try metrics format (has date and value)
    elif "date" in obj and "metric" in obj:
        return (
            obj.get("project_id", ""),
            obj.get("metric", ""),
            obj.get("date", "")
        )
    # Fallback: use the entire line as the key
    else:
        return json.dumps(obj, sort_keys=True)


def concatenate_files(files, output_path, dry_run=False):
    """Concatenate JSONL files into output file, merging with existing data and deduplicating."""
    if dry_run:
        print(f"  Would create/update: {output_path}")
        if output_path.exists():
            print(f"    (merging with existing file)")
        for f in files:
            print(f"    - Concat: {f}")
        return True

    try:
        import json

        # Use a dictionary keyed by unique identifier for deduplication
        # This keeps the latest value for each unique record
        records = {}

        # If output file already exists, read its contents first
        if output_path.exists():
            with open(output_path, "r") as existing_file:
                for line in existing_file:
                    line = line.strip()
                    if line:  # Skip empty lines
                        try:
                            obj = json.loads(line)
                            key = get_unique_key(obj)
                            records[key] = line
                        except json.JSONDecodeError:
                            # If line can't be parsed, keep it as-is
                            records[line] = line

        # Read all input files (these will overwrite existing records with same key)
        for file_path in files:
            with open(file_path, "r") as infile:
                for line in infile:
                    line = line.strip()
                    if line:  # Skip empty lines
                        try:
                            obj = json.loads(line)
                            key = get_unique_key(obj)
                            records[key] = line
                        except json.JSONDecodeError:
                            # If line can't be parsed, keep it as-is
                            records[line] = line

        # Sort lines by date/datetime for consistency
        sorted_lines = sorted(records.values(), key=get_sort_key_from_line)

        # Write deduplicated and sorted data
        with open(output_path, "w") as outfile:
            for line in sorted_lines:
                outfile.write(line + "\n")

        return True
    except Exception as e:
        print(f"Error concatenating files into {output_path}: {e}", file=sys.stderr)
        return False


def move_to_archive(files, dry_run=False):
    """Move source files to archive directory after successful concatenation."""
    if not files:
        return

    # Create archive directory in the same location as the first file
    archive_dir = files[0].parent / "archive"

    if dry_run:
        for f in files:
            print(f"    - Archive: {f} → {archive_dir / f.name}")
        return

    # Create archive directory if it doesn't exist
    archive_dir.mkdir(exist_ok=True)

    for file_path in files:
        try:
            dest_path = archive_dir / file_path.name
            # If file exists in archive, overwrite it
            if dest_path.exists():
                dest_path.unlink()
            file_path.rename(dest_path)
        except Exception as e:
            print(f"Warning: Could not archive {file_path}: {e}", file=sys.stderr)


def cleanup_old_archives(archive_dir, keep_days, dry_run=False, today=None):
    """Delete archived files older than keep_days."""
    if not archive_dir.exists():
        return 0

    if today is None:
        today = date.today()

    cutoff_date = today - timedelta(days=keep_days)
    deleted_count = 0

    for file_path in archive_dir.glob("*.jsonl"):
        parsed = parse_filename(file_path.name)
        if not parsed:
            continue

        _, year, month, day, _, date_type = parsed

        # Determine the file's date
        if date_type == "daily" and day:
            file_date = date(year, month, day)
        elif date_type == "monthly" and month:
            # Use last day of month as the file date
            last_day = monthrange(year, month)[1]
            file_date = date(year, month, last_day)
        else:
            # Yearly files - use Dec 31 as the file date
            file_date = date(year, 12, 31)

        if file_date < cutoff_date:
            if dry_run:
                print(f"  Would delete from archive: {file_path}")
            else:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(
                        f"Warning: Could not delete {file_path}: {e}", file=sys.stderr
                    )

    return deleted_count


def process_daily_to_monthly(groups, dry_run=False, force=False, today=None):
    """Process daily files and create monthly files for complete months."""
    actions = []

    for prefix, suffix_groups in groups.items():
        for suffix, type_groups in suffix_groups.items():
            daily_groups = type_groups["daily"]

            for (year, month), files in daily_groups.items():
                if not is_month_complete(year, month, today):
                    continue

                # Sort files chronologically
                sorted_files = sort_files_chronologically(files)

                # Create output filename
                output_name = (
                    f"{prefix}_{year:04d}-{month:02d}{suffix}"
                    if prefix
                    else f"{year:04d}-{month:02d}{suffix}"
                )
                output_path = sorted_files[0].parent / output_name

                # Note: No need to check if output exists - concatenate_files now merges

                actions.append(
                    {
                        "type": "daily_to_monthly",
                        "files": sorted_files,
                        "output": output_path,
                        "period": f"{year}-{month:02d}",
                    }
                )

    return actions


def process_monthly_to_yearly(groups, dry_run=False, force=False, today=None):
    """Process monthly files and create yearly files for complete years."""
    actions = []

    for prefix, suffix_groups in groups.items():
        for suffix, type_groups in suffix_groups.items():
            monthly_groups = type_groups["monthly"]

            for year, files in monthly_groups.items():
                if not is_year_complete(year, today):
                    continue

                # Check if we have all 12 months (optional, but good practice)
                # We'll proceed with whatever months we have

                # Sort files chronologically
                sorted_files = sort_files_chronologically(files)

                # Create output filename
                output_name = (
                    f"{prefix}_{year:04d}{suffix}" if prefix else f"{year:04d}{suffix}"
                )
                output_path = sorted_files[0].parent / output_name

                # Note: No need to check if output exists - concatenate_files now merges

                actions.append(
                    {
                        "type": "monthly_to_yearly",
                        "files": sorted_files,
                        "output": output_path,
                        "period": f"{year}",
                    }
                )

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Concatenate daily files into monthly, and monthly files into yearly aggregates."
    )
    parser.add_argument(
        "files", nargs="+", type=Path, help="List of JSONL files to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing output files"
    )
    parser.add_argument(
        "--today",
        type=str,
        help="Override current date for testing (format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--keep-days",
        type=int,
        default=90,
        help="Keep archived files for this many days before deleting (default: 90)",
    )

    args = parser.parse_args()

    # Convert to absolute paths and filter existing files
    file_paths = []
    for f in args.files:
        if not f.exists():
            print(f"Warning: File does not exist: {f}", file=sys.stderr)
            continue
        if not f.is_file():
            print(f"Warning: Not a file: {f}", file=sys.stderr)
            continue
        file_paths.append(f)

    if not file_paths:
        print("Error: No valid files to process", file=sys.stderr)
        sys.exit(1)

    # Parse --today argument or use current date
    if args.today:
        try:
            today = datetime.strptime(args.today, "%Y-%m-%d").date()
            print(f"Using override date: {today}")
        except ValueError:
            print(
                f"Error: Invalid date format for --today: {args.today}", file=sys.stderr
            )
            print("Expected format: YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        today = date.today()

    # Group files by prefix, suffix, and time period
    groups = group_files_by_period(file_paths)

    # Process daily -> monthly
    daily_actions = process_daily_to_monthly(groups, args.dry_run, args.force, today)

    # Display summary
    if args.dry_run:
        print("DRY RUN - No changes will be made\n")

    # Execute daily to monthly and collect newly created monthly files
    new_monthly_files = []
    if daily_actions:
        print(f"Daily → Monthly aggregations ({len(daily_actions)}):")
        for action in daily_actions:
            print(f"\nPeriod: {action['period']}")
            success = concatenate_files(action["files"], action["output"], args.dry_run)
            if success:
                move_to_archive(action["files"], args.dry_run)
                # Track the newly created monthly file
                new_monthly_files.append(action["output"])

    # Add newly created monthly files to the groups for yearly processing
    if new_monthly_files:
        for monthly_file in new_monthly_files:
            parsed = parse_filename(monthly_file.name)
            if parsed:
                prefix, year, month, day, suffix, date_type = parsed
                if date_type == "monthly":
                    groups[prefix][suffix]["monthly"][year].append(monthly_file)

    # Process monthly -> yearly (including newly created monthly files)
    monthly_actions = process_monthly_to_yearly(groups, args.dry_run, args.force, today)

    # Execute monthly to yearly
    if monthly_actions:
        if daily_actions:
            print()  # Add spacing if we had daily actions
        print(f"Monthly → Yearly aggregations ({len(monthly_actions)}):")
        for action in monthly_actions:
            print(f"\nPeriod: {action['period']}")
            success = concatenate_files(action["files"], action["output"], args.dry_run)
            if success:
                move_to_archive(action["files"], args.dry_run)

    if not daily_actions and not monthly_actions:
        print("No complete periods found to aggregate.")
        return

    # Clean up old archived files
    if file_paths:
        archive_dir = file_paths[0].parent / "archive"
        if archive_dir.exists() or args.dry_run:
            if args.dry_run:
                print("\nArchive cleanup:")
            else:
                print("\nCleaning up old archived files...")

            deleted = cleanup_old_archives(
                archive_dir, args.keep_days, args.dry_run, today
            )
            if not args.dry_run and deleted > 0:
                print(
                    f"Deleted {deleted} archived files older than {args.keep_days} days"
                )

    if args.dry_run:
        print("\nDRY RUN complete - no files were modified")
    else:
        print("\nAggregation complete")


if __name__ == "__main__":
    main()
