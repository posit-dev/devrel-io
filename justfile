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
    uv run scripts/fetch-inputs.py -o data/input/inputs.csv

# Sort config.toml alphabetically
sort-config:
    uv run python scripts/sort-config.py

# Check if config.toml is sorted (exits with error if not)
check-config:
    uv run python scripts/sort-config.py --check

# Run the Shiny dashboard with auto-reload
app:
    -lsof -ti:8765 | xargs kill -9 2>/dev/null || true
    uv run shiny run scripts/app.py --port 8765 --reload --launch-browser

# Fetch GitHub events for all projects
fetch-github *ARGS:
    uv run python scripts/fetch-github.py {{ARGS}}

# Fetch PyPI downloads for all projects
fetch-pypi *ARGS:
    uv run python scripts/fetch-pypi.py {{ARGS}}

# Fetch CRAN downloads for all projects
fetch-cran *ARGS:
    uv run python scripts/fetch-cran.py {{ARGS}}

# Fetch Plausible analytics for all projects
fetch-plausible *ARGS:
    uv run python scripts/fetch-plausible.py {{ARGS}}

# Fetch Open VSX metrics for all projects
fetch-openvsx *ARGS:
    uv run python scripts/fetch-openvsx.py {{ARGS}}

# Aggregate daily data into monthly/yearly files
aggregate-data:
    ./scripts/aggregate-data.sh

# Consolidate all data sources into single Parquet file
output-to-parquet:
    uv run python scripts/output-to-parquet.py

# Fetch all data sources and aggregate
fetch:
    just fetch-github
    just fetch-pypi
    just fetch-cran
    just fetch-plausible
    just fetch-openvsx
    just aggregate-data
    just output-to-parquet

# Export dependencies to requirements.txt for Posit Connect
export-deps:
    uv export --no-hashes --no-dev > requirements.txt
