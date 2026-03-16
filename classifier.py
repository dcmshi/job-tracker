"""
LLM-based classifier using Gemini Flash.
Called on every email to classify type and filter false positives,
and to enrich company/job_title/ats_provider where regex falls short.
"""

import json
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"

# Valid email_type values
EMAIL_TYPES = [
    "Application Confirmation",
    "Recruiter Outreach",
    "Interview",
    "Rejection",
    "Assessment",
    "Offer",
    "Other",
]

PROMPT = """You are classifying and extracting data from a job search related email.

Subject: {subject}
From: {from_header}
Snippet: {snippet}
Body (truncated): {body}

Respond with a JSON object only — no markdown, no explanation:
{{
  "is_job_related": true or false,
  "email_type": one of {email_types},
  "company": "Company name, or null if not determinable",
  "job_title": "Job title, or null if not mentioned anywhere",
  "ats_provider": "ATS provider name (e.g. Lever, Greenhouse, Workday), or null if unknown"
}}

Rules:
- is_job_related must be false for anything unrelated to a job search (e.g. bank transfers, membership renewals, subscriptions, newsletters, software deployment notices)
- email_type must be one of the exact strings listed above
- "Application Confirmation": ATS or company confirming they received your application
- "Recruiter Outreach": a recruiter or hiring manager reaching out about a role
- "Interview": invitation to interview, scheduling, or interview-related correspondence
- "Rejection": company or recruiter communicating they are not moving forward
- "Assessment": coding challenge, take-home test, or technical assessment request
- "Offer": job offer or offer letter
- "Other": job-related but doesn't fit the above (e.g. follow-up, status update)
- Extract company from subject, sender name, or body
- Extract job title from anywhere in the email — body often has the most detail
- Identify ATS provider from the sender domain if recognisable
- Return null (not the string "null") for fields you cannot determine
"""


def classify_and_extract(
    subject: str,
    from_header: str,
    snippet: str,
    api_key: str,
    body: str = "",
) -> dict:
    """
    Returns a dict with keys:
      is_job_related (bool)
      email_type (str)
      company (str | None)
      job_title (str | None)
      ats_provider (str | None)

    body is used for extraction only — never logged or stored.
    Returns None if the API call fails.
    """
    try:
        client = genai.Client(api_key=api_key)
        prompt = PROMPT.format(
            subject=subject,
            from_header=from_header,
            snippet=snippet,
            body=body[:1000] if body else "(not available)",
            email_types=EMAIL_TYPES,
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        required = {"is_job_related", "email_type", "company", "job_title", "ats_provider"}
        missing = required - set(data.keys())
        if missing:
            print(f"  [WARN] Gemini response missing fields: {missing}")
            return None
        return data
    except json.JSONDecodeError as e:
        print(f"  [WARN] Gemini returned invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"  [WARN] Gemini classification failed: {e}")
        return None
