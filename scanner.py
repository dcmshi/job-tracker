import base64
import re
from datetime import date, datetime, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from models import JobApplication
from parser import detect_ats_provider, extract_company, extract_job_title, parse_internal_date

# Broad query to capture all job search related emails.
# Gemini handles false positive filtering and email_type classification.
GMAIL_QUERY = (
    'subject:('
    '"thank you for applying" OR "thanks for applying" OR '
    '"application received" OR "application confirmation" OR "application submitted" OR '
    '"your application" OR "we received your application" OR '
    '"interview" OR "phone screen" OR "video call" OR '
    '"job opportunity" OR "open role" OR "new role" OR "exciting opportunity" OR '
    '"offer letter" OR "job offer" OR '
    '"unfortunately" OR "other candidates" OR "not moving forward" OR '
    '"coding challenge" OR "technical assessment" OR "take-home" OR '
    '"recruiter" OR "hiring manager"'
    ')'
)
THREAD_LINK_BASE = "https://mail.google.com/mail/u/0/#all/"


def build_gmail_service(creds: Credentials):
    return build("gmail", "v1", credentials=creds)


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch_applications(
    creds: Credentials,
    since: date,
    existing_thread_ids: set[str],
    gemini_api_key: str | None = None,
    existing_subject_keys: set[tuple] | None = None,
) -> list[JobApplication]:
    """
    Query Gmail for job application emails since `since`,
    skipping any thread IDs already in `existing_thread_ids`.
    Also deduplicates on (company, email_subject) to catch same-subject threads.

    If gemini_api_key is provided, all emails are passed through Gemini Flash
    for email_type classification and false-positive filtering.
    """
    service = build_gmail_service(creds)
    since_str = since.strftime("%Y/%m/%d")
    query = f"{GMAIL_QUERY} after:{since_str}"

    print(f"Querying Gmail: {query}")

    messages = _list_all_messages(service, query)
    print(f"Found {len(messages)} matching messages.")

    applications: list[JobApplication] = []
    seen_threads: set[str] = set(existing_thread_ids)
    seen_subject_keys: set[tuple] = set(existing_subject_keys or set())
    llm_calls = 0
    skipped_false_positives = 0
    skipped_dupes = 0

    for msg_stub in messages:
        thread_id = msg_stub["threadId"]

        if thread_id in seen_threads:
            continue
        seen_threads.add(thread_id)

        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_stub["id"], format="metadata",
                 metadataHeaders=["Subject", "From", "Date"])
            .execute(num_retries=2)
        )

        headers = msg.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject")
        from_header = _get_header(headers, "From")
        snippet = msg.get("snippet", "")
        internal_date = msg.get("internalDate", "0")

        company = extract_company(subject, from_header)
        job_title = extract_job_title(subject, snippet)
        ats_provider = detect_ats_provider(from_header)
        email_type = "Unknown"

        # Always call Gemini when key is available — needed for email_type
        # classification and false positive filtering on the broader query
        if gemini_api_key:
            from classifier import classify_and_extract
            body = _get_email_body(service, msg_stub["id"])
            result = classify_and_extract(subject, from_header, snippet, gemini_api_key, body)
            llm_calls += 1

            if result is not None:
                if not result.get("is_job_related", True):
                    print(f"  [SKIP] False positive filtered: {subject!r}")
                    skipped_false_positives += 1
                    continue

                company = result.get("company") or company
                job_title = result.get("job_title") or job_title
                ats_provider = result.get("ats_provider") or ats_provider
                email_type = result.get("email_type") or email_type

        subject_key = (company.strip().lower(), subject.strip().lower())
        if subject_key in seen_subject_keys:
            print(f"  [SKIP] Duplicate subject filtered: {subject!r}")
            skipped_dupes += 1
            continue
        seen_subject_keys.add(subject_key)

        app = JobApplication(
            thread_id=thread_id,
            company=company or "Unknown",
            job_title=job_title or "Unknown",
            date_applied=parse_internal_date(internal_date),
            email_type=email_type,
            ats_provider=ats_provider or "Unknown",
            email_subject=subject,
            thread_link=f"{THREAD_LINK_BASE}{thread_id}",
            date_logged=datetime.now(tz=timezone.utc),
        )
        applications.append(app)

    if gemini_api_key:
        print(f"[INFO] Gemini used for {llm_calls} email(s), {skipped_false_positives} false positive(s) and {skipped_dupes} duplicate(s) filtered.")

    applications.sort(key=lambda a: a.date_applied)
    return applications


def _get_email_body(service, msg_id: str) -> str:
    """
    Fetch the plain text body of an email for job title extraction only.
    Prefers text/plain, falls back to stripping HTML from text/html.
    The body is never logged or stored — used transiently for extraction.
    """
    try:
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute(num_retries=2)
        payload = msg.get("payload", {})
        return _extract_text_from_payload(payload)
    except Exception:
        return ""


def _extract_text_from_payload(payload: dict) -> str:
    """Recursively extract plain text from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    parts = payload.get("parts", [])

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")

    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
        # Strip tags to get plain text
        return re.sub(r"<[^>]+>", " ", html)

    # Recurse into multipart — prefer text/plain parts
    plain = ""
    for part in parts:
        text = _extract_text_from_payload(part)
        if part.get("mimeType") == "text/plain" and text:
            return text
        plain = plain or text

    return plain


def _list_all_messages(service, query: str) -> list[dict]:
    """Page through all messages matching the query and return stubs."""
    results = []
    page_token = None

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token

        response = service.users().messages().list(**kwargs).execute(num_retries=2)
        results.extend(response.get("messages", []))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results
