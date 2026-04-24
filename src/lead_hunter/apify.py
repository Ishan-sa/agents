from __future__ import annotations

from dataclasses import dataclass

from apify_client import ApifyClient

from .models import Business

ACTOR_ID = "compass/crawler-google-places"


@dataclass(frozen=True)
class ApifyResult:
    businesses: list[Business]
    cost_usd: float
    run_id: str


def scrape_google_maps(
    api_token: str,
    niche: str,
    city: str,
    max_results: int,
    max_cost_usd: float,
) -> ApifyResult:
    client = ApifyClient(api_token)
    run_input = {
        "searchStringsArray": [f"{niche} in {city}"],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "maxCostPerRun": max_cost_usd,
        "scrapeContacts": False,  # we don't need email scraping from Apify; we do it via Claude
    }
    actor = client.actor(ACTOR_ID)
    run = actor.call(run_input=run_input)
    if run is None:
        raise RuntimeError("Apify run returned None")

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError(f"Apify run missing defaultDatasetId: {run}")

    items = list(client.dataset(dataset_id).iterate_items())
    businesses = [_to_business(item) for item in items]
    cost = float(run.get("usageTotalUsd", 0.0))
    return ApifyResult(businesses=businesses, cost_usd=cost, run_id=run.get("id", ""))


def _to_business(item: dict) -> Business:
    return Business(
        name=item.get("title") or "(unnamed)",
        address=item.get("address") or "",
        phone=item.get("phone"),
        website=item.get("website"),
        maps_rating=float(item.get("totalScore") or 0.0),
        maps_reviews=int(item.get("reviewsCount") or 0),
        permanently_closed=bool(item.get("permanentlyClosed", False)),
    )
