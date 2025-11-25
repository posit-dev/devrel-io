#!/usr/bin/env python3
"""
Fetch Google Analytics 4 data for badge analytics.

Downloads session data filtered by 'Session manual ad content' = 'supported-by-posit'
and outputs daily session counts per session source as JSONL files.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    RunReportRequest,
)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


def get_credentials():
    """
    Get credentials using OAuth 2.0.

    Tries in order:
    1. Refresh token from GOOGLE_OAUTH_REFRESH_TOKEN environment variable
    2. Saved token from token.json file
    3. New OAuth flow using client_secrets.json
    """
    SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
    TOKEN_FILE = 'token.json'
    CLIENT_SECRETS_FILE = 'client_secrets.json'

    creds = None

    # Method 1: Try refresh token from environment variable (for GitHub Actions)
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

    # Debug: check what we got
    print(f"DEBUG: refresh_token present: {bool(refresh_token)}")
    print(f"DEBUG: client_id present: {bool(client_id)}")
    print(f"DEBUG: client_secret present: {bool(client_secret)}")

    if refresh_token and client_id and client_secret:
        print("Using credentials from environment variables...")
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )
        # Refresh to get an access token
        print("Refreshing credentials to obtain access token...")
        try:
            creds.refresh(Request())
            print("Successfully authenticated with environment variables")
            return creds
        except Exception as e:
            print(f"Error refreshing credentials from environment variables: {e}", file=sys.stderr)
            sys.exit(1)

    # Method 2: Try loading from token file
    if Path(TOKEN_FILE).exists():
        print(f"Loading credentials from {TOKEN_FILE}...")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}", file=sys.stderr)
                print("Please delete token.json and re-authenticate.", file=sys.stderr)
                sys.exit(1)

    # Method 3: Run OAuth flow if no valid credentials
    if not creds or not creds.valid:
        if not Path(CLIENT_SECRETS_FILE).exists():
            print(f"Error: {CLIENT_SECRETS_FILE} not found", file=sys.stderr)
            print("\nTo authenticate, you need either:", file=sys.stderr)
            print(f"1. A {CLIENT_SECRETS_FILE} file to run the OAuth flow", file=sys.stderr)
            print("2. Environment variables: GOOGLE_OAUTH_REFRESH_TOKEN, GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET", file=sys.stderr)
            sys.exit(1)

        print(f"Running OAuth flow using {CLIENT_SECRETS_FILE}...")
        print("A browser window will open for authentication.")

        try:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        except Exception as e:
            print(f"Error during OAuth flow: {e}", file=sys.stderr)
            sys.exit(1)

        # Save credentials for future runs
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f"Credentials saved to {TOKEN_FILE}")

        # Display refresh token for GitHub Actions setup
        print("\n" + "="*60)
        print("For GitHub Actions, set these secrets:")
        print("="*60)
        print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
        print(f"GOOGLE_OAUTH_CLIENT_ID={creds.client_id}")
        print(f"GOOGLE_OAUTH_CLIENT_SECRET={creds.client_secret}")
        print("="*60 + "\n")

    return creds


def parse_date(date_string):
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_string}. Use YYYY-MM-DD")


def fetch_analytics_data(property_id, start_date, end_date):
    """
    Fetch analytics data from GA4.

    Args:
        property_id: GA4 property ID
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        List of dicts with keys: date, source, count
    """
    credentials = get_credentials()
    client = BetaAnalyticsDataClient(credentials=credentials)

    # Build the request
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionSource"),
        ],
        metrics=[
            Metric(name="sessions"),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="sessionManualAdContent",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value="supported-by-posit",
                ),
            )
        ),
    )

    try:
        response = client.run_report(request)
    except Exception as e:
        print(f"Error: Failed to fetch data from GA4: {e}", file=sys.stderr)
        sys.exit(1)

    # Process the response
    results = []
    for row in response.rows:
        date_value = row.dimension_values[0].value  # format: YYYYMMDD
        source = row.dimension_values[1].value
        count = int(row.metric_values[0].value)

        # Convert date format from YYYYMMDD to YYYY-MM-DD
        formatted_date = f"{date_value[:4]}-{date_value[4:6]}-{date_value[6:]}"

        results.append({
            "date": formatted_date,
            "source": source,
            "count": count,
        })

    return results


def write_jsonl_files(data, prefix="supported-by-posit_ga", output_dir="data"):
    """
    Write data to JSONL files, one file per date.

    Args:
        data: List of dicts with keys: date, source, count
        prefix: Prefix for output filenames
        output_dir: Directory to write files to (default: data)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Group data by date
    data_by_date = {}
    for record in data:
        date = record["date"]
        if date not in data_by_date:
            data_by_date[date] = []
        data_by_date[date].append(record)

    # Write one file per date
    for date, records in sorted(data_by_date.items()):
        filename = output_path / f"{prefix}_{date}.jsonl"
        try:
            with open(filename, "w") as f:
                for record in records:
                    f.write(json.dumps(record) + "\n")
            print(f"Written {len(records)} records to {filename}")
        except Exception as e:
            print(f"Error: Failed to write {filename}: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch GA4 data for badge analytics filtered by 'supported-by-posit'"
    )

    # Default to yesterday
    yesterday = (datetime.now() - timedelta(days=1)).date()

    parser.add_argument(
        "--start-date",
        type=parse_date,
        default=yesterday,
        help="Start date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--end-date",
        type=parse_date,
        default=yesterday,
        help="End date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--property-id",
        type=str,
        default="322289629",
        help="GA4 property ID (default: 322289629)",
    )

    args = parser.parse_args()

    # Use end_date from args (which defaults to yesterday)
    end_date = args.end_date

    # Validate date range
    if end_date < args.start_date:
        print("Error: end-date must be greater than or equal to start-date", file=sys.stderr)
        sys.exit(1)

    # Convert dates to string format for API
    start_date_str = args.start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    print(f"Fetching data from {start_date_str} to {end_date_str}...")

    # Fetch data
    data = fetch_analytics_data(args.property_id, start_date_str, end_date_str)

    if not data:
        print("No data found for the specified date range and filter.")
        return

    # Write JSONL files
    write_jsonl_files(data)


if __name__ == "__main__":
    main()
