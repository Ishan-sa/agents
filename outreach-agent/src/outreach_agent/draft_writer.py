from __future__ import annotations

import json

import httpx

from .config import Thresholds, llm_settings
from .models import DraftResult, EligibleLead

MAX_HTML_CHARS = 120_000

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _parse_inner_json(text: str) -> dict:
    """Strip markdown code fences if present, then slice to outermost {...}."""
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


def build_user_prompt(lead: EligibleLead, html: str) -> str:
    truncated = html[:MAX_HTML_CHARS]
    truncation_note = (
        f"\n\n[HTML truncated to {MAX_HTML_CHARS} chars]"
        if len(html) > MAX_HTML_CHARS
        else ""
    )
    return (
        f"Business: {lead.business_name}\n"
        f"Niche: {lead.niche}\n"
        f"City: {lead.city}\n"
        f"Website: {lead.website}\n"
        f"Owner name guess: {lead.owner_name_guess}\n"
        f"Tier: {lead.tier}\n"
        f"Site score (0-10, higher = worse site): {lead.site_score}\n"
        f"Site evidence (from earlier audit): {lead.site_evidence}\n"
        f"Lead pitch (from earlier audit): {lead.lead_pitch}\n"
        f"\n--- CURRENT HTML ---\n{truncated}{truncation_note}\n"
    )


def write_draft(
    lead: EligibleLead,
    html: str,
    system_prompt: str,
) -> DraftResult:
    user_prompt = build_user_prompt(lead, html)
    settings = llm_settings()

    payload = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            OPENROUTER_URL,
            json=payload,
            headers=headers,
            timeout=Thresholds.LLM_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as e:
        raise RuntimeError(f"openrouter request failed: {e}")

    if resp.status_code != 200:
        raise RuntimeError(f"openrouter HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _parse_inner_json(content)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"openrouter returned unparseable output: {e}: {resp.text[:500]}")

    return DraftResult(
        action=parsed["action"],
        subject=str(parsed.get("subject", "")),
        body=str(parsed.get("body", "")),
        skip_reason=str(parsed.get("skip_reason", "")),
    )
