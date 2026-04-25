from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

import httpx
from dotenv import load_dotenv

EmailConfidence = Literal["high", "medium", "low", "none"]

MAX_HTML_CHARS = 120_000

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_TIMEOUT_SECONDS = 120


def _llm_settings() -> dict:
    load_dotenv()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash").strip()
    return {"api_key": key, "model": model}


def _parse_inner_json(text: str) -> dict:
    """Claude sometimes wraps JSON in ```json ... ``` fences. Extract the
    JSON object by stripping fences then slicing to the outermost {...}."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3].rstrip()
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        s = s[first : last + 1]
    return json.loads(s)

_SYSTEM_PROMPT = """You are a website quality auditor for a web agency that sells redesigns to local service businesses.

You look at the HTML of a business's current website (or are told the site is unreachable) and score it against a rubric. Return ONLY valid JSON matching the schema — no prose, no code fences.

Scoring rubric (higher = worse site = better lead, cap at 10):
- No website at all / URL 404s: +4
- URL is a Facebook/Instagram page, not a real site: +3
- Mobile-broken (no viewport meta, no responsive CSS): +2
- Pre-2015 aesthetic (table layouts, tiny fonts, dated styles): +2
- No HTTPS: +1
- No clear CTA (no Book/Call/Quote above the fold, no visible phone): +1
- Slow/heavy (page > 5MB or > 50 render-blocking resources): +1
- Broken images or missing favicon: +1
- Placeholder content (lorem ipsum, "Your Business Name", default template strings): +2
- Free-tier builder (Wix free, GoDaddy default, Weebly default, unmodified WP default theme): +2

Also extract, from the HTML:
- owner_name_guess: the business owner's full name, if findable on About/Contact/footer. Empty string if not.
- email_guess: a contact email. Prefer owner/personal over info@/contact@. Empty string if not found.
- email_confidence: "high" if clearly the owner's email, "medium" if a business email, "low" if scraped from obfuscation/regex, "none" if none found.
- contact_form_url: a URL path to a contact form, if no email was found. Empty otherwise.
- linkedin_url: a LinkedIn URL for the business or owner, if linked from the site. Empty otherwise.

Finally, write lead_pitch: 1-2 sentences explaining why this is a good lead for a web redesign agency. Ground it in concrete observations (specific issues + business signals).

Return JSON with exactly these keys:
{
  "site_score": <int 0-10>,
  "evidence": [<short string per flagged signal>],
  "owner_name_guess": <string>,
  "email_guess": <string>,
  "email_confidence": <"high"|"medium"|"low"|"none">,
  "contact_form_url": <string>,
  "linkedin_url": <string>,
  "lead_pitch": <string>
}
"""


@dataclass(frozen=True)
class JudgeResult:
    site_score: int
    evidence: list[str]
    owner_name_guess: str
    email_guess: str
    email_confidence: EmailConfidence
    contact_form_url: str
    linkedin_url: str
    lead_pitch: str


def build_judge_prompt(business_name: str, website_url: str, html: str) -> str:
    truncated = html[:MAX_HTML_CHARS]
    truncation_note = (
        f"\n\n[HTML truncated to {MAX_HTML_CHARS} chars]" if len(html) > MAX_HTML_CHARS else ""
    )
    return (
        f"{_SYSTEM_PROMPT}\n"
        f"Business: {business_name}\n"
        f"Website URL: {website_url}\n"
        f"HTML:\n{truncated}{truncation_note}\n"
    )


def judge_website(
    business_name: str,
    website_url: str,
    html: str,
    site_unreachable: bool = False,
) -> JudgeResult:
    """Call `claude -p` to score and extract from a website. Blocks."""
    if site_unreachable:
        user_prompt = (
            f"Business: {business_name}\n"
            f"Website URL: {website_url}\n"
            f"Website is UNREACHABLE (timed out or connection refused). "
            f"Score based on the signal that the site is non-functional. "
            f"Return the same JSON schema. Skip HTML extraction (return empty strings).\n"
        )
    else:
        user_prompt = build_judge_prompt(business_name, website_url, html)

    settings = _llm_settings()
    payload_req = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            OPENROUTER_URL,
            json=payload_req,
            headers=headers,
            timeout=LLM_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as e:
        raise RuntimeError(f"openrouter request failed: {e}")

    if resp.status_code != 200:
        raise RuntimeError(f"openrouter HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        payload = _parse_inner_json(content)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"openrouter returned unparseable output: {e}: {resp.text[:500]}")

    return JudgeResult(
        site_score=int(payload["site_score"]),
        evidence=list(payload.get("evidence", [])),
        owner_name_guess=str(payload.get("owner_name_guess", "")),
        email_guess=str(payload.get("email_guess", "")),
        email_confidence=payload.get("email_confidence", "none"),
        contact_form_url=str(payload.get("contact_form_url", "")),
        linkedin_url=str(payload.get("linkedin_url", "")),
        lead_pitch=str(payload.get("lead_pitch", "")),
    )
