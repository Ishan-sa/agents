from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from reply_handler.config import Cadence
from reply_handler.jobs.follow_ups import _decide_action, _last_outbound_date
from reply_handler.models import TrackedLead


CADENCE = Cadence(followup_1_days=5, followup_2_days=12, cold_days=25)
NOW = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)


def _lead(
    *,
    status: str,
    date_sent_days_ago: int | None = None,
    last_followup_days_ago: int | None = None,
    followup_count: str = "0",
) -> TrackedLead:
    return TrackedLead(
        row_number=2,
        business_name="X", niche="", city="", website="",
        email_guess="a@b.com", owner_name_guess="",
        site_evidence="", lead_pitch="", subject_line="",
        status=status,
        gmail_draft_id="", date_drafted="",
        date_sent=(
            (NOW - timedelta(days=date_sent_days_ago)).isoformat()
            if date_sent_days_ago is not None else ""
        ),
        gmail_thread_id="t", gmail_message_id="m",
        last_reply_date="", reply_class="", reply_draft_id="",
        followup_count=followup_count,
        last_followup_date=(
            (NOW - timedelta(days=last_followup_days_ago)).isoformat()
            if last_followup_days_ago is not None else ""
        ),
        last_followup_draft_id="",
    )


def test_fresh_send_is_noop():
    lead = _lead(status="sent", date_sent_days_ago=2)
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "noop"


def test_send_at_threshold_triggers_first_followup():
    lead = _lead(status="sent", date_sent_days_ago=5)
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "followup_1"


def test_followup_one_recently_drafted_is_noop():
    lead = _lead(
        status="followup_1_drafted", date_sent_days_ago=6,
        last_followup_days_ago=1, followup_count="1",
    )
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "noop"


def test_followup_two_after_threshold_from_followup_one():
    lead = _lead(
        status="followup_1_drafted", date_sent_days_ago=20,
        last_followup_days_ago=14, followup_count="1",
    )
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "followup_2"


def test_count_two_recent_is_noop():
    lead = _lead(
        status="followup_2_drafted", date_sent_days_ago=30,
        last_followup_days_ago=18, followup_count="2",
    )
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "noop"


def test_count_two_past_cold_threshold_marks_cold():
    lead = _lead(
        status="followup_2_drafted", date_sent_days_ago=40,
        last_followup_days_ago=30, followup_count="2",
    )
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "cold"


def test_count_one_past_cold_threshold_marks_cold_directly():
    """If for some reason follow-up #2 never got drafted but enough time has
    passed, we still want to mark cold — never start a brand-new #2 after the
    cold cutoff."""
    lead = _lead(
        status="followup_1_drafted", date_sent_days_ago=40,
        last_followup_days_ago=30, followup_count="1",
    )
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "cold"


def test_non_sent_status_is_noop():
    lead = _lead(status="replied_interested", date_sent_days_ago=10)
    assert _decide_action(lead=lead, now=NOW, cadence=CADENCE) == "noop"


def test_last_outbound_uses_most_recent():
    lead = _lead(
        status="followup_1_drafted", date_sent_days_ago=20,
        last_followup_days_ago=3, followup_count="1",
    )
    last = _last_outbound_date(lead)
    assert last is not None
    # the followup, 3 days ago, should win over the original send (20 days ago)
    assert (NOW - last).days == 3


def test_no_dates_returns_none():
    lead = _lead(status="sent")
    assert _last_outbound_date(lead) is None
