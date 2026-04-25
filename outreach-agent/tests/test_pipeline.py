from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from outreach_agent.fetch import FetchResult
from outreach_agent.models import DraftResult, EligibleLead, OutreachRun
from outreach_agent.pipeline import run_pipeline


def _lead(name, row, tier="warm", score=4, email="x@x", form=""):
    return EligibleLead(
        row_number=row, business_name=name, niche="plumbers", city="Burnaby BC",
        website=f"https://{name.lower().replace(' ', '')}.com",
        email_guess=email, contact_form_url=form, owner_name_guess="",
        site_score=score, site_evidence="x", lead_pitch="p", tier=tier,
    )


def _async_return(value):
    return value


async def test_pipeline_drafts_skips_and_writes_to_sheet():
    leads = [
        _lead("Hot", 2, tier="hot", score=8),
        _lead("Warm", 3, tier="warm", score=4),
        _lead("Chain", 4, tier="warm", score=5),
    ]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads

    fetch_results = {
        "https://hot.com": FetchResult(True, "<html>HOT</html>", 200, ""),
        "https://warm.com": FetchResult(True, "<html>WARM</html>", 200, ""),
        "https://chain.com": FetchResult(True, "<html>CHAIN</html>", 200, ""),
    }

    drafts_by_business = {
        "Hot": DraftResult(action="draft", subject="hot subject",
                            body="hot body", skip_reason=""),
        "Warm": DraftResult(action="draft", subject="warm subject",
                             body="warm body", skip_reason=""),
        "Chain": DraftResult(action="skip", subject="", body="",
                              skip_reason="franchise / chain"),
    }

    gmail = MagicMock()
    # draft_id depends on order called; use side_effect of subject prefix
    gmail.create_draft.side_effect = lambda to, subject, body: f"r-{subject[:3]}"

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(fetch_results[url])), \
         patch("outreach_agent.pipeline.write_draft",
               side_effect=lambda lead, html, system_prompt: drafts_by_business[lead.business_name]), \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets,
            gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="Ishan", sender_agency_name="Co",
            sender_calendar_url="https://cal/me",
            batch_size=5,
            niche=None, city=None, tier=None,
            dry_run=False,
        )

    assert isinstance(run, OutreachRun)
    assert run.drafted == 2
    assert run.skipped == 1
    assert run.errors == 0
    sheets.ensure_schema.assert_called_once()
    sheets.apply_lead_updates.assert_called_once()
    sheets.append_run.assert_called_once()
    # Two Gmail drafts should have been created (Hot + Warm), Chain was skipped
    assert gmail.create_draft.call_count == 2


async def test_pipeline_dry_run_skips_gmail_and_sheet_writes():
    leads = [_lead("Hot", 2, tier="hot", score=8)]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads

    gmail = MagicMock()

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(
                   FetchResult(True, "<html/>", 200, ""))), \
         patch("outreach_agent.pipeline.write_draft",
               return_value=DraftResult(action="draft", subject="s",
                                          body="b", skip_reason="")), \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets, gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="I", sender_agency_name="C",
            sender_calendar_url="https://x",
            batch_size=5, niche=None, city=None, tier=None,
            dry_run=True,
        )
    assert run.dry_run is True
    assert run.drafted == 1
    gmail.create_draft.assert_not_called()
    sheets.apply_lead_updates.assert_not_called()
    sheets.append_run.assert_not_called()


async def test_pipeline_batch_size_caps_results():
    leads = [_lead(f"L{i}", i + 2) for i in range(10)]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads
    gmail = MagicMock()
    gmail.create_draft.return_value = "r-x"

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(
                   FetchResult(True, "<html/>", 200, ""))), \
         patch("outreach_agent.pipeline.write_draft",
               return_value=DraftResult(action="draft", subject="s",
                                          body="b", skip_reason="")), \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets, gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="I", sender_agency_name="C",
            sender_calendar_url="https://x",
            batch_size=3, niche=None, city=None, tier=None,
            dry_run=False,
        )
    assert run.drafted == 3
    assert gmail.create_draft.call_count == 3


async def test_pipeline_handles_fetch_failure_as_error():
    leads = [_lead("Hot", 2, tier="hot", score=8)]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads
    gmail = MagicMock()

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(
                   FetchResult(False, "", None, "timeout"))), \
         patch("outreach_agent.pipeline.write_draft") as mock_write, \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets, gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="I", sender_agency_name="C",
            sender_calendar_url="https://x",
            batch_size=5, niche=None, city=None, tier=None,
            dry_run=False,
        )
    assert run.drafted == 0
    assert run.errors == 1
    mock_write.assert_not_called()
    gmail.create_draft.assert_not_called()
