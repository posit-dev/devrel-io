# Devrel I/O

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
