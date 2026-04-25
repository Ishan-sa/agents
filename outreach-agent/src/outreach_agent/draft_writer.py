from __future__ import annotations

import json
import subprocess

from .config import Thresholds
from .models import DraftResult, EligibleLead

MAX_HTML_CHARS = 120_000


def _parse_inner_json(text: str) -> dict:
    """Claude sometimes wraps JSON in ```json ... ``` fences. Extract the
    JSON object by finding the first '{' and the matching last '}'."""
    s = text.strip()
    if s.startswith("```"):
        # strip opening fence (```json or ```)
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        # strip closing fence
        if s.endswith("```"):
            s = s[: -3].rstrip()
    # As a final safety net, slice to the outermost {...}
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

    cmd = [
        "claude", "-p",
        "--model", "claude-sonnet-4-6",
        "--output-format", "json",
        "--max-turns", "1",
        "--system-prompt", system_prompt,
        user_prompt,
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=Thresholds.CLAUDE_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {proc.stderr.strip() or 'no stderr'}")

    try:
        outer = json.loads(proc.stdout)
        result_field = outer["result"]
        payload = (
            _parse_inner_json(result_field) if isinstance(result_field, str) else result_field
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise RuntimeError(
            f"claude -p returned unparseable output: {e}: {proc.stdout[:500]}"
        )

    return DraftResult(
        action=payload["action"],
        subject=str(payload.get("subject", "")),
        body=str(payload.get("body", "")),
        skip_reason=str(payload.get("skip_reason", "")),
    )
