import json
import sys
from datetime import date
from pathlib import Path

import gspread
from google.oauth2.credentials import Credentials

from models import JobApplication

CONFIG_PATH = Path("config.json")
SHEET_NAME = "Job Application Tracker"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def _save_config(data: dict) -> None:
    existing = _load_config()
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2))


def get_sheets_client(creds: Credentials) -> gspread.Client:
    try:
        return gspread.authorize(creds)
    except Exception as e:
        print(f"\n[ERROR] Failed to authorize Google Sheets client: {e}", file=sys.stderr)
        print("Make sure your credentials are valid and Sheets API is enabled.", file=sys.stderr)
        sys.exit(1)


def open_or_create_sheet(creds: Credentials) -> gspread.Spreadsheet:
    """Open the configured sheet, or create a new one on first run."""
    client = get_sheets_client(creds)
    config = _load_config()
    sheet_id = config.get("sheet_id")

    if sheet_id:
        try:
            return client.open_by_key(sheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"\n[ERROR] Spreadsheet with ID '{sheet_id}' not found.", file=sys.stderr)
            print("Delete config.json to create a new sheet, or fix the sheet_id.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n[ERROR] Could not open Google Sheet: {e}", file=sys.stderr)
            sys.exit(1)

    # First run: create a new sheet
    try:
        spreadsheet = client.create(SHEET_NAME)
        _save_config({"sheet_id": spreadsheet.id})
        worksheet = spreadsheet.sheet1
        worksheet.append_row(JobApplication.sheet_headers(), value_input_option="RAW")
        print(f"\n[INFO] Created new Google Sheet: {SHEET_NAME}")
        print(f"[INFO] URL: {spreadsheet.url}")
        print(f"[INFO] Sheet ID saved to config.json")
        return spreadsheet
    except Exception as e:
        print(f"\n[ERROR] Failed to create Google Sheet: {e}", file=sys.stderr)
        sys.exit(1)


def get_existing_thread_ids(spreadsheet: gspread.Spreadsheet) -> set[str]:
    """Return all thread IDs already logged (column A, skipping header)."""
    worksheet = spreadsheet.sheet1
    try:
        values = worksheet.col_values(1)  # column A
        return set(values[1:])  # skip header row
    except Exception as e:
        print(f"\n[ERROR] Could not read existing thread IDs: {e}", file=sys.stderr)
        sys.exit(1)


def get_existing_subject_keys(spreadsheet: gspread.Spreadsheet) -> set[tuple]:
    """Return (company, email_subject) pairs already logged, for secondary dedup."""
    worksheet = spreadsheet.sheet1
    try:
        companies = worksheet.col_values(2)   # column B: company
        subjects = worksheet.col_values(7)    # column G: email_subject
        # Pad shorter list and skip header row
        pairs = zip(companies[1:], subjects[1:])
        return {(c.strip().lower(), s.strip().lower()) for c, s in pairs if c and s}
    except Exception as e:
        print(f"\n[ERROR] Could not read existing subject keys: {e}", file=sys.stderr)
        sys.exit(1)


def get_latest_date(spreadsheet: gspread.Spreadsheet) -> date | None:
    """Return the most recent date_applied from the sheet, or None if empty."""
    worksheet = spreadsheet.sheet1
    try:
        values = worksheet.col_values(4)  # column D: date_applied
        dates = []
        for v in values[1:]:  # skip header
            try:
                dates.append(date.fromisoformat(v))
            except ValueError:
                continue
        return max(dates) if dates else None
    except Exception as e:
        print(f"\n[ERROR] Could not read latest date from sheet: {e}", file=sys.stderr)
        sys.exit(1)


def append_applications(
    spreadsheet: gspread.Spreadsheet,
    applications: list[JobApplication],
) -> None:
    """Append new job application rows to the sheet, writing header if sheet is empty."""
    if not applications:
        return
    worksheet = spreadsheet.sheet1
    try:
        if worksheet.acell("A1").value != "thread_id":
            worksheet.append_row(JobApplication.sheet_headers(), value_input_option="RAW")
        rows = [app.to_sheet_row() for app in applications]
        worksheet.append_rows(rows, value_input_option="RAW")
    except Exception as e:
        print(f"\n[ERROR] Failed to write rows to Google Sheet: {e}", file=sys.stderr)
        sys.exit(1)
