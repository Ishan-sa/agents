"""Thin OpenRouter wrapper shared by reply-classification and follow-up
drafting. Mirrors outreach-agent's draft_writer style."""

from __future__ import annotations

import json

import httpx

from .config import Thresholds, llm_settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def parse_inner_json(text: str) -> dict:
    """Strip markdown code fences if present, then slice to outermost {...}."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3].rstrip()
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        s = s[first : last + 1]
    return json.loads(s)


def call_openrouter_json(*, system_prompt: str, user_prompt: str, temperature: float = 0.6) -> dict:
    settings = llm_settings()
    payload = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(
            OPENROUTER_URL, json=payload, headers=headers,
            timeout=Thresholds.LLM_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as e:
        raise RuntimeError(f"openrouter request failed: {e}")

    if resp.status_code != 200:
        raise RuntimeError(f"openrouter HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return parse_inner_json(content)
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"openrouter returned unparseable output: {e}: {resp.text[:500]}")
