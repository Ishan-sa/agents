"""Job: for every `sent` lead, look for an inbound reply. If found, classify
+ draft a contextual response in-thread."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import Thresholds
from ..gmail_client import GmailClient, InboundReply
from ..llm import call_openrouter_json
from ..models import LeadUpdate, ReplyClass, ReplyClassification, TrackedLead
from ..sheets import ReplyHandlerSheets
from ..voice import build_reply_prompt


MAX_REPLY_BODY_CHARS = 8_000


@dataclass
class CheckRepliesResult:
    drafted: int
    errors: int
    notes: list[str]


def _build_user_prompt(*, lead: TrackedLead, original_subject: str, reply: InboundReply) -> str:
    body = reply.body_text[:MAX_REPLY_BODY_CHARS]
    truncation_note = (
        f"\n\n[reply truncated to {MAX_REPLY_BODY_CHARS} chars]"
        if len(reply.body_text) > MAX_REPLY_BODY_CHARS
        else ""
    )
    return (
        f"Business: {lead.business_name}\n"
        f"Niche: {lead.niche}\n"
        f"City: {lead.city}\n"
        f"Owner name guess: {lead.owner_name_guess}\n"
        f"Original outbound subject: {original_subject}\n"
        f"\n--- INBOUND REPLY ---\n"
        f"From: {reply.from_address}\n"
        f"Subject: {reply.subject}\n\n"
        f"{body}{truncation_note}\n"
    )


def _classify_and_draft(
    *, lead: TrackedLead, reply: InboundReply, system_prompt: str,
) -> ReplyClassification:
    user_prompt = _build_user_prompt(
        lead=lead,
        original_subject=lead.subject_line,
        reply=reply,
    )
    parsed = call_openrouter_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.5,
    )
    cls_raw = str(parsed.get("reply_class", "none")).strip()
    if cls_raw not in ("interested", "question", "declined", "auto_reply", "none"):
        cls_raw = "none"
    return ReplyClassification(
        reply_class=cls_raw,  # type: ignore[arg-type]
        draft_subject=str(parsed.get("draft_subject", "")),
        draft_body=str(parsed.get("draft_body", "")),
        skip_reason=str(parsed.get("skip_reason", "")),
    )


def run_check_replies(
    *,
    sheets: ReplyHandlerSheets,
    gmail: GmailClient,
    voice_examples_path: Path,
    sender_name: str,
    sender_agency_name: str,
    sender_calendar_url: str,
    dry_run: bool,
) -> CheckRepliesResult:
    sheets.ensure_schema()
    sent = sheets.read_leads_with_status({"sent"})

    # cap how many replies we draft per run, in case a backlog appears
    sent = sent[: Thresholds.MAX_REPLIES_PER_RUN]

    system_prompt = build_reply_prompt(
        voice_examples_path=voice_examples_path,
        sender_name=sender_name,
        sender_agency_name=sender_agency_name,
        sender_calendar_url=sender_calendar_url,
    )

    updates: list[LeadUpdate] = []
    notes: list[str] = []
    drafted = 0
    errors = 0

    for lead in sent:
        if not lead.gmail_thread_id or not lead.gmail_message_id:
            continue
        try:
            reply = gmail.latest_inbound_message(
                thread_id=lead.gmail_thread_id,
                our_message_id=lead.gmail_message_id,
            )
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: read thread failed: {e}")
            continue

        if reply is None:
            continue  # no reply yet

        try:
            cls = _classify_and_draft(
                lead=lead, reply=reply, system_prompt=system_prompt,
            )
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: classify failed: {e}")
            continue

        received_at = datetime.fromtimestamp(
            reply.received_at_epoch_ms / 1000, tz=timezone.utc
        )

        if not cls.should_draft():
            # auto_reply / none: just record class + date, no draft
            if dry_run:
                print(f"[dry-run] {lead.business_name}: classified={cls.reply_class}; no draft")
            else:
                updates.append(LeadUpdate.replied(
                    row_number=lead.row_number,
                    reply_class=cls.reply_class,
                    last_reply_date=received_at,
                    reply_draft_id="",
                ))
            continue

        if dry_run:
            drafted += 1
            print(f"\n--- DRY RUN reply draft for {lead.business_name} (class={cls.reply_class}) ---")
            print(f"Subject: {cls.draft_subject}")
            print(f"\n{cls.draft_body}\n")
            continue

        try:
            draft_id = gmail.create_reply_draft(
                thread_id=lead.gmail_thread_id,
                to=reply.from_address,
                subject=cls.draft_subject or f"Re: {lead.subject_line}",
                body=cls.draft_body,
                in_reply_to_message_id=reply.rfc822_message_id,
                references=reply.headers.get("references", "") or reply.rfc822_message_id,
            )
            drafted += 1
            updates.append(LeadUpdate.replied(
                row_number=lead.row_number,
                reply_class=cls.reply_class,
                last_reply_date=received_at,
                reply_draft_id=draft_id,
            ))
        except Exception as e:
            errors += 1
            notes.append(f"{lead.business_name}: create reply draft failed: {e}")

    if not dry_run:
        sheets.apply_lead_updates(updates)

    return CheckRepliesResult(drafted=drafted, errors=errors, notes=notes)
