from datetime import date, datetime
from pydantic import BaseModel


class JobApplication(BaseModel):
    thread_id: str
    company: str
    job_title: str = "Unknown"
    date_applied: date
    email_type: str = "Unknown"
    ats_provider: str
    email_subject: str
    thread_link: str
    date_logged: datetime

    def to_sheet_row(self) -> list:
        return [
            self.thread_id,
            self.company,
            self.job_title,
            self.date_applied.isoformat(),
            self.email_type,
            self.ats_provider,
            self.email_subject,
            self.thread_link,
            self.date_logged.isoformat(),
        ]

    @classmethod
    def sheet_headers(cls) -> list:
        return [
            "thread_id",
            "company",
            "job_title",
            "date_applied",
            "email_type",
            "ats_provider",
            "email_subject",
            "thread_link",
            "date_logged",
        ]
