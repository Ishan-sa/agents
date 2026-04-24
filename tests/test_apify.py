from unittest.mock import MagicMock, patch

from lead_hunter.apify import ApifyResult, scrape_google_maps
from lead_hunter.models import Business


def test_scrape_google_maps_maps_fields_and_returns_cost():
    fake_items = [
        {
            "title": "Bob's Plumbing",
            "address": "123 Main St, Burnaby BC",
            "phone": "+1 604-555-0100",
            "website": "https://bobsplumbing.ca",
            "totalScore": 4.6,
            "reviewsCount": 127,
            "permanentlyClosed": False,
        },
        {
            "title": "No Web Plumber",
            "address": "1 Other St",
            "phone": "+1 604-555-0101",
            "website": None,
            "totalScore": 4.0,
            "reviewsCount": 12,
            "permanentlyClosed": False,
        },
    ]

    # Simulates Apify behavior: usageTotalUsd is 0/missing on .call() return,
    # then populated when the run is refetched via client.run(id).get().
    initial_run = {"id": "run_abc", "usageTotalUsd": 0.0, "defaultDatasetId": "ds_abc"}
    refreshed_run = {"id": "run_abc", "usageTotalUsd": 0.73, "defaultDatasetId": "ds_abc"}

    fake_actor = MagicMock()
    fake_actor.call.return_value = initial_run

    fake_dataset = MagicMock()
    fake_dataset.iterate_items.return_value = iter(fake_items)

    fake_run_client = MagicMock()
    fake_run_client.get.return_value = refreshed_run

    fake_client = MagicMock()
    fake_client.actor.return_value = fake_actor
    fake_client.dataset.return_value = fake_dataset
    fake_client.run.return_value = fake_run_client

    with patch("lead_hunter.apify.ApifyClient", return_value=fake_client):
        result = scrape_google_maps(
            api_token="tok",
            niche="plumbers",
            city="Burnaby BC",
            max_results=50,
            max_cost_usd=5.0,
        )
    assert isinstance(result, ApifyResult)
    assert result.cost_usd == 0.73
    assert len(result.businesses) == 2
    assert all(isinstance(b, Business) for b in result.businesses)
    assert result.businesses[0].name == "Bob's Plumbing"
    assert result.businesses[0].maps_reviews == 127
    assert result.businesses[1].website is None
