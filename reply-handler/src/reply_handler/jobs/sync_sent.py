"""Job: detect drafts that have been sent and update the sheet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..gmail_client import GmailClient
from ..models import LeadUpdate, TrackedLead
from ..sheets import ReplyHandlerSheets


@dataclass
class SyncSentResult:
    synced: int
    errors: int
    notes: list[str]


def _resolve_recipient(lead: TrackedLead) -> str:
    return lead.email_guess.strip()


def run_sync_sent(
    *,
    sheets: ReplyHandlerSheets,
    gmail: GmailClient,
    dry_run: bool,
) -> SyncSentResult:
    """For each `drafted` lead with a gmail_draft_id: check whether that draft
    still exists. If gone, search Sent by recipient+subject to find the sent
    message. Update sheet to status=sent."""
    sheets.ensure_schema()
    drafted = sheets.read_leads_with_status({"drafted"})

    updates: list[LeadUpdate] = []
    notes: list[str] = []
    synced = 0
    errors = 0

    for lead in drafted:
        if not lead.gmail_draft_id:
            continue  # nothing to track
        try:
            still_drafted = gmail.draft_exists(lead.gmail_draft_id)
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: draft_exists failed: {e}")
            continue

        if still_drafted:
            continue  # not yet sent — leave alone

        # draft is gone: either sent or manually deleted. Try to find it in Sent.
        recipient = _resolve_recipient(lead)
        try:
            sent = gmail.find_sent_message_for_draft(
                draft_id=lead.gmail_draft_id,
                to_address=recipient,
                subject=lead.subject_line,
            )
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: search Sent failed: {e}")
            continue

        if sent is None:
            # operator probably deleted the draft without sending — leave the
            # row alone so they can decide what to do
            notes.append(f"{lead.business_name}: draft gone, no Sent match")
            continue

        sent_at = datetime.fromtimestamp(sent.sent_at_epoch_ms / 1000, tz=timezone.utc)
        updates.append(LeadUpdate.sent(
            row_number=lead.row_number,
            date_sent=sent_at,
            thread_id=sent.thread_id,
            message_id=sent.message_id,
        ))
        synced += 1

    if not dry_run:
        sheets.apply_lead_updates(updates)

    return SyncSentResult(synced=synced, errors=errors, notes=notes)
