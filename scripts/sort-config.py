#!/usr/bin/env python3
"""
Sort config.toml file alphabetically.

Sorts projects by key and keys within each project alphabetically.
Keeps [gsheet] section at the top.
"""

import sys
import tomllib
from collections import OrderedDict
from pathlib import Path


def sort_config_toml(config_path: Path, check_only: bool = False) -> bool:
    """
    Sort config.toml file alphabetically.

    Args:
        config_path: Path to config.toml file
        check_only: If True, only check if file is sorted (don't modify)

    Returns:
        True if file is sorted (or was sorted successfully), False otherwise
    """
    # Read the file
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # Create new ordered dict
    sorted_config = OrderedDict()

    # Keep gsheet at the top if it exists
    if "gsheet" in config:
        sorted_config["gsheet"] = config["gsheet"]

    # Sort projects
    if "projects" in config:
        sorted_projects = OrderedDict()
        for project_key in sorted(config["projects"].keys()):
            # Sort keys within each project
            sorted_project = OrderedDict(sorted(config["projects"][project_key].items()))
            sorted_projects[project_key] = sorted_project
        sorted_config["projects"] = sorted_projects

    # Generate sorted TOML content
    sorted_content = []

    # Write gsheet section
    if "gsheet" in sorted_config:
        sorted_content.append("[gsheet]")
        for key, value in sorted_config["gsheet"].items():
            sorted_content.append(f'{key} = "{value}"')
        sorted_content.append("")

    # Write projects
    if "projects" in sorted_config:
        for project_name, project_data in sorted_config["projects"].items():
            sorted_content.append(f"[projects.{project_name}]")
            for key, value in project_data.items():
                if isinstance(value, str):
                    sorted_content.append(f'{key} = "{value}"')
                else:
                    sorted_content.append(f"{key} = {value}")
            sorted_content.append("")

    # Add final newline to match standard format
    sorted_text = "\n".join(sorted_content) + "\n"

    # Read current file content
    with open(config_path, "r") as f:
        current_text = f.read()

    # Check if already sorted
    if current_text == sorted_text:
        return True

    if check_only:
        return False

    # Write sorted content
    with open(config_path, "w") as f:
        f.write(sorted_text)

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sort config.toml alphabetically",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sort config.toml in place
  %(prog)s

  # Check if config.toml is sorted (exit 1 if not)
  %(prog)s --check

  # Sort a specific file
  %(prog)s path/to/config.toml
        """,
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default="config.toml",
        help="Path to config.toml (default: config.toml)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if file is sorted without modifying it",
    )

    args = parser.parse_args()

    config_path = Path(args.config_path)

    if not config_path.exists():
        print(f"Error: {config_path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        is_sorted = sort_config_toml(config_path, check_only=args.check)

        if args.check:
            if is_sorted:
                print(f"✓ {config_path} is sorted")
                sys.exit(0)
            else:
                print(f"✗ {config_path} is not sorted", file=sys.stderr)
                print(f"  Run 'python scripts/sort-config.py' to sort it", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"✓ {config_path} sorted successfully")
            sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
