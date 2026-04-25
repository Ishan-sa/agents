import os
import pytest
from lead_hunter.config import Config, Thresholds


def test_config_loads_from_env(monkeypatch, tmp_path):
    sa = tmp_path / "sa.json"
    sa.write_text("{}")
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_123")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet_abc")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", str(sa))
    monkeypatch.setenv("APIFY_MAX_COST_USD", "5")
    monkeypatch.setenv("DEFAULT_MAX_RESULTS", "100")

    c = Config.from_env()
    assert c.apify_api_token == "tok_123"
    assert c.google_sheet_id == "sheet_abc"
    assert c.service_account_path == sa
    assert c.apify_max_cost_usd == 5.0
    assert c.default_max_results == 100


def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="APIFY_API_TOKEN"):
        Config.from_env()


def test_thresholds_are_constants():
    assert Thresholds.REVIEWS_MIN == 10
    assert Thresholds.RATING_MIN == 3.5
    assert Thresholds.RATING_REJECT_BELOW == 3.0
    assert Thresholds.SITE_SCORE_HOT_MIN == 6
    assert Thresholds.SITE_SCORE_WARM_MIN == 3
    assert Thresholds.SITE_SCORE_REJECT_MAX == 2
    assert Thresholds.MAX_RESULTS_HARD_CAP == 250
    assert Thresholds.FETCH_CONCURRENCY == 10
    assert Thresholds.FETCH_TIMEOUT_SECONDS == 15
    assert Thresholds.FETCH_RETRIES == 1
    assert Thresholds.REVIEWS_DEAD_BELOW == 5
