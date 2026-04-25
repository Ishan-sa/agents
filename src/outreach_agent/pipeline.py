from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import ulid

from .config import Thresholds
from .draft_writer import write_draft
from .fetch import fetch_site
from .gmail_client import GmailClient
from .models import EligibleLead, LeadUpdate, OutreachRun
from .sheets import OutreachSheets
from .voice import build_system_prompt


def _resolve_recipient(lead: EligibleLead) -> str:
    """Use email_guess if present; otherwise empty string (operator handles
    form-only leads manually in Gmail's compose UI)."""
    return lead.email_guess.strip() if lead.has_email() else ""


async def run_pipeline(
    sheets: OutreachSheets,
    gmail: GmailClient,
    voice_examples_path: Path,
    sender_name: str,
    sender_agency_name: str,
    sender_calendar_url: str,
    batch_size: int,
    niche: str | None,
    city: str | None,
    tier: str | None,
    dry_run: bool,
) -> OutreachRun:
    start = time.time()
    batch_size = min(batch_size, Thresholds.BATCH_SIZE_HARD_CAP)
    run_id = str(ulid.new())
    now = datetime.now(timezone.utc)

    sheets.ensure_schema()

    eligible_all = sheets.read_eligible_leads(niche=niche, city=city, tier=tier)
    eligible_count = len(eligible_all)
    leads = eligible_all[:batch_size]

    system_prompt = build_system_prompt(
        voice_examples_path=voice_examples_path,
        sender_name=sender_name,
        sender_agency_name=sender_agency_name,
        sender_calendar_url=sender_calendar_url,
    )

    sem = asyncio.Semaphore(Thresholds.CONCURRENCY)
    results: list[tuple[EligibleLead, str, Exception | None]] = []
    # status: ("drafted" | "skipped" | "error", payload)

    async def process(lead: EligibleLead):
        async with sem:
            fetch = await fetch_site(lead.website)
            if not fetch.ok:
                return (lead, "error", RuntimeError(f"fetch_failed: {fetch.reason}"))
            try:
                draft_or_skip = await asyncio.to_thread(
                    write_draft, lead, fetch.html, system_prompt
                )
            except Exception as e:
                return (lead, "error", e)

            if draft_or_skip.is_skip():
                return (lead, "skipped", draft_or_skip)
            return (lead, "drafted", draft_or_skip)

    raw = await asyncio.gather(*(process(l) for l in leads))

    drafted = 0
    skipped = 0
    errors = 0
    notes_lines: list[str] = []
    updates: list[LeadUpdate] = []

    for lead, status, payload in raw:
        if status == "error":
            errors += 1
            notes_lines.append(f"{lead.business_name}: {payload}")
            continue

        if status == "skipped":
            skipped += 1
            if not dry_run:
                updates.append(LeadUpdate.skipped(
                    row_number=lead.row_number,
                    date_drafted=now,
                    skip_reason=payload.skip_reason,
                ))
            continue

        # status == "drafted"
        if dry_run:
            drafted += 1
            print(f"\n--- DRY RUN draft for {lead.business_name} ---")
            print(f"To: {_resolve_recipient(lead)}")
            print(f"Subject: {payload.subject}")
            print(f"\n{payload.body}\n")
            continue

        try:
            draft_id = gmail.create_draft(
                to=_resolve_recipient(lead),
                subject=payload.subject,
                body=payload.body,
            )
            drafted += 1
            updates.append(LeadUpdate.drafted(
                row_number=lead.row_number,
                date_drafted=now,
                subject_line=payload.subject,
                gmail_draft_id=draft_id,
            ))
        except Exception as e:
            errors += 1
            notes_lines.append(f"{lead.business_name}: gmail_create_failed: {e}")

    if not dry_run:
        sheets.apply_lead_updates(updates)

    duration = time.time() - start
    run = OutreachRun(
        run_id=run_id, date=now, batch_size=batch_size,
        filter_niche=niche or "", filter_city=city or "", filter_tier=tier or "",
        eligible_count=eligible_count, drafted=drafted, skipped=skipped,
        errors=errors, duration_seconds=duration, dry_run=dry_run,
        notes="; ".join(notes_lines),
    )
    if not dry_run:
        sheets.append_run(run)
    return run
