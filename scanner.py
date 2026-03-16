from datetime import date, datetime, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from models import JobApplication
from parser import detect_ats_provider, extract_company, extract_job_title, parse_internal_date

GMAIL_QUERY = (
    'subject:("application" OR "received" OR "thank you for applying" OR "thanks for applying")'
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
) -> list[JobApplication]:
    """
    Query Gmail for job application emails since `since`,
    skipping any thread IDs already in `existing_thread_ids`.
    Returns a list of parsed JobApplication objects.
    """
    service = build_gmail_service(creds)
    since_str = since.strftime("%Y/%m/%d")
    query = f"{GMAIL_QUERY} after:{since_str}"

    print(f"Querying Gmail: {query}")

    messages = _list_all_messages(service, query)
    print(f"Found {len(messages)} matching messages.")

    applications: list[JobApplication] = []
    seen_threads: set[str] = set(existing_thread_ids)

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
            .execute()
        )

        headers = msg.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject")
        from_header = _get_header(headers, "From")
        snippet = msg.get("snippet", "")
        internal_date = msg.get("internalDate", "0")

        app = JobApplication(
            thread_id=thread_id,
            company=extract_company(subject, from_header),
            job_title=extract_job_title(subject, snippet),
            date_applied=parse_internal_date(internal_date),
            ats_provider=detect_ats_provider(from_header),
            email_subject=subject,
            thread_link=f"{THREAD_LINK_BASE}{thread_id}",
            date_logged=datetime.now(tz=timezone.utc),
        )
        applications.append(app)

    applications.sort(key=lambda a: a.date_applied)
    return applications


def _list_all_messages(service, query: str) -> list[dict]:
    """Page through all messages matching the query and return stubs."""
    results = []
    page_token = None

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token

        response = service.users().messages().list(**kwargs).execute()
        results.extend(response.get("messages", []))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results
