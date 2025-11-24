# List available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Download Google Sheets data from config.toml to data/input
get-inputs:
    uv run gsheet.py -o data/input/inputs.csv

# Run the Shiny dashboard with auto-reload
app:
    uv run shiny run app.py --port 8765 --reload
