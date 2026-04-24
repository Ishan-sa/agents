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
    final_url: str
    reason: str  # "" if ok, else "no_website"/"timeout"/"http_404"/"connect_error"/etc.
    bytes_size: int


async def fetch_site(
    url: str | None,
    timeout_seconds: int = Thresholds.FETCH_TIMEOUT_SECONDS,
    retries: int = Thresholds.FETCH_RETRIES,
) -> FetchResult:
    if not url:
        return FetchResult(False, "", None, "", "no_website", 0)

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(url)
                text = resp.text
                if 200 <= resp.status_code < 300:
                    return FetchResult(
                        ok=True,
                        html=text,
                        status_code=resp.status_code,
                        final_url=str(resp.url),
                        reason="",
                        bytes_size=len(text.encode("utf-8", errors="ignore")),
                    )
                return FetchResult(
                    ok=False,
                    html=text,
                    status_code=resp.status_code,
                    final_url=str(resp.url),
                    reason=f"http_{resp.status_code}",
                    bytes_size=len(text.encode("utf-8", errors="ignore")),
                )
        except httpx.TimeoutException as e:
            last_exc = e
            if attempt == retries:
                return FetchResult(False, "", None, url, "timeout", 0)
        except httpx.ConnectError as e:
            last_exc = e
            if attempt == retries:
                return FetchResult(False, "", None, url, f"connect_error: {e}", 0)
        except httpx.HTTPError as e:
            last_exc = e
            if attempt == retries:
                return FetchResult(False, "", None, url, f"http_error: {e}", 0)

    # Unreachable, but keep type-checker happy
    return FetchResult(False, "", None, url, f"unknown: {last_exc}", 0)
