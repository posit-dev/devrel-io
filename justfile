# List available commands
default:
    @just --list

# Download Google Sheets data from config.toml to data/output
get-inputs:
    uv run gsheet.py -o data/output/inputs.csv

# Download specific sheet by name
get-sheet sheet_name output="":
    #!/usr/bin/env bash
    if [ -n "{{output}}" ]; then
        uv run gsheet.py -s "{{sheet_name}}" -o "{{output}}"
    else
        uv run gsheet.py -s "{{sheet_name}}" -o "data/output/{{sheet_name}}.csv"
    fi

# Install dependencies
install:
    uv sync

# Clean downloaded CSV files from data/output
clean:
    rm -f data/output/*.csv
    @echo "Cleaned data/output directory"

# Run with a custom URL
get-url url output="data/output/output.csv":
    uv run gsheet.py "{{url}}" -o "{{output}}"
