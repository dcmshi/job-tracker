"""
Test suite for parser.py, models.py, scanner.py, classifier.py, and main.py logic.
Run with: uv run python tests.py
"""

import sys
import argparse
import base64
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from parser import detect_ats_provider, extract_company, extract_job_title, parse_internal_date
from models import JobApplication
from scanner import _extract_text_from_payload
from classifier import classify_and_extract, EMAIL_TYPES
from main import parse_date

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

failures = 0


def check(label: str, got, expected):
    global failures
    if got == expected:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}")
        print(f"         expected: {expected!r}")
        print(f"         got:      {got!r}")
        failures += 1


def check_true(label: str, condition: bool):
    check(label, condition, True)


# ---------------------------------------------------------------------------
# ATS Provider Detection
# ---------------------------------------------------------------------------
print("\n=== ATS Provider Detection ===")
check("Lever subdomain",        detect_ats_provider("no-reply@hire.lever.co"),       "Lever")
check("Greenhouse direct",      detect_ats_provider("jobs@greenhouse.io"),            "Greenhouse")
check("Workday",                detect_ats_provider("noreply@myworkday.com"),         "Workday")
check("iCIMS",                  detect_ats_provider("apply@icims.com"),               "iCIMS")
check("SmartRecruiters",        detect_ats_provider("hr@smartrecruiters.com"),        "SmartRecruiters")
check("Ashby",                  detect_ats_provider("jobs@ashbyhq.com"),              "Ashby")
check("Unknown company domain", detect_ats_provider("hr@amazon.com"),                "Unknown")
check("No @ symbol",            detect_ats_provider("invalid-header"),               "Unknown")

# ---------------------------------------------------------------------------
# Company Extraction
# ---------------------------------------------------------------------------
print("\n=== Company Extraction ===")
check("Thank you for applying to",        extract_company("Thank you for applying to Acme Corp!", ""),              "Acme Corp")
check("Thanks for applying to",           extract_company("Thanks for applying to Stripe", ""),                     "Stripe")
check("Your application to ... received", extract_company("Your application to Google has been received", ""),      "Google")
check("Company has received",             extract_company("Acme Corp has received your application", ""),           "Acme Corp")
check("Application received at",          extract_company("Application received at Meta", ""),                      "Meta")
check("We received your application at",  extract_company("We received your application at Stripe", ""),            "Stripe")
check("You applied to",                   extract_company("You applied to OpenAI for a role", ""),                  "OpenAI")
check("From header fallback",             extract_company("Unrecognised subject line", "Lever <noreply@lever.co>"), "Lever")
check("Unknown fallback",                 extract_company("Unrecognised subject line", "noreply@random.com"),       "Unknown")

# ---------------------------------------------------------------------------
# Job Title Extraction
# ---------------------------------------------------------------------------
print("\n=== Job Title Extraction ===")
check("From snippet: applied for ... position",
      extract_job_title("Thank you for applying",
                        "applied for the Senior Backend Engineer position at Stripe"),
      "Senior Backend Engineer")

check("From subject: application for ... role",
      extract_job_title("Application for the Data Scientist role", ""),
      "Data Scientist")

check("From subject: Re: title at company",
      extract_job_title("Re: Software Engineer at Acme", ""),
      "Software Engineer")

check("From subject: position: Title",
      extract_job_title("Position: Machine Learning Engineer", ""),
      "Machine Learning Engineer")

check("No title found — default",
      extract_job_title("Application received", "no title here just thanks"),
      "Unknown")

check("Snippet: application for ... at",
      extract_job_title("Thank you",
                        "your application for the Product Manager role at Uber"),
      "Product Manager")

# ---------------------------------------------------------------------------
# Date Parsing (parser.py)
# ---------------------------------------------------------------------------
print("\n=== Date Parsing ===")
# 2026-01-15 00:00:00 UTC = 1768435200000 ms
check("Epoch ms to date",
      parse_internal_date("1768435200000"),
      date(2026, 1, 15))

check("Recent date",
      parse_internal_date("1741996800000"),  # 2025-03-15 UTC
      date(2025, 3, 15))

# ---------------------------------------------------------------------------
# JobApplication Model (models.py)
# ---------------------------------------------------------------------------
print("\n=== JobApplication Model ===")

sample = JobApplication(
    thread_id="abc123",
    company="Acme Corp",
    job_title="Senior Engineer",
    date_applied=date(2026, 2, 1),
    email_type="Application Confirmation",
    ats_provider="Lever",
    email_subject="Thank you for applying to Acme Corp",
    thread_link="https://mail.google.com/mail/u/0/#all/abc123",
    date_logged=datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
)

check("sheet_headers length",     len(JobApplication.sheet_headers()), 9)
check("sheet_headers first col",  JobApplication.sheet_headers()[0],   "thread_id")
check("sheet_headers email_type", JobApplication.sheet_headers()[4],   "email_type")
check("sheet_headers last col",   JobApplication.sheet_headers()[-1],  "date_logged")

