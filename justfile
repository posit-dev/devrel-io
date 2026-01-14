# List available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Install pre-commit hooks (optional, for auto-sorting config.toml)
install-hooks:
    @echo "Installing pre-commit hooks..."
    @command -v pre-commit >/dev/null 2>&1 || { \
        echo "pre-commit not found. Installing..."; \
        if command -v brew >/dev/null 2>&1; then \
            brew install pre-commit; \
        else \
            pip install pre-commit; \
        fi; \
    }
    @pre-commit install
    @echo "✓ Pre-commit hooks installed!"
    @echo "  config.toml will be automatically sorted on git commit"

# Download Google Sheets data from config.toml to data/input
get-inputs:
    uv run fetch_inputs.py -o data/input/inputs.csv

# Sort config.toml alphabetically
sort-config:
    uv run python scripts/sort-config.py

# Check if config.toml is sorted (exits with error if not)
check-config:
    uv run python scripts/sort-config.py --check

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
    uv run python fetch_openvsx.py
    ./aggregate-data.sh
    uv run python output_to_parquet.py

# Export dependencies to requirements.txt for Posit Connect
export-deps:
    uv export --no-hashes --no-dev > requirements.txt
