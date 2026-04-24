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
    assert "viewport" in prompt.lower()  # rubric mentions signals
    assert "We fix pipes" in prompt


def test_build_judge_prompt_truncates_long_html():
    big_html = "x" * 200_000
    prompt = build_judge_prompt("B", "https://b.com", big_html)
    assert len(prompt) < 150_000


def _fake_completed(stdout_text: str):
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout_text
    m.stderr = ""
    return m


def test_judge_website_parses_valid_response():
    fake_payload = json.dumps({
        "result": json.dumps({
            "site_score": 7,
            "evidence": ["no HTTPS", "pre-2015 aesthetic"],
            "owner_name_guess": "Bob Smith",
            "email_guess": "bob@bobsplumbing.ca",
            "email_confidence": "medium",
            "contact_form_url": "",
            "linkedin_url": "",
            "lead_pitch": "Mobile-broken site, 127 reviews — real business.",
        })
    })
    with patch("lead_hunter.claude_judge.subprocess.run",
               return_value=_fake_completed(fake_payload)):
        r = judge_website("Bob's Plumbing", "https://b.com", "<html>…</html>")
    assert isinstance(r, JudgeResult)
    assert r.site_score == 7
    assert r.owner_name_guess == "Bob Smith"
    assert r.email_confidence == "medium"
    assert "Mobile-broken" in r.lead_pitch


def test_judge_website_handles_unreachable_fallback():
    # When no HTML (site unreachable), caller passes empty html; judge should
    # return a zero-score result based on the prompt's instructions.
    fake_payload = json.dumps({
        "result": json.dumps({
            "site_score": 4,  # partial signal from having no site
            "evidence": ["site unreachable"],
            "owner_name_guess": "",
            "email_guess": "",
            "email_confidence": "none",
            "contact_form_url": "",
            "linkedin_url": "",
            "lead_pitch": "Website unreachable; qualified on Maps signals alone.",
        })
    })
    with patch("lead_hunter.claude_judge.subprocess.run",
               return_value=_fake_completed(fake_payload)):
        r = judge_website("X", "https://x", html="", site_unreachable=True)
    assert r.site_score == 4
    assert r.email_confidence == "none"


def test_judge_website_raises_on_bad_json():
    with patch("lead_hunter.claude_judge.subprocess.run",
               return_value=_fake_completed("not json")):
        with pytest.raises(RuntimeError, match="claude -p"):
            judge_website("X", "https://x", "<html/>")


def test_judge_website_raises_on_nonzero_exit():
    bad = MagicMock()
    bad.returncode = 2
    bad.stdout = ""
    bad.stderr = "auth failure"
    with patch("lead_hunter.claude_judge.subprocess.run", return_value=bad):
        with pytest.raises(RuntimeError, match="auth failure"):
            judge_website("X", "https://x", "<html/>")
