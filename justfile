# List available commands
default:
    @just --list

# Download Google Sheets data from config.toml
get-inputs:
    uv run gsheet.py

# Download specific sheet by name
get-sheet sheet_name output="":
    #!/usr/bin/env bash
    if [ -n "{{output}}" ]; then
        uv run gsheet.py -s "{{sheet_name}}" -o "{{output}}"
    else
        uv run gsheet.py -s "{{sheet_name}}"
    fi

# Install dependencies
install:
    uv sync

# Clean downloaded CSV files
clean:
    rm -f *.csv
    @echo "Cleaned all CSV files"

# Run with a custom URL
get-url url:
    uv run gsheet.py "{{url}}"
