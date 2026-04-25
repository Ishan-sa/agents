from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import Config, Thresholds
from .gmail_client import GmailClient
from .pipeline import run_pipeline
from .sheets import OutreachSheets


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="outreach-agent",
        description=(
            "Read qualified leads from the Google Sheet and stage personalized "
            "Gmail drafts for manual review."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=Thresholds.BATCH_SIZE_DEFAULT,
                        help=f"how many drafts to create (default {Thresholds.BATCH_SIZE_DEFAULT}, "
                             f"max {Thresholds.BATCH_SIZE_HARD_CAP})")
    parser.add_argument("--niche", default=None, help='filter to one niche (e.g. "plumbers")')
    parser.add_argument("--city", default=None, help='filter to one city (e.g. "Burnaby BC")')
    parser.add_argument("--tier", default=None, choices=["hot", "warm"],
                        help="filter to one tier")
    parser.add_argument("--dry-run", action="store_true",
                        help="research and write drafts but skip Gmail and Sheets writes; print to stdout")
    args = parser.parse_args()

    cfg = Config.from_env()
    sheets = OutreachSheets.from_credentials(
        service_account_path=cfg.service_account_path,
        sheet_id=cfg.google_sheet_id,
    )
    gmail = GmailClient.from_token(cfg.gmail_token_path)
    voice_path = Path("voice_examples.md").resolve()

    print(
        f"→ outreach-agent: batch={args.batch_size} "
        f"niche={args.niche or '*'} city={args.city or '*'} tier={args.tier or '*'} "
        f"{'(DRY RUN)' if args.dry_run else ''}"
    )
    run = asyncio.run(run_pipeline(
        sheets=sheets, gmail=gmail, voice_examples_path=voice_path,
        sender_name=cfg.sender_name,
        sender_agency_name=cfg.sender_agency_name,
        sender_calendar_url=cfg.sender_calendar_url,
        batch_size=args.batch_size,
        niche=args.niche, city=args.city, tier=args.tier,
        dry_run=args.dry_run,
    ))
    print(
        f"✓ run {run.run_id}: {run.drafted} drafted, {run.skipped} skipped, "
        f"{run.errors} errors, {run.duration_seconds:.1f}s "
        f"(eligible: {run.eligible_count})"
    )
    if run.notes:
        print(f"  notes: {run.notes}")
    return 0 if run.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
