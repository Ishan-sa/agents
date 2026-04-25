from __future__ import annotations

import argparse
import asyncio
import sys

from .config import Config
from .pipeline import run_pipeline
from .sheets import SheetsClient


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="lead-hunter",
        description="Scrape local businesses with bad websites and write qualified leads to Google Sheets.",
    )
    parser.add_argument("--niche", required=True, help='e.g. "plumbers"')
    parser.add_argument("--city", required=True, help='e.g. "Burnaby BC"')
    parser.add_argument("--max-results", type=int, default=None,
                        help="override default_max_results from env")
    args = parser.parse_args()

    cfg = Config.from_env()
    max_results = args.max_results if args.max_results is not None else cfg.default_max_results

    sheets = SheetsClient.from_credentials(
        service_account_path=cfg.service_account_path,
        sheet_id=cfg.google_sheet_id,
    )

    print(f"→ lead-hunter: {args.niche} in {args.city} (max {max_results})")
    run = asyncio.run(run_pipeline(
        apify_token=cfg.apify_api_token,
        sheets=sheets,
        niche=args.niche,
        city=args.city,
        max_results=max_results,
        apify_max_cost_usd=cfg.apify_max_cost_usd,
    ))
    print(
        f"✓ run {run.run_id}: {run.qualified} qualified, "
        f"{run.rejected} rejected, "
        f"{run.new_after_dedup}/{run.apify_results} new after dedup, "
        f"${run.apify_cost_usd:.2f} apify, "
        f"{run.duration_seconds:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
