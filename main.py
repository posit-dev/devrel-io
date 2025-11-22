import argparse
import re
import sys
from pathlib import Path
import requests


def parse_google_sheets_url(url):
    """Extract spreadsheet ID and gid from a Google Sheets URL."""
    spreadsheet_pattern = r'/spreadsheets/d/([a-zA-Z0-9-_]+)'
    gid_pattern = r'[#&]gid=([0-9]+)'

    spreadsheet_match = re.search(spreadsheet_pattern, url)
    gid_match = re.search(gid_pattern, url)

    if not spreadsheet_match:
        raise ValueError("Invalid Google Sheets URL: couldn't find spreadsheet ID")

    spreadsheet_id = spreadsheet_match.group(1)
    gid = gid_match.group(1) if gid_match else '0'

    return spreadsheet_id, gid


def get_export_url(spreadsheet_id, gid='0'):
    """Generate the CSV export URL for a Google Sheet."""
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


def download_google_sheet(url, output_path=None):
    """Download a Google Sheet as CSV."""
    spreadsheet_id, gid = parse_google_sheets_url(url)
    export_url = get_export_url(spreadsheet_id, gid)

    print(f"Downloading from: {export_url}")

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

    if output_path is None:
        output_path = f"sheet_{spreadsheet_id}_gid_{gid}.csv"

    output_file = Path(output_path)
    output_file.write_text(response.text, encoding='utf-8')

    print(f"✓ Downloaded to: {output_file.absolute()}")
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
        '-o', '--output',
        help='Output CSV file path (default: sheet_<id>_gid_<gid>.csv)'
    )

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        sys.exit(1)

    try:
        download_google_sheet(args.url, args.output)
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
