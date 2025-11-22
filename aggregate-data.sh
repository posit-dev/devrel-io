#!/usr/bin/env bash
#
# Aggregate daily JSONL files into monthly/yearly files across all data directories
#
# Usage:
#   ./aggregate-data.sh [--dry-run] [--force] [--keep-days N]

set -euo pipefail

# Parse command line arguments
DRY_RUN=""
FORCE=""
KEEP_DAYS="90"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --force)
            FORCE="--force"
            shift
            ;;
        --keep-days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--dry-run] [--force] [--keep-days N]" >&2
            exit 1
            ;;
    esac
done

# Find all directories under data/ that contain .jsonl files
# Use find to get all directories, then check if they contain .jsonl files
find data -type d | while IFS= read -r dir; do
    # Skip the archive directories
    if [[ "$dir" == *"/archive" ]] || [[ "$dir" == *"/archive/"* ]]; then
        continue
    fi

    # Check if this directory contains any .jsonl files
    jsonl_files=("$dir"/*.jsonl)

    # Check if glob matched any files (handle case where glob doesn't match)
    if [[ -e "${jsonl_files[0]}" ]]; then
        echo "=================================================="
        echo "Processing: $dir"
        echo "=================================================="

        # Run concat-dates.py with all arguments
        uv run python concat-dates.py $DRY_RUN $FORCE --keep-days "$KEEP_DAYS" "$dir"/*.jsonl

        echo ""
    fi
done

echo "=================================================="
echo "Aggregation complete!"
echo "=================================================="
