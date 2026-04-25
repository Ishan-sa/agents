"""Job: cadence-based follow-up nudges for sent leads with no reply."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import Cadence, Thresholds
from ..gmail_client import GmailClient
from ..llm import call_openrouter_json
from ..models import FollowupContent, LeadUpdate, TrackedLead
from ..sheets import ReplyHandlerSheets
from ..voice import build_followup_prompt


# Statuses eligible for a follow-up nudge. We deliberately INCLUDE the
# previous followup_*_drafted statuses so a follow-up #1 that's been sent (and
# the operator hasn't reviewed yet) can still progress to #2 once the cadence
# threshold passes. The followup_count column is the source of truth for how
# many we've already drafted.
SENT_LIKE_STATUSES = {"sent", "followup_1_drafted", "followup_2_drafted"}


@dataclass
class FollowUpsResult:
    drafted: int
    marked_cold: int
    errors: int
    notes: list[str]


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _days_since(ref: datetime, now: datetime) -> float:
    return (now - ref).total_seconds() / 86400.0


def _last_outbound_date(lead: TrackedLead) -> datetime | None:
    """The clock for the next nudge starts at whichever was most recent: the
    original send, or our last follow-up."""
    last_followup = _parse_iso(lead.last_followup_date)
    sent = _parse_iso(lead.date_sent)
    candidates = [d for d in (last_followup, sent) if d is not None]
    return max(candidates) if candidates else None


def _decide_action(
    *, lead: TrackedLead, now: datetime, cadence: Cadence,
) -> str:
    """Returns one of: 'noop', 'followup_1', 'followup_2', 'cold'."""
    if lead.status not in SENT_LIKE_STATUSES:
        return "noop"
    last = _last_outbound_date(lead)
    if last is None:
        return "noop"
    days = _days_since(last, now)
    count = lead.followup_count_int()

    if count == 0:
        return "followup_1" if days >= cadence.followup_1_days else "noop"
    if count == 1:
        if days >= cadence.cold_days:
            return "cold"
        if days >= cadence.followup_2_days:
            return "followup_2"
        return "noop"
    # count >= 2
    if days >= cadence.cold_days:
        return "cold"
    return "noop"


def _draft_followup_body(
    *, lead: TrackedLead, followup_number: int, system_prompt: str,
) -> FollowupContent:
    user_prompt = (
        f"Business: {lead.business_name}\n"
        f"Niche: {lead.niche}\n"
        f"City: {lead.city}\n"
        f"Owner name guess: {lead.owner_name_guess}\n"
        f"Original outbound subject: {lead.subject_line}\n"
        f"Site evidence (from earlier audit): {lead.site_evidence}\n"
        f"Lead pitch (from earlier audit): {lead.lead_pitch}\n"
        f"Follow-up number: {followup_number}\n"
    )
    parsed = call_openrouter_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.6,
    )
    return FollowupContent(
        subject=str(parsed.get("subject", f"Re: {lead.subject_line}")),
        body=str(parsed.get("body", "")),
    )


def _last_message_in_thread_for_threading(
    gmail: GmailClient, thread_id: str
) -> tuple[str, str, str]:
    """Returns (to_address, in_reply_to, references) by looking at the LAST
    message in the thread (so the follow-up correctly nests under whatever
    came most recently, even if that was our own previous follow-up)."""
    thread = gmail.get_thread(thread_id)
    messages = thread.get("messages") or []
    if not messages:
        return ("", "", "")
    last = messages[-1]
    payload = last.get("payload") or {}
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    rfc_id = headers.get("message-id", "")
    references = headers.get("references", "") or rfc_id

    # Recipient: prefer the original outbound recipient — i.e. the prospect.
    # If the last message was from us, the "To" is correct. If the last was
    # from them, we want to reply to the "From".
    label_ids = set(last.get("labelIds") or [])
    if "SENT" in label_ids:
        to = headers.get("to", "")
    else:
        to = headers.get("from", "")
    return (to, rfc_id, references)


def run_follow_ups(
    *,
    sheets: ReplyHandlerSheets,
    gmail: GmailClient,
    voice_examples_path: Path,
    sender_name: str,
    sender_agency_name: str,
    sender_calendar_url: str,
    cadence: Cadence,
    dry_run: bool,
) -> FollowUpsResult:
    sheets.ensure_schema()
    candidates = sheets.read_leads_with_status(SENT_LIKE_STATUSES)

    now = datetime.now(timezone.utc)

    updates: list[LeadUpdate] = []
    notes: list[str] = []
    drafted = 0
    marked_cold = 0
    errors = 0

    drafted_count_so_far = 0
    for lead in candidates:
        action = _decide_action(lead=lead, now=now, cadence=cadence)
        if action == "noop":
            continue

        if action == "cold":
            if dry_run:
                print(f"[dry-run] {lead.business_name}: would mark cold")
            else:
                updates.append(LeadUpdate.cold(row_number=lead.row_number))
            marked_cold += 1
            continue

        # action is followup_1 or followup_2
        if drafted_count_so_far >= Thresholds.MAX_FOLLOWUPS_PER_RUN:
            notes.append("max followups per run reached; deferring rest")
            break

        followup_number = 1 if action == "followup_1" else 2

        # Need the original subject + thread + last-message threading info
        if not lead.gmail_thread_id:
            errors += 1
            notes.append(f"{lead.business_name}: missing gmail_thread_id")
            continue

        try:
            to_addr, in_reply_to, references = _last_message_in_thread_for_threading(
                gmail, lead.gmail_thread_id,
            )
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: read thread failed: {e}")
            continue

        if not to_addr:
            to_addr = lead.email_guess

        try:
            system_prompt = build_followup_prompt(
                voice_examples_path=voice_examples_path,
                sender_name=sender_name,
                sender_agency_name=sender_agency_name,
                sender_calendar_url=sender_calendar_url,
                followup_number=followup_number,
            )
            content = _draft_followup_body(
                lead=lead,
                followup_number=followup_number,
                system_prompt=system_prompt,
            )
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: followup gen failed: {e}")
            continue

        if dry_run:
            drafted += 1
            drafted_count_so_far += 1
            print(f"\n--- DRY RUN follow-up #{followup_number} for {lead.business_name} ---")
            print(f"Subject: {content.subject}")
            print(f"\n{content.body}\n")
            continue

        try:
            draft_id = gmail.create_reply_draft(
                thread_id=lead.gmail_thread_id,
                to=to_addr,
                subject=content.subject or f"Re: {lead.subject_line}",
                body=content.body,
                in_reply_to_message_id=in_reply_to,
                references=references or in_reply_to,
            )
            drafted += 1
            drafted_count_so_far += 1
            updates.append(LeadUpdate.followup(
                row_number=lead.row_number,
                followup_number=followup_number,
                date=now,
                draft_id=draft_id,
            ))
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: create followup draft failed: {e}")

    if not dry_run:
        sheets.apply_lead_updates(updates)

    return FollowUpsResult(
        drafted=drafted, marked_cold=marked_cold, errors=errors, notes=notes,
    )
