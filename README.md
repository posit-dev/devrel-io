# DevRel I/O

**Automated collection and aggregation of developer relations metrics from multiple sources**

Track project adoption, engagement, and growth across GitHub, PyPI, CRAN, and web analytics. Designed for developer relations teams monitoring open source projects.

## Key Features

- **Multi-source data collection**: GitHub events, PyPI downloads, CRAN downloads, Plausible analytics, Google Analytics, Google Sheets
- **Automated daily updates**: GitHub Actions workflow fetches yesterday's data every night
- **Smart aggregation**: Daily files automatically merge into monthly and yearly aggregates with deduplication
- **Interactive dashboard**: Shiny app for visualizing metrics and trends
- **JSONL format**: One JSON object per line for easy processing, streaming, and analysis
- **Incremental updates**: Fetch only new data, merge with existing files

---

## Table of Contents

- [Prerequisites & Quick Start](#prerequisites--quick-start)
- [Understanding the Data Structure](#understanding-the-data-structure)
- [Configuration](#configuration)
- [Data Collection Scripts](#data-collection-scripts)
- [Data Aggregation Pipeline](#data-aggregation-pipeline)
- [Dashboard](#dashboard)
- [Automation](#automation)
- [Common Workflows](#common-workflows)
- [Reference](#reference)

---

## Prerequisites & Quick Start

### System Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [just](https://github.com/casey/just) (command runner - optional but recommended)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/jeroenjanssens/devrel-io.git
cd devrel-io

# 2. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install just (optional, for convenient commands)
# macOS: brew install just
# Linux: cargo install just

# 4. Copy config template
cp config.toml.example config.toml

# 5. Install dependencies
uv sync
# Or with just:
just install
```

### First Run

Fetch sample data to verify your setup:

```bash
# Fetch GitHub events for one project
uv run python fetch_github.py --project quarto --start-date 2025-01-01 --end-date 2025-01-01

# Check the output
ls data/output/github/quarto/
```

You should see a `2025-01-01.jsonl` file with GitHub events.

---

## Understanding the Data Structure

### Directory Layout

```
data/
├── input/                      # Source data
│   └── inputs.csv             # Google Sheets data
└── output/                     # Collected metrics
    ├── github/                # GitHub events (stars, forks, issues, PRs)
    │   ├── quarto/
    │   ├── shiny-python/
    │   └── ...
    ├── pypi/                  # PyPI download counts
    │   ├── plotnine/
    │   └── ...
    ├── cran/                  # CRAN download counts
    │   ├── ggplot2/
    │   └── ...
    ├── plausible/             # Web analytics
    │   ├── plotnine/
    │   └── ...
    ├── ga/                    # GA4 badge analytics
    ├── openvsx/               # Open VSX extension metrics
    │   ├── quarto/
    │   └── ...
    └── all.parquet            # Consolidated data (all sources)
```

### File Organization

Each project directory contains:

- **Daily files**: `2025-01-15.jsonl` - Raw data for a single day
- **Monthly aggregates**: `2025-01.jsonl` - All days in January 2025
- **Yearly aggregates**: `2025.jsonl` - All months in 2025
- **Archives**: `archive/` - Old daily/monthly files after aggregation

**Example**: `data/output/github/quarto/`
```
2025-01-01.jsonl          # Today's data (daily)
2025-01-02.jsonl
...
2025-01.jsonl             # All of January (monthly aggregate)
2024.jsonl                # All of 2024 (yearly aggregate)
archive/                  # Older files moved here after aggregation
  ├── 2024-12-01.jsonl
  └── 2024-12.jsonl
```

### Data Formats

**Events** (GitHub):
```json
{
  "event_type": "star",
  "project_id": "quarto",
  "github_repo": "quarto-dev/quarto-cli",
  "datetime": "2025-01-15T10:30:00Z",
  "user": "octocat"
}
```

**Metrics** (PyPI, CRAN, Plausible):
```json
{
  "metric": "downloads",
  "project_id": "plotnine",
  "date": "2025-01-15",
  "value": 5432
}
```

### Why JSONL?

**JSONL** (JSON Lines) stores one JSON object per line:
- **Streamable**: Process large files line-by-line without loading everything into memory
- **Appendable**: Add new records without reparsing the entire file
- **Simple**: Easy to process with standard tools (jq, grep, Python, R)
- **Git-friendly**: Line-based diffs work well

---

## Configuration

Projects are defined in `config.toml`. Each project can have multiple data sources.

### Adding a New Project

```toml
[projects.my-project]
name = "My Project"
language = "python"
github = "owner/repo"           # GitHub repository
pypi = "package-name"           # PyPI package name
cran = "packagename"            # CRAN package name
plausible = "example.com"       # Plausible site ID
website = "https://example.com"
description = "A great project"
hex_color = "#3976B3"           # For dashboard visualization
```

### Available Fields

| Field | Description | Required? |
|-------|-------------|-----------|
| `name` | Display name | Yes |
| `language` | Language (python/r/javascript/etc) | Yes |
| `github` | GitHub repo (owner/repo) | For GitHub events |
| `pypi` | PyPI package name | For PyPI downloads |
| `cran` | CRAN package name | For CRAN downloads |
| `plausible` | Plausible site ID | For web analytics |
| `google_analytics_property` | GA4 property ID | For GA4 data |
| `website` | Project website | Optional |
| `description` | Short description | Optional |
| `hex_color` | Color for charts | Optional |

### Google Sheets Configuration

To fetch data from Google Sheets:

```toml
[gsheet]
url = "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit?gid=0#gid=0"
```

**Note**: The sheet must be shared with "Anyone with the link" (View permission).

### Keeping config.toml Sorted

The `config.toml` file should be kept alphabetically sorted (both projects and keys within each project) to minimize merge conflicts and maintain consistency.

**Sorting the config file**:

```bash
# Using justfile (recommended)
just sort-config

# Or directly
uv run python scripts/sort-config.py
```

**Checking if sorted**:

```bash
# Using justfile
just check-config

# Or directly
uv run python scripts/sort-config.py --check
```

**Automatic sorting with pre-commit** (optional):

If you want config.toml to be automatically sorted before each commit:

```bash
just install-hooks
```

This will install pre-commit (if needed) and set up the hooks. After this, config.toml will be automatically sorted on every commit.

**CI validation**: Pull requests are automatically checked to ensure config.toml is sorted. If the check fails, simply run `just sort-config` and commit the changes.

---

## Data Collection Scripts

All fetch scripts follow the same pattern:
- Default to yesterday's data (incremental updates)
- Support date ranges for historical fetching
- Output to `data/output/{source}/{project}/{date}.jsonl`
- Can filter by project or process all projects

### fetch_github.py

**Fetches**: Stars, forks, issues (open/close), PRs (open/merge), comments

```bash
# Fetch yesterday's data for all projects (default)
uv run python fetch_github.py

# Specific project and date range
uv run python fetch_github.py --project quarto --start-date 2025-01-01 --end-date 2025-01-07

# Specific event types only
uv run python fetch_github.py --event-type star,fork

# Arbitrary repository (not in config.toml)
uv run python fetch_github.py --repo torvalds/linux

# Output to stdout (for piping to jq)
uv run python fetch_github.py --project quarto --output -
```

**Authentication**: GitHub Personal Access Token (optional but recommended)

1. Create token at https://github.com/settings/tokens
2. Select "Generate new token (classic)"
3. **No scopes needed** (public data only)
4. Copy token and add to `.env`:
   ```bash
   cp .env.example .env
   # Edit .env:
   GITHUB_TOKEN=ghp_your_token_here
   ```

**Rate limits**:
- Without token: 60 requests/hour
- With token: 5,000 requests/hour

**Available event types**:
- `star` - Repository starred
- `fork` - Repository forked
- `issue_open` - Issue created
- `issue_close` - Issue closed
- `pr_open` - Pull request created
- `pr_merge` - Pull request merged
- `issue_comment` - Comment on an issue
- `pr_comment` - Comment on a pull request

### fetch_pypi.py

**Fetches**: Daily download counts from PyPI

```bash
# Fetch yesterday's data for all projects with 'pypi' field
uv run python fetch_pypi.py

# Specific project
uv run python fetch_pypi.py --project plotnine

# Date range
uv run python fetch_pypi.py --start-date 2025-01-01 --end-date 2025-01-31
```

**Authentication**: None required

**Output**: `data/output/pypi/{project}/{date}.jsonl`

### fetch_cran.py

**Fetches**: Daily download counts from CRAN (R packages)

```bash
# Fetch yesterday's data for all R projects with 'cran' field
uv run python fetch_cran.py

# Specific project
uv run python fetch_cran.py --project ggplot2

# Date range
uv run python fetch_cran.py --start-date 2025-01-01 --end-date 2025-01-31
```

**Authentication**: None required

**Output**: `data/output/cran/{project}/{date}.jsonl`

### fetch_plausible.py

**Fetches**: Web analytics (pageviews, visitors, visits)

```bash
# Fetch yesterday's data for all projects with 'plausible' field
uv run python fetch_plausible.py --api-key YOUR_KEY

# Specific project
uv run python fetch_plausible.py --project plotnine --api-key YOUR_KEY

# Date range
uv run python fetch_plausible.py --start-date 2025-01-01 --end-date 2025-01-31 --api-key YOUR_KEY
```

**Authentication**: Plausible API key (required)

1. Get API key from Plausible: Settings → API Keys
2. Add to `.env`:
   ```bash
   PLAUSIBLE_KEY=your_key_here
   ```
3. Use `--api-key` flag or set `PLAUSIBLE_KEY` environment variable

**Output**: `data/output/plausible/{project}/{date}.jsonl`

### fetch_ga.py

**Fetches**: Google Analytics 4 data (filtered by 'supported-by-posit' badge)

```bash
# Fetch yesterday's data
uv run python fetch_ga.py

# Date range
uv run python fetch_ga.py --start-date 2025-01-01 --end-date 2025-01-31
```

**Authentication**: OAuth 2.0 (requires setup)

**Setup Steps**:

1. **Create Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable the "Google Analytics Data API"

2. **Create OAuth 2.0 Credentials**:
   - Navigate to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Desktop app" as application type
   - Download the credentials as `client_secrets.json`
   - Place `client_secrets.json` in the project root directory

3. **First-time Authentication**:
   ```bash
   uv run python fetch_ga.py
   ```
   - A browser window will open for authentication
   - Sign in with your Google account (must have GA4 access)
   - Grant the requested permissions
   - Credentials will be saved to `token.json` for future use

4. **GitHub Actions Setup** (optional):
   - After first authentication, the script displays three secrets
   - Add them to repository secrets (Settings → Secrets):
     - `GOOGLE_OAUTH_REFRESH_TOKEN`
     - `GOOGLE_OAUTH_CLIENT_ID`
     - `GOOGLE_OAUTH_CLIENT_SECRET`

**Output**: `data/output/ga/supported-by-posit_ga_{date}.jsonl`

### fetch_openvsx.py

**Fetches**: Open VSX extension metrics (snapshot data)

```bash
# Fetch yesterday's data for all projects with 'openvsx' field
uv run python fetch_openvsx.py

# Specific project
uv run python fetch_openvsx.py --project quarto

# Output to stdout
uv run python fetch_openvsx.py --project quarto --output -
```

**Authentication**: None required (public API)

**Metrics collected**:
- `total_downloads` - Cumulative download count
- `rating` - Average user rating
- `reviews` - Number of reviews

**Output**: `data/output/openvsx/{project}/{date}.jsonl`

**Note**: This API provides snapshot data only (no historical data), so each run fetches yesterday's metrics.

### fetch_inputs.py

**Fetches**: Google Sheets data as CSV

```bash
# Fetch using URL from config.toml
uv run python fetch_inputs.py

# Fetch from specific URL
uv run python fetch_inputs.py "https://docs.google.com/spreadsheets/d/SHEET_ID/edit"

# Download specific sheet by name
uv run python fetch_inputs.py -s "Sheet Name"

# Custom output path
uv run python fetch_inputs.py -o data/custom.csv
```

**Authentication**: None (sheet must be publicly accessible)

**Troubleshooting**: If you get a permission error:
1. Open the sheet in Google Sheets
2. Click 'Share' → 'Anyone with the link'
3. Set permission to 'Viewer'

**Output**: `data/input/inputs.csv`

---

## Data Aggregation Pipeline

### How It Works

1. **Fetch daily data**: Each script creates `YYYY-MM-DD.jsonl` files
2. **Aggregate monthly**: `concat-dates.py` merges daily files into `YYYY-MM.jsonl`
3. **Aggregate yearly**: Monthly files merge into `YYYY.jsonl`
4. **Deduplicate**: Automatically removes duplicate records by unique key
5. **Archive**: Source files moved to `archive/` after successful aggregation
6. **Consolidate**: `output_to_parquet.py` creates `all.parquet` from all sources

### concat-dates.py

**Purpose**: Merges daily files into monthly aggregates, monthly into yearly aggregates.

**Key features**:
- Only processes complete months and years
- **Merges with existing files** (doesn't overwrite)
- **Deduplicates** by unique key (project_id + metric + date)
- Archives source files after successful aggregation
- Cleans up old archives (default: 90 days)

```bash
# Manual run (processes specific directory)
uv run python concat-dates.py data/output/github/quarto/*.jsonl

# Dry run to preview changes
uv run python concat-dates.py --dry-run data/output/github/quarto/*.jsonl

# Custom archive retention
uv run python concat-dates.py --keep-days 180 data/output/github/quarto/*.jsonl
```

**Options**:
- `--dry-run`: Show what would be done without making changes
- `--keep-days N`: Keep archived files for N days (default: 90)
- `--today YYYY-MM-DD`: Override current date for testing

### aggregate-data.sh

**Purpose**: Wrapper script that runs `concat-dates.py` on all data directories.

```bash
# Aggregate all projects, all sources
./aggregate-data.sh

# Dry run
./aggregate-data.sh --dry-run

# Custom retention
./aggregate-data.sh --keep-days 180
```

This finds all directories with `.jsonl` files under `data/` and aggregates them.

### output_to_parquet.py

**Purpose**: Combines data from all sources into a single Parquet file for analysis.

```bash
# Create consolidated Parquet file
uv run python output_to_parquet.py
```

**Output**: `data/output/all.parquet`

**Schema**: Normalized format with columns:
- `project_id`: Project identifier
- `source`: Data source (github, pypi, cran, plausible)
- `metric`: Metric name (star, downloads, pageviews, etc.)
- `date`: Date of the metric
- `value`: Numeric value

---

## Dashboard

Interactive Shiny dashboard for visualizing DevRel metrics.

### Running Locally

```bash
# Install dependencies (if not already done)
just install

# Run the Shiny app
uv run shiny run app.py --port 8765

# Or use justfile shortcut
just app
```

The dashboard opens at http://127.0.0.1:8765

### Features

- **Project filtering**: Select one or more projects
- **Metric selection**: Choose which metrics to display
- **Time series visualization**: Line charts with trends
- **Data table**: View filtered input data

### Deploying to Posit Connect

The project includes `requirements.txt` for deployment:

```bash
# Deploy using rsconnect-python or Posit Connect UI
# requirements.txt is automatically kept in sync via GitHub Actions
```

To manually regenerate `requirements.txt`:

```bash
just export-deps
# Or:
uv export --no-hashes --no-dev > requirements.txt
```

---

## Automation

### Daily Data Collection (GitHub Actions)

The workflow `.github/workflows/fetch-output.yml` automatically:
1. Fetches GitHub events for all projects (yesterday's data)
2. Fetches Plausible analytics for projects with `plausible` field
3. Fetches PyPI downloads for projects with `pypi` field
4. Fetches CRAN downloads for projects with `cran` field
5. Runs aggregation pipeline (`aggregate-data.sh`)
6. Creates consolidated Parquet file (`output_to_parquet.py`)
7. Commits and pushes data to the repository

**Schedule**: Daily at 1am ET (6am UTC)

**Manual trigger**: Go to Actions tab → Fetch DevRel Data → Run workflow

### Setup GitHub Actions

**Required secrets** (Settings → Secrets and variables → Actions):

1. **GH_TOKEN**: GitHub Personal Access Token
   - Create at https://github.com/settings/tokens
   - No scopes needed (public data only)
   - Copy and add as repository secret

2. **PLAUSIBLE_KEY**: Plausible API key
   - Get from Plausible: Settings → API Keys
   - Copy and add as repository secret

**Optional secrets** (for Google Analytics):
- `GOOGLE_OAUTH_REFRESH_TOKEN`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`

### Dependency Updates (GitHub Actions)

The workflow `.github/workflows/update-requirements.yml` automatically:
- Regenerates `requirements.txt` when `pyproject.toml` or `uv.lock` changes
- Commits the updated file
- Keeps deployment dependencies in sync

---

## Common Workflows

### Adding a New Project

1. Edit `config.toml` and add project definition:
   ```toml
   [projects.my-new-project]
   name = "My New Project"
   language = "python"
   github = "owner/repo"
   pypi = "package-name"
   website = "https://example.com"
   description = "An awesome project"
   hex_color = "#FF5733"
   ```

2. Fetch historical data:
   ```bash
   # Fetch last 30 days
   uv run python fetch_github.py --project my-new-project --start-date 2024-12-01 --end-date 2025-01-01
   uv run python fetch_pypi.py --project my-new-project --start-date 2024-12-01 --end-date 2025-01-01
   ```

3. Run aggregation:
   ```bash
   ./aggregate-data.sh
   ```

### Backfilling Historical Data

Fetch data for a specific date range:

```bash
# GitHub events for all of 2024
uv run python fetch_github.py --project quarto --start-date 2024-01-01 --end-date 2024-12-31

# PyPI downloads for a specific month
uv run python fetch_pypi.py --project plotnine --start-date 2024-11-01 --end-date 2024-11-30
```

Then aggregate:

```bash
./aggregate-data.sh
```

### Troubleshooting Failed Fetches

**Rate limit exceeded**:
```bash
# Check rate limit status
curl -I https://api.github.com/rate_limit
# Add or refresh your GitHub token
```

**Token expired**:
1. Generate new token at https://github.com/settings/tokens
2. Update `.env` file
3. Update GitHub Actions secret (`GH_TOKEN`)

**Missing data**:
- Check if project has the required field in `config.toml` (e.g., `pypi`, `cran`)
- Verify date range (some data sources may not have historical data)
- Check script output for error messages

### Manually Triggering Aggregation

Run aggregation after manual data fetches:

```bash
# Aggregate all projects
./aggregate-data.sh

# Preview changes first
./aggregate-data.sh --dry-run

# Aggregate specific project
uv run python concat-dates.py data/output/github/quarto/*.jsonl
```

### Viewing Raw Data

Use `jq` to query JSONL files:

```bash
# Count events by type
cat data/output/github/quarto/2025-01-15.jsonl | jq -r '.event_type' | sort | uniq -c

# Extract all star events
cat data/output/github/quarto/2025.jsonl | jq 'select(.event_type == "star")'

# Get download counts for a specific date
cat data/output/pypi/plotnine/2025-01.jsonl | jq 'select(.date == "2025-01-15") | .value'

# Count total downloads in a month
cat data/output/cran/ggplot2/2025-01.jsonl | jq -s 'map(.value) | add'
```

---

## Reference

### justfile Commands

```bash
just --list              # Show all available commands
just install             # Install dependencies (uv sync)
just install-hooks       # Install pre-commit hooks (optional)
just get-inputs          # Fetch Google Sheets data
just sort-config         # Sort config.toml alphabetically
just check-config        # Check if config.toml is sorted
just app                 # Run Shiny dashboard
just export-deps         # Export requirements.txt for deployment
```

### API Endpoints

| Source | Endpoint | Authentication |
|--------|----------|----------------|
| GitHub | `api.github.com` | Optional (token) |
| PyPI | `pypistats.org/api` | None |
| CRAN | `cranlogs.r-pkg.org` | None |
| Plausible | `plausible.io/api/v2` | Required (API key) |
| Google Analytics | `analyticsdata.googleapis.com` | OAuth 2.0 |
| Open VSX | `open-vsx.org/api` | None |

### File Format Examples

**GitHub event (star)**:
```json
{"event_type": "star", "project_id": "quarto", "github_repo": "quarto-dev/quarto-cli", "datetime": "2025-01-15T10:30:00Z", "user": "octocat"}
```

**PyPI downloads**:
```json
{"metric": "downloads", "project_id": "plotnine", "date": "2025-01-15", "value": 5432}
```

**CRAN downloads**:
```json
{"metric": "downloads", "project_id": "ggplot2", "date": "2025-01-15", "value": 28745}
```

**Plausible analytics**:
```json
{"metric": "pageviews", "project_id": "plotnine", "date": "2025-01-15", "value": 1523}
{"metric": "visitors", "project_id": "plotnine", "date": "2025-01-15", "value": 457}
{"metric": "visits", "project_id": "plotnine", "date": "2025-01-15", "value": 612}
```

**Open VSX metrics**:
```json
{"metric": "total_downloads", "project_id": "quarto", "date": "2025-01-15", "value": 1200780}
{"metric": "rating", "project_id": "quarto", "date": "2025-01-15", "value": 5.0}
{"metric": "reviews", "project_id": "quarto", "date": "2025-01-15", "value": 1}
```

### Troubleshooting

**"Google Sheet is private" error**:
1. Open sheet in Google Sheets
2. Click 'Share' → Under 'General access', select 'Anyone with the link'
3. Set permission to 'Viewer'

**"Rate limit exceeded" (GitHub)**:
- Without token: Limited to 60 requests/hour
- With token: 5,000 requests/hour
- Add `GITHUB_TOKEN` to `.env` file

**"No PLAUSIBLE_KEY provided"**:
- Get API key from Plausible: Settings → API Keys
- Add to `.env` file: `PLAUSIBLE_KEY=your_key_here`

**Aggregation not working**:
- Check that month/year is complete (concat-dates.py only processes complete periods)
- Run with `--dry-run` to see what would be aggregated
- Use `--today` flag to override current date for testing

**Dashboard not loading data**:
- Ensure `data/output/all.parquet` exists
- Run `uv run python output_to_parquet.py` to regenerate
- Check file permissions

---

## Development

### Project Structure

```
devrel-io/
├── fetch_*.py              # Data collection scripts
├── concat-dates.py         # Aggregation logic
├── aggregate-data.sh       # Aggregation wrapper
├── output_to_parquet.py    # Parquet consolidation
├── app.py                  # Shiny dashboard
├── config.toml             # Project configuration
├── pyproject.toml          # Python dependencies
├── justfile                # Command shortcuts
├── .github/workflows/      # GitHub Actions
│   ├── fetch-output.yml    # Daily data collection
│   └── update-requirements.yml  # Dependency sync
└── data/                   # Data storage
    ├── input/              # Google Sheets data
    └── output/             # Collected metrics
```

### Testing Fetch Scripts

Test with a single project and recent date:

```bash
# Test GitHub fetch
uv run python fetch_github.py --project quarto --start-date 2025-01-01 --end-date 2025-01-01

# Test PyPI fetch
uv run python fetch_pypi.py --project plotnine --start-date 2025-01-01 --end-date 2025-01-01

# Verify output
ls -lh data/output/github/quarto/
cat data/output/github/quarto/2025-01-01.jsonl | jq
```

### Code Patterns

All fetch scripts follow a common pattern:

1. **Load config**: `load_config()` reads `config.toml`
2. **Parse arguments**: `argparse` for CLI options
3. **Fetch data**: API-specific logic
4. **Transform**: Convert to standard JSONL format
5. **Group by date**: `group_by_date()` organizes records
6. **Write JSONL**: One file per project per date

See `fetch_pypi.py` for a simple, well-commented example.

---

## License

MIT License

Copyright (c) 2025 Jeroen Janssens

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contributing

Contributions welcome! To add a new data source:

1. Create a new `fetch_*.py` script following existing patterns
2. Add configuration fields to `config.toml`
3. Update this README with usage instructions
4. Add the script to `.github/workflows/fetch-output.yml`

---

**Questions?** Open an issue or check existing documentation in the `fetch_*.py` scripts.
