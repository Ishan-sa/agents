from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from lead_hunter.models import Lead, RejectedLead, Run
from lead_hunter.sheets import SheetsClient


def _lead(name="Bob's"):
    return Lead(
        date_added=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source_run="r1", business_name=name, niche="plumbers", city="Burnaby BC",
        address="x", phone="+1", website="https://x", maps_rating=4.5, maps_reviews=50,
        site_score=7, site_evidence="no HTTPS", owner_name_guess="Bob", email_guess="b@x",
        email_confidence="medium", contact_form_url="", linkedin_url="",
        lead_pitch="p", tier="hot", site_unreachable=False,
    )


def _rejected():
    return RejectedLead(
        date_added=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source_run="r1", business_name="Good Co", niche="plumbers", city="Burnaby BC",
        address="x", phone="+1", website="https://x", maps_rating=4.8, maps_reviews=200,
        site_score=1, reject_reason="site already good",
    )


def _run():
    return Run(
        run_id="r1", date=datetime(2026, 4, 24, tzinfo=timezone.utc),
        niche="plumbers", city="Burnaby BC", max_results=100,
        apify_results=80, new_after_dedup=60, qualified=30, rejected=30,
        apify_cost_usd=0.5, duration_seconds=100.0, notes="",
    )


def test_read_existing_keys_collects_phone_and_website():
    leads_ws = MagicMock()
    leads_ws.get_all_records.return_value = [
        {"website": "https://a.com", "phone": "+1111"},
        {"website": "", "phone": "+2222"},
    ]
    rejected_ws = MagicMock()
    rejected_ws.get_all_records.return_value = [
        {"website": "https://b.com", "phone": ""},
    ]
    runs_ws = MagicMock()

    spread = MagicMock()
    spread.worksheet.side_effect = lambda name: {
        "Leads": leads_ws, "Rejected": rejected_ws, "Runs": runs_ws,
    }[name]

    client = SheetsClient(spread=spread)
    keys = client.existing_dedup_keys()
    assert keys == {
        "website:https://a.com", "phone:+1111",
        "phone:+2222",
        "website:https://b.com",
    }


def test_append_leads_and_rejected_and_run_calls_sheets_once_each():
    leads_ws = MagicMock()
    rejected_ws = MagicMock()
    runs_ws = MagicMock()
    spread = MagicMock()
    spread.worksheet.side_effect = lambda name: {
        "Leads": leads_ws, "Rejected": rejected_ws, "Runs": runs_ws,
    }[name]

    client = SheetsClient(spread=spread)
    client.append(leads=[_lead(), _lead("B")], rejected=[_rejected()], run=_run())

    leads_ws.append_rows.assert_called_once()
    rejected_ws.append_rows.assert_called_once()
    runs_ws.append_row.assert_called_once()
    # headers weren't touched on append path
    leads_ws.update.assert_not_called()
