import base64
from unittest.mock import MagicMock, patch

from outreach_agent.gmail_client import GmailClient, build_raw_message


def test_build_raw_message_returns_base64_with_to_subject_body():
    raw = build_raw_message(to="bob@bobs.ca", subject="hey bob",
                             body="line one\nline two")
    decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
    assert "To: bob@bobs.ca" in decoded
    assert "Subject: hey bob" in decoded
    assert "line one" in decoded
    assert "line two" in decoded


def test_build_raw_message_handles_empty_to_field():
    """When email is empty (form-only lead), still produces a valid message."""
    raw = build_raw_message(to="", subject="s", body="b")
    decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
    assert "Subject: s" in decoded
    assert "b" in decoded


def test_create_draft_calls_gmail_api_and_returns_id():
    fake_create = MagicMock()
    fake_create.execute.return_value = {"id": "r-12345", "message": {"id": "m-1"}}
    fake_drafts = MagicMock()
    fake_drafts.create.return_value = fake_create
    fake_users = MagicMock()
    fake_users.drafts.return_value = fake_drafts
    fake_service = MagicMock()
    fake_service.users.return_value = fake_users

    client = GmailClient(service=fake_service)
    draft_id = client.create_draft(to="bob@bobs.ca", subject="hey",
                                     body="hi")
    assert draft_id == "r-12345"
    fake_drafts.create.assert_called_once()
    kwargs = fake_drafts.create.call_args.kwargs
    assert kwargs["userId"] == "me"
    assert "raw" in kwargs["body"]["message"]
