# Devrel I/O

A Python CLI tool for developer relations workflows.

## Features

- Download Google Sheets as CSV files

## Usage

### Download a Google Sheet as CSV

```bash
uv run main.py "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0"
```

Specify an output file:
```bash
uv run main.py "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0" -o output.csv
```

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
