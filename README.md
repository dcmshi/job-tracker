# Job Application Tracker

A CLI tool that scans your Gmail for job search related emails and logs structured data to Google Sheets for organised tracking.

Captures application confirmations, recruiter outreach, interviews, rejections, assessments, and offers — classified automatically using Gemini Flash.

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
   - **Google Drive API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Set application type to **Desktop app**
6. Download the JSON file and save it as `credentials.json` in this directory
7. Go to **APIs & Services → OAuth consent screen → Test users** and add your Gmail address

> See `credentials.template.json` for the expected file structure.

### 3. Get a Gemini API key

1. Go to [aistudio.google.com](https://aistudio.google.com/)
2. Click **Get API key → Create API key**
3. Select your existing Google Cloud project
4. Copy the key and add it to `config.json`:

```json
{
  "gemini_api_key": "YOUR_KEY_HERE"
}
```

> The Gemini key is used to classify email types (Interview, Rejection, etc.) and enrich extraction. The free tier allows 1,500 requests/day — well above typical scan volume.

### 4. Authenticate

```bash
uv run python main.py --auth
```

This opens a browser window. Sign in and approve access. A `token.json` file will be saved locally for future runs.

> **Note:** You may see an "unverified app" warning — this is expected for personal Google Cloud projects. Click **Advanced → Go to [project] (unsafe)** to proceed.

### 5. Run your first scan

```bash
uv run python main.py --scan
```

On first run, this will:
- Create a new Google Sheet named **"Job Application Tracker"**
- Print its URL and save the Sheet ID to `config.json`
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
| B | `company` | Parsed from subject/sender/body — defaults to `Unknown` |
| C | `job_title` | Extracted from email body — defaults to `Unknown` |
| D | `date_applied` | Date of the email |
| E | `email_type` | Classified by Gemini: Application Confirmation, Recruiter Outreach, Interview, Rejection, Assessment, Offer, Other |
| F | `ats_provider` | Detected from sender domain — defaults to `Unknown` |
| G | `email_subject` | Raw subject line |
| H | `thread_link` | Direct Gmail link to the thread |
| I | `date_logged` | Timestamp when the scanner added this row |

---

## Files

| File | Description |
|------|-------------|
| `credentials.json` | Your Google OAuth client secret (**gitignored**, never commit) |
| `credentials.template.json` | Setup instructions and expected JSON structure |
| `token.json` | Auto-generated OAuth token (**gitignored**) |
| `config.json` | Stores Sheet ID and Gemini API key after first run (**gitignored**) |
| `applications_log.json` | Local fallback log when using `--local` (**gitignored**) |

---

## Quick Reference

```bash
# Day-to-day use
uv run python main.py --scan

# Re-scan from a specific date
uv run python main.py --scan --since 2026-01-01

# If token expires
uv run python main.py --auth

# Run tests
uv run python tests.py
```

---

## Running Tests

```bash
uv run python tests.py
```