row = sample.to_sheet_row()
check("to_sheet_row length",      len(row),    9)
check("to_sheet_row thread_id",   row[0],      "abc123")
check("to_sheet_row company",     row[1],      "Acme Corp")
check("to_sheet_row job_title",   row[2],      "Senior Engineer")
check("to_sheet_row date",        row[3],      "2026-02-01")
check("to_sheet_row email_type",  row[4],      "Application Confirmation")
check("to_sheet_row ats",         row[5],      "Lever")

check("default job_title",
      JobApplication(
          thread_id="x", company="Y", date_applied=date(2026,1,1),
          ats_provider="Z", email_subject="S", thread_link="L",
          date_logged=datetime.now(tz=timezone.utc),
      ).job_title,
      "Unknown")

check("default email_type",
      JobApplication(
          thread_id="x", company="Y", date_applied=date(2026,1,1),
          ats_provider="Z", email_subject="S", thread_link="L",
          date_logged=datetime.now(tz=timezone.utc),
      ).email_type,
      "Unknown")

# ---------------------------------------------------------------------------
# Email Body Extraction (scanner.py)
# ---------------------------------------------------------------------------
print("\n=== Email Body Extraction ===")

def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()

check("Plain text payload",
      _extract_text_from_payload({
          "mimeType": "text/plain",
          "body": {"data": _b64("Thank you for applying to Acme for the role of Data Engineer.")},
      }),
      "Thank you for applying to Acme for the role of Data Engineer.")

check("HTML payload strips tags",
      _extract_text_from_payload({
          "mimeType": "text/html",
          "body": {"data": _b64("<p>Thank you for <b>applying</b> to Acme.</p>")},
      }).strip(),
      "Thank you for  applying  to Acme.")

check("Multipart prefers plain over html",
      _extract_text_from_payload({
          "mimeType": "multipart/alternative",
          "parts": [
              {"mimeType": "text/plain", "body": {"data": _b64("Plain text body.")}},
              {"mimeType": "text/html",  "body": {"data": _b64("<p>HTML body.</p>")}},
          ],
      }),
      "Plain text body.")

check("Empty payload returns empty string",
      _extract_text_from_payload({}),
      "")

# ---------------------------------------------------------------------------
# CLI Date Parser (main.py)
# ---------------------------------------------------------------------------
print("\n=== CLI Date Parser ===")
check("Valid date",   parse_date("2026-03-15"), date(2026, 3, 15))
check("Start of year",parse_date("2026-01-01"), date(2026, 1, 1))

try:
    parse_date("not-a-date")
    check("Invalid date raises", False, True)
except argparse.ArgumentTypeError:
    check("Invalid date raises ArgumentTypeError", True, True)

# ---------------------------------------------------------------------------
# Classifier (classifier.py) — mocked, no real API calls
# ---------------------------------------------------------------------------
print("\n=== Classifier (mocked) ===")

_valid_response = {
    "is_job_related": True,
    "email_type": "Application Confirmation",
    "company": "Acme Corp",
    "job_title": "Data Engineer",
    "ats_provider": "Greenhouse",
}

_false_positive_response = {
    "is_job_related": False,
    "email_type": "Other",
    "company": None,
    "job_title": None,
    "ats_provider": None,
}

def _mock_client(response_dict):
    mock_response = MagicMock()
    mock_response.text = str(response_dict).replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client

import json

with patch("classifier.genai.Client") as MockClient:
    MockClient.return_value.models.generate_content.return_value.text = json.dumps(_valid_response)
    result = classify_and_extract("Thank you for applying", "jobs@greenhouse.io", "snippet", "fake-key", "body text")
    check("Valid response: is_job_related",  result["is_job_related"], True)
    check("Valid response: email_type",      result["email_type"],     "Application Confirmation")
    check("Valid response: company",         result["company"],        "Acme Corp")
    check("Valid response: job_title",       result["job_title"],      "Data Engineer")
    check("Valid response: ats_provider",    result["ats_provider"],   "Greenhouse")

with patch("classifier.genai.Client") as MockClient:
    MockClient.return_value.models.generate_content.return_value.text = json.dumps(_false_positive_response)
    result = classify_and_extract("Build your app today", "noreply@heroku.com", "snippet", "fake-key")
    check("False positive: is_job_related",  result["is_job_related"], False)

with patch("classifier.genai.Client") as MockClient:
    MockClient.return_value.models.generate_content.side_effect = Exception("API error")
    result = classify_and_extract("subject", "from", "snippet", "fake-key")
    check("API failure returns None",        result, None)

check_true("All email_types are strings", all(isinstance(t, str) for t in EMAIL_TYPES))
check("EMAIL_TYPES count", len(EMAIL_TYPES), 7)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
if failures == 0:
    print(f"\033[92mAll tests passed.\033[0m\n")
else:
    print(f"\033[91m{failures} test(s) failed.\033[0m\n")
    sys.exit(1)
