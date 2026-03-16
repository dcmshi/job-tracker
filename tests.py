"""
Test suite for parser.py logic.
Run with: uv run python tests.py
"""

import sys
from parser import detect_ats_provider, extract_company, extract_job_title

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
check("Thank you for applying to",       extract_company("Thank you for applying to Acme Corp!", ""),             "Acme Corp")
check("Thanks for applying to",          extract_company("Thanks for applying to Stripe", ""),                    "Stripe")
check("Your application to ... received",extract_company("Your application to Google has been received", ""),     "Google")
check("Company has received",            extract_company("Acme Corp has received your application", ""),          "Acme Corp")
check("Application received at",         extract_company("Application received at Meta", ""),                     "Meta")
check("We received your application at", extract_company("We received your application at Stripe", ""),           "Stripe")
check("You applied to",                  extract_company("You applied to OpenAI for a role", ""),                 "OpenAI")
check("From header fallback",            extract_company("Unrecognised subject line", "Lever <noreply@lever.co>"), "Lever")
check("Unknown fallback",                extract_company("Unrecognised subject line", "noreply@random.com"),      "Unknown")

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
# Summary
# ---------------------------------------------------------------------------
print()
if failures == 0:
    print(f"\033[92mAll tests passed.\033[0m\n")
else:
    print(f"\033[91m{failures} test(s) failed.\033[0m\n")
    sys.exit(1)
