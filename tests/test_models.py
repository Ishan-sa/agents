from datetime import datetime, timezone
from lead_hunter.models import Business, Lead, RejectedLead, Run


def test_business_is_immutable_and_dedup_keys_present():
    b = Business(
        name="Bob's Plumbing",
        address="123 Main St, Burnaby BC",
        phone="+16045550100",
        website="https://bobsplumbing.ca",
        maps_rating=4.6,
        maps_reviews=127,
        permanently_closed=False,
    )
    assert b.name == "Bob's Plumbing"
    assert b.dedup_keys() == {"website:https://bobsplumbing.ca", "phone:+16045550100"}


def test_business_dedup_keys_skip_missing():
    b = Business(
        name="No Web Plumber",
        address="1 Other St",
        phone="+16045550101",
        website=None,
        maps_rating=4.0,
        maps_reviews=12,
        permanently_closed=False,
    )
    assert b.dedup_keys() == {"phone:+16045550101"}


def test_lead_round_trips_to_dict_for_sheets():
    lead = Lead(
        date_added=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source_run="01HXYZ",
        business_name="Bob's Plumbing",
        niche="plumbers",
        city="Burnaby BC",
        address="123 Main St",
        phone="+16045550100",
        website="https://bobsplumbing.ca",
        maps_rating=4.6,
        maps_reviews=127,
        site_score=7,
        site_evidence="No HTTPS; pre-2015 aesthetic; slow/heavy",
        owner_name_guess="Bob Smith",
        email_guess="bob@bobsplumbing.ca",
        email_confidence="medium",
        contact_form_url="",
        linkedin_url="",
        lead_pitch="Site is mobile-broken and still on HTTP. 127 reviews at 4.6 — real business.",
        tier="hot",
        site_unreachable=False,
    )
    row = lead.to_sheet_row()
    assert row[2] == "Bob's Plumbing"
    assert row[-2] == "hot"
    assert len(row) == len(Lead.sheet_columns())


def test_run_round_trips_to_dict_for_sheets():
    r = Run(
        run_id="01HXYZ",
        date=datetime(2026, 4, 24, tzinfo=timezone.utc),
        niche="plumbers",
        city="Burnaby BC",
        max_results=100,
        apify_results=98,
        new_after_dedup=72,
        qualified=41,
        rejected=31,
        apify_cost_usd=0.82,
        duration_seconds=214.3,
        notes="",
    )
    row = r.to_sheet_row()
    assert row[2] == "plumbers"
    assert len(row) == len(Run.sheet_columns())
