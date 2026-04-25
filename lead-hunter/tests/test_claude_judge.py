import json
from unittest.mock import patch, MagicMock

import pytest

from lead_hunter.claude_judge import (
    JudgeResult,
    judge_website,
    build_judge_prompt,
)


def test_build_judge_prompt_includes_rubric_and_html():
    prompt = build_judge_prompt(
        business_name="Bob's Plumbing",
        website_url="https://bobsplumbing.ca",
        html="<html><body>We fix pipes</body></html>",
    )
    assert "Bob's Plumbing" in prompt
    assert "bobsplumbing.ca" in prompt
    assert "viewport" in prompt.lower()
    assert "We fix pipes" in prompt


def test_build_judge_prompt_truncates_long_html():
    big_html = "x" * 200_000
    prompt = build_judge_prompt("B", "https://b.com", big_html)
    assert len(prompt) < 150_000


def _openrouter_response(content: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    payload = {"choices": [{"message": {"content": content}}]}
    resp.text = json.dumps(payload)
    resp.json.return_value = payload
    return resp


@pytest.fixture(autouse=True)
def _set_openrouter_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")


def test_judge_website_parses_valid_response():
    content = json.dumps({
        "site_score": 7,
        "evidence": ["no HTTPS", "pre-2015 aesthetic"],
        "owner_name_guess": "Bob Smith",
        "email_guess": "bob@bobsplumbing.ca",
        "email_confidence": "medium",
        "contact_form_url": "",
        "linkedin_url": "",
        "lead_pitch": "Mobile-broken site, 127 reviews — real business.",
    })
    with patch("lead_hunter.claude_judge.httpx.post",
               return_value=_openrouter_response(content)):
        r = judge_website("Bob's Plumbing", "https://b.com", "<html>…</html>")
    assert isinstance(r, JudgeResult)
    assert r.site_score == 7
    assert r.owner_name_guess == "Bob Smith"
    assert r.email_confidence == "medium"
    assert "Mobile-broken" in r.lead_pitch


def test_judge_website_handles_unreachable_fallback():
    content = json.dumps({
        "site_score": 4,
        "evidence": ["site unreachable"],
        "owner_name_guess": "",
        "email_guess": "",
        "email_confidence": "none",
        "contact_form_url": "",
        "linkedin_url": "",
        "lead_pitch": "Website unreachable; qualified on Maps signals alone.",
    })
    with patch("lead_hunter.claude_judge.httpx.post",
               return_value=_openrouter_response(content)):
        r = judge_website("X", "https://x", html="", site_unreachable=True)
    assert r.site_score == 4
    assert r.email_confidence == "none"


def test_judge_website_strips_markdown_fences():
    content = "```json\n" + json.dumps({
        "site_score": 5, "evidence": [], "owner_name_guess": "",
        "email_guess": "", "email_confidence": "none",
        "contact_form_url": "", "linkedin_url": "", "lead_pitch": "x",
    }) + "\n```"
    with patch("lead_hunter.claude_judge.httpx.post",
               return_value=_openrouter_response(content)):
        r = judge_website("X", "https://x", "<html/>")
    assert r.site_score == 5


def test_judge_website_raises_on_bad_json():
    bad = MagicMock()
    bad.status_code = 200
    bad.text = "not json"
    bad.json.side_effect = json.JSONDecodeError("no", "not json", 0)
    with patch("lead_hunter.claude_judge.httpx.post", return_value=bad):
        with pytest.raises(RuntimeError, match="unparseable"):
            judge_website("X", "https://x", "<html/>")


def test_judge_website_raises_on_non_200():
    bad = MagicMock()
    bad.status_code = 401
    bad.text = "unauthorized"
    with patch("lead_hunter.claude_judge.httpx.post", return_value=bad):
        with pytest.raises(RuntimeError, match="HTTP 401.*unauthorized"):
            judge_website("X", "https://x", "<html/>")
