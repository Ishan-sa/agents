from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def build_raw_message(to: str, subject: str, body: str) -> str:
    """Return a base64-urlsafe-encoded RFC 2822 message for Gmail API."""
    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")


class GmailClient:
    def __init__(self, service):
        self._service = service

    @classmethod
    def from_token(cls, token_path: Path) -> "GmailClient":
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return cls(service=service)

    def create_draft(self, to: str, subject: str, body: str) -> str:
        raw = build_raw_message(to=to, subject=subject, body=body)
        resp = self._service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()
        return resp["id"]
