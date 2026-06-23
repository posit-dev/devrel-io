# List available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Fetch all metrics
fetch:
    velocirepo fetch

# Fetch GitHub events
fetch-github:
    velocirepo fetch-github

# Fetch PyPI downloads
fetch-pypi:
    velocirepo fetch-pypi

# Fetch CRAN downloads
fetch-cran:
    velocirepo fetch-cran

# Fetch Plausible analytics
fetch-plausible:
    velocirepo fetch-plausible

# Fetch Open VSX metrics
fetch-openvsx:
    velocirepo fetch-openvsx

# Query metrics with SQL
query *ARGS:
    velocirepo query {{ARGS}}

# Validate project configuration
validate:
    velocirepo validate-projects

# Run the Shiny dashboard with auto-reload
app:
    -lsof -ti:8765 | xargs kill -9 2>/dev/null || true
    uv run shiny run scripts/app.py --port 8765 --reload --launch-browser
