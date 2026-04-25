import json
from unittest.mock import MagicMock, patch

import pytest

from outreach_agent.draft_writer import build_user_prompt, write_draft
from outreach_agent.models import EligibleLead


def _lead(**overrides) -> EligibleLead:
    defaults = dict(
        row_number=2, business_name="Bob's Plumbing", niche="plumbers",
        city="Burnaby BC", website="https://bobs.ca",
        email_guess="bob@bobs.ca", contact_form_url="",
        owner_name_guess="Bob Smith", site_score=7,
        site_evidence="No HTTPS; pre-2015 aesthetic",
        lead_pitch="Mobile-broken site, 127 reviews — real business.",
        tier="hot",
    )
    defaults.update(overrides)
    return EligibleLead(**defaults)


def test_build_user_prompt_includes_lead_facts_and_truncates_html():
    lead = _lead()
    prompt = build_user_prompt(lead, html="<html>" + "x" * 200_000 + "</html>")
    assert "Bob's Plumbing" in prompt
    assert "Bob Smith" in prompt
    assert "https://bobs.ca" in prompt
    assert "Mobile-broken site" in prompt
    assert len(prompt) < 150_000


def _openrouter_response(content: str, status: int = 200, body: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    if body is not None:
        resp.text = body
        resp.json.side_effect = json.JSONDecodeError("no", body, 0)
    else:
        payload = {"choices": [{"message": {"content": content}}]}
        resp.text = json.dumps(payload)
        resp.json.return_value = payload
    return resp


@pytest.fixture(autouse=True)
def _set_openrouter_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")


def test_write_draft_parses_draft_action():
    content = json.dumps({
        "action": "draft",
        "subject": "Noticed something on bobs.ca",
        "body": "Hey Bob,\n\n...\n\nIshan",
        "skip_reason": "",
    })
    with patch("outreach_agent.draft_writer.httpx.post",
               return_value=_openrouter_response(content)):
        result = write_draft(lead=_lead(), html="<html/>", system_prompt="SYS")
    assert result.is_draft()
    assert result.subject == "Noticed something on bobs.ca"
    assert "Hey Bob" in result.body


def test_write_draft_parses_skip_action():
    content = json.dumps({
        "action": "skip", "subject": "", "body": "",
        "skip_reason": "site is in punjabi only",
    })
    with patch("outreach_agent.draft_writer.httpx.post",
               return_value=_openrouter_response(content)):
        result = write_draft(lead=_lead(), html="<html/>", system_prompt="SYS")
    assert result.is_skip()
    assert "punjabi" in result.skip_reason


def test_write_draft_strips_markdown_fences():
    content = "```json\n" + json.dumps({
        "action": "draft", "subject": "S", "body": "B", "skip_reason": "",
    }) + "\n```"
    with patch("outreach_agent.draft_writer.httpx.post",
               return_value=_openrouter_response(content)):
        result = write_draft(lead=_lead(), html="<html/>", system_prompt="SYS")
    assert result.is_draft()
    assert result.subject == "S"


def test_write_draft_sends_system_and_user_messages():
    content = json.dumps({
        "action": "skip", "subject": "", "body": "", "skip_reason": "test",
    })
    with patch("outreach_agent.draft_writer.httpx.post",
               return_value=_openrouter_response(content)) as mock_post:
        write_draft(lead=_lead(), html="<html/>", system_prompt="MY_SYSTEM_PROMPT")
    sent = mock_post.call_args.kwargs["json"]
    assert sent["model"] == "google/gemini-2.5-flash"
    assert sent["messages"][0]["role"] == "system"
    assert sent["messages"][0]["content"] == "MY_SYSTEM_PROMPT"
    assert sent["messages"][1]["role"] == "user"
    auth = mock_post.call_args.kwargs["headers"]["Authorization"]
    assert auth == "Bearer sk-or-test"


def test_write_draft_raises_on_non_200():
    with patch("outreach_agent.draft_writer.httpx.post",
               return_value=_openrouter_response("", status=429, body="rate limited")):
        with pytest.raises(RuntimeError, match="HTTP 429.*rate limited"):
            write_draft(lead=_lead(), html="<html/>", system_prompt="X")


def test_write_draft_raises_on_bad_json():
    bad = MagicMock()
    bad.status_code = 200
    bad.text = "not json"
    bad.json.side_effect = json.JSONDecodeError("no", "not json", 0)
    with patch("outreach_agent.draft_writer.httpx.post", return_value=bad):
        with pytest.raises(RuntimeError, match="unparseable"):
            write_draft(lead=_lead(), html="<html/>", system_prompt="X")
