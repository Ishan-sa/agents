from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from outreach_agent.models import EligibleLead, LeadUpdate, OutreachRun
from outreach_agent.sheets import OutreachSheets

LEAD_HEADERS_BASE = [
    "date_added", "source_run", "business_name", "niche", "city",
    "address", "phone", "website", "maps_rating", "maps_reviews",
    "site_score", "site_evidence", "owner_name_guess", "email_guess",
    "email_confidence", "contact_form_url", "linkedin_url", "lead_pitch",
    "site_unreachable", "tier", "status",
]
NEW_COLS = ["date_drafted", "subject_line", "gmail_draft_id", "skip_reason"]


def _build_spread(lead_rows: list[list[str]], lead_headers=None,
                   has_outreach_runs_tab: bool = False):
    """Build a MagicMock spreadsheet with a Leads tab and optionally Outreach_Runs."""
    headers = lead_headers if lead_headers is not None else LEAD_HEADERS_BASE
    leads_ws = MagicMock()
    leads_ws.row_values.return_value = headers
    leads_ws.get_all_values.return_value = [headers, *lead_rows]
    leads_ws.col_count = len(headers)

    runs_ws = MagicMock()

    worksheets = [leads_ws]
    if has_outreach_runs_tab:
        worksheets.append(runs_ws)

    spread = MagicMock()
    spread.worksheets.return_value = worksheets

    def _ws(name):
        if name == "Leads":
            return leads_ws
        if name == "Outreach_Runs":
            if not has_outreach_runs_tab:
                from gspread import WorksheetNotFound
                raise WorksheetNotFound(name)
            return runs_ws
        raise KeyError(name)
    spread.worksheet.side_effect = _ws

    spread.add_worksheet.return_value = runs_ws
    return spread, leads_ws, runs_ws


def _row(values_by_col: dict, headers=LEAD_HEADERS_BASE) -> list[str]:
    return [str(values_by_col.get(h, "")) for h in headers]


def test_ensure_schema_adds_missing_lead_columns_and_runs_tab():
    headers = LEAD_HEADERS_BASE  # missing all 4 new cols
    spread, leads_ws, _ = _build_spread([], lead_headers=headers,
                                          has_outreach_runs_tab=False)
    sc = OutreachSheets(spread=spread)
    sc.ensure_schema()

    # Should have appended the 4 missing columns to header row
    leads_ws.update.assert_called()
    # Should have created Outreach_Runs tab
    spread.add_worksheet.assert_called_once()
    args, kwargs = spread.add_worksheet.call_args
    assert kwargs.get("title") == "Outreach_Runs" or args[0] == "Outreach_Runs"


def test_ensure_schema_idempotent_when_everything_present():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    spread, leads_ws, _ = _build_spread([], lead_headers=headers,
                                          has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    sc.ensure_schema()
    leads_ws.update.assert_not_called()
    spread.add_worksheet.assert_not_called()


def test_read_eligible_leads_filters_and_sorts():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    rows = [
        # row 2: warm, score 4, has email — eligible
        _row({
            "business_name": "Warm Co", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://w.com", "email_guess": "w@w.com",
            "site_score": "4", "site_evidence": "x", "owner_name_guess": "W",
            "lead_pitch": "p", "tier": "warm", "status": "",
        }, headers),
        # row 3: hot, score 7, has email — eligible (will sort first)
        _row({
            "business_name": "Hot Co", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://h.com", "email_guess": "h@h.com",
            "site_score": "7", "site_evidence": "x", "owner_name_guess": "H",
            "lead_pitch": "p", "tier": "hot", "status": "",
        }, headers),
        # row 4: hot, score 9, but already drafted — INELIGIBLE
        _row({
            "business_name": "Already Done", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://d.com", "email_guess": "d@d.com",
            "site_score": "9", "site_evidence": "x", "owner_name_guess": "D",
            "lead_pitch": "p", "tier": "hot", "status": "drafted",
        }, headers),
        # row 5: warm, score 5, neither email nor absolute form URL — INELIGIBLE
        _row({
            "business_name": "No Contact", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://n.com", "email_guess": "",
            "contact_form_url": "/contact/",
            "site_score": "5", "site_evidence": "x", "owner_name_guess": "",
            "lead_pitch": "p", "tier": "warm", "status": "",
        }, headers),
        # row 6: warm, score 4, absolute form URL — eligible
        _row({
            "business_name": "Form Co", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://f.com", "email_guess": "",
            "contact_form_url": "https://f.com/contact",
            "site_score": "4", "site_evidence": "x", "owner_name_guess": "",
            "lead_pitch": "p", "tier": "warm", "status": "",
        }, headers),
    ]
    spread, _, _ = _build_spread(rows, lead_headers=headers,
                                   has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    eligible = sc.read_eligible_leads()
    # Eligible: rows 2, 3, 6. Sort: tier=hot first, then site_score desc.
    names = [l.business_name for l in eligible]
    assert names == ["Hot Co", "Warm Co", "Form Co"]
    # Row numbers are 1-indexed with header on row 1
    assert eligible[0].row_number == 3
    assert eligible[1].row_number == 2
    assert eligible[2].row_number == 6


def test_read_eligible_leads_applies_filters():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    rows = [
        _row({
            "business_name": "Plumber Burnaby", "niche": "plumbers",
            "city": "Burnaby BC", "website": "https://p.com",
            "email_guess": "p@p.com", "site_score": "5", "tier": "warm",
            "status": "",
        }, headers),
        _row({
            "business_name": "Barber Vancouver", "niche": "barbers",
            "city": "Vancouver BC", "website": "https://b.com",
            "email_guess": "b@b.com", "site_score": "7", "tier": "hot",
            "status": "",
        }, headers),
    ]
    spread, _, _ = _build_spread(rows, lead_headers=headers,
                                   has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    plumbers_only = sc.read_eligible_leads(niche="plumbers")
    assert [l.business_name for l in plumbers_only] == ["Plumber Burnaby"]
    hot_only = sc.read_eligible_leads(tier="hot")
    assert [l.business_name for l in hot_only] == ["Barber Vancouver"]


def test_apply_lead_updates_writes_correct_cells():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    spread, leads_ws, _ = _build_spread([], lead_headers=headers,
                                          has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    updates = [
        LeadUpdate.drafted(
            row_number=3,
            date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
            subject_line="hey",
            gmail_draft_id="r-1",
        ),
        LeadUpdate.skipped(
            row_number=5,
            date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
            skip_reason="franchise",
        ),
    ]
    sc.apply_lead_updates(updates)
    leads_ws.batch_update.assert_called_once()
    payload = leads_ws.batch_update.call_args[0][0]
    # Should be one entry per (row × column-being-updated). 2 updates × 5 cols each = 10 entries.
    assert len(payload) == 10
    # Sanity: each entry has range and values
    for entry in payload:
        assert "range" in entry
        assert "values" in entry


def test_append_outreach_run_writes_one_row():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    spread, _, runs_ws = _build_spread([], lead_headers=headers,
                                         has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    run = OutreachRun(
        run_id="01", date=datetime(2026, 4, 25, tzinfo=timezone.utc),
        batch_size=5, filter_niche="", filter_city="", filter_tier="",
        eligible_count=10, drafted=4, skipped=1, errors=0,
        duration_seconds=42.0, dry_run=False, notes="",
    )
    sc.append_run(run)
    runs_ws.append_row.assert_called_once()
