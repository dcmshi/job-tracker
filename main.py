import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from models import JobApplication

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH = Path("token.json")
LOCAL_LOG_PATH = Path("applications_log.json")
DEFAULT_SINCE = date(2026, 1, 1)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


# --- Auth ---

def load_credentials() -> Credentials:
    """Load credentials from token.json, refreshing if expired."""
    if not CREDENTIALS_PATH.exists():
        print(
            "\n[ERROR] credentials.json not found.\n"
            "Follow the instructions in credentials.template.json to set up your Google OAuth credentials.\n"
            "Then run: uv run python main.py --auth",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds

    return None  # needs fresh auth flow


def run_auth_flow() -> Credentials:
    """Run the OAuth2 flow and save token.json."""
    if not CREDENTIALS_PATH.exists():
        print(
            "\n[ERROR] credentials.json not found.\n"
            "Follow the instructions in credentials.template.json first.",
            file=sys.stderr,
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    print("[INFO] Authentication successful. token.json saved.")
    return creds


def _save_token(creds: Credentials) -> None:
    TOKEN_PATH.write_text(creds.to_json())


# --- Local log ---

def load_local_log() -> list[dict]:
    if LOCAL_LOG_PATH.exists():
        return json.loads(LOCAL_LOG_PATH.read_text())
    return []


def save_local_log(applications: list[JobApplication]) -> None:
    existing = load_local_log()
    existing_ids = {entry["thread_id"] for entry in existing}
    new_entries = [
        app.model_dump(mode="json")
        for app in applications
        if app.thread_id not in existing_ids
    ]
    all_entries = existing + new_entries
    LOCAL_LOG_PATH.write_text(json.dumps(all_entries, indent=2, default=str))
    print(f"[INFO] Saved {len(new_entries)} new entries to {LOCAL_LOG_PATH}")


# --- Main ---

def cmd_auth(args) -> None:
    run_auth_flow()


def load_gemini_key() -> str | None:
    """Load Gemini API key from config.json if present."""
    config = json.loads(Path("config.json").read_text()) if Path("config.json").exists() else {}
    key = config.get("gemini_api_key")
    if not key:
        print("[INFO] No gemini_api_key in config.json — skipping LLM enrichment.")
    return key or None


def cmd_scan(args) -> None:
    from scanner import fetch_applications

    # Load credentials
    creds = load_credentials()
    if creds is None:
        print("[INFO] No valid token found. Running auth flow...")
        creds = run_auth_flow()

    gemini_api_key = load_gemini_key()
    use_local = args.local

    # Determine start date
    if use_local:
        # Local mode: check existing log for latest date
        existing_log = load_local_log()
        existing_thread_ids = {entry["thread_id"] for entry in existing_log}
        if args.since:
            since = args.since
        elif existing_log:
            latest = max(
                date.fromisoformat(e["date_applied"])
                for e in existing_log
                if e.get("date_applied")
            )
            print(f"[INFO] Latest date in local log: {latest}. Scanning from that date.")
            since = latest
        else:
            since = DEFAULT_SINCE

        print(f"[INFO] Scanning from {since} (local mode)")
        applications = fetch_applications(creds, since, existing_thread_ids, gemini_api_key)

        if not applications:
            print("[INFO] No new applications found.")
            return

        print(f"[INFO] Found {len(applications)} new application(s).")
        save_local_log(applications)

    else:
        # Sheets mode
        from sheets import open_or_create_sheet, get_existing_thread_ids, get_existing_subject_keys, get_latest_date, append_applications

        spreadsheet = open_or_create_sheet(creds)
        existing_thread_ids = get_existing_thread_ids(spreadsheet)
        existing_subject_keys = get_existing_subject_keys(spreadsheet)

        if args.since:
            since = args.since
        else:
            latest = get_latest_date(spreadsheet)
            if latest:
                print(f"[INFO] Latest date in sheet: {latest}. Scanning from that date.")
                since = latest
            else:
                since = DEFAULT_SINCE

        print(f"[INFO] Scanning from {since}")
        applications = fetch_applications(creds, since, existing_thread_ids, gemini_api_key, existing_subject_keys)

        if not applications:
            print("[INFO] No new applications found.")
            return

        print(f"[INFO] Found {len(applications)} new application(s). Writing to sheet...")
        append_applications(spreadsheet, applications)
        print(f"[INFO] Done. {len(applications)} row(s) added.")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: '{value}'. Use YYYY-MM-DD.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job Application Tracker — scans Gmail and logs applications to Google Sheets."
    )
    subparsers = parser.add_subparsers(dest="command")

    # --auth
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Initialize or refresh OAuth credentials.",
    )

    # --scan
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan Gmail for new job application emails.",
    )
    parser.add_argument(
        "--since",
        type=parse_date,
        metavar="YYYY-MM-DD",
        help="Scan from this date (overrides sheet/log latest date and default).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Write results to local applications_log.json instead of Google Sheets.",
    )

    args = parser.parse_args()

    if args.auth:
        cmd_auth(args)
    elif args.scan:
        cmd_scan(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
