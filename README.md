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
- Download GitHub stars data for projects with incremental daily updates

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

## GitHub Stars Tracking

Track GitHub stars for your projects over time with incremental daily updates.

### Setup GitHub Token

To use the GitHub stars feature, you need a GitHub Personal Access Token:

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
   uv run python github_stars.py --id quarto
   ```

**Note:** The `.env` file is gitignored and will not be committed. Keep your token secure and never share it.

### GitHub Stars Usage

```bash
# Download yesterday's stars for all projects
uv run python github_stars.py

# Download for a specific project
uv run python github_stars.py --id quarto

# Download for a date range
uv run python github_stars.py --id quarto --start-date 2024-01-01 --end-date 2024-01-31

# Output to stdout instead of files
uv run python github_stars.py --id quarto --output -

# Pipe to jq for filtering
uv run python github_stars.py --id quarto --output - | jq .
```

### Output Format

Stars are saved as JSONL files organized by project:
```
data/output/github_stars/
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
{"project_id": "quarto", "github_repo": "quarto-dev/quarto-cli", "datetime": "2024-01-15T10:30:00Z", "user": "username"}
```

### Rate Limits

- **Without token:** 60 requests/hour
- **With token:** 5,000 requests/hour

For daily incremental updates, even without a token you should be fine. For historical data downloads, a token is highly recommended.
