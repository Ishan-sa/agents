from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import Thresholds

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
)


@dataclass(frozen=True)
class FetchResult:
    ok: bool
    html: str
    status_code: int | None
    reason: str  # "" if ok


async def fetch_site(
    url: str,
    timeout_seconds: int = Thresholds.FETCH_TIMEOUT_SECONDS,
    retries: int = Thresholds.FETCH_RETRIES,
) -> FetchResult:
    if not url:
        return FetchResult(False, "", None, "no_website")

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(url)
                if 200 <= resp.status_code < 300:
                    return FetchResult(True, resp.text, resp.status_code, "")
                return FetchResult(
                    False, resp.text, resp.status_code, f"http_{resp.status_code}"
                )
        except httpx.TimeoutException as e:
            last_exc = e
            if attempt == retries:
                return FetchResult(False, "", None, "timeout")
        except httpx.ConnectError as e:
            last_exc = e
            if attempt == retries:
                return FetchResult(False, "", None, f"connect_error: {e}")
        except httpx.HTTPError as e:
            last_exc = e
            if attempt == retries:
                return FetchResult(False, "", None, f"http_error: {e}")

    return FetchResult(False, "", None, f"unknown: {last_exc}")
