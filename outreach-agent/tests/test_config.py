import pytest

from outreach_agent.config import Config, Thresholds


def test_config_loads_from_env(monkeypatch, tmp_path):
    sa = tmp_path / "sa.json"
    sa.write_text("{}")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet_abc")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", str(sa))
    monkeypatch.setenv("GMAIL_OAUTH_CREDENTIALS_PATH", "./gmail-oauth-credentials.json")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", "./gmail-token.json")
    monkeypatch.setenv("SENDER_NAME", "Ishan")
    monkeypatch.setenv("SENDER_AGENCY_NAME", "TestCo")
    monkeypatch.setenv("SENDER_CALENDAR_URL", "https://cal.com/ishan")

    c = Config.from_env()
    assert c.google_sheet_id == "sheet_abc"
    assert c.service_account_path == sa
    assert c.gmail_credentials_path.name == "gmail-oauth-credentials.json"
    assert c.gmail_token_path.name == "gmail-token.json"
    assert c.sender_name == "Ishan"
    assert c.sender_agency_name == "TestCo"
    assert c.sender_calendar_url == "https://cal.com/ishan"


def test_config_raises_on_missing_required(monkeypatch):
    for k in ["GOOGLE_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_PATH",
              "GMAIL_OAUTH_CREDENTIALS_PATH", "GMAIL_TOKEN_PATH",
              "SENDER_NAME", "SENDER_AGENCY_NAME", "SENDER_CALENDAR_URL"]:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="Missing required env vars"):
        Config.from_env()


def test_thresholds_constants():
    assert Thresholds.BATCH_SIZE_DEFAULT == 5
    assert Thresholds.BATCH_SIZE_HARD_CAP == 20
    assert Thresholds.FETCH_TIMEOUT_SECONDS == 15
    assert Thresholds.FETCH_RETRIES == 1
    assert Thresholds.CONCURRENCY == 3
    assert Thresholds.CLAUDE_TIMEOUT_SECONDS == 120
