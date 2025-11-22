import argparse
import re
import sys
from pathlib import Path
from io import StringIO
import requests
from bs4 import BeautifulSoup
import polars as pl


def parse_google_sheets_url(url):
    """Extract spreadsheet ID from a Google Sheets URL."""
    spreadsheet_pattern = r'/spreadsheets/d/([a-zA-Z0-9-_]+)'
    spreadsheet_match = re.search(spreadsheet_pattern, url)

    if not spreadsheet_match:
        raise ValueError("Invalid Google Sheets URL: couldn't find spreadsheet ID")

    spreadsheet_id = spreadsheet_match.group(1)
    return spreadsheet_id


def get_all_sheets(spreadsheet_id):
    """Get all sheet names and gids from a Google Spreadsheet."""
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    response = requests.get(url)

    if response.status_code == 401:
        raise PermissionError(
            "The Google Sheet is private and requires authentication.\n"
            "Please make the sheet accessible by:\n"
            "  1. Opening the sheet in Google Sheets\n"
            "  2. Click 'Share' in the top right\n"
            "  3. Under 'General access', select 'Anyone with the link'\n"
            "  4. Set permission to 'Viewer'\n"
            "  5. Click 'Done' and try again"
        )

    response.raise_for_status()

    # Parse HTML to find sheet information
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find sheets in the page source using regex patterns
    # Google Sheets embeds sheet info in JavaScript variables
    sheets = []
    sheet_pattern = r'"(\d+)","([^"]+)"'

    # Look for sheet data in script tags or data attributes
    for script in soup.find_all('script'):
        if script.string:
            matches = re.findall(r'\["sheet\.(\d+)","([^"]+)"', script.string)
            for gid, name in matches:
                sheets.append({'name': name, 'gid': gid})

    # Fallback: try to extract from a different pattern
    if not sheets:
        text = response.text
        # Look for sheet data in various formats
        matches = re.findall(r'\["sheet\.(\d+)","([^"]+)"', text)
        for gid, name in matches:
            sheets.append({'name': name, 'gid': gid})

    # If still no sheets found, try another pattern
    if not sheets:
        matches = re.findall(r'"gid":"(\d+)"[^}]*"title":"([^"]+)"', text)
        for gid, name in matches:
            sheets.append({'name': name, 'gid': gid})

    # Remove duplicates
    seen = set()
    unique_sheets = []
    for sheet in sheets:
        key = (sheet['name'], sheet['gid'])
        if key not in seen:
            seen.add(key)
            unique_sheets.append(sheet)

    if not unique_sheets:
        # Default to gid=0 if we can't find sheets
        unique_sheets = [{'name': 'Sheet1', 'gid': '0'}]

    return unique_sheets


def get_export_url(spreadsheet_id, gid='0'):
    """Generate the CSV export URL for a Google Sheet."""
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


def download_sheet_to_dataframe(spreadsheet_id, gid):
    """Download a single sheet as a Polars DataFrame."""
    export_url = get_export_url(spreadsheet_id, gid)

    response = requests.get(export_url)

    if response.status_code == 401:
        raise PermissionError(
            "The Google Sheet is private and requires authentication.\n"
            "Please make the sheet accessible by:\n"
            "  1. Opening the sheet in Google Sheets\n"
            "  2. Click 'Share' in the top right\n"
            "  3. Under 'General access', select 'Anyone with the link'\n"
            "  4. Set permission to 'Viewer'\n"
            "  5. Click 'Done' and try again"
        )

    response.raise_for_status()

    # Parse CSV into Polars DataFrame
    df = pl.read_csv(StringIO(response.text))
    return df


def download_google_sheet(url, sheet_name=None, output_path=None):
    """Download Google Sheet(s) as CSV.

    Args:
        url: Google Sheets URL
        sheet_name: Specific sheet name to download. If None, downloads all sheets.
        output_path: Output CSV file path
    """
    spreadsheet_id = parse_google_sheets_url(url)

    if sheet_name:
        # Download specific sheet
        sheets = get_all_sheets(spreadsheet_id)
        target_sheet = None
        for sheet in sheets:
            if sheet['name'] == sheet_name:
                target_sheet = sheet
                break

        if not target_sheet:
            available = ', '.join([s['name'] for s in sheets])
            raise ValueError(f"Sheet '{sheet_name}' not found. Available sheets: {available}")

        print(f"Downloading sheet: {target_sheet['name']} (gid={target_sheet['gid']})")
        df = download_sheet_to_dataframe(spreadsheet_id, target_sheet['gid'])

    else:
        # Download all sheets and concatenate
        sheets = get_all_sheets(spreadsheet_id)
        print(f"Found {len(sheets)} sheet(s): {', '.join([s['name'] for s in sheets])}")

        dataframes = []
        for sheet in sheets:
            print(f"Downloading sheet: {sheet['name']} (gid={sheet['gid']})")
            df = download_sheet_to_dataframe(spreadsheet_id, sheet['gid'])
            dataframes.append(df)

        if len(dataframes) == 1:
            df = dataframes[0]
        else:
            print(f"Concatenating {len(dataframes)} sheets with diagonal strategy...")
            df = pl.concat(dataframes, how="diagonal")

    # Save to file
    if output_path is None:
        if sheet_name:
            output_path = f"sheet_{spreadsheet_id}_{sheet_name}.csv"
        else:
            output_path = f"sheet_{spreadsheet_id}_all.csv"

    output_file = Path(output_path)
    df.write_csv(output_file)

    print(f"✓ Downloaded to: {output_file.absolute()}")
    print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Devrel I/O - Download Google Sheets as CSV"
    )
    parser.add_argument(
        'url',
        nargs='?',
        help='Google Sheets URL to download'
    )
    parser.add_argument(
        '-s', '--sheet',
        help='Specific sheet name to download (if omitted, downloads all sheets)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output CSV file path (default: sheet_<id>_<name>.csv)'
    )

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        sys.exit(1)

    try:
        download_google_sheet(args.url, args.sheet, args.output)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
