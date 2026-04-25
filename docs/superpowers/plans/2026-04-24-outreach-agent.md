# Outreach Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI agent that reads qualified leads from the existing `lead-hunter` Google Sheet, drafts a personalized cold email per lead via `claude -p`, and stages each email as a Gmail draft in the operator's inbox for manual review and send.

**Architecture:** Sibling repo to `lead-hunter` (own git, own `pyproject.toml`, no shared library). Python orchestrator with `uv` dep mgmt. Subsystems: Sheets adapter (read/update Leads, append Outreach_Runs), website re-fetcher, Claude draft writer (subprocess), Gmail OAuth bootstrap + drafts.create wrapper, pipeline coordinator. Gmail uses OAuth user creds with `gmail.compose` scope only — agent cannot send or read mail.

**Tech Stack:** Python 3.12, `uv`, `gspread` + `google-auth` (Sheets), `google-auth-oauthlib` + `google-api-python-client` (Gmail), `httpx` (re-fetch), `pydantic`, `python-dotenv`, `ulid-py`, `pytest` + `pytest-asyncio` + `pytest-mock`. Claude Code CLI (`claude -p`) for all LLM reasoning.

---

## File Structure

```
agents/outreach-agent/
├── .gitignore
├── .env.example
├── CLAUDE.md
├── pyproject.toml
├── uv.lock
├── voice_examples.md            ← operator-tunable voice examples (loaded at runtime)
├── src/outreach_agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                   ← argparse, wires pipeline
│   ├── config.py                ← env + tunable thresholds
│   ├── models.py                ← pydantic: EligibleLead, LeadUpdate, DraftResult, OutreachRun
│   ├── sheets.py                ← OutreachSheets: read leads w/ row index, ensure schema, batch update
│   ├── fetch.py                 ← async website re-fetcher (mirrors lead-hunter)
│   ├── draft_writer.py          ← claude -p subprocess → DraftResult
│   ├── voice.py                 ← loads voice_examples.md and builds the system prompt
│   ├── gmail_client.py          ← Gmail API drafts.create + token refresh
│   ├── bootstrap_gmail.py       ← one-time OAuth flow CLI
│   └── pipeline.py              ← orchestrator
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_sheets.py
│   ├── test_fetch.py
│   ├── test_voice.py
│   ├── test_draft_writer.py
│   ├── test_gmail_client.py
│   └── test_pipeline.py
└── data/
    ├── .gitkeep
    └── orphaned_drafts.log      (gitignored)
```

---

## Task 1: Repo scaffold + git init

**Files:**
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/.gitignore`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/.env.example`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/pyproject.toml`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/voice_examples.md`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/data/.gitkeep`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/src/outreach_agent/__init__.py` (empty)
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/tests/__init__.py` (empty)

- [ ] **Step 1: Initialize git inside outreach-agent directory**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
git init -q
git branch -M main
```

- [ ] **Step 2: Write `.gitignore`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/.gitignore`

```
# Secrets
.env
.env.local
service-account.json
*-service-account.json
gmail-oauth-credentials.json
gmail-token.json

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# uv
.uv/

