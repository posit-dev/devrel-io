# List available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Download Google Sheets data from config.toml to data/input
get-inputs:
    uv run fetch_inputs.py -o data/input/inputs.csv

# Run the Shiny dashboard with auto-reload
app:
    -lsof -ti:8765 | xargs kill -9 2>/dev/null || true
    uv run shiny run app.py --port 8765 --reload --launch-browser

# Fetch all data sources and aggregate
fetch:
    uv run python fetch_github.py
    uv run python fetch_pypi.py
    uv run python fetch_cran.py
    uv run python fetch_plausible.py
    uv run python fetch_analytics.py
    ./aggregate-data.sh
    uv run python output_to_parquet.py

# Export dependencies to requirements.txt for Posit Connect
export-deps:
    uv export --no-hashes --no-dev > requirements.txt
