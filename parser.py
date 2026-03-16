import re
from datetime import date, datetime, timezone

# --- ATS provider detection ---

ATS_DOMAINS = {
    "lever.co": "Lever",
    "greenhouse.io": "Greenhouse",
    "myworkday.com": "Workday",
    "icims.com": "iCIMS",
    "smartrecruiters.com": "SmartRecruiters",
    "jobvite.com": "Jobvite",
    "taleo.net": "Taleo",
    "successfactors.com": "SAP SuccessFactors",
    "bamboohr.com": "BambooHR",
    "ashbyhq.com": "Ashby",
    "recruitee.com": "Recruitee",
    "workable.com": "Workable",
    "breezy.hr": "Breezy HR",
    "jazz.co": "JazzHR",
    "applytojob.com": "ApplyToJob",
}

def detect_ats_provider(from_header: str) -> str:
    """Detect ATS provider from the sender email domain."""
    match = re.search(r"@([\w.\-]+)", from_header)
    if not match:
        return "Unknown"
    domain = match.group(1).lower()
    for ats_domain, name in ATS_DOMAINS.items():
        if domain.endswith(ats_domain):
            return name
    return "Unknown"


# --- Company name extraction ---

# Ordered from most to least specific
# Stop words that signal end of company name
_STOP = r"(?:\s*(?:[!\-,|]|\bhas\b|\bhave\b|\bwill\b|\bis\b|\bfor\b)|$)"

COMPANY_PATTERNS = [
    r"thank you for applying to (.+?)" + _STOP,
    r"thanks for applying to (.+?)" + _STOP,
    r"your application to (.+?)" + _STOP,
    r"application (?:received|submitted)(?: by)?(?: at)? (.+?)" + _STOP,
    r"we received your application(?: at| for| to)? (.+?)" + _STOP,
    r"you applied (?:to|at) (.+?)" + _STOP,
    r"(.+?) (?:has received|received) your application",
]

def extract_company(subject: str, from_header: str) -> str:
    """Extract company name from subject line, falling back to sender name."""
    for pattern in COMPANY_PATTERNS:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            company = match.group(1).strip().rstrip(".")
            if company:
                return company

    # Fall back to the display name in the From header (e.g. "Lever <noreply@lever.co>")
    name_match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
    if name_match:
        return name_match.group(1).strip()

    return "Unknown"


# --- Job title extraction ---

JOB_TITLE_PATTERNS = [
    r"(?:position|role|job|opening):\s+([^\n,|!.]{3,60})",
    r"\bapplied (?:for(?: the)?|to)(?: the)? (.+?)(?:\s*(?:\b(?:position|role|job)\b|\bat\b|@|\|))",
    r"\bapplication for(?: the)? (.+?)(?:\s*(?:\b(?:position|role|job)\b|\bat\b|@|\|)|$)",
    r"\b(?:re|regarding):\s+(.+?)(?:\s*\bat\b\s+|\s*[-|]\s*|\s*$)",
]

DEFAULT_JOB_TITLE = "Unknown"

def extract_job_title(subject: str, snippet: str) -> str:
    """
    Attempt to extract a job title from the subject line and body snippet.
    Falls back to DEFAULT_JOB_TITLE if nothing is found.
    Only uses snippet (Gmail's ~100 char preview) — never the full body.
    """
    for text in (subject, snippet):
        for pattern in JOB_TITLE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip().rstrip(".,!")
                # Sanity check: ignore if too short or looks like boilerplate
                if len(title) > 3 and not re.match(r"^(your|the|a|an|our)\b", title, re.I):
                    return title
    return DEFAULT_JOB_TITLE


# --- Date parsing ---

def parse_internal_date(internal_date_ms: str) -> date:
    """Convert Gmail's internalDate (epoch ms string) to a date object."""
    ts = int(internal_date_ms) / 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()
