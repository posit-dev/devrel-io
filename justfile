# List available commands
default:
    @just --list

# Download Google Sheets data from config.toml to data/input
get-inputs:
    uv run gsheet.py -o data/input/inputs.csv

# Download specific sheet by name
get-sheet sheet_name output="":
    #!/usr/bin/env bash
    if [ -n "{{output}}" ]; then
        uv run gsheet.py -s "{{sheet_name}}" -o "{{output}}"
    else
        uv run gsheet.py -s "{{sheet_name}}" -o "data/input/{{sheet_name}}.csv"
    fi

# Install dependencies
install:
    uv sync

# Clean downloaded CSV files from data/input
clean:
    rm -f data/input/*.csv
    @echo "Cleaned data/input directory"

# Run with a custom URL
get-url url output="data/input/output.csv":
    uv run gsheet.py "{{url}}" -o "{{output}}"
