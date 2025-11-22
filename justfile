# List available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Download Google Sheets data from config.toml to data/input
get-inputs:
    uv run gsheet.py -o data/input/inputs.csv
