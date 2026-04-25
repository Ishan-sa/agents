from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lead_hunter.apify import ApifyResult
from lead_hunter.claude_judge import JudgeResult
from lead_hunter.fetch import FetchResult
from lead_hunter.models import Business
from lead_hunter.pipeline import run_pipeline


def _biz(name, website="https://x.com", phone="+1555", rating=4.5, reviews=50, closed=False):
    return Business(
        name=name, address="addr", phone=phone, website=website,
        maps_rating=rating, maps_reviews=reviews, permanently_closed=closed,
    )


async def test_pipeline_happy_path_writes_hot_and_warm_and_rejected():
    businesses = [
        _biz("Hot Co", website="https://hot.com", phone="+1001"),
        _biz("Warm Co", website="https://warm.com", phone="+1002"),
        _biz("Good Site Co", website="https://good.com", phone="+1003"),
        _biz("Dead Co", website="https://dead.com", reviews=2, phone="+1004"),
    ]
    apify_result = ApifyResult(businesses=businesses, cost_usd=0.5, run_id="apify_1")

    fetches = {
        "https://hot.com": FetchResult(True, "<html/>", 200, "https://hot.com", "", 100),
        "https://warm.com": FetchResult(True, "<html/>", 200, "https://warm.com", "", 100),
        "https://good.com": FetchResult(True, "<html/>", 200, "https://good.com", "", 100),
        "https://dead.com": FetchResult(True, "<html/>", 200, "https://dead.com", "", 100),
    }

    judgements = {
        "Hot Co": JudgeResult(7, ["no HTTPS"], "A", "a@x", "medium", "", "", "hot pitch"),
        "Warm Co": JudgeResult(4, ["slow"], "B", "b@x", "medium", "", "", "warm pitch"),
        "Good Site Co": JudgeResult(1, [], "C", "c@x", "medium", "", "", "fine site"),
        "Dead Co": JudgeResult(8, [], "", "", "none", "", "", "doesn't matter"),
    }

    sheets = MagicMock()
    sheets.existing_dedup_keys.return_value = set()

    with patch("lead_hunter.pipeline.scrape_google_maps", return_value=apify_result), \
         patch("lead_hunter.pipeline.fetch_site",
               side_effect=lambda url, **_: fetches[url]), \
         patch("lead_hunter.pipeline.judge_website",
               side_effect=lambda name, url, html, site_unreachable=False: judgements[name]):
        summary = await run_pipeline(
            apify_token="tok",
            sheets=sheets,
            niche="plumbers",
            city="Burnaby BC",
            max_results=10,
            apify_max_cost_usd=5.0,
        )

    sheets.ensure_schema.assert_called_once()
    sheets.append.assert_called_once()
    kwargs = sheets.append.call_args.kwargs
    lead_names = [l.business_name for l in kwargs["leads"]]
    rejected_names = [r.business_name for r in kwargs["rejected"]]

    assert set(lead_names) == {"Hot Co", "Warm Co"}
    assert set(rejected_names) == {"Good Site Co", "Dead Co"}
    assert summary.qualified == 2
    assert summary.rejected == 2


async def _async_return(value):
    return value
