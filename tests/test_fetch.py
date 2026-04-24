import httpx
import pytest
import respx

from lead_hunter.fetch import FetchResult, fetch_site


@respx.mock
async def test_fetch_success_returns_html():
    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="<html><body>hi</body></html>")
    )
    r = await fetch_site("https://example.com")
    assert isinstance(r, FetchResult)
    assert r.ok is True
    assert "hi" in r.html
    assert r.status_code == 200
    assert r.final_url == "https://example.com"


@respx.mock
async def test_fetch_404_marks_unreachable_false_but_records_status():
    respx.get("https://example.com").mock(return_value=httpx.Response(404, text=""))
    r = await fetch_site("https://example.com")
    assert r.ok is False
    assert r.status_code == 404
    assert r.reason == "http_404"


@respx.mock
async def test_fetch_network_error_returns_failure():
    respx.get("https://example.com").mock(side_effect=httpx.ConnectError("boom"))
    r = await fetch_site("https://example.com")
    assert r.ok is False
    assert r.status_code is None
    assert "connect" in r.reason.lower()


@respx.mock
async def test_fetch_timeout_returns_failure():
    respx.get("https://example.com").mock(side_effect=httpx.ReadTimeout("slow"))
    r = await fetch_site("https://example.com", timeout_seconds=1)
    assert r.ok is False
    assert r.reason == "timeout"


async def test_fetch_none_url_returns_no_site():
    r = await fetch_site(None)
    assert r.ok is False
    assert r.reason == "no_website"