# Local data
data/*
!data/.gitkeep

# macOS
.DS_Store
```

- [ ] **Step 3: Write `.env.example`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/.env.example`

```
# Reuse the same Google Sheet as lead-hunter
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json

# Gmail OAuth (created via bootstrap_gmail.py)
GMAIL_OAUTH_CREDENTIALS_PATH=./gmail-oauth-credentials.json
GMAIL_TOKEN_PATH=./gmail-token.json

# Sender identity (embedded in every draft)
SENDER_NAME=
SENDER_AGENCY_NAME=
SENDER_CALENDAR_URL=
```

- [ ] **Step 4: Write `pyproject.toml`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/pyproject.toml`

```toml
[project]
name = "outreach-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "gspread>=6.1",
    "google-auth>=2.30",
    "google-auth-oauthlib>=1.2",
    "google-api-python-client>=2.140",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "pydantic>=2.7",
    "ulid-py>=1.1",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
    "respx>=0.21",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/outreach_agent"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["src"]

[project.scripts]
outreach-agent = "outreach_agent.cli:main"
```

- [ ] **Step 5: Write initial `voice_examples.md`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/voice_examples.md`

```markdown
# Voice examples for the outreach agent

Edit this file to tune the agent's writing voice. The examples below are loaded into the system prompt at runtime — no code changes needed when you update them.

Keep examples short, casual, lowercase-friendly. Each example shows a complete email body.

---

## Example 1 — plumber, dated WordPress site

Subject: noticed something on artisanplumbing.ca

hey artisan plumbing team,

took a quick look at your site — the COVID banner is still up from 2020 and the whole thing's running on the default WordPress theme over plain http. for a 30-year A+ BBB business, the site really undersells how established you are.

i build sites for trades companies in vancouver, usually shipping in under a week. happy to put together a free 1-page mockup of what your homepage could look like rebuilt — just reply 'yes' if you want me to send it over.

or if you'd rather chat for 15 min: <CALENDAR_URL>

ishan

---

## Example 2 — barbershop, instagram-only

Subject: your booking flow

hey shiny barbershop,

your insta looks great but the website itself is just a single page pointing back to dms — feels like you're losing walk-in searches who want to book without messaging you.

i build sites for local shops in vancouver, usually ships in a week. want me to put together a free 1-page mockup of a proper homepage with online booking? just reply 'yes' and i'll send it over.

or grab 15 min on my calendar: <CALENDAR_URL>

ishan

---

## Example 3 — appliance repair, template builder

Subject: quick note on alltechappliances.ca

hey all tech team,

site loads fine but it's clearly a yodle / template-flip — generic copy, no real photos, no clear "book a repair" button above the fold. you've got 200+ reviews so the demand is obviously there, the site just isn't catching it.

i rebuild sites for trades businesses in vancouver, ships in under a week. want a free 1-page mockup of what a real homepage could look like? reply 'yes' and i'll send it over.

or here's my calendar if you'd rather chat: <CALENDAR_URL>

ishan
```

- [ ] **Step 6: Create empty package files**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
mkdir -p src/outreach_agent tests data
touch src/outreach_agent/__init__.py tests/__init__.py data/.gitkeep
```

- [ ] **Step 7: Install deps with uv**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
uv sync
```

Expected: `.venv/` created, `uv.lock` written.

- [ ] **Step 8: Sanity check pytest collection**

```bash
uv run pytest
```

Expected: exit code 5 (no tests collected).

- [ ] **Step 9: Commit**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
git add .
git commit -q -m "chore: scaffold outreach-agent package skeleton"
```

---

## Task 2: Data models

**Files:**
- Create: `src/outreach_agent/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_models.py`

```python
from datetime import datetime, timezone

from outreach_agent.models import (
    DraftResult,
    EligibleLead,
    LeadUpdate,
    OutreachRun,
)


def test_eligible_lead_carries_row_number_and_lead_data():
    lead = EligibleLead(
        row_number=7,
        business_name="Bob's Plumbing",
        niche="plumbers",
        city="Burnaby BC",
        website="https://bobs.ca",
        email_guess="bob@bobs.ca",
        contact_form_url="",
        owner_name_guess="Bob Smith",
        site_score=7,
        site_evidence="No HTTPS; pre-2015 aesthetic",
        lead_pitch="Mobile-broken site, 127 reviews — real business.",
        tier="hot",
    )
    assert lead.row_number == 7
    assert lead.has_email() is True
    assert lead.has_absolute_form_url() is False


def test_eligible_lead_form_url_helper():
    relative = EligibleLead(
        row_number=1, business_name="X", niche="y", city="z",
        website="https://x", email_guess="", contact_form_url="/contact/",
        owner_name_guess="", site_score=4, site_evidence="", lead_pitch="",
        tier="warm",
    )
    absolute = relative.model_copy(update={"contact_form_url": "https://x/contact"})
    assert relative.has_absolute_form_url() is False
    assert absolute.has_absolute_form_url() is True


def test_draft_result_draft_action():
    d = DraftResult(
        action="draft",
        subject="noticed something on x.com",
        body="hey x team,\n...\n\nishan",
        skip_reason="",
    )
    assert d.action == "draft"
    assert d.is_draft() is True
    assert d.is_skip() is False


def test_draft_result_skip_action():
    d = DraftResult(
        action="skip",
        subject="",
        body="",
        skip_reason="site is in punjabi only",
    )
    assert d.is_skip() is True
    assert d.is_draft() is False


def test_lead_update_drafted_payload():
    u = LeadUpdate.drafted(
        row_number=7,
        date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
        subject_line="noticed something on x.com",
        gmail_draft_id="r-12345",
    )
    assert u.row_number == 7
    assert u.values["status"] == "drafted"
    assert u.values["gmail_draft_id"] == "r-12345"
    assert u.values["subject_line"] == "noticed something on x.com"
    assert u.values["skip_reason"] == ""


def test_lead_update_skipped_payload():
    u = LeadUpdate.skipped(
        row_number=9,
        date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
        skip_reason="franchise / chain",
    )
    assert u.values["status"] == "skipped"
    assert u.values["skip_reason"] == "franchise / chain"
    assert u.values["gmail_draft_id"] == ""
    assert u.values["subject_line"] == ""


def test_outreach_run_to_sheet_row():
    r = OutreachRun(
        run_id="01ABC", date=datetime(2026, 4, 25, tzinfo=timezone.utc),
        batch_size=5, filter_niche="", filter_city="", filter_tier="",
        eligible_count=12, drafted=4, skipped=1, errors=0,
        duration_seconds=42.0, dry_run=False, notes="",
    )
    row = r.to_sheet_row()
    assert row[0] == "01ABC"
    assert row[2] == "5"
    assert len(row) == len(OutreachRun.sheet_columns())
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
uv run pytest tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `models.py`**

File: `src/outreach_agent/models.py`

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Tier = Literal["hot", "warm"]
Action = Literal["draft", "skip"]


class EligibleLead(BaseModel):
    """A lead read from the Sheet that is eligible for drafting."""

    model_config = ConfigDict(frozen=True)

    row_number: int            # 1-indexed; row 1 is header, first data row is 2
    business_name: str
    niche: str
    city: str
    website: str
    email_guess: str
    contact_form_url: str
    owner_name_guess: str
    site_score: int
    site_evidence: str
    lead_pitch: str
    tier: Tier

    def has_email(self) -> bool:
        return bool(self.email_guess.strip())

    def has_absolute_form_url(self) -> bool:
        return self.contact_form_url.strip().lower().startswith(("http://", "https://"))


class DraftResult(BaseModel):
    """What the Claude draft-writer returns."""

    model_config = ConfigDict(frozen=True)

    action: Action
    subject: str
    body: str
    skip_reason: str

    def is_draft(self) -> bool:
        return self.action == "draft"

    def is_skip(self) -> bool:
        return self.action == "skip"


class LeadUpdate(BaseModel):
    """A pending update to one row in the Leads tab. Built via factory methods
    so all fields are populated correctly for each transition."""

    model_config = ConfigDict(frozen=True)

    row_number: int
    values: dict[str, str]  # column_name -> string value

    @classmethod
    def drafted(
        cls,
        *,
        row_number: int,
        date_drafted: datetime,
        subject_line: str,
        gmail_draft_id: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": "drafted",
                "date_drafted": date_drafted.isoformat(),
                "subject_line": subject_line,
                "gmail_draft_id": gmail_draft_id,
                "skip_reason": "",
            },
        )

    @classmethod
    def skipped(
        cls,
        *,
        row_number: int,
        date_drafted: datetime,
        skip_reason: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": "skipped",
                "date_drafted": date_drafted.isoformat(),
                "subject_line": "",
                "gmail_draft_id": "",
                "skip_reason": skip_reason,
            },
        )


class OutreachRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    date: datetime
    batch_size: int
    filter_niche: str
    filter_city: str
    filter_tier: str
    eligible_count: int
    drafted: int
    skipped: int
    errors: int
    duration_seconds: float
    dry_run: bool
    notes: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "run_id", "date", "batch_size",
            "filter_niche", "filter_city", "filter_tier",
            "eligible_count", "drafted", "skipped", "errors",
            "duration_seconds", "dry_run", "notes",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.run_id,
            self.date.isoformat(),
            str(self.batch_size),
            self.filter_niche,
            self.filter_city,
            self.filter_tier,
            str(self.eligible_count),
            str(self.drafted),
            str(self.skipped),
            str(self.errors),
            f"{self.duration_seconds:.1f}",
            "TRUE" if self.dry_run else "FALSE",
            self.notes,
        ]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/models.py tests/test_models.py
git commit -q -m "feat(outreach): data models for EligibleLead, LeadUpdate, DraftResult, OutreachRun"
```

---

## Task 3: Config

**Files:**
- Create: `src/outreach_agent/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_config.py`

```python
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
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `config.py`**

File: `src/outreach_agent/config.py`

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class Thresholds:
    BATCH_SIZE_DEFAULT: int = 5
    BATCH_SIZE_HARD_CAP: int = 20
    FETCH_TIMEOUT_SECONDS: int = 15
    FETCH_RETRIES: int = 1
    CONCURRENCY: int = 3
    CLAUDE_TIMEOUT_SECONDS: int = 120


@dataclass(frozen=True)
class Config:
    google_sheet_id: str
    service_account_path: Path
    gmail_credentials_path: Path
    gmail_token_path: Path
    sender_name: str
    sender_agency_name: str
    sender_calendar_url: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        required = [
            "GOOGLE_SHEET_ID",
            "GOOGLE_SERVICE_ACCOUNT_PATH",
            "GMAIL_OAUTH_CREDENTIALS_PATH",
            "GMAIL_TOKEN_PATH",
            "SENDER_NAME",
            "SENDER_AGENCY_NAME",
            "SENDER_CALENDAR_URL",
        ]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

        return cls(
            google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
            service_account_path=Path(os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"]),
            gmail_credentials_path=Path(os.environ["GMAIL_OAUTH_CREDENTIALS_PATH"]),
            gmail_token_path=Path(os.environ["GMAIL_TOKEN_PATH"]),
            sender_name=os.environ["SENDER_NAME"],
            sender_agency_name=os.environ["SENDER_AGENCY_NAME"],
            sender_calendar_url=os.environ["SENDER_CALENDAR_URL"],
        )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/config.py tests/test_config.py
git commit -q -m "feat(outreach): config loader with tunable thresholds"
```

---

## Task 4: Voice loader

**Files:**
- Create: `src/outreach_agent/voice.py`
- Create: `tests/test_voice.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_voice.py`

```python
from pathlib import Path

from outreach_agent.voice import (
    build_system_prompt,
    load_voice_examples,
)


def test_load_voice_examples_reads_file(tmp_path):
    f = tmp_path / "voice.md"
    f.write_text("# voice\n\n## Example 1\n\nhey there\n")
    text = load_voice_examples(f)
    assert "hey there" in text


def test_build_system_prompt_includes_identity_and_examples(tmp_path):
    f = tmp_path / "voice.md"
    f.write_text("EXAMPLE_BODY_TEXT_HERE")
    prompt = build_system_prompt(
        voice_examples_path=f,
        sender_name="Ishan",
        sender_agency_name="TestCo",
        sender_calendar_url="https://cal.com/ishan",
    )
    assert "EXAMPLE_BODY_TEXT_HERE" in prompt
    assert "Ishan" in prompt
    assert "TestCo" in prompt
    assert "https://cal.com/ishan" in prompt
    # Mentions JSON schema and skip rules
    assert '"action"' in prompt
    assert '"draft"' in prompt and '"skip"' in prompt
    assert "subject" in prompt.lower()
    assert "body" in prompt.lower()


def test_build_system_prompt_substitutes_calendar_placeholder(tmp_path):
    """Voice examples reference <CALENDAR_URL> as a placeholder; the prompt
    builder substitutes the actual URL so Claude sees the literal value."""
    f = tmp_path / "voice.md"
    f.write_text("here's my calendar: <CALENDAR_URL>")
    prompt = build_system_prompt(
        voice_examples_path=f,
        sender_name="Ishan",
        sender_agency_name="TestCo",
        sender_calendar_url="https://cal.com/me",
    )
    assert "<CALENDAR_URL>" not in prompt
    assert "https://cal.com/me" in prompt
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_voice.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `voice.py`**

File: `src/outreach_agent/voice.py`

```python
from __future__ import annotations

from pathlib import Path

_PROMPT_TEMPLATE = """You write cold outreach emails for {sender_name} at {sender_agency_name}, a solo web design agency that ships full website rebuilds in under a week.

You receive structured info about a local business and the HTML of their current website. You write ONE personalized email that goes into {sender_name}'s Gmail drafts folder. The operator reviews and sends manually.

# Voice rules

- Casual, direct, short. Lowercase OK in subject and greeting.
- ~80–130 words total in the body. No more.
- Plain text only. No markdown, no HTML, no bullet points, no emoji.
- One specific observation that grounds the email in their actual website. Not "I love what you do." Reference something only an actual site visitor would know — a stale banner, a broken section, a generic template, a missing booking flow.
- Do NOT use words like "leverage", "synergy", "circle back", "I hope this email finds you well", "as a fellow business owner". No corporate AI-speak.
- Sender signs off with first name only, lowercase.

# Voice examples (study these carefully — the goal is to match this tone)

{voice_examples}

# Address line

If `owner_name_guess` is non-empty and looks like a real first name, use it: "hey <first name>,". Otherwise use "hey <business name> team," or just "hey,".

# Required CTA structure (always exactly two CTAs in this order)

1. "Want a free 1-page mockup of your homepage rebuilt? Just reply 'yes'." (paraphrase OK, must include "free", "mockup", and "reply")
2. "Or here's my calendar: {sender_calendar_url}" (or paraphrase, must include the literal URL)

# When to skip (return action: "skip")

Skip and explain in skip_reason if any of these apply:
- Site is in a non-English language and you cannot understand its content
- Business is a chain or franchise (e.g., "Mr. Rooter", "1-800-Got-Junk", "Roto-Rooter") — these go through corporate procurement
- Site indicates the business is not located in the operator's region (anywhere outside Metro Vancouver)
- Site is so broken or content-thin that you have no specific observation to ground the email
- Anything else that makes the lead inappropriate for a solo founder cold outreach

# Output schema

Return ONLY valid JSON, no prose, no code fences:

{{
  "action": "draft" | "skip",
  "subject": <string, empty if action=skip>,
  "body": <string, empty if action=skip>,
  "skip_reason": <string, empty if action=draft>
}}
"""


def load_voice_examples(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_system_prompt(
    voice_examples_path: Path,
    sender_name: str,
    sender_agency_name: str,
    sender_calendar_url: str,
) -> str:
    raw_examples = load_voice_examples(voice_examples_path)
    examples = raw_examples.replace("<CALENDAR_URL>", sender_calendar_url)
    return _PROMPT_TEMPLATE.format(
        sender_name=sender_name,
        sender_agency_name=sender_agency_name,
        sender_calendar_url=sender_calendar_url,
        voice_examples=examples,
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_voice.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/voice.py tests/test_voice.py
git commit -q -m "feat(outreach): voice loader builds Claude system prompt from voice_examples.md"
```

---

## Task 5: Website re-fetcher

**Files:**
- Create: `src/outreach_agent/fetch.py`
- Create: `tests/test_fetch.py`

This mirrors lead-hunter's fetcher. We duplicate intentionally — small file, no shared library.

- [ ] **Step 1: Write the failing test**

File: `tests/test_fetch.py`

```python
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
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_fetch.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `fetch.py`**

File: `src/outreach_agent/fetch.py`

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_fetch.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/fetch.py tests/test_fetch.py
git commit -q -m "feat(outreach): async website re-fetcher with timeout and retry"
```

---

## Task 6: Draft writer (claude -p subprocess)

**Files:**
- Create: `src/outreach_agent/draft_writer.py`
- Create: `tests/test_draft_writer.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_draft_writer.py`

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from outreach_agent.draft_writer import build_user_prompt, write_draft
from outreach_agent.models import EligibleLead


def _lead(**overrides) -> EligibleLead:
    defaults = dict(
        row_number=2, business_name="Bob's Plumbing", niche="plumbers",
        city="Burnaby BC", website="https://bobs.ca",
        email_guess="bob@bobs.ca", contact_form_url="",
        owner_name_guess="Bob Smith", site_score=7,
        site_evidence="No HTTPS; pre-2015 aesthetic",
        lead_pitch="Mobile-broken site, 127 reviews — real business.",
        tier="hot",
    )
    defaults.update(overrides)
    return EligibleLead(**defaults)


def test_build_user_prompt_includes_lead_facts_and_truncates_html():
    lead = _lead()
    prompt = build_user_prompt(lead, html="<html>" + "x" * 200_000 + "</html>")
    assert "Bob's Plumbing" in prompt
    assert "Bob Smith" in prompt
    assert "https://bobs.ca" in prompt
    assert "Mobile-broken site" in prompt
    assert len(prompt) < 150_000  # truncated


def _completed(stdout_text: str, returncode: int = 0, stderr: str = ""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout_text
    m.stderr = stderr
    return m


def test_write_draft_parses_draft_action():
    payload = json.dumps({
        "result": json.dumps({
            "action": "draft",
            "subject": "noticed something on bobs.ca",
            "body": "hey bob,\n\n...\n\nishan",
            "skip_reason": "",
        })
    })
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed(payload)):
        result = write_draft(
            lead=_lead(), html="<html/>",
            system_prompt="SYSTEM_PROMPT_HERE",
        )
    assert result.is_draft()
    assert result.subject == "noticed something on bobs.ca"
    assert "hey bob" in result.body


def test_write_draft_parses_skip_action():
    payload = json.dumps({
        "result": json.dumps({
            "action": "skip",
            "subject": "",
            "body": "",
            "skip_reason": "site is in punjabi only",
        })
    })
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed(payload)):
        result = write_draft(
            lead=_lead(), html="<html/>",
            system_prompt="SYSTEM_PROMPT_HERE",
        )
    assert result.is_skip()
    assert "punjabi" in result.skip_reason


def test_write_draft_passes_system_prompt_via_cli_arg():
    payload = json.dumps({
        "result": json.dumps({
            "action": "skip", "subject": "", "body": "",
            "skip_reason": "test",
        })
    })
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed(payload)) as mock_run:
        write_draft(
            lead=_lead(), html="<html/>",
            system_prompt="MY_SYSTEM_PROMPT",
        )
    args = mock_run.call_args[0][0]
    assert "--system-prompt" in args
    sys_idx = args.index("--system-prompt")
    assert args[sys_idx + 1] == "MY_SYSTEM_PROMPT"


def test_write_draft_raises_on_nonzero_exit():
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed("", returncode=2, stderr="auth fail")):
        with pytest.raises(RuntimeError, match="auth fail"):
            write_draft(lead=_lead(), html="<html/>", system_prompt="X")


def test_write_draft_raises_on_bad_json():
    with patch("outreach_agent.draft_writer.subprocess.run",
               return_value=_completed("not json")):
        with pytest.raises(RuntimeError, match="claude -p"):
            write_draft(lead=_lead(), html="<html/>", system_prompt="X")
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_draft_writer.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `draft_writer.py`**

File: `src/outreach_agent/draft_writer.py`

```python
from __future__ import annotations

import json
import subprocess

from .config import Thresholds
from .models import DraftResult, EligibleLead

MAX_HTML_CHARS = 120_000


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
            json.loads(result_field) if isinstance(result_field, str) else result_field
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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_draft_writer.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/draft_writer.py tests/test_draft_writer.py
git commit -q -m "feat(outreach): claude -p subprocess wrapper for draft writing"
```

---

## Task 7: Sheets adapter

**Files:**
- Create: `src/outreach_agent/sheets.py`
- Create: `tests/test_sheets.py`

This is the most complex module — handles schema migration (adds new columns to Leads if absent), eligibility filtering, batched updates by row number, and the new Outreach_Runs tab.

- [ ] **Step 1: Write the failing test**

File: `tests/test_sheets.py`

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from outreach_agent.models import EligibleLead, LeadUpdate, OutreachRun
from outreach_agent.sheets import OutreachSheets

LEAD_HEADERS_BASE = [
    "date_added", "source_run", "business_name", "niche", "city",
    "address", "phone", "website", "maps_rating", "maps_reviews",
    "site_score", "site_evidence", "owner_name_guess", "email_guess",
    "email_confidence", "contact_form_url", "linkedin_url", "lead_pitch",
    "site_unreachable", "tier", "status",
]
NEW_COLS = ["date_drafted", "subject_line", "gmail_draft_id", "skip_reason"]


def _build_spread(lead_rows: list[list[str]], lead_headers=None,
                   has_outreach_runs_tab: bool = False):
    """Build a MagicMock spreadsheet with a Leads tab and optionally Outreach_Runs."""
    headers = lead_headers if lead_headers is not None else LEAD_HEADERS_BASE
    leads_ws = MagicMock()
    leads_ws.row_values.return_value = headers
    leads_ws.get_all_values.return_value = [headers, *lead_rows]
    leads_ws.col_count = len(headers)

    runs_ws = MagicMock()

    worksheets = [leads_ws]
    if has_outreach_runs_tab:
        worksheets.append(runs_ws)

    spread = MagicMock()
    spread.worksheets.return_value = worksheets

    def _ws(name):
        if name == "Leads":
            return leads_ws
        if name == "Outreach_Runs":
            if not has_outreach_runs_tab:
                from gspread import WorksheetNotFound
                raise WorksheetNotFound(name)
            return runs_ws
        raise KeyError(name)
    spread.worksheet.side_effect = _ws

    spread.add_worksheet.return_value = runs_ws
    return spread, leads_ws, runs_ws


def _row(values_by_col: dict, headers=LEAD_HEADERS_BASE) -> list[str]:
    return [str(values_by_col.get(h, "")) for h in headers]


def test_ensure_schema_adds_missing_lead_columns_and_runs_tab():
    headers = LEAD_HEADERS_BASE  # missing all 4 new cols
    spread, leads_ws, _ = _build_spread([], lead_headers=headers,
                                          has_outreach_runs_tab=False)
    sc = OutreachSheets(spread=spread)
    sc.ensure_schema()

    # Should have appended the 4 missing columns to header row
    leads_ws.update.assert_called()
    # Should have created Outreach_Runs tab
    spread.add_worksheet.assert_called_once()
    args, kwargs = spread.add_worksheet.call_args
    assert kwargs.get("title") == "Outreach_Runs" or args[0] == "Outreach_Runs"


def test_ensure_schema_idempotent_when_everything_present():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    spread, leads_ws, _ = _build_spread([], lead_headers=headers,
                                          has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    sc.ensure_schema()
    leads_ws.update.assert_not_called()
    spread.add_worksheet.assert_not_called()


def test_read_eligible_leads_filters_and_sorts():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    rows = [
        # row 2: warm, score 4, has email — eligible
        _row({
            "business_name": "Warm Co", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://w.com", "email_guess": "w@w.com",
            "site_score": "4", "site_evidence": "x", "owner_name_guess": "W",
            "lead_pitch": "p", "tier": "warm", "status": "",
        }, headers),
        # row 3: hot, score 7, has email — eligible (will sort first)
        _row({
            "business_name": "Hot Co", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://h.com", "email_guess": "h@h.com",
            "site_score": "7", "site_evidence": "x", "owner_name_guess": "H",
            "lead_pitch": "p", "tier": "hot", "status": "",
        }, headers),
        # row 4: hot, score 9, but already drafted — INELIGIBLE
        _row({
            "business_name": "Already Done", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://d.com", "email_guess": "d@d.com",
            "site_score": "9", "site_evidence": "x", "owner_name_guess": "D",
            "lead_pitch": "p", "tier": "hot", "status": "drafted",
        }, headers),
        # row 5: warm, score 5, neither email nor absolute form URL — INELIGIBLE
        _row({
            "business_name": "No Contact", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://n.com", "email_guess": "",
            "contact_form_url": "/contact/",
            "site_score": "5", "site_evidence": "x", "owner_name_guess": "",
            "lead_pitch": "p", "tier": "warm", "status": "",
        }, headers),
        # row 6: warm, score 4, absolute form URL — eligible
        _row({
            "business_name": "Form Co", "niche": "plumbers", "city": "Burnaby BC",
            "website": "https://f.com", "email_guess": "",
            "contact_form_url": "https://f.com/contact",
            "site_score": "4", "site_evidence": "x", "owner_name_guess": "",
            "lead_pitch": "p", "tier": "warm", "status": "",
        }, headers),
    ]
    spread, _, _ = _build_spread(rows, lead_headers=headers,
                                   has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    eligible = sc.read_eligible_leads()
    # Eligible: rows 2, 3, 6. Sort: tier=hot first, then site_score desc.
    names = [l.business_name for l in eligible]
    assert names == ["Hot Co", "Warm Co", "Form Co"]
    # Row numbers are 1-indexed with header on row 1
    assert eligible[0].row_number == 3
    assert eligible[1].row_number == 2
    assert eligible[2].row_number == 6


def test_read_eligible_leads_applies_filters():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    rows = [
        _row({
            "business_name": "Plumber Burnaby", "niche": "plumbers",
            "city": "Burnaby BC", "website": "https://p.com",
            "email_guess": "p@p.com", "site_score": "5", "tier": "warm",
            "status": "",
        }, headers),
        _row({
            "business_name": "Barber Vancouver", "niche": "barbers",
            "city": "Vancouver BC", "website": "https://b.com",
            "email_guess": "b@b.com", "site_score": "7", "tier": "hot",
            "status": "",
        }, headers),
    ]
    spread, _, _ = _build_spread(rows, lead_headers=headers,
                                   has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    plumbers_only = sc.read_eligible_leads(niche="plumbers")
    assert [l.business_name for l in plumbers_only] == ["Plumber Burnaby"]
    hot_only = sc.read_eligible_leads(tier="hot")
    assert [l.business_name for l in hot_only] == ["Barber Vancouver"]


def test_apply_lead_updates_writes_correct_cells():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    spread, leads_ws, _ = _build_spread([], lead_headers=headers,
                                          has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    updates = [
        LeadUpdate.drafted(
            row_number=3,
            date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
            subject_line="hey",
            gmail_draft_id="r-1",
        ),
        LeadUpdate.skipped(
            row_number=5,
            date_drafted=datetime(2026, 4, 25, tzinfo=timezone.utc),
            skip_reason="franchise",
        ),
    ]
    sc.apply_lead_updates(updates)
    leads_ws.batch_update.assert_called_once()
    payload = leads_ws.batch_update.call_args[0][0]
    # Should be one entry per (row × column-being-updated). 2 updates × 5 cols each = 10 entries.
    assert len(payload) == 10
    # Sanity: each entry has range and values
    for entry in payload:
        assert "range" in entry
        assert "values" in entry


def test_append_outreach_run_writes_one_row():
    headers = LEAD_HEADERS_BASE + NEW_COLS
    spread, _, runs_ws = _build_spread([], lead_headers=headers,
                                         has_outreach_runs_tab=True)
    sc = OutreachSheets(spread=spread)
    run = OutreachRun(
        run_id="01", date=datetime(2026, 4, 25, tzinfo=timezone.utc),
        batch_size=5, filter_niche="", filter_city="", filter_tier="",
        eligible_count=10, drafted=4, skipped=1, errors=0,
        duration_seconds=42.0, dry_run=False, notes="",
    )
    sc.append_run(run)
    runs_ws.append_row.assert_called_once()
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_sheets.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sheets.py`**

File: `src/outreach_agent/sheets.py`

```python
from __future__ import annotations

from pathlib import Path

import gspread

from .models import EligibleLead, LeadUpdate, OutreachRun, Tier

LEADS = "Leads"
OUTREACH_RUNS = "Outreach_Runs"

NEW_LEAD_COLUMNS = ["date_drafted", "subject_line", "gmail_draft_id", "skip_reason"]


def _col_letter(col_index_1based: int) -> str:
    """Convert 1-indexed column number to A1-style letter (1 → 'A', 27 → 'AA')."""
    letters = ""
    n = col_index_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


class OutreachSheets:
    def __init__(self, spread):
        self._spread = spread

    @classmethod
    def from_credentials(cls, service_account_path: Path, sheet_id: str) -> "OutreachSheets":
        gc = gspread.service_account(filename=str(service_account_path))
        return cls(spread=gc.open_by_key(sheet_id))

    def ensure_schema(self) -> None:
        """Add missing columns to Leads, create Outreach_Runs tab if absent."""
        leads_ws = self._spread.worksheet(LEADS)
        existing_headers = leads_ws.row_values(1)
        missing = [c for c in NEW_LEAD_COLUMNS if c not in existing_headers]
        if missing:
            new_headers = existing_headers + missing
            leads_ws.update(range_name="A1", values=[new_headers])

        existing_tabs = {ws.title for ws in self._spread.worksheets()}
        if OUTREACH_RUNS not in existing_tabs:
            ws = self._spread.add_worksheet(
                title=OUTREACH_RUNS, rows=1000, cols=len(OutreachRun.sheet_columns())
            )
            ws.update(range_name="A1", values=[OutreachRun.sheet_columns()])

    def read_eligible_leads(
        self,
        niche: str | None = None,
        city: str | None = None,
        tier: str | None = None,
    ) -> list[EligibleLead]:
        leads_ws = self._spread.worksheet(LEADS)
        rows = leads_ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = rows[0]
        idx = {h: i for i, h in enumerate(headers)}

        eligible: list[EligibleLead] = []
        for row_offset, raw in enumerate(rows[1:], start=2):  # row 2 is first data row
            def col(name: str) -> str:
                i = idx.get(name)
                return raw[i] if i is not None and i < len(raw) else ""

            status = col("status").strip()
            if status:
                continue  # already drafted/sent/skipped

            email = col("email_guess").strip()
            form_url = col("contact_form_url").strip()
            has_email = bool(email)
            has_abs_form = form_url.lower().startswith(("http://", "https://"))
            if not (has_email or has_abs_form):
                continue

            tier_raw = col("tier").strip().lower()
            if tier_raw not in ("hot", "warm"):
                continue

            if niche and col("niche").strip().lower() != niche.lower():
                continue
            if city and col("city").strip().lower() != city.lower():
                continue
            if tier and tier_raw != tier.lower():
                continue

            try:
                site_score = int(col("site_score") or "0")
            except ValueError:
                site_score = 0

            eligible.append(EligibleLead(
                row_number=row_offset,
                business_name=col("business_name"),
                niche=col("niche"),
                city=col("city"),
                website=col("website"),
                email_guess=email,
                contact_form_url=form_url,
                owner_name_guess=col("owner_name_guess"),
                site_score=site_score,
                site_evidence=col("site_evidence"),
                lead_pitch=col("lead_pitch"),
                tier=tier_raw,  # type: ignore[arg-type]
            ))

        # tier=hot first, then site_score desc
        eligible.sort(key=lambda l: (0 if l.tier == "hot" else 1, -l.site_score))
        return eligible

    def apply_lead_updates(self, updates: list[LeadUpdate]) -> None:
        if not updates:
            return
        leads_ws = self._spread.worksheet(LEADS)
        headers = leads_ws.row_values(1)
        col_index = {h: i + 1 for i, h in enumerate(headers)}

        payload = []
        for upd in updates:
            for col_name, value in upd.values.items():
                if col_name not in col_index:
                    continue
                cell = f"{_col_letter(col_index[col_name])}{upd.row_number}"
                payload.append({"range": cell, "values": [[value]]})

        if payload:
            leads_ws.batch_update(payload, value_input_option="RAW")

    def append_run(self, run: OutreachRun) -> None:
        ws = self._spread.worksheet(OUTREACH_RUNS)
        ws.append_row(run.to_sheet_row(), value_input_option="RAW")
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_sheets.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/sheets.py tests/test_sheets.py
git commit -q -m "feat(outreach): sheets adapter — schema migration, eligibility, batch updates"
```

---

## Task 8: Gmail client (drafts.create)

**Files:**
- Create: `src/outreach_agent/gmail_client.py`
- Create: `tests/test_gmail_client.py`

The Gmail API expects a base64-urlsafe-encoded RFC 2822 message. We use Python's `email` module to build it.

- [ ] **Step 1: Write the failing test**

File: `tests/test_gmail_client.py`

```python
import base64
from unittest.mock import MagicMock, patch

from outreach_agent.gmail_client import GmailClient, build_raw_message


def test_build_raw_message_returns_base64_with_to_subject_body():
    raw = build_raw_message(to="bob@bobs.ca", subject="hey bob",
                             body="line one\nline two")
    decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
    assert "To: bob@bobs.ca" in decoded
    assert "Subject: hey bob" in decoded
    assert "line one" in decoded
    assert "line two" in decoded


def test_build_raw_message_handles_empty_to_field():
    """When email is empty (form-only lead), still produces a valid message."""
    raw = build_raw_message(to="", subject="s", body="b")
    decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
    assert "Subject: s" in decoded
    assert "b" in decoded


def test_create_draft_calls_gmail_api_and_returns_id():
    fake_create = MagicMock()
    fake_create.execute.return_value = {"id": "r-12345", "message": {"id": "m-1"}}
    fake_drafts = MagicMock()
    fake_drafts.create.return_value = fake_create
    fake_users = MagicMock()
    fake_users.drafts.return_value = fake_drafts
    fake_service = MagicMock()
    fake_service.users.return_value = fake_users

    client = GmailClient(service=fake_service)
    draft_id = client.create_draft(to="bob@bobs.ca", subject="hey",
                                     body="hi")
    assert draft_id == "r-12345"
    fake_drafts.create.assert_called_once()
    kwargs = fake_drafts.create.call_args.kwargs
    assert kwargs["userId"] == "me"
    assert "raw" in kwargs["body"]["message"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_gmail_client.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `gmail_client.py`**

File: `src/outreach_agent/gmail_client.py`

```python
from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def build_raw_message(to: str, subject: str, body: str) -> str:
    """Return a base64-urlsafe-encoded RFC 2822 message for Gmail API."""
    msg = MIMEText(body, _charset="utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")


class GmailClient:
    def __init__(self, service):
        self._service = service

    @classmethod
    def from_token(cls, token_path: Path) -> "GmailClient":
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return cls(service=service)

    def create_draft(self, to: str, subject: str, body: str) -> str:
        raw = build_raw_message(to=to, subject=subject, body=body)
        resp = self._service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()
        return resp["id"]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_gmail_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/outreach_agent/gmail_client.py tests/test_gmail_client.py
git commit -q -m "feat(outreach): Gmail API wrapper for drafts.create"
```

---

## Task 9: Bootstrap Gmail OAuth (one-time CLI)

**Files:**
- Create: `src/outreach_agent/bootstrap_gmail.py`

This is a small CLI script the operator runs ONCE to authorize the agent. No tests — it's an interactive browser flow that depends on Google's UI.

- [ ] **Step 1: Implement `bootstrap_gmail.py`**

File: `src/outreach_agent/bootstrap_gmail.py`

```python
"""One-time setup: opens a browser, asks the operator to authorize the agent
to create Gmail drafts in their account, and writes the resulting refresh
token to disk. Run once before using the outreach-agent CLI for the first time."""

from __future__ import annotations

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import Config
from .gmail_client import GMAIL_SCOPES


def main() -> int:
    cfg = Config.from_env()

    if not cfg.gmail_credentials_path.exists():
        print(
            f"ERROR: OAuth client credentials not found at "
            f"{cfg.gmail_credentials_path}.\n"
            f"Create an OAuth client (type: Desktop App) in Google Cloud Console, "
            f"download the JSON, and save it to that path.",
            file=sys.stderr,
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(
        str(cfg.gmail_credentials_path), GMAIL_SCOPES
    )
    creds = flow.run_local_server(port=0, open_browser=True)
    cfg.gmail_token_path.write_text(creds.to_json())
    print(f"✓ Gmail token saved to {cfg.gmail_token_path}")
    print("You can now run: uv run python -m outreach_agent --batch-size 5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke check the file imports cleanly (no auth happens)**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
uv run python -c "from outreach_agent import bootstrap_gmail; print('ok')"
```

Expected: prints `ok`. (Running `main()` requires real env + credentials; smoke test only verifies imports.)

- [ ] **Step 3: Commit**

```bash
git add src/outreach_agent/bootstrap_gmail.py
git commit -q -m "feat(outreach): bootstrap_gmail — one-time OAuth flow CLI"
```

---

## Task 10: Pipeline orchestration

**Files:**
- Create: `src/outreach_agent/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_pipeline.py`

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from outreach_agent.fetch import FetchResult
from outreach_agent.models import DraftResult, EligibleLead, OutreachRun
from outreach_agent.pipeline import run_pipeline


def _lead(name, row, tier="warm", score=4, email="x@x", form=""):
    return EligibleLead(
        row_number=row, business_name=name, niche="plumbers", city="Burnaby BC",
        website=f"https://{name.lower().replace(' ', '')}.com",
        email_guess=email, contact_form_url=form, owner_name_guess="",
        site_score=score, site_evidence="x", lead_pitch="p", tier=tier,
    )


async def _async_return(value):
    return value


async def test_pipeline_drafts_skips_and_writes_to_sheet():
    leads = [
        _lead("Hot", 2, tier="hot", score=8),
        _lead("Warm", 3, tier="warm", score=4),
        _lead("Chain", 4, tier="warm", score=5),
    ]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads

    fetch_results = {
        "https://hot.com": FetchResult(True, "<html>HOT</html>", 200, ""),
        "https://warm.com": FetchResult(True, "<html>WARM</html>", 200, ""),
        "https://chain.com": FetchResult(True, "<html>CHAIN</html>", 200, ""),
    }

    drafts_by_business = {
        "Hot": DraftResult(action="draft", subject="hot subject",
                            body="hot body", skip_reason=""),
        "Warm": DraftResult(action="draft", subject="warm subject",
                             body="warm body", skip_reason=""),
        "Chain": DraftResult(action="skip", subject="", body="",
                              skip_reason="franchise / chain"),
    }

    gmail = MagicMock()
    # draft_id depends on order called; use side_effect of subject prefix
    gmail.create_draft.side_effect = lambda to, subject, body: f"r-{subject[:3]}"

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(fetch_results[url])), \
         patch("outreach_agent.pipeline.write_draft",
               side_effect=lambda lead, html, system_prompt: drafts_by_business[lead.business_name]), \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets,
            gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="Ishan", sender_agency_name="Co",
            sender_calendar_url="https://cal/me",
            batch_size=5,
            niche=None, city=None, tier=None,
            dry_run=False,
        )

    assert isinstance(run, OutreachRun)
    assert run.drafted == 2
    assert run.skipped == 1
    assert run.errors == 0
    sheets.ensure_schema.assert_called_once()
    sheets.apply_lead_updates.assert_called_once()
    sheets.append_run.assert_called_once()
    # Two Gmail drafts should have been created (Hot + Warm), Chain was skipped
    assert gmail.create_draft.call_count == 2


async def test_pipeline_dry_run_skips_gmail_and_sheet_writes():
    leads = [_lead("Hot", 2, tier="hot", score=8)]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads

    gmail = MagicMock()

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(
                   FetchResult(True, "<html/>", 200, ""))), \
         patch("outreach_agent.pipeline.write_draft",
               return_value=DraftResult(action="draft", subject="s",
                                          body="b", skip_reason="")), \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets, gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="I", sender_agency_name="C",
            sender_calendar_url="https://x",
            batch_size=5, niche=None, city=None, tier=None,
            dry_run=True,
        )
    assert run.dry_run is True
    assert run.drafted == 1
    gmail.create_draft.assert_not_called()
    sheets.apply_lead_updates.assert_not_called()
    sheets.append_run.assert_not_called()


async def test_pipeline_batch_size_caps_results():
    leads = [_lead(f"L{i}", i + 2) for i in range(10)]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads
    gmail = MagicMock()
    gmail.create_draft.return_value = "r-x"

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(
                   FetchResult(True, "<html/>", 200, ""))), \
         patch("outreach_agent.pipeline.write_draft",
               return_value=DraftResult(action="draft", subject="s",
                                          body="b", skip_reason="")), \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets, gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="I", sender_agency_name="C",
            sender_calendar_url="https://x",
            batch_size=3, niche=None, city=None, tier=None,
            dry_run=False,
        )
    assert run.drafted == 3
    assert gmail.create_draft.call_count == 3


async def test_pipeline_handles_fetch_failure_as_error():
    leads = [_lead("Hot", 2, tier="hot", score=8)]
    sheets = MagicMock()
    sheets.read_eligible_leads.return_value = leads
    gmail = MagicMock()

    with patch("outreach_agent.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(
                   FetchResult(False, "", None, "timeout"))), \
         patch("outreach_agent.pipeline.write_draft") as mock_write, \
         patch("outreach_agent.pipeline.build_system_prompt", return_value="SYS"):
        run = await run_pipeline(
            sheets=sheets, gmail=gmail,
            voice_examples_path=MagicMock(),
            sender_name="I", sender_agency_name="C",
            sender_calendar_url="https://x",
            batch_size=5, niche=None, city=None, tier=None,
            dry_run=False,
        )
    assert run.drafted == 0
    assert run.errors == 1
    mock_write.assert_not_called()
    gmail.create_draft.assert_not_called()
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `pipeline.py`**

File: `src/outreach_agent/pipeline.py`

```python
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import ulid

from .config import Thresholds
from .draft_writer import write_draft
from .fetch import fetch_site
from .gmail_client import GmailClient
from .models import EligibleLead, LeadUpdate, OutreachRun
from .sheets import OutreachSheets
from .voice import build_system_prompt


def _resolve_recipient(lead: EligibleLead) -> str:
    """Use email_guess if present; otherwise empty string (operator handles
    form-only leads manually in Gmail's compose UI)."""
    return lead.email_guess.strip() if lead.has_email() else ""


async def run_pipeline(
    sheets: OutreachSheets,
    gmail: GmailClient,
    voice_examples_path: Path,
    sender_name: str,
    sender_agency_name: str,
    sender_calendar_url: str,
    batch_size: int,
    niche: str | None,
    city: str | None,
    tier: str | None,
    dry_run: bool,
) -> OutreachRun:
    start = time.time()
    batch_size = min(batch_size, Thresholds.BATCH_SIZE_HARD_CAP)
    run_id = str(ulid.new())
    now = datetime.now(timezone.utc)

    sheets.ensure_schema()

    eligible_all = sheets.read_eligible_leads(niche=niche, city=city, tier=tier)
    eligible_count = len(eligible_all)
    leads = eligible_all[:batch_size]

    system_prompt = build_system_prompt(
        voice_examples_path=voice_examples_path,
        sender_name=sender_name,
        sender_agency_name=sender_agency_name,
        sender_calendar_url=sender_calendar_url,
    )

    sem = asyncio.Semaphore(Thresholds.CONCURRENCY)
    results: list[tuple[EligibleLead, str, Exception | None]] = []
    # status: ("drafted" | "skipped" | "error", payload)

    async def process(lead: EligibleLead):
        async with sem:
            fetch = await fetch_site(lead.website)
            if not fetch.ok:
                return (lead, "error", RuntimeError(f"fetch_failed: {fetch.reason}"))
            try:
                draft_or_skip = await asyncio.to_thread(
                    write_draft, lead, fetch.html, system_prompt
                )
            except Exception as e:
                return (lead, "error", e)

            if draft_or_skip.is_skip():
                return (lead, "skipped", draft_or_skip)
            return (lead, "drafted", draft_or_skip)

    raw = await asyncio.gather(*(process(l) for l in leads))

    drafted = 0
    skipped = 0
    errors = 0
    notes_lines: list[str] = []
    updates: list[LeadUpdate] = []

    for lead, status, payload in raw:
        if status == "error":
            errors += 1
            notes_lines.append(f"{lead.business_name}: {payload}")
            continue

        if status == "skipped":
            skipped += 1
            if not dry_run:
                updates.append(LeadUpdate.skipped(
                    row_number=lead.row_number,
                    date_drafted=now,
                    skip_reason=payload.skip_reason,
                ))
            continue

        # status == "drafted"
        if dry_run:
            drafted += 1
            print(f"\n--- DRY RUN draft for {lead.business_name} ---")
            print(f"To: {_resolve_recipient(lead)}")
            print(f"Subject: {payload.subject}")
            print(f"\n{payload.body}\n")
            continue

        try:
            draft_id = gmail.create_draft(
                to=_resolve_recipient(lead),
                subject=payload.subject,
                body=payload.body,
            )
            drafted += 1
            updates.append(LeadUpdate.drafted(
                row_number=lead.row_number,
                date_drafted=now,
                subject_line=payload.subject,
                gmail_draft_id=draft_id,
            ))
        except Exception as e:
            errors += 1
            notes_lines.append(f"{lead.business_name}: gmail_create_failed: {e}")

    if not dry_run:
        sheets.apply_lead_updates(updates)

    duration = time.time() - start
    run = OutreachRun(
        run_id=run_id, date=now, batch_size=batch_size,
        filter_niche=niche or "", filter_city=city or "", filter_tier=tier or "",
        eligible_count=eligible_count, drafted=drafted, skipped=skipped,
        errors=errors, duration_seconds=duration, dry_run=dry_run,
        notes="; ".join(notes_lines),
    )
    if not dry_run:
        sheets.append_run(run)
    return run
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all tests pass (~33 total: models 7 + config 3 + voice 3 + fetch 4 + draft_writer 6 + sheets 6 + gmail 3 + pipeline 4 = 36).

- [ ] **Step 6: Commit**

```bash
git add src/outreach_agent/pipeline.py tests/test_pipeline.py
git commit -q -m "feat(outreach): pipeline orchestrator wiring fetch, draft, gmail, sheets"
```

---

## Task 11: CLI

**Files:**
- Create: `src/outreach_agent/cli.py`
- Create: `src/outreach_agent/__main__.py`

- [ ] **Step 1: Implement `cli.py`**

File: `src/outreach_agent/cli.py`

```python
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import Config, Thresholds
from .gmail_client import GmailClient
from .pipeline import run_pipeline
from .sheets import OutreachSheets


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="outreach-agent",
        description=(
            "Read qualified leads from the Google Sheet and stage personalized "
            "Gmail drafts for manual review."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=Thresholds.BATCH_SIZE_DEFAULT,
                        help=f"how many drafts to create (default {Thresholds.BATCH_SIZE_DEFAULT}, "
                             f"max {Thresholds.BATCH_SIZE_HARD_CAP})")
    parser.add_argument("--niche", default=None, help='filter to one niche (e.g. "plumbers")')
    parser.add_argument("--city", default=None, help='filter to one city (e.g. "Burnaby BC")')
    parser.add_argument("--tier", default=None, choices=["hot", "warm"],
                        help="filter to one tier")
    parser.add_argument("--dry-run", action="store_true",
                        help="research and write drafts but skip Gmail and Sheets writes; print to stdout")
    args = parser.parse_args()

    cfg = Config.from_env()
    sheets = OutreachSheets.from_credentials(
        service_account_path=cfg.service_account_path,
        sheet_id=cfg.google_sheet_id,
    )
    gmail = GmailClient.from_token(cfg.gmail_token_path)
    voice_path = Path("voice_examples.md").resolve()

    print(
        f"→ outreach-agent: batch={args.batch_size} "
        f"niche={args.niche or '*'} city={args.city or '*'} tier={args.tier or '*'} "
        f"{'(DRY RUN)' if args.dry_run else ''}"
    )
    run = asyncio.run(run_pipeline(
        sheets=sheets, gmail=gmail, voice_examples_path=voice_path,
        sender_name=cfg.sender_name,
        sender_agency_name=cfg.sender_agency_name,
        sender_calendar_url=cfg.sender_calendar_url,
        batch_size=args.batch_size,
        niche=args.niche, city=args.city, tier=args.tier,
        dry_run=args.dry_run,
    ))
    print(
        f"✓ run {run.run_id}: {run.drafted} drafted, {run.skipped} skipped, "
        f"{run.errors} errors, {run.duration_seconds:.1f}s "
        f"(eligible: {run.eligible_count})"
    )
    if run.notes:
        print(f"  notes: {run.notes}")
    return 0 if run.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Implement `__main__.py`**

File: `src/outreach_agent/__main__.py`

```python
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 3: Smoke test CLI help (no env required)**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
uv run python -m outreach_agent --help
```

Expected: argparse help text showing `--batch-size`, `--niche`, `--city`, `--tier`, `--dry-run`.

- [ ] **Step 4: Commit**

```bash
git add src/outreach_agent/cli.py src/outreach_agent/__main__.py
git commit -q -m "feat(outreach): CLI entry point with batch + filter + dry-run flags"
```

---

## Task 12: CLAUDE.md

**Files:**
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent/CLAUDE.md`

```markdown
# outreach-agent

Reads qualified leads from the Google Sheet maintained by `lead-hunter`, drafts a personalized cold email per lead via `claude -p`, and stages each as a Gmail draft for manual review and send.

## Setup (one time)

1. `uv sync`
2. Copy `service-account.json` from `lead-hunter/` (same Google service account is reused for Sheets access).
3. Copy `.env.example` to `.env` and fill:
   - `GOOGLE_SHEET_ID` — same as lead-hunter
   - `GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json`
   - `GMAIL_OAUTH_CREDENTIALS_PATH=./gmail-oauth-credentials.json`
   - `GMAIL_TOKEN_PATH=./gmail-token.json`
   - `SENDER_NAME` — your first name
   - `SENDER_AGENCY_NAME` — your agency's name
   - `SENDER_CALENDAR_URL` — your Calendly / Cal.com link
4. In Google Cloud Console (the same project as lead-hunter):
   - Enable the Gmail API
   - Create an OAuth Client ID, type **Desktop App**, name `outreach-agent`
   - Download the JSON, save to `./gmail-oauth-credentials.json`
5. Run the one-time OAuth bootstrap:
   ```bash
   uv run python -m outreach_agent.bootstrap_gmail
   ```
   A browser opens. Log in with the Google account that should receive drafts. Grant `gmail.compose` scope only. The refresh token is saved to `./gmail-token.json`.
6. Ensure `claude` CLI is installed and `claude login` has been run with the Max subscription account.

## Run

```bash
# default: 5 drafts, top hot/warm leads first, real Gmail drafts created
uv run python -m outreach_agent

# bigger batch
uv run python -m outreach_agent --batch-size 15

# filter by niche / city / tier
uv run python -m outreach_agent --niche "plumbers" --city "Maple Ridge BC"
uv run python -m outreach_agent --tier hot --batch-size 10

# preview without creating Gmail drafts (prints to stdout, no sheet writes)
uv run python -m outreach_agent --batch-size 3 --dry-run
```

After a real run:
- New drafts appear in your Gmail Drafts folder.
- The `Leads` sheet has `status=drafted` for those leads with `subject_line`, `gmail_draft_id`, `date_drafted`.
- The `Outreach_Runs` sheet has a new row summarizing the run.

You then open Gmail, review each draft, and click Send (or edit then send).

## Tuning the agent's voice

Edit `voice_examples.md`. Add 1-2 of your best-performing real emails as new examples. Remove examples that don't match your voice. The file is loaded fresh each run — no code changes needed.

If you want to change scoring thresholds (batch size, concurrency), edit `src/outreach_agent/config.py` → `Thresholds`.

## Costs

- Apify: $0 (no scraping; reuses lead-hunter data)
- Claude: $0 at margin (Max subscription via `claude -p`)
- Gmail / Sheets: free
- **Total per draft: ~$0.**

## Out of scope

No sending — you click Send. No reply detection. No follow-ups. No mockup generation. No LinkedIn outreach. Each is a separate agent.

## Reverting a bad draft

If a draft was created and you want to undo it: delete the draft in Gmail, then in the Leads sheet set `status=""` and clear `gmail_draft_id` for that row. The lead becomes eligible again on next run.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -q -m "docs(outreach): operator-facing CLAUDE.md with setup and run instructions"
```

---

## Task 13: End-to-end smoke test (manual, with real accounts)

This is operator-driven. The agent depends on real Gmail OAuth, real Sheet, and real `claude` CLI, none of which can be mocked end-to-end.

- [ ] **Step 1: Verify prerequisites**

Operator has completed all setup steps in `CLAUDE.md`:
- `.env` filled
- `service-account.json` copied from lead-hunter
- `gmail-oauth-credentials.json` downloaded from Google Cloud
- Bootstrap OAuth flow completed (`gmail-token.json` exists)
- `claude --version` works

- [ ] **Step 2: Dry-run first**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/outreach-agent
uv run python -m outreach_agent --batch-size 3 --dry-run
```

Expected:
- Prints 3 draft previews to stdout
- No Gmail drafts created (check Gmail to confirm)
- No new rows in Leads or Outreach_Runs (check sheet)
- Drafts look right (subject is specific, body references something concrete from each site)

If drafts look bad, edit `voice_examples.md` and re-run the dry-run before going to step 3.

- [ ] **Step 3: Real run, small batch**

```bash
uv run python -m outreach_agent --batch-size 3
```

Expected:
- 3 drafts appear in Gmail Drafts folder
- 3 rows in Leads have `status=drafted` with `subject_line`, `gmail_draft_id` populated
- 1 new row in Outreach_Runs

- [ ] **Step 4: Verify success criterion**

Open Gmail Drafts. Read all 3 drafts. Operator should be willing to send at least 2 of the 3 with no edits, and the third with minor tweaks. If quality is below that bar, tune `voice_examples.md` and re-run.

- [ ] **Step 5: Commit any voice tuning**

```bash
git add voice_examples.md
git commit -q -m "tune(outreach): voice_examples adjusted after first real-batch review"
```

---

## Self-Review

**Spec coverage:**
- §1 Purpose / §2 Operator context — Tasks 1, 12 ✓
- §3 CTA — Task 4 (system prompt embeds CTA + voice examples reference it) ✓
- §4 Inputs — Task 11 CLI ✓
- §5 Lead selection — Task 7 (`read_eligible_leads`) ✓
- §6.1 New Leads columns — Task 7 (`ensure_schema` adds them) ✓
- §6.2 Outreach_Runs tab — Task 7 (`ensure_schema` creates), Task 2 model ✓
- §6.3 Gmail drafts — Task 8 ✓
- §7 Architecture — Task 10 pipeline ✓
- §8 Email voice / structure — Task 4 voice loader + voice_examples.md content in Task 1 ✓
- §9 Skip rules — Task 4 (system prompt enumerates them) ✓
- §10 Gmail integration — Tasks 8 + 9 ✓
- §11 Cost & limits — Task 3 Thresholds ✓
- §12 Failure modes — Tasks 5, 6, 10 (fetch failures → error; bad JSON → exception bubbles up; skip → skipped status; dry_run path) ✓
- §13 Repo layout — Task 1 ✓
- §14 Env vars — Task 1 + Task 3 ✓
- §15 Out of scope — respected throughout (no send, no reply, no follow-up) ✓
- §16 Success criteria — Task 13 step 4 ✓

**Placeholder scan:** No "TBD", no "implement later", no "similar to Task N", no vague "add error handling". Each test step has full code.

**Type consistency:**
- `Tier = Literal["hot", "warm"]` defined in models.py, used consistently
- `Action = Literal["draft", "skip"]` defined in models.py, used in DraftResult and pipeline
- `EligibleLead.row_number` is 1-indexed throughout (header=1, first data row=2) — consistent across sheets.py, models.py, pipeline.py, tests
- `LeadUpdate.values` keys are exactly the 5 new columns: `status`, `date_drafted`, `subject_line`, `gmail_draft_id`, `skip_reason` — consistent across models.py factories, sheets.py `apply_lead_updates`, and the column list in sheets.py `NEW_LEAD_COLUMNS`
- `OutreachRun.sheet_columns()` matches the columns documented in spec §6.2
- `gmail_compose` scope (`https://www.googleapis.com/auth/gmail.compose`) defined once in `gmail_client.GMAIL_SCOPES` and reused in bootstrap_gmail.py via import

**Gaps fixed inline:**
- Pipeline test for fetch failure path added (was implicit in spec §12 failure modes)
- `_resolve_recipient` helper documented for the form-only-lead edge case (spec §6.3)
- Dry-run path explicitly tested to avoid accidental Gmail writes during testing (spec §4 inputs)

No further issues found.
