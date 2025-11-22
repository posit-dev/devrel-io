# Devrel I/O

A Python CLI tool for developer relations workflows.

## Features

- Download Google Sheets as CSV files
- Download specific sheets by name
- Download all sheets and concatenate them using Polars (diagonal strategy)
- Store default URL in configuration file

## Configuration

You can store your Google Sheets URL in a configuration file to avoid typing it every time:

1. Copy the example config file:
```bash
cp config.toml.example config.toml
```

2. Edit `config.toml` with your Google Sheets URL:
```toml
[gsheet]
url = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit?gid=0#gid=0"
```

3. Run the script without providing a URL:
```bash
uv run gsheet.py
```

The script will use the URL from `config.toml`. You can still override it by providing a URL as an argument.

## Quick Start with Just

This project includes a `justfile` for common tasks. Install [just](https://github.com/casey/just) and run:

```bash
# See all available commands
just

# Download sheets using config.toml
just get-inputs

# Download a specific sheet
just get-sheet "Sheet1"

# Download with custom output path
just get-sheet "Sheet1" output.csv

# Download from a different URL
just get-url "https://docs.google.com/spreadsheets/d/OTHER_ID/edit"

# Clean downloaded CSV files
just clean

# Install dependencies
just install
```

## Usage

### Download all sheets (concatenated)

```bash
uv run gsheet.py "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0"
```

This will download all sheets and concatenate them using Polars' diagonal strategy, which handles sheets with different columns gracefully.

### Download a specific sheet

```bash
uv run gsheet.py "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0" -s "Sheet Name"
```

### Specify an output file

```bash
uv run gsheet.py "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0" -o output.csv
```

### Options

- `-s, --sheet`: Specific sheet name to download (if omitted, downloads all sheets)
- `-o, --output`: Output CSV file path

**Note:** The Google Sheet must be shared with "Anyone with the link" access. If you get a permission error, follow these steps:
1. Open the sheet in Google Sheets
2. Click 'Share' in the top right
3. Under 'General access', select 'Anyone with the link'
4. Set permission to 'Viewer'
5. Click 'Done' and try again

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package management.

### Prerequisites

- Python 3.8 or higher
- uv (install via `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Getting Started

1. Clone the repository:
```bash
git clone https://github.com/yourusername/devrel-io.git
cd devrel-io
```

2. Install dependencies:
```bash
uv sync
```

3. Run the application:
```bash
uv run devrel-io
```

### Development

To work on the project:

```bash
# Install dependencies
uv sync

# Run the CLI
uv run devrel-io

# Add new dependencies
uv add package-name

# Add dev dependencies
uv add --dev package-name
```
