import httpx
import respx

from outreach_agent.fetch import FetchResult, fetch_site


@respx.mock
async def test_fetch_success_returns_html():
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html>hi</html>")
    )
    r = await fetch_site("https://example.com")
    assert r.ok is True
    assert "hi" in r.html
    assert r.status_code == 200


@respx.mock
async def test_fetch_404_records_failure():
    respx.get("https://example.com").mock(return_value=httpx.Response(404, text=""))
    r = await fetch_site("https://example.com")
    assert r.ok is False
    assert r.reason == "http_404"


@respx.mock
async def test_fetch_timeout_returns_failure():
    respx.get("https://example.com").mock(side_effect=httpx.ReadTimeout("slow"))
    r = await fetch_site("https://example.com", timeout_seconds=1)
    assert r.ok is False
    assert r.reason == "timeout"


async def test_fetch_empty_url_returns_no_site():
    r = await fetch_site("")
    assert r.ok is False
    assert r.reason == "no_website"
