from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ulid

from .config import Config
from .gmail_client import GmailClient
from .jobs.check_replies import run_check_replies
from .jobs.follow_ups import run_follow_ups
from .jobs.sync_sent import run_sync_sent
from .models import ReplyHandlerRun
from .sheets import ReplyHandlerSheets


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reply-handler",
        description=(
            "Closes the loop on the outreach pipeline. Subcommands: sync-sent, "
            "check-replies, follow-ups, all."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="run all logic but skip Gmail draft creation and Sheet writes; print to stdout",
    )
    sub = parser.add_subparsers(dest="job", required=True)
    sub.add_parser("sync-sent", help="detect drafts that have been sent")
    sub.add_parser("check-replies", help="classify + draft replies for inbound messages")
    sub.add_parser("follow-ups", help="cadence-based follow-up nudges")
    sub.add_parser("all", help="run sync-sent, check-replies, then follow-ups in order")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    cfg = Config.from_env()
    sheets = ReplyHandlerSheets.from_credentials(
        service_account_path=cfg.service_account_path,
        sheet_id=cfg.google_sheet_id,
    )
    gmail = GmailClient.from_token(cfg.gmail_token_path)
    voice_path = Path("voice_examples.md").resolve()

    job = args.job
    print(f"→ reply-handler: {job} {'(DRY RUN)' if args.dry_run else ''}")

    start = time.time()
    sent_synced = 0
    replies_drafted = 0
    followups_drafted = 0
    marked_cold = 0
    errors = 0
    notes_lines: list[str] = []

    if job in ("sync-sent", "all"):
        r = run_sync_sent(sheets=sheets, gmail=gmail, dry_run=args.dry_run)
        sent_synced = r.synced
        errors += r.errors
        notes_lines += [f"[sync] {n}" for n in r.notes]
        print(f"  sync-sent: {r.synced} synced, {r.errors} errors")

    if job in ("check-replies", "all"):
        r2 = run_check_replies(
            sheets=sheets, gmail=gmail,
            voice_examples_path=voice_path,
            sender_name=cfg.sender_name,
            sender_agency_name=cfg.sender_agency_name,
            sender_calendar_url=cfg.sender_calendar_url,
            dry_run=args.dry_run,
        )
        replies_drafted = r2.drafted
        errors += r2.errors
        notes_lines += [f"[reply] {n}" for n in r2.notes]
        print(f"  check-replies: {r2.drafted} drafted, {r2.errors} errors")

    if job in ("follow-ups", "all"):
        r3 = run_follow_ups(
            sheets=sheets, gmail=gmail,
            voice_examples_path=voice_path,
            sender_name=cfg.sender_name,
            sender_agency_name=cfg.sender_agency_name,
            sender_calendar_url=cfg.sender_calendar_url,
            cadence=cfg.cadence,
            dry_run=args.dry_run,
        )
        followups_drafted = r3.drafted
        marked_cold = r3.marked_cold
        errors += r3.errors
        notes_lines += [f"[fup] {n}" for n in r3.notes]
        print(f"  follow-ups: {r3.drafted} drafted, {r3.marked_cold} cold, {r3.errors} errors")

    duration = time.time() - start
    run = ReplyHandlerRun(
        run_id=str(ulid.new()),
        date=datetime.now(timezone.utc),
        job=job,
        sent_synced=sent_synced,
        replies_drafted=replies_drafted,
        followups_drafted=followups_drafted,
        marked_cold=marked_cold,
        errors=errors,
        duration_seconds=duration,
        dry_run=args.dry_run,
        notes="; ".join(notes_lines),
    )
    if not args.dry_run:
        sheets.append_run(run)

    print(
        f"✓ run {run.run_id}: synced={sent_synced} replies={replies_drafted} "
        f"followups={followups_drafted} cold={marked_cold} errors={errors} "
        f"({duration:.1f}s)"
    )
    if run.notes:
        print(f"  notes: {run.notes}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
