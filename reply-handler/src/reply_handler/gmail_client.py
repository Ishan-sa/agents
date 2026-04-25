from __future__ import annotations

import base64
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# gmail.modify covers reading messages, modifying labels, AND creating drafts
# (including in-thread). gmail.compose alone can't read messages.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass(frozen=True)
class SentMessage:
    """The result of looking up a sent draft. Used by sync-sent."""

    message_id: str       # Gmail's internal message id
    thread_id: str
    rfc822_message_id: str  # the Message-ID: header — useful for In-Reply-To
    sent_at_epoch_ms: int


@dataclass(frozen=True)
class InboundReply:
    """A message in a thread that was received from the prospect (not from us)."""

    message_id: str
    thread_id: str
    from_address: str
    subject: str
    body_text: str
    received_at_epoch_ms: int
    rfc822_message_id: str
    headers: dict[str, str]   # lowercase keys


def _b64url_encode(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def _b64url_decode(s: str) -> bytes:
    # Gmail sometimes omits padding
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _extract_text_from_payload(payload: dict) -> str:
    """Walk a Gmail message payload and concat any text/plain parts."""
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    if mime == "text/plain" and data:
        try:
            return _b64url_decode(data).decode("utf-8", errors="replace")
        except Exception:
            return ""

    parts = payload.get("parts") or []
    chunks: list[str] = []
    for p in parts:
        chunks.append(_extract_text_from_payload(p))
    out = "\n".join(c for c in chunks if c)
    if out:
        return out

    # Fallback: text/html if no text/plain anywhere
    if mime == "text/html" and data:
        try:
            html = _b64url_decode(data).decode("utf-8", errors="replace")
            # crude: strip tags
            import re
            return re.sub(r"<[^>]+>", " ", html)
        except Exception:
            return ""
    return ""


def _headers_dict(payload: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", []) if "name" in h and "value" in h}


def build_raw_reply(
    *,
    to: str,
    subject: str,
    body: str,
    in_reply_to_message_id: str,
    references: str,
) -> str:
    """RFC 2822 message bytes (base64-urlsafe encoded) with proper threading
    headers so Gmail nests the draft under the original thread."""
    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    if in_reply_to_message_id:
        msg["In-Reply-To"] = in_reply_to_message_id
    if references:
        msg["References"] = references
    return _b64url_encode(msg.as_bytes())


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

    # ---- draft lifecycle ----

    def draft_exists(self, draft_id: str) -> bool:
        """True if the draft is still in Drafts (i.e. has not been sent or
        deleted)."""
        try:
            self._service.users().drafts().get(userId="me", id=draft_id).execute()
            return True
        except HttpError as e:
            if e.resp.status in (404, 410):
                return False
            raise

    def find_sent_message_for_draft(
        self, *, draft_id: str, to_address: str, subject: str
    ) -> SentMessage | None:
        """A sent draft disappears from Drafts and shows up in Sent under a new
        message id. We can't look the draft up by id (404), so search Sent for
        a message that matches the recipient + subject and return the most
        recent one. The caller has already verified the draft is gone."""
        # 1: search Sent for a candidate match
        # Gmail query operators:
        #   to:foo@example.com  subject:"..."  in:sent
        # Quote subject so spaces parse, escape any double-quotes inside it.
        safe_subject = subject.replace('"', '\\"').strip()
        query_parts = ["in:sent"]
        if to_address:
            query_parts.append(f"to:{to_address}")
        if safe_subject:
            query_parts.append(f'subject:"{safe_subject}"')
        query = " ".join(query_parts)

        resp = (
            self._service.users()
            .messages()
            .list(userId="me", q=query, maxResults=5)
            .execute()
        )
        msgs = resp.get("messages") or []
        if not msgs:
            return None

        # take the most recent (first in list is the newest)
        meta = (
            self._service.users()
            .messages()
            .get(userId="me", id=msgs[0]["id"], format="metadata",
                 metadataHeaders=["Message-ID", "Date", "Subject", "To"])
            .execute()
        )
        headers = _headers_dict(meta.get("payload", {}))
        rfc_id = headers.get("message-id", "")
        internal = int(meta.get("internalDate", "0"))
        return SentMessage(
            message_id=meta["id"],
            thread_id=meta["threadId"],
            rfc822_message_id=rfc_id,
            sent_at_epoch_ms=internal,
        )

    # ---- thread / reply detection ----

    def get_thread(self, thread_id: str) -> dict:
        return (
            self._service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )

    def latest_inbound_message(
        self, *, thread_id: str, our_message_id: str
    ) -> InboundReply | None:
        """Return the most recent message in the thread that came FROM the
        prospect (not from us). `our_message_id` is the Gmail id of the email
        we sent — anything after it that's not labeled SENT counts as inbound."""
        thread = self.get_thread(thread_id)
        messages = thread.get("messages") or []
        # find the index of our outbound and look at messages strictly after it
        try:
            our_idx = next(
                i for i, m in enumerate(messages) if m["id"] == our_message_id
            )
        except StopIteration:
            our_idx = -1

        candidates = messages[our_idx + 1 :] if our_idx >= 0 else messages

        # walk in reverse so we get the newest inbound first
        for m in reversed(candidates):
            label_ids = set(m.get("labelIds") or [])
            if "SENT" in label_ids:
                continue  # skip our own follow-ups
            payload = m.get("payload") or {}
            headers = _headers_dict(payload)
            return InboundReply(
                message_id=m["id"],
                thread_id=m["threadId"],
                from_address=headers.get("from", ""),
                subject=headers.get("subject", ""),
                body_text=_extract_text_from_payload(payload),
                received_at_epoch_ms=int(m.get("internalDate", "0")),
                rfc822_message_id=headers.get("message-id", ""),
                headers=headers,
            )
        return None

    # ---- creating drafts ----

    def create_reply_draft(
        self,
        *,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to_message_id: str,
        references: str,
    ) -> str:
        raw = build_raw_reply(
            to=to,
            subject=subject,
            body=body,
            in_reply_to_message_id=in_reply_to_message_id,
            references=references,
        )
        resp = (
            self._service.users()
            .drafts()
            .create(
                userId="me",
                body={"message": {"raw": raw, "threadId": thread_id}},
            )
            .execute()
        )
        return resp["id"]
