from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import ulid

from .apify import scrape_google_maps
from .claude_judge import judge_website
from .config import Thresholds
from .dedup import filter_new
from .fetch import fetch_site
from .models import Business, Lead, RejectedLead, Run
from .qualifier import qualify
from .sheets import SheetsClient


async def run_pipeline(
    apify_token: str,
    sheets: SheetsClient,
    niche: str,
    city: str,
    max_results: int,
    apify_max_cost_usd: float,
) -> Run:
    start = time.time()
    max_results = min(max_results, Thresholds.MAX_RESULTS_HARD_CAP)
    run_id = str(ulid.new())
    now = datetime.now(timezone.utc)

    sheets.ensure_schema()
    existing_keys = sheets.existing_dedup_keys()

    apify_result = scrape_google_maps(
        api_token=apify_token,
        niche=niche,
        city=city,
        max_results=max_results,
        max_cost_usd=apify_max_cost_usd,
    )

    new_businesses = filter_new(apify_result.businesses, existing_keys)

    sem = asyncio.Semaphore(Thresholds.FETCH_CONCURRENCY)

    async def process(business: Business):
        async with sem:
            fetch = await fetch_site(business.website)
            site_unreachable = bool(business.website) and not fetch.ok and fetch.reason != "no_website"
            judge = await asyncio.to_thread(
                judge_website,
                business.name,
                business.website or "",
                fetch.html if fetch.ok else "",
                site_unreachable,
            )
            return business, judge, site_unreachable

    results = await asyncio.gather(*(process(b) for b in new_businesses))

    leads: list[Lead] = []
    rejected: list[RejectedLead] = []

    for business, judge, site_unreachable in results:
        evidence_str = "; ".join(judge.evidence) if judge.evidence else ""
        qr = qualify(business, judge.site_score)
        if qr.verdict == "qualify":
            assert qr.tier is not None
            leads.append(Lead(
                date_added=now, source_run=run_id,
                business_name=business.name, niche=niche, city=city,
                address=business.address, phone=business.phone, website=business.website,
                maps_rating=business.maps_rating, maps_reviews=business.maps_reviews,
                site_score=judge.site_score, site_evidence=evidence_str,
                owner_name_guess=judge.owner_name_guess,
                email_guess=judge.email_guess,
                email_confidence=judge.email_confidence,
                contact_form_url=judge.contact_form_url,
                linkedin_url=judge.linkedin_url,
                lead_pitch=judge.lead_pitch,
                tier=qr.tier,
                site_unreachable=site_unreachable,
            ))
        else:
            rejected.append(RejectedLead(
                date_added=now, source_run=run_id,
                business_name=business.name, niche=niche, city=city,
                address=business.address, phone=business.phone, website=business.website,
                maps_rating=business.maps_rating, maps_reviews=business.maps_reviews,
                site_score=judge.site_score, reject_reason=qr.reason,
            ))

    duration = time.time() - start
    run = Run(
        run_id=run_id, date=now, niche=niche, city=city,
        max_results=max_results,
        apify_results=len(apify_result.businesses),
        new_after_dedup=len(new_businesses),
        qualified=len(leads),
        rejected=len(rejected),
        apify_cost_usd=apify_result.cost_usd,
        duration_seconds=duration,
        notes="",
    )
    sheets.append(leads=leads, rejected=rejected, run=run)
    return run
