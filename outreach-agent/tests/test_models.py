from datetime import datetime, timezone

from outreach_agent.models import (
    DraftResult,
    EligibleLead,
    LeadUpdate,
    OutreachRun,
)


def test_eligible_lead_carries_row_number_and_lead_data():
    lead = EligibleLead(
        row_number=7,
        business_name="Bob's Plumbing",
        niche="plumbers",
        city="Burnaby BC",
        website="https://bobs.ca",
        email_guess="bob@bobs.ca",
        contact_form_url="",
        owner_name_guess="Bob Smith",
        site_score=7,
        site_evidence="No HTTPS; pre-2015 aesthetic",
        lead_pitch="Mobile-broken site, 127 reviews — real business.",
        tier="hot",
    )
    assert lead.row_number == 7
    assert lead.has_email() is True
    assert lead.has_absolute_form_url() is False


def test_eligible_lead_form_url_helper():
    relative = EligibleLead(
        row_number=1, business_name="X", niche="y", city="z",
        website="https://x", email_guess="", contact_form_url="/contact/",
        owner_name_guess="", site_score=4, site_evidence="", lead_pitch="",
        tier="warm",
    )
    absolute = relative.model_copy(update={"contact_form_url": "https://x/contact"})
    assert relative.has_absolute_form_url() is False
    assert absolute.has_absolute_form_url() is True


def test_draft_result_draft_action():
    d = DraftResult(
        action="draft",
        subject="noticed something on x.com",
        body="hey x team,\n...\n\nishan",
        skip_reason="",
    )
    assert d.action == "draft"
    assert d.is_draft() is True
    assert d.is_skip() is False


def test_draft_result_skip_action():
    d = DraftResult(
        action="skip",
        subject="",
        body="",
        skip_reason="site is in punjabi only",
    )
    assert d.is_skip() is True
    assert d.is_draft() is False


def test_lead_update_drafted_payload():
    u = LeadUpdate.drafted(
        row_number=7,
        date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
        subject_line="noticed something on x.com",
        gmail_draft_id="r-12345",
    )
    assert u.row_number == 7
    assert u.values["status"] == "drafted"
    assert u.values["gmail_draft_id"] == "r-12345"
    assert u.values["subject_line"] == "noticed something on x.com"
    assert u.values["skip_reason"] == ""


def test_lead_update_skipped_payload():
    u = LeadUpdate.skipped(
        row_number=9,
        date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
        skip_reason="franchise / chain",
    )
    assert u.values["status"] == "skipped"
    assert u.values["skip_reason"] == "franchise / chain"
    assert u.values["gmail_draft_id"] == ""
    assert u.values["subject_line"] == ""


def test_outreach_run_to_sheet_row():
    r = OutreachRun(
        run_id="01ABC", date=datetime(2026, 4, 25, tzinfo=timezone.utc),
        batch_size=5, filter_niche="", filter_city="", filter_tier="",
        eligible_count=12, drafted=4, skipped=1, errors=0,
        duration_seconds=42.0, dry_run=False, notes="",
    )
    row = r.to_sheet_row()
    assert row[0] == "01ABC"
    assert row[2] == "5"
    assert len(row) == len(OutreachRun.sheet_columns())
