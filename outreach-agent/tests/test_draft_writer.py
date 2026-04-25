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
    assert len(prompt) < 150_000  # truncated


def _completed(stdout_text: str, returncode: int = 0, stderr: str = ""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout_text
    m.stderr = stderr
    return m


def test_write_draft_parses_draft_action():
    payload = json.dumps({
        "result": json.dumps({
            "action": "draft",
            "subject": "noticed something on bobs.ca",
            "body": "hey bob,\n\n...\n\nishan",
            "skip_reason": "",
        })
    })
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed(payload)):
        result = write_draft(
            lead=_lead(), html="<html/>",
            system_prompt="SYSTEM_PROMPT_HERE",
        )
    assert result.is_draft()
    assert result.subject == "noticed something on bobs.ca"
    assert "hey bob" in result.body


def test_write_draft_parses_skip_action():
    payload = json.dumps({
        "result": json.dumps({
            "action": "skip",
            "subject": "",
            "body": "",
            "skip_reason": "site is in punjabi only",
        })
    })
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed(payload)):
        result = write_draft(
            lead=_lead(), html="<html/>",
            system_prompt="SYSTEM_PROMPT_HERE",
        )
    assert result.is_skip()
    assert "punjabi" in result.skip_reason


def test_write_draft_passes_system_prompt_via_cli_arg():
    payload = json.dumps({
        "result": json.dumps({
            "action": "skip", "subject": "", "body": "",
            "skip_reason": "test",
        })
    })
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed(payload)) as mock_run:
        write_draft(
            lead=_lead(), html="<html/>",
            system_prompt="MY_SYSTEM_PROMPT",
        )
    args = mock_run.call_args[0][0]
    assert "--system-prompt" in args
    sys_idx = args.index("--system-prompt")
    assert args[sys_idx + 1] == "MY_SYSTEM_PROMPT"


def test_write_draft_raises_on_nonzero_exit():
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed("", returncode=2, stderr="auth fail")):
        with pytest.raises(RuntimeError, match="claude -p exit 2.*auth fail"):
            write_draft(lead=_lead(), html="<html/>", system_prompt="X")


def test_write_draft_raises_on_bad_json():
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed("not json")):
        with pytest.raises(RuntimeError, match="claude -p"):
            write_draft(lead=_lead(), html="<html/>", system_prompt="X")
