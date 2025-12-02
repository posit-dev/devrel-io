# DevRel I/O

Download Google Sheets as CSV files for developer relations workflows.

## Quick Start

1. Install [just](https://github.com/casey/just) and [uv](https://docs.astral.sh/uv/)

2. Copy the example config file:
```bash
cp config.toml.example config.toml
```

3. Edit `config.toml` with your Google Sheets URL:
```toml
[gsheet]
url = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit?gid=0#gid=0"
```

4. Install dependencies and download your data:
```bash
just install
just get-inputs
```

Your data will be saved to `data/input/inputs.csv`.

**Note:** The Google Sheet must be shared with "Anyone with the link" access.

## Features

- Download Google Sheets as CSV files
- Automatically discover and download all sheets in a spreadsheet
- Concatenate multiple sheets using Polars (diagonal strategy handles different columns)
- Store configuration in `config.toml` for easy reuse
- Data saved to `data/input/` and tracked in git
- Download GitHub events (stars, forks, issues, PRs, comments) with incremental daily updates

## Advanced Usage

### Download with custom options

```bash
# Use config.toml URL, custom output path
uv run gsheet.py -o custom_output.csv

# Download from a different URL
uv run gsheet.py "https://docs.google.com/spreadsheets/d/OTHER_SPREADSHEET_ID/edit"

# Download a specific sheet by name
uv run gsheet.py -s "Sheet Name"

# Combine options
uv run gsheet.py "URL" -s "Sheet Name" -o output.csv
```

### CLI Options

- `-s, --sheet`: Specific sheet name to download (if omitted, downloads all sheets)
- `-o, --output`: Output CSV file path (default: `sheet_{id}_all.csv`)

### Troubleshooting

If you get a permission error:
1. Open the sheet in Google Sheets
2. Click 'Share' in the top right
3. Under 'General access', select 'Anyone with the link'
4. Set permission to 'Viewer'
5. Click 'Done' and try again

## GitHub Events Tracking

Track GitHub events for your projects over time with incremental daily updates. Supports stars, forks, issues, pull requests, and comments.

### Setup GitHub Token

To use the GitHub events feature, you need a GitHub Personal Access Token:

1. **Create a GitHub Token:**
   - Go to https://github.com/settings/tokens
   - Click **"Generate new token"** → **"Generate new token (classic)"**
   - Give it a descriptive name (e.g., "DevRel I/O Stars")
   - Select expiration (recommended: 90 days or 1 year)
   - **No scopes/permissions needed** - leave all checkboxes unchecked (public data only)
   - Click **"Generate token"** at the bottom
   - **Copy the token** (you won't see it again!)

2. **Add Token to .env file:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your token:
   ```bash
   GITHUB_TOKEN=ghp_your_actual_token_here
   ```

3. **Verify it works:**
   ```bash
   uv run python fetch_github.py --project quarto --event-type star
   ```

**Note:** The `.env` file is gitignored and will not be committed. Keep your token secure and never share it.

### GitHub Events Usage

```bash
# Download all event types for yesterday (default)
uv run python fetch_github.py

# Download specific event types
uv run python fetch_github.py --event-type star,fork,issue_open

# Download for a specific project from config.toml
uv run python fetch_github.py --project quarto

# Download for an arbitrary repository (not in config.toml)
uv run python fetch_github.py --repo torvalds/linux
uv run python fetch_github.py --repo https://github.com/torvalds/linux

# Download for a date range
uv run python fetch_github.py --project quarto --start-date 2024-01-01 --end-date 2024-01-31

# Output to stdout instead of files
uv run python fetch_github.py --project quarto --output -

# Pipe to jq for filtering
uv run python fetch_github.py --project quarto --output - | jq '.event_type'
```

**Available Event Types:**
- `star` - Repository starred
- `fork` - Repository forked
- `issue_open` - Issue created
- `issue_close` - Issue closed
- `pr_open` - Pull request created
- `pr_merge` - Pull request merged
- `issue_comment` - Comment on an issue
- `pr_comment` - Comment on a pull request

### Output Format

Events are saved as JSONL files organized by project:
```
data/output/github/
├── quarto/
│   ├── 2024-01-15.jsonl
│   └── 2024-01-16.jsonl
├── shiny-python/
│   └── 2024-01-15.jsonl
└── gt/
    └── 2024-01-15.jsonl
```

Each JSONL line contains:
```json
{"event_type": "star", "project_id": "quarto", "github_repo": "quarto-dev/quarto-cli", "datetime": "2024-01-15T10:30:00Z", "user": "username"}
{"event_type": "fork", "project_id": "quarto", "github_repo": "quarto-dev/quarto-cli", "datetime": "2024-01-15T14:22:00Z", "user": "username"}
{"event_type": "issue_open", "project_id": "quarto", "github_repo": "quarto-dev/quarto-cli", "datetime": "2024-01-15T16:45:00Z", "user": "username"}
```

### Rate Limits

- **Without token:** 60 requests/hour
- **With token:** 5,000 requests/hour

For daily incremental updates, even without a token you should be fine. For historical data downloads, a token is highly recommended.

## Automated Daily Updates with GitHub Actions

The repository includes a GitHub Actions workflow that automatically fetches all DevRel data daily and aggregates it.

### Setup

1. **Add Secrets:**
   - Go to your repository settings: `Settings` → `Secrets and variables` → `Actions`
   - Click **"New repository secret"** for each:

   **Required secrets:**
   - Name: `GH_TOKEN`
     - Value: Your GitHub Personal Access Token (see [Setup GitHub Token](#setup-github-token) above)

   - Name: `PLAUSIBLE_KEY`
     - Value: Your Plausible API key (from Plausible Settings → API Keys)

2. **Enable Actions:**
   - The workflow runs automatically daily at 1am ET (6am UTC)
   - Can also be triggered manually: `Actions` tab → `Fetch DevRel Data` → `Run workflow`

### What the workflow does:

1. Fetches GitHub events for all projects in `config.toml` (yesterday's data)
2. Fetches Plausible analytics for all projects with `plausible` field
3. Fetches PyPI download stats for all projects with `pypi` field
4. Runs `aggregate-data.sh` to create monthly/yearly files
5. Commits and pushes data files to the repository

### Workflow file location:

`.github/workflows/fetch-github-events.yml`

## Shiny Dashboard

Visualize GitHub events and input data with an interactive Shiny dashboard.

### Running the Dashboard

```bash
# Install dependencies (if not already done)
just install

# Run the Shiny app
uv run shiny run app.py

# Or use the justfile command
just app
```

The dashboard will open in your browser at http://127.0.0.1:8765

### Dashboard Features

- **Project Selector:** Filter data by project from config.toml
- **Event Type Filters:** Toggle which GitHub event types to display
- **Weekly Trend Chart:** Line graph showing event counts aggregated by ISO week
- **Input Data Table:** View filtered input data with formatted column names

## Deploying to Posit Connect

The app includes a `requirements.txt` file for deploying to Posit Connect.

### Automatic Updates

The `requirements.txt` is automatically regenerated whenever `pyproject.toml` or `uv.lock` changes via GitHub Actions.

### Manual Regeneration

To regenerate `requirements.txt` locally:

```bash
just export-deps
```

This runs `uv export --no-hashes --no-dev > requirements.txt` to create a deployment-ready requirements file from your locked dependencies.
