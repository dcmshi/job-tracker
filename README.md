# Job Application Tracker

A CLI tool that scans your Gmail for job application confirmation emails and logs them to Google Sheets for organised tracking.

Each entry captures: company, job title, date applied, ATS provider, email subject, a direct Gmail thread link, and the date it was logged.

---

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- A Google account with Gmail

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Create Google Cloud credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the following APIs:
   - **Gmail API**
   - **Google Sheets API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Set application type to **Desktop app**
6. Download the JSON file and save it as `credentials.json` in this directory

> See `credentials.template.json` for the expected file structure.

### 3. Authenticate

```bash
uv run python main.py --auth
```

This opens a browser window. Sign in and approve access. A `token.json` file will be saved locally for future runs.

> **Note:** You may see an "unverified app" warning — this is expected for personal Google Cloud projects. Click **Advanced → Go to [project] (unsafe)** to proceed.

### 4. Run your first scan

```bash
uv run python main.py --scan
```

On first run, this will:
- Create a new Google Sheet named **"Job Application Tracker"**
- Print its URL
- Save the Sheet ID to `config.json` for future runs
- Populate it with all matching emails from **January 1, 2026** onward

---

## Usage

```bash
# Incremental scan (picks up from latest date in sheet)
uv run python main.py --scan

# Scan from a specific date
uv run python main.py --scan --since 2026-02-01

# Write to local JSON file instead of Google Sheets
uv run python main.py --scan --local

# Re-run OAuth flow (e.g. if token expires)
uv run python main.py --auth
```

---

## Output

Results are written to your Google Sheet with the following columns:

| Column | Field | Notes |
|--------|-------|-------|
| A | `thread_id` | Unique dedup key |
| B | `company` | Parsed from subject/sender — defaults to `Unknown` |
| C | `job_title` | Extracted from body snippet — defaults to `Unknown` |
| D | `date_applied` | Date of the email |
| E | `ats_provider` | Detected from sender domain — defaults to `Unknown` |
| F | `email_subject` | Raw subject line |
| G | `thread_link` | Direct Gmail link to the thread |
| H | `date_logged` | Timestamp when the scanner added this row |

---

## Files

| File | Description |
|------|-------------|
| `credentials.json` | Your Google OAuth client secret (**gitignored**, never commit) |
| `credentials.template.json` | Setup instructions and expected JSON structure |
| `token.json` | Auto-generated OAuth token (**gitignored**) |
| `config.json` | Stores your Sheet ID after first run (**gitignored**) |
| `applications_log.json` | Local fallback log when using `--local` (**gitignored**) |

---

## Running Tests

```bash
uv run python tests.py
```
