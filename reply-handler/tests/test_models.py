from __future__ import annotations

from datetime import datetime, timezone

from reply_handler.models import LeadUpdate, ReplyClassification


def test_lead_update_sent_carries_thread_and_message_ids():
    upd = LeadUpdate.sent(
        row_number=42,
        date_sent=datetime(2026, 4, 1, tzinfo=timezone.utc),
        thread_id="thr_123",
        message_id="msg_456",
    )
    assert upd.row_number == 42
    assert upd.values["status"] == "sent"
    assert upd.values["gmail_thread_id"] == "thr_123"
    assert upd.values["gmail_message_id"] == "msg_456"
    assert upd.values["date_sent"].startswith("2026-04-01")


def test_lead_update_replied_uses_class_in_status():
    upd = LeadUpdate.replied(
        row_number=7,
        reply_class="interested",
        last_reply_date=datetime(2026, 4, 2, tzinfo=timezone.utc),
        reply_draft_id="draft_xyz",
    )
    assert upd.values["status"] == "replied_interested"
    assert upd.values["reply_class"] == "interested"
    assert upd.values["reply_draft_id"] == "draft_xyz"


def test_lead_update_followup_increments_count_field():
    upd = LeadUpdate.followup(
        row_number=9,
        followup_number=2,
        date=datetime(2026, 4, 3, tzinfo=timezone.utc),
        draft_id="d1",
    )
    assert upd.values["status"] == "followup_2_drafted"
    assert upd.values["followup_count"] == "2"
    assert upd.values["last_followup_draft_id"] == "d1"


def test_lead_update_cold():
    upd = LeadUpdate.cold(row_number=11)
    assert upd.values == {"status": "cold"}


def test_reply_classification_should_draft():
    interested = ReplyClassification(
        reply_class="interested", draft_subject="Re: hi", draft_body="hey",
    )
    auto = ReplyClassification(
        reply_class="auto_reply", draft_subject="", draft_body="",
        skip_reason="OOO",
    )
    assert interested.should_draft() is True
    assert auto.should_draft() is False
