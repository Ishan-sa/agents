# Lead-Hunter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python-based Claude Code agent that scrapes Google Maps via Apify, judges each business's website quality using Claude via subscription-authed `claude -p` subprocess calls, qualifies leads, and writes results to a Google Sheet.

**Architecture:** Python orchestrator (`uv`-managed, no venv fuss) wraps four subsystems — Apify client, website fetcher, Claude judge (subprocess), Google Sheets writer — coordinated by a pipeline module. Pure-logic modules (qualifier, dedup) are TDD'd; wrapper modules get integration-style tests with mocked externals.

**Tech Stack:** Python 3.12, `uv`, `apify-client`, `gspread` + `google-auth`, `httpx` (async), `beautifulsoup4`, `python-dotenv`, `pydantic` for models, `pytest` + `pytest-asyncio` for tests. Claude Code CLI (`claude -p`) for all LLM reasoning.

---

## File Structure

```
agents/
├── .gitignore                    # root: ignores .env, service-account.json, data/, __pycache__, .venv
├── README.md                     # root: lists each agent, what it does
└── lead-hunter/
    ├── .env.example              # template with empty API keys
    ├── CLAUDE.md                 # operator-facing usage, agent rubric
    ├── pyproject.toml            # uv project config + deps
    ├── uv.lock                   # committed, from `uv lock`
    ├── src/lead_hunter/
    │   ├── __init__.py
    │   ├── __main__.py           # `python -m lead_hunter …` entry
    │   ├── cli.py                # argparse, wires into pipeline
    │   ├── config.py             # env loading + thresholds
    │   ├── models.py             # pydantic: Business, Lead, RejectedLead, Run
    │   ├── qualifier.py          # pure rules: score + maps stats → tier / reject
    │   ├── dedup.py              # pure: given existing keys + incoming list → new list
    │   ├── fetch.py              # async website fetcher with timeout/retry
    │   ├── claude_judge.py       # `claude -p` subprocess wrapper → score + extract
    │   ├── apify.py              # Apify Google Maps scraper wrapper
    │   ├── sheets.py             # gspread wrapper: read keys, append rows
    │   └── pipeline.py           # orchestrates end-to-end
    ├── tests/
    │   ├── __init__.py
    │   ├── test_config.py
    │   ├── test_qualifier.py
    │   ├── test_dedup.py
    │   ├── test_fetch.py
    │   ├── test_claude_judge.py
    │   └── test_pipeline.py
    └── data/                     # gitignored: local run logs, cached HTML
```

---

## Task 1: Repo scaffold + git init

**Files:**
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/.gitignore`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/README.md`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/.env.example`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/pyproject.toml`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/data/.gitkeep`
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/src/lead_hunter/__init__.py` (empty)
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/tests/__init__.py` (empty)

- [ ] **Step 1: Initialize git at the repo root**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents
git init
git branch -M main
```

- [ ] **Step 2: Write `.gitignore` at the repo root**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/.gitignore`

```
# Secrets
.env
.env.local
service-account.json
*-service-account.json

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

# Per-agent local data
**/data/*
!**/data/.gitkeep

# macOS
.DS_Store
```

- [ ] **Step 3: Write repo-root README**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/README.md`

```markdown
# agents

Collection of Claude Code–driven agents, one per directory. Each agent is self-contained with its own `.env`, `CLAUDE.md`, code, and spec.

## Agents

- **`lead-hunter/`** — Scrapes local businesses with bad/no websites from Google Maps, qualifies them, writes qualified leads to a Google Sheet. See `lead-hunter/CLAUDE.md`.

## Convention

Every agent directory contains:

- `CLAUDE.md` — operator-facing usage + the agent's embedded instructions
- `.env.example` — required env vars, committed
- `.env` — actual secrets, gitignored
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans
- `src/` — implementation
- `tests/` — pytest suite
- `data/` — local run logs (gitignored)
```

- [ ] **Step 4: Write `lead-hunter/.env.example`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/.env.example`

```
# Apify — get from https://console.apify.com/account/integrations
APIFY_API_TOKEN=

# Google Sheets
# Share your sheet with the service account's email (found in the JSON).
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json

# Apify cost cap per run (USD)
APIFY_MAX_COST_USD=5

# Default max results per run (hard cap enforced in code)
DEFAULT_MAX_RESULTS=100
```

- [ ] **Step 5: Write `pyproject.toml`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/pyproject.toml`

```toml
[project]
name = "lead-hunter"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "apify-client>=1.8",
    "gspread>=6.1",
    "google-auth>=2.30",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "python-dotenv>=1.0",
    "pydantic>=2.7",
    "tenacity>=8.5",
    "ulid-py>=1.1",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
    "respx>=0.21",  # mock httpx
    "ruff>=0.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/lead_hunter"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["src"]

[project.scripts]
lead-hunter = "lead_hunter.cli:main"
```

- [ ] **Step 6: Create empty package / data placeholders**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter
mkdir -p src/lead_hunter tests data
touch src/lead_hunter/__init__.py tests/__init__.py data/.gitkeep
```

- [ ] **Step 7: Install deps with uv**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter
uv sync
```

Expected: creates `.venv/`, writes `uv.lock`, no errors.

- [ ] **Step 8: Sanity check pytest runs (no tests yet, exits 5 = no tests collected — acceptable)**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter
uv run pytest
```

Expected: exit code 5, "no tests ran".

- [ ] **Step 9: Commit**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents
git add .gitignore README.md lead-hunter/
git commit -m "chore: scaffold repo with lead-hunter package skeleton"
```

---

## Task 2: Data models

**Files:**
- Create: `src/lead_hunter/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_models.py`

```python
from datetime import datetime, timezone
from lead_hunter.models import Business, Lead, RejectedLead, Run


def test_business_is_immutable_and_dedup_keys_present():
    b = Business(
        name="Bob's Plumbing",
        address="123 Main St, Burnaby BC",
        phone="+16045550100",
        website="https://bobsplumbing.ca",
        maps_rating=4.6,
        maps_reviews=127,
        permanently_closed=False,
    )
    assert b.name == "Bob's Plumbing"
    assert b.dedup_keys() == {"website:https://bobsplumbing.ca", "phone:+16045550100"}


def test_business_dedup_keys_skip_missing():
    b = Business(
        name="No Web Plumber",
        address="1 Other St",
        phone="+16045550101",
        website=None,
        maps_rating=4.0,
        maps_reviews=12,
        permanently_closed=False,
    )
    assert b.dedup_keys() == {"phone:+16045550101"}


def test_lead_round_trips_to_dict_for_sheets():
    lead = Lead(
        date_added=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source_run="01HXYZ",
        business_name="Bob's Plumbing",
        niche="plumbers",
        city="Burnaby BC",
        address="123 Main St",
        phone="+16045550100",
        website="https://bobsplumbing.ca",
        maps_rating=4.6,
        maps_reviews=127,
        site_score=7,
        site_evidence="No HTTPS; pre-2015 aesthetic; slow/heavy",
        owner_name_guess="Bob Smith",
        email_guess="bob@bobsplumbing.ca",
        email_confidence="medium",
        contact_form_url="",
        linkedin_url="",
        lead_pitch="Site is mobile-broken and still on HTTP. 127 reviews at 4.6 — real business.",
        tier="hot",
        site_unreachable=False,
    )
    row = lead.to_sheet_row()
    assert row[2] == "Bob's Plumbing"
    assert row[-2] == "hot"
    assert len(row) == len(Lead.sheet_columns())


def test_run_round_trips_to_dict_for_sheets():
    r = Run(
        run_id="01HXYZ",
        date=datetime(2026, 4, 24, tzinfo=timezone.utc),
        niche="plumbers",
        city="Burnaby BC",
        max_results=100,
        apify_results=98,
        new_after_dedup=72,
        qualified=41,
        rejected=31,
        apify_cost_usd=0.82,
        duration_seconds=214.3,
        notes="",
    )
    row = r.to_sheet_row()
    assert row[2] == "plumbers"
    assert len(row) == len(Run.sheet_columns())
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter
uv run pytest tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: lead_hunter.models`.

- [ ] **Step 3: Implement `models.py`**

File: `src/lead_hunter/models.py`

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Tier = Literal["hot", "warm"]
EmailConfidence = Literal["high", "medium", "low", "none"]


class Business(BaseModel):
    """Raw Google Maps record, pre-qualification."""

    model_config = ConfigDict(frozen=True)

    name: str
    address: str
    phone: str | None
    website: str | None
    maps_rating: float
    maps_reviews: int
    permanently_closed: bool

    def dedup_keys(self) -> set[str]:
        keys: set[str] = set()
        if self.website:
            keys.add(f"website:{self.website}")
        if self.phone:
            keys.add(f"phone:{self.phone}")
        return keys


class Lead(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_added: datetime
    source_run: str
    business_name: str
    niche: str
    city: str
    address: str
    phone: str | None
    website: str | None
    maps_rating: float
    maps_reviews: int
    site_score: int
    site_evidence: str
    owner_name_guess: str
    email_guess: str
    email_confidence: EmailConfidence
    contact_form_url: str
    linkedin_url: str
    lead_pitch: str
    tier: Tier
    site_unreachable: bool

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "date_added", "source_run", "business_name", "niche", "city",
            "address", "phone", "website", "maps_rating", "maps_reviews",
            "site_score", "site_evidence", "owner_name_guess", "email_guess",
            "email_confidence", "contact_form_url", "linkedin_url", "lead_pitch",
            "tier", "site_unreachable", "status",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.date_added.isoformat(),
            self.source_run,
            self.business_name,
            self.niche,
            self.city,
            self.address,
            self.phone or "",
            self.website or "",
            f"{self.maps_rating:.1f}",
            str(self.maps_reviews),
            str(self.site_score),
            self.site_evidence,
            self.owner_name_guess,
            self.email_guess,
            self.email_confidence,
            self.contact_form_url,
            self.linkedin_url,
            self.lead_pitch,
            self.tier,
            "TRUE" if self.site_unreachable else "FALSE",
            "",  # status column reserved
        ]


class RejectedLead(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_added: datetime
    source_run: str
    business_name: str
    niche: str
    city: str
    address: str
    phone: str | None
    website: str | None
    maps_rating: float
    maps_reviews: int
    site_score: int | None  # None if rejected pre-scoring (e.g., closed)
    reject_reason: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "date_added", "source_run", "business_name", "niche", "city",
            "address", "phone", "website", "maps_rating", "maps_reviews",
            "site_score", "reject_reason",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.date_added.isoformat(),
            self.source_run,
            self.business_name,
            self.niche,
            self.city,
            self.address,
            self.phone or "",
            self.website or "",
            f"{self.maps_rating:.1f}",
            str(self.maps_reviews),
            "" if self.site_score is None else str(self.site_score),
            self.reject_reason,
        ]


class Run(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    date: datetime
    niche: str
    city: str
    max_results: int
    apify_results: int
    new_after_dedup: int
    qualified: int
    rejected: int
    apify_cost_usd: float
    duration_seconds: float
    notes: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "run_id", "date", "niche", "city", "max_results",
            "apify_results", "new_after_dedup", "qualified", "rejected",
            "apify_cost_usd", "duration_seconds", "notes",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.run_id,
            self.date.isoformat(),
            self.niche,
            self.city,
            str(self.max_results),
            str(self.apify_results),
            str(self.new_after_dedup),
            str(self.qualified),
            str(self.rejected),
            f"{self.apify_cost_usd:.4f}",
            f"{self.duration_seconds:.1f}",
            self.notes,
        ]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/models.py tests/test_models.py
git commit -m "feat(lead-hunter): data models for Business, Lead, RejectedLead, Run"
```

---

## Task 3: Config (env loading + thresholds)

**Files:**
- Create: `src/lead_hunter/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_config.py`

```python
import os
import pytest
from lead_hunter.config import Config, Thresholds


def test_config_loads_from_env(monkeypatch, tmp_path):
    sa = tmp_path / "sa.json"
    sa.write_text("{}")
    monkeypatch.setenv("APIFY_API_TOKEN", "tok_123")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet_abc")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_PATH", str(sa))
    monkeypatch.setenv("APIFY_MAX_COST_USD", "5")
    monkeypatch.setenv("DEFAULT_MAX_RESULTS", "100")

    c = Config.from_env()
    assert c.apify_api_token == "tok_123"
    assert c.google_sheet_id == "sheet_abc"
    assert c.service_account_path == sa
    assert c.apify_max_cost_usd == 5.0
    assert c.default_max_results == 100


def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="APIFY_API_TOKEN"):
        Config.from_env()


def test_thresholds_are_constants():
    assert Thresholds.REVIEWS_MIN == 10
    assert Thresholds.RATING_MIN == 3.5
    assert Thresholds.RATING_REJECT_BELOW == 3.0
    assert Thresholds.SITE_SCORE_HOT_MIN == 6
    assert Thresholds.SITE_SCORE_WARM_MIN == 3
    assert Thresholds.SITE_SCORE_REJECT_MAX == 2
    assert Thresholds.MAX_RESULTS_HARD_CAP == 250
    assert Thresholds.FETCH_CONCURRENCY == 10
    assert Thresholds.FETCH_TIMEOUT_SECONDS == 15
    assert Thresholds.FETCH_RETRIES == 1
    assert Thresholds.REVIEWS_DEAD_BELOW == 5
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `config.py`**

File: `src/lead_hunter/config.py`

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class Thresholds:
    """Tunable scoring and filtering constants. Edit here, not inline."""

    REVIEWS_MIN: int = 10
    REVIEWS_DEAD_BELOW: int = 5
    RATING_MIN: float = 3.5
    RATING_REJECT_BELOW: float = 3.0

    SITE_SCORE_HOT_MIN: int = 6
    SITE_SCORE_WARM_MIN: int = 3
    SITE_SCORE_REJECT_MAX: int = 2

    MAX_RESULTS_HARD_CAP: int = 250

    FETCH_CONCURRENCY: int = 10
    FETCH_TIMEOUT_SECONDS: int = 15
    FETCH_RETRIES: int = 1


@dataclass(frozen=True)
class Config:
    apify_api_token: str
    google_sheet_id: str
    service_account_path: Path
    apify_max_cost_usd: float
    default_max_results: int

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        required = ["APIFY_API_TOKEN", "GOOGLE_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_PATH"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

        return cls(
            apify_api_token=os.environ["APIFY_API_TOKEN"],
            google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
            service_account_path=Path(os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"]),
            apify_max_cost_usd=float(os.getenv("APIFY_MAX_COST_USD", "5")),
            default_max_results=int(os.getenv("DEFAULT_MAX_RESULTS", "100")),
        )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/config.py tests/test_config.py
git commit -m "feat(lead-hunter): config loader with tunable thresholds"
```

---

## Task 4: Qualifier (pure rules)

**Files:**
- Create: `src/lead_hunter/qualifier.py`
- Create: `tests/test_qualifier.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_qualifier.py`

```python
import pytest
from lead_hunter.models import Business
from lead_hunter.qualifier import QualifyResult, qualify


def biz(**overrides) -> Business:
    defaults = dict(
        name="X", address="Y", phone="+1", website="https://x",
        maps_rating=4.5, maps_reviews=50, permanently_closed=False,
    )
    defaults.update(overrides)
    return Business(**defaults)


def test_closed_always_rejected():
    r = qualify(biz(permanently_closed=True), site_score=5)
    assert r.verdict == "reject"
    assert "closed" in r.reason.lower()


def test_too_few_reviews_rejected():
    r = qualify(biz(maps_reviews=3), site_score=7)
    assert r.verdict == "reject"
    assert "reviews" in r.reason.lower()


def test_rating_too_low_rejected():
    r = qualify(biz(maps_rating=2.5), site_score=7)
    assert r.verdict == "reject"
    assert "rating" in r.reason.lower()


def test_site_already_good_rejected():
    r = qualify(biz(maps_reviews=50, maps_rating=4.8), site_score=1)
    assert r.verdict == "reject"
    assert "already good" in r.reason.lower()


def test_hot_lead():
    r = qualify(biz(maps_reviews=50, maps_rating=4.6), site_score=7)
    assert r.verdict == "qualify"
    assert r.tier == "hot"


def test_warm_lead_mid_score():
    r = qualify(biz(maps_reviews=50, maps_rating=4.6), site_score=4)
    assert r.verdict == "qualify"
    assert r.tier == "warm"


def test_borderline_reviews_exactly_ten_hot():
    r = qualify(biz(maps_reviews=10, maps_rating=3.5), site_score=6)
    assert r.verdict == "qualify"
    assert r.tier == "hot"


def test_rating_just_below_floor_but_above_reject():
    # rating 3.3: not "reject for rating" but not "hot" either (< RATING_MIN)
    # Falls to warm if score in warm range, else reject on site-already-good
    r = qualify(biz(maps_reviews=50, maps_rating=3.3), site_score=7)
    # score ≥ hot but rating < hot threshold → fall to warm tier
    assert r.verdict == "qualify"
    assert r.tier == "warm"
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_qualifier.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `qualifier.py`**

File: `src/lead_hunter/qualifier.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Thresholds
from .models import Business, Tier

Verdict = Literal["qualify", "reject"]


@dataclass(frozen=True)
class QualifyResult:
    verdict: Verdict
    tier: Tier | None
    reason: str


def qualify(business: Business, site_score: int) -> QualifyResult:
    if business.permanently_closed:
        return QualifyResult("reject", None, "business permanently closed")

    if business.maps_reviews < Thresholds.REVIEWS_DEAD_BELOW:
        return QualifyResult(
            "reject", None,
            f"only {business.maps_reviews} reviews — likely dead or fake",
        )

    if business.maps_rating < Thresholds.RATING_REJECT_BELOW:
        return QualifyResult(
            "reject", None,
            f"rating {business.maps_rating:.1f} too low — would hurt association",
        )

    if site_score <= Thresholds.SITE_SCORE_REJECT_MAX:
        return QualifyResult(
            "reject", None,
            f"site already good (score {site_score}) — not a fit",
        )

    if business.maps_reviews < Thresholds.REVIEWS_MIN:
        return QualifyResult(
            "reject", None,
            f"only {business.maps_reviews} reviews — below minimum viability",
        )

    is_hot = (
        site_score >= Thresholds.SITE_SCORE_HOT_MIN
        and business.maps_rating >= Thresholds.RATING_MIN
    )
    tier: Tier = "hot" if is_hot else "warm"
    return QualifyResult(
        "qualify", tier,
        f"site_score={site_score}, reviews={business.maps_reviews}, rating={business.maps_rating:.1f}",
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_qualifier.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/qualifier.py tests/test_qualifier.py
git commit -m "feat(lead-hunter): qualifier rules routing businesses to hot/warm/reject"
```

---

## Task 5: Dedup (pure logic)

**Files:**
- Create: `src/lead_hunter/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_dedup.py`

```python
from lead_hunter.dedup import filter_new
from lead_hunter.models import Business


def biz(name, website=None, phone=None):
    return Business(
        name=name, address="x", phone=phone, website=website,
        maps_rating=4.0, maps_reviews=20, permanently_closed=False,
    )


def test_filter_new_removes_website_duplicates():
    existing = {"website:https://a.com"}
    incoming = [biz("A", website="https://a.com"), biz("B", website="https://b.com")]
    result = filter_new(incoming, existing)
    assert [b.name for b in result] == ["B"]


def test_filter_new_removes_phone_duplicates():
    existing = {"phone:+15551111"}
    incoming = [biz("A", phone="+15551111"), biz("B", phone="+15552222")]
    assert [b.name for b in filter_new(incoming, existing)] == ["B"]


def test_filter_new_removes_if_any_key_matches():
    existing = {"phone:+15551111"}
    incoming = [biz("A", website="https://new.com", phone="+15551111")]
    assert filter_new(incoming, existing) == []


def test_filter_new_keeps_business_with_neither_key_matching():
    existing = {"website:https://x.com", "phone:+19999"}
    incoming = [biz("A", website="https://y.com", phone="+18888")]
    assert [b.name for b in filter_new(incoming, existing)] == ["A"]


def test_filter_new_dedups_within_incoming_batch():
    existing: set[str] = set()
    incoming = [
        biz("A", website="https://a.com", phone="+1"),
        biz("A-dup", website="https://a.com", phone="+2"),  # same website → dupe
    ]
    result = filter_new(incoming, existing)
    assert [b.name for b in result] == ["A"]


def test_filter_new_keeps_businesses_with_no_dedup_keys():
    # Business with neither website nor phone has empty dedup_keys — always "new"
    existing: set[str] = set()
    incoming = [biz("Ghost")]
    assert [b.name for b in filter_new(incoming, existing)] == ["Ghost"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `dedup.py`**

File: `src/lead_hunter/dedup.py`

```python
from __future__ import annotations

from collections.abc import Iterable

from .models import Business


def filter_new(incoming: Iterable[Business], existing_keys: set[str]) -> list[Business]:
    """Return businesses whose dedup keys don't intersect existing_keys.
    Also dedupes within the incoming batch itself (first occurrence wins).
    A business with no dedup keys is always treated as new."""
    seen = set(existing_keys)
    result: list[Business] = []
    for b in incoming:
        keys = b.dedup_keys()
        if keys and keys & seen:
            continue
        result.append(b)
        seen.update(keys)
    return result
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/dedup.py tests/test_dedup.py
git commit -m "feat(lead-hunter): dedup filter against existing sheet keys"
```

---

## Task 6: Website fetcher

**Files:**
- Create: `src/lead_hunter/fetch.py`
- Create: `tests/test_fetch.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_fetch.py`

```python
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
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_fetch.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `fetch.py`**

File: `src/lead_hunter/fetch.py`

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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_fetch.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/fetch.py tests/test_fetch.py
git commit -m "feat(lead-hunter): async website fetcher with retry and timeout"
```

---

## Task 7: Claude judge (subprocess wrapper)

**Files:**
- Create: `src/lead_hunter/claude_judge.py`
- Create: `tests/test_claude_judge.py`

**Note:** `claude -p` is the Claude Code CLI in non-interactive mode. `--output-format json` returns `{"result": "...", ...}`. We pass `--max-turns 1` to ensure a single response (no agentic looping). System prompt via `--system-prompt`. We ask Claude to return JSON and parse it.

- [ ] **Step 1: Write the failing test**

File: `tests/test_claude_judge.py`

```python
import json
from unittest.mock import patch, MagicMock

import pytest

from lead_hunter.claude_judge import (
    JudgeResult,
    judge_website,
    build_judge_prompt,
)


def test_build_judge_prompt_includes_rubric_and_html():
    prompt = build_judge_prompt(
        business_name="Bob's Plumbing",
        website_url="https://bobsplumbing.ca",
        html="<html><body>We fix pipes</body></html>",
    )
    assert "Bob's Plumbing" in prompt
    assert "bobsplumbing.ca" in prompt
    assert "viewport" in prompt.lower()  # rubric mentions signals
    assert "We fix pipes" in prompt


def test_build_judge_prompt_truncates_long_html():
    big_html = "x" * 200_000
    prompt = build_judge_prompt("B", "https://b.com", big_html)
    assert len(prompt) < 150_000


def _fake_completed(stdout_text: str):
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout_text
    m.stderr = ""
    return m


def test_judge_website_parses_valid_response():
    fake_payload = json.dumps({
        "result": json.dumps({
            "site_score": 7,
            "evidence": ["no HTTPS", "pre-2015 aesthetic"],
            "owner_name_guess": "Bob Smith",
            "email_guess": "bob@bobsplumbing.ca",
            "email_confidence": "medium",
            "contact_form_url": "",
            "linkedin_url": "",
            "lead_pitch": "Mobile-broken site, 127 reviews — real business.",
        })
    })
    with patch("lead_hunter.claude_judge.subprocess.run",
               return_value=_fake_completed(fake_payload)):
        r = judge_website("Bob's Plumbing", "https://b.com", "<html>…</html>")
    assert isinstance(r, JudgeResult)
    assert r.site_score == 7
    assert r.owner_name_guess == "Bob Smith"
    assert r.email_confidence == "medium"
    assert "Mobile-broken" in r.lead_pitch


def test_judge_website_handles_unreachable_fallback():
    # When no HTML (site unreachable), caller passes empty html; judge should
    # return a zero-score result based on the prompt’s instructions.
    fake_payload = json.dumps({
        "result": json.dumps({
            "site_score": 4,  # partial signal from having no site
            "evidence": ["site unreachable"],
            "owner_name_guess": "",
            "email_guess": "",
            "email_confidence": "none",
            "contact_form_url": "",
            "linkedin_url": "",
            "lead_pitch": "Website unreachable; qualified on Maps signals alone.",
        })
    })
    with patch("lead_hunter.claude_judge.subprocess.run",
               return_value=_fake_completed(fake_payload)):
        r = judge_website("X", "https://x", html="", site_unreachable=True)
    assert r.site_score == 4
    assert r.email_confidence == "none"


def test_judge_website_raises_on_bad_json():
    with patch("lead_hunter.claude_judge.subprocess.run",
               return_value=_fake_completed("not json")):
        with pytest.raises(RuntimeError, match="claude -p"):
            judge_website("X", "https://x", "<html/>")


def test_judge_website_raises_on_nonzero_exit():
    bad = MagicMock()
    bad.returncode = 2
    bad.stdout = ""
    bad.stderr = "auth failure"
    with patch("lead_hunter.claude_judge.subprocess.run", return_value=bad):
        with pytest.raises(RuntimeError, match="auth failure"):
            judge_website("X", "https://x", "<html/>")
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_claude_judge.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `claude_judge.py`**

File: `src/lead_hunter/claude_judge.py`

```python
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Literal

EmailConfidence = Literal["high", "medium", "low", "none"]

MAX_HTML_CHARS = 120_000  # leaves room for prompt overhead under CLI arg limits

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

    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--max-turns", "1",
        "--system-prompt", _SYSTEM_PROMPT,
        user_prompt,
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {proc.stderr.strip() or 'no stderr'}")

    try:
        outer = json.loads(proc.stdout)
        payload = json.loads(outer["result"]) if isinstance(outer.get("result"), str) else outer["result"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise RuntimeError(f"claude -p returned unparseable output: {e}: {proc.stdout[:500]}")

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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_claude_judge.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/claude_judge.py tests/test_claude_judge.py
git commit -m "feat(lead-hunter): claude -p subprocess wrapper for scoring and extraction"
```

---

## Task 8: Apify client wrapper

**Files:**
- Create: `src/lead_hunter/apify.py`
- Create: `tests/test_apify.py`

**Note:** Uses Apify's `compass/crawler-google-places` actor. We call `client.actor(...).call(run_input=...)` which blocks until the run completes, then iterate dataset items.

- [ ] **Step 1: Write the failing test**

File: `tests/test_apify.py`

```python
from unittest.mock import MagicMock, patch

from lead_hunter.apify import ApifyResult, scrape_google_maps
from lead_hunter.models import Business


def test_scrape_google_maps_maps_fields_and_returns_cost():
    fake_items = [
        {
            "title": "Bob's Plumbing",
            "address": "123 Main St, Burnaby BC",
            "phone": "+1 604-555-0100",
            "website": "https://bobsplumbing.ca",
            "totalScore": 4.6,
            "reviewsCount": 127,
            "permanentlyClosed": False,
        },
        {
            "title": "No Web Plumber",
            "address": "1 Other St",
            "phone": "+1 604-555-0101",
            "website": None,
            "totalScore": 4.0,
            "reviewsCount": 12,
            "permanentlyClosed": False,
        },
    ]

    fake_run = {"id": "run_abc", "usageTotalUsd": 0.73}
    fake_actor = MagicMock()
    fake_actor.call.return_value = fake_run

    fake_dataset = MagicMock()
    fake_dataset.iterate_items.return_value = iter(fake_items)

    fake_client = MagicMock()
    fake_client.actor.return_value = fake_actor
    fake_client.dataset.return_value = fake_dataset
    # default_dataset_id comes from the run dict in real API; simulate
    fake_run["defaultDatasetId"] = "ds_abc"

    with patch("lead_hunter.apify.ApifyClient", return_value=fake_client):
        result = scrape_google_maps(
            api_token="tok",
            niche="plumbers",
            city="Burnaby BC",
            max_results=50,
            max_cost_usd=5.0,
        )
    assert isinstance(result, ApifyResult)
    assert result.cost_usd == 0.73
    assert len(result.businesses) == 2
    assert all(isinstance(b, Business) for b in result.businesses)
    assert result.businesses[0].name == "Bob's Plumbing"
    assert result.businesses[0].maps_reviews == 127
    assert result.businesses[1].website is None
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_apify.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `apify.py`**

File: `src/lead_hunter/apify.py`

```python
from __future__ import annotations

from dataclasses import dataclass

from apify_client import ApifyClient

from .models import Business

ACTOR_ID = "compass/crawler-google-places"


@dataclass(frozen=True)
class ApifyResult:
    businesses: list[Business]
    cost_usd: float
    run_id: str


def scrape_google_maps(
    api_token: str,
    niche: str,
    city: str,
    max_results: int,
    max_cost_usd: float,
) -> ApifyResult:
    client = ApifyClient(api_token)
    run_input = {
        "searchStringsArray": [f"{niche} in {city}"],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "maxCostPerRun": max_cost_usd,
        "scrapeContacts": False,  # we don't need email scraping from Apify; we do it via Claude
    }
    actor = client.actor(ACTOR_ID)
    run = actor.call(run_input=run_input)
    if run is None:
        raise RuntimeError("Apify run returned None")

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        raise RuntimeError(f"Apify run missing defaultDatasetId: {run}")

    items = list(client.dataset(dataset_id).iterate_items())
    businesses = [_to_business(item) for item in items]
    cost = float(run.get("usageTotalUsd", 0.0))
    return ApifyResult(businesses=businesses, cost_usd=cost, run_id=run.get("id", ""))


def _to_business(item: dict) -> Business:
    return Business(
        name=item.get("title") or "(unnamed)",
        address=item.get("address") or "",
        phone=item.get("phone"),
        website=item.get("website"),
        maps_rating=float(item.get("totalScore") or 0.0),
        maps_reviews=int(item.get("reviewsCount") or 0),
        permanently_closed=bool(item.get("permanentlyClosed", False)),
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_apify.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/apify.py tests/test_apify.py
git commit -m "feat(lead-hunter): Apify Google Maps scraper wrapper"
```

---

## Task 9: Google Sheets wrapper

**Files:**
- Create: `src/lead_hunter/sheets.py`
- Create: `tests/test_sheets.py`

**Note:** `gspread` with service-account auth. Three worksheets by name: `Leads`, `Rejected`, `Runs`. On first run they may not exist — `ensure_schema()` creates them and writes headers if needed.

- [ ] **Step 1: Write the failing test**

File: `tests/test_sheets.py`

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from lead_hunter.models import Lead, RejectedLead, Run
from lead_hunter.sheets import SheetsClient


def _lead(name="Bob's"):
    return Lead(
        date_added=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source_run="r1", business_name=name, niche="plumbers", city="Burnaby BC",
        address="x", phone="+1", website="https://x", maps_rating=4.5, maps_reviews=50,
        site_score=7, site_evidence="no HTTPS", owner_name_guess="Bob", email_guess="b@x",
        email_confidence="medium", contact_form_url="", linkedin_url="",
        lead_pitch="p", tier="hot", site_unreachable=False,
    )


def _rejected():
    return RejectedLead(
        date_added=datetime(2026, 4, 24, tzinfo=timezone.utc),
        source_run="r1", business_name="Good Co", niche="plumbers", city="Burnaby BC",
        address="x", phone="+1", website="https://x", maps_rating=4.8, maps_reviews=200,
        site_score=1, reject_reason="site already good",
    )


def _run():
    return Run(
        run_id="r1", date=datetime(2026, 4, 24, tzinfo=timezone.utc),
        niche="plumbers", city="Burnaby BC", max_results=100,
        apify_results=80, new_after_dedup=60, qualified=30, rejected=30,
        apify_cost_usd=0.5, duration_seconds=100.0, notes="",
    )


def test_read_existing_keys_collects_phone_and_website():
    leads_ws = MagicMock()
    leads_ws.get_all_records.return_value = [
        {"website": "https://a.com", "phone": "+1111"},
        {"website": "", "phone": "+2222"},
    ]
    rejected_ws = MagicMock()
    rejected_ws.get_all_records.return_value = [
        {"website": "https://b.com", "phone": ""},
    ]
    runs_ws = MagicMock()

    spread = MagicMock()
    spread.worksheet.side_effect = lambda name: {
        "Leads": leads_ws, "Rejected": rejected_ws, "Runs": runs_ws,
    }[name]

    client = SheetsClient(spread=spread)
    keys = client.existing_dedup_keys()
    assert keys == {
        "website:https://a.com", "phone:+1111",
        "phone:+2222",
        "website:https://b.com",
    }


def test_append_leads_and_rejected_and_run_calls_sheets_once_each():
    leads_ws = MagicMock()
    rejected_ws = MagicMock()
    runs_ws = MagicMock()
    spread = MagicMock()
    spread.worksheet.side_effect = lambda name: {
        "Leads": leads_ws, "Rejected": rejected_ws, "Runs": runs_ws,
    }[name]

    client = SheetsClient(spread=spread)
    client.append(leads=[_lead(), _lead("B")], rejected=[_rejected()], run=_run())

    leads_ws.append_rows.assert_called_once()
    rejected_ws.append_rows.assert_called_once()
    runs_ws.append_row.assert_called_once()
    # headers weren’t touched on append path
    leads_ws.update.assert_not_called()
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_sheets.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `sheets.py`**

File: `src/lead_hunter/sheets.py`

```python
from __future__ import annotations

from pathlib import Path

import gspread

from .models import Lead, RejectedLead, Run

LEADS = "Leads"
REJECTED = "Rejected"
RUNS = "Runs"


class SheetsClient:
    def __init__(self, spread):
        self._spread = spread

    @classmethod
    def from_credentials(cls, service_account_path: Path, sheet_id: str) -> "SheetsClient":
        gc = gspread.service_account(filename=str(service_account_path))
        spread = gc.open_by_key(sheet_id)
        return cls(spread=spread)

    def ensure_schema(self) -> None:
        existing = {ws.title for ws in self._spread.worksheets()}
        specs = [
            (LEADS, Lead.sheet_columns()),
            (REJECTED, RejectedLead.sheet_columns()),
            (RUNS, Run.sheet_columns()),
        ]
        for name, headers in specs:
            if name not in existing:
                ws = self._spread.add_worksheet(title=name, rows=1000, cols=len(headers))
                ws.update(range_name="A1", values=[headers])
            else:
                ws = self._spread.worksheet(name)
                first_row = ws.row_values(1)
                if first_row != headers:
                    ws.update(range_name="A1", values=[headers])

    def existing_dedup_keys(self) -> set[str]:
        keys: set[str] = set()
        for name in (LEADS, REJECTED):
            try:
                ws = self._spread.worksheet(name)
            except gspread.WorksheetNotFound:
                continue
            for row in ws.get_all_records():
                website = (row.get("website") or "").strip()
                phone = (row.get("phone") or "").strip()
                if website:
                    keys.add(f"website:{website}")
                if phone:
                    keys.add(f"phone:{phone}")
        return keys

    def append(
        self,
        leads: list[Lead],
        rejected: list[RejectedLead],
        run: Run,
    ) -> None:
        if leads:
            self._spread.worksheet(LEADS).append_rows(
                [lead.to_sheet_row() for lead in leads],
                value_input_option="RAW",
            )
        if rejected:
            self._spread.worksheet(REJECTED).append_rows(
                [r.to_sheet_row() for r in rejected],
                value_input_option="RAW",
            )
        self._spread.worksheet(RUNS).append_row(
            run.to_sheet_row(),
            value_input_option="RAW",
        )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_sheets.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lead_hunter/sheets.py tests/test_sheets.py
git commit -m "feat(lead-hunter): gspread wrapper with ensure_schema and batched append"
```

---

## Task 10: Pipeline orchestration

**Files:**
- Create: `src/lead_hunter/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

File: `tests/test_pipeline.py`

```python
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lead_hunter.apify import ApifyResult
from lead_hunter.claude_judge import JudgeResult
from lead_hunter.fetch import FetchResult
from lead_hunter.models import Business
from lead_hunter.pipeline import run_pipeline


def _biz(name, website="https://x.com", phone="+1555", rating=4.5, reviews=50, closed=False):
    return Business(
        name=name, address="addr", phone=phone, website=website,
        maps_rating=rating, maps_reviews=reviews, permanently_closed=closed,
    )


async def test_pipeline_happy_path_writes_hot_and_warm_and_rejected():
    businesses = [
        _biz("Hot Co", website="https://hot.com"),
        _biz("Warm Co", website="https://warm.com"),
        _biz("Good Site Co", website="https://good.com"),
        _biz("Dead Co", website="https://dead.com", reviews=2),
    ]
    apify_result = ApifyResult(businesses=businesses, cost_usd=0.5, run_id="apify_1")

    fetches = {
        "https://hot.com": FetchResult(True, "<html/>", 200, "https://hot.com", "", 100),
        "https://warm.com": FetchResult(True, "<html/>", 200, "https://warm.com", "", 100),
        "https://good.com": FetchResult(True, "<html/>", 200, "https://good.com", "", 100),
        "https://dead.com": FetchResult(True, "<html/>", 200, "https://dead.com", "", 100),
    }

    judgements = {
        "Hot Co": JudgeResult(7, ["no HTTPS"], "A", "a@x", "medium", "", "", "hot pitch"),
        "Warm Co": JudgeResult(4, ["slow"], "B", "b@x", "medium", "", "", "warm pitch"),
        "Good Site Co": JudgeResult(1, [], "C", "c@x", "medium", "", "", "fine site"),
        "Dead Co": JudgeResult(8, [], "", "", "none", "", "", "doesn't matter"),
    }

    sheets = MagicMock()
    sheets.existing_dedup_keys.return_value = set()

    with patch("lead_hunter.pipeline.scrape_google_maps", return_value=apify_result), \
         patch("lead_hunter.pipeline.fetch_site",
               side_effect=lambda url, **_: _async_return(fetches[url])), \
         patch("lead_hunter.pipeline.judge_website",
               side_effect=lambda name, url, html, site_unreachable=False: judgements[name]):
        summary = await run_pipeline(
            apify_token="tok",
            sheets=sheets,
            niche="plumbers",
            city="Burnaby BC",
            max_results=10,
            apify_max_cost_usd=5.0,
        )

    sheets.ensure_schema.assert_called_once()
    sheets.append.assert_called_once()
    kwargs = sheets.append.call_args.kwargs
    lead_names = [l.business_name for l in kwargs["leads"]]
    rejected_names = [r.business_name for r in kwargs["rejected"]]

    assert set(lead_names) == {"Hot Co", "Warm Co"}
    assert set(rejected_names) == {"Good Site Co", "Dead Co"}
    assert summary.qualified == 2
    assert summary.rejected == 2


async def _async_return(value):
    return value
```

- [ ] **Step 2: Run test to verify failure**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `pipeline.py`**

File: `src/lead_hunter/pipeline.py`

```python
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import ulid

from .apify import scrape_google_maps
from .claude_judge import judge_website
from .config import Thresholds
from .dedup import filter_new
from .fetch import fetch_site
from .models import Business, Lead, RejectedLead, Run
from .qualifier import qualify
from .sheets import SheetsClient


async def run_pipeline(
    apify_token: str,
    sheets: SheetsClient,
    niche: str,
    city: str,
    max_results: int,
    apify_max_cost_usd: float,
) -> Run:
    start = time.time()
    max_results = min(max_results, Thresholds.MAX_RESULTS_HARD_CAP)
    run_id = str(ulid.new())
    now = datetime.now(timezone.utc)

    sheets.ensure_schema()
    existing_keys = sheets.existing_dedup_keys()

    apify_result = scrape_google_maps(
        api_token=apify_token,
        niche=niche,
        city=city,
        max_results=max_results,
        max_cost_usd=apify_max_cost_usd,
    )

    new_businesses = filter_new(apify_result.businesses, existing_keys)

    sem = asyncio.Semaphore(Thresholds.FETCH_CONCURRENCY)

    async def process(business: Business) -> tuple[Business, int, str, object]:
        async with sem:
            fetch = await fetch_site(business.website)
            site_unreachable = not fetch.ok and fetch.reason != "no_website"
            # Run the blocking Claude subprocess in a thread so we don't stall the loop
            judge = await asyncio.to_thread(
                judge_website,
                business.name,
                business.website or "",
                fetch.html if fetch.ok else "",
                site_unreachable,
            )
            evidence_str = "; ".join(judge.evidence) if judge.evidence else ""
            return business, judge.site_score, evidence_str, judge

    results = await asyncio.gather(*(process(b) for b in new_businesses))

    leads: list[Lead] = []
    rejected: list[RejectedLead] = []

    for business, score, evidence_str, judge in results:
        qr = qualify(business, score)
        if qr.verdict == "qualify":
            assert qr.tier is not None
            leads.append(Lead(
                date_added=now, source_run=run_id,
                business_name=business.name, niche=niche, city=city,
                address=business.address, phone=business.phone, website=business.website,
                maps_rating=business.maps_rating, maps_reviews=business.maps_reviews,
                site_score=score, site_evidence=evidence_str,
                owner_name_guess=judge.owner_name_guess,
                email_guess=judge.email_guess,
                email_confidence=judge.email_confidence,
                contact_form_url=judge.contact_form_url,
                linkedin_url=judge.linkedin_url,
                lead_pitch=judge.lead_pitch,
                tier=qr.tier,
                site_unreachable=(business.website is not None and
                                  not _was_site_ok(business, score)),
            ))
        else:
            rejected.append(RejectedLead(
                date_added=now, source_run=run_id,
                business_name=business.name, niche=niche, city=city,
                address=business.address, phone=business.phone, website=business.website,
                maps_rating=business.maps_rating, maps_reviews=business.maps_reviews,
                site_score=score, reject_reason=qr.reason,
            ))

    duration = time.time() - start
    run = Run(
        run_id=run_id, date=now, niche=niche, city=city,
        max_results=max_results,
        apify_results=len(apify_result.businesses),
        new_after_dedup=len(new_businesses),
        qualified=len(leads),
        rejected=len(rejected),
        apify_cost_usd=apify_result.cost_usd,
        duration_seconds=duration,
        notes="",
    )
    sheets.append(leads=leads, rejected=rejected, run=run)
    return run


def _was_site_ok(business: Business, score: int) -> bool:
    """Heuristic to set site_unreachable on the Lead row. We don't have direct
    access to the FetchResult here, so we infer: if site_score != 0 and website
    exists, assume the site was reachable. Called only when website is set."""
    # In practice, judge_website was called with site_unreachable=True only if
    # the fetch failed; in that case the score still reflects Claude's judgment.
    # We keep this simple and return True whenever a website exists; the
    # site_unreachable flag is set in pipeline when needed (see future refinement).
    return True
```

> **Refinement note for the implementer:** the `site_unreachable` flag on each Lead should be sourced from the actual `FetchResult`, not inferred. Thread the fetch result through the return tuple from `process()` so it's available when building the `Lead`. Update the test to pass unreachable cases and verify the flag.

- [ ] **Step 4: Refine — propagate real `site_unreachable` through the pipeline**

Edit `src/lead_hunter/pipeline.py`:

Replace the `process()` return and the loop that consumes it:

```python
    async def process(business: Business):
        async with sem:
            fetch = await fetch_site(business.website)
            site_unreachable = bool(business.website) and not fetch.ok and fetch.reason != "no_website"
            judge = await asyncio.to_thread(
                judge_website,
                business.name,
                business.website or "",
                fetch.html if fetch.ok else "",
                site_unreachable,
            )
            return business, judge, site_unreachable

    results = await asyncio.gather(*(process(b) for b in new_businesses))

    leads: list[Lead] = []
    rejected: list[RejectedLead] = []

    for business, judge, site_unreachable in results:
        evidence_str = "; ".join(judge.evidence) if judge.evidence else ""
        qr = qualify(business, judge.site_score)
        if qr.verdict == "qualify":
            assert qr.tier is not None
            leads.append(Lead(
                date_added=now, source_run=run_id,
                business_name=business.name, niche=niche, city=city,
                address=business.address, phone=business.phone, website=business.website,
                maps_rating=business.maps_rating, maps_reviews=business.maps_reviews,
                site_score=judge.site_score, site_evidence=evidence_str,
                owner_name_guess=judge.owner_name_guess,
                email_guess=judge.email_guess,
                email_confidence=judge.email_confidence,
                contact_form_url=judge.contact_form_url,
                linkedin_url=judge.linkedin_url,
                lead_pitch=judge.lead_pitch,
                tier=qr.tier,
                site_unreachable=site_unreachable,
            ))
        else:
            rejected.append(RejectedLead(
                date_added=now, source_run=run_id,
                business_name=business.name, niche=niche, city=city,
                address=business.address, phone=business.phone, website=business.website,
                maps_rating=business.maps_rating, maps_reviews=business.maps_reviews,
                site_score=judge.site_score, reject_reason=qr.reason,
            ))
```

Delete the now-unused `_was_site_ok` helper.

- [ ] **Step 5: Run tests to verify pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -v
```

Expected: all tests pass (models 4 + config 3 + qualifier 8 + dedup 6 + fetch 5 + claude_judge 6 + apify 1 + sheets 2 + pipeline 1 = 36 tests).

- [ ] **Step 7: Commit**

```bash
git add src/lead_hunter/pipeline.py tests/test_pipeline.py
git commit -m "feat(lead-hunter): end-to-end pipeline wiring fetch, judge, qualify, write"
```

---

## Task 11: CLI entry point

**Files:**
- Create: `src/lead_hunter/cli.py`
- Create: `src/lead_hunter/__main__.py`

- [ ] **Step 1: Implement `cli.py`**

File: `src/lead_hunter/cli.py`

```python
from __future__ import annotations

import argparse
import asyncio
import sys

from .config import Config
from .pipeline import run_pipeline
from .sheets import SheetsClient


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="lead-hunter",
        description="Scrape local businesses with bad websites and write qualified leads to Google Sheets.",
    )
    parser.add_argument("--niche", required=True, help='e.g. "plumbers"')
    parser.add_argument("--city", required=True, help='e.g. "Burnaby BC"')
    parser.add_argument("--max-results", type=int, default=None,
                        help="override default_max_results from env")
    args = parser.parse_args()

    cfg = Config.from_env()
    max_results = args.max_results if args.max_results is not None else cfg.default_max_results

    sheets = SheetsClient.from_credentials(
        service_account_path=cfg.service_account_path,
        sheet_id=cfg.google_sheet_id,
    )

    print(f"→ lead-hunter: {args.niche} in {args.city} (max {max_results})")
    run = asyncio.run(run_pipeline(
        apify_token=cfg.apify_api_token,
        sheets=sheets,
        niche=args.niche,
        city=args.city,
        max_results=max_results,
        apify_max_cost_usd=cfg.apify_max_cost_usd,
    ))
    print(
        f"✓ run {run.run_id}: {run.qualified} qualified, "
        f"{run.rejected} rejected, "
        f"{run.new_after_dedup}/{run.apify_results} new after dedup, "
        f"${run.apify_cost_usd:.2f} apify, "
        f"{run.duration_seconds:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Implement `__main__.py`**

File: `src/lead_hunter/__main__.py`

```python
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 3: Smoke test CLI help (no keys needed)**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter
uv run python -m lead_hunter --help
```

Expected: argparse help text showing `--niche`, `--city`, `--max-results`.

- [ ] **Step 4: Commit**

```bash
git add src/lead_hunter/cli.py src/lead_hunter/__main__.py
git commit -m "feat(lead-hunter): CLI entry point with --niche / --city / --max-results"
```

---

## Task 12: CLAUDE.md for the agent folder

**Files:**
- Create: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/CLAUDE.md`

- [ ] **Step 1: Write `CLAUDE.md`**

File: `/Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter/CLAUDE.md`

```markdown
# lead-hunter

Scrapes local businesses with bad/no websites from Google Maps (via Apify), scores each site via `claude -p`, writes qualified leads to a Google Sheet.

## Setup (one time)

1. `uv sync` — installs deps.
2. Copy `.env.example` to `.env` and fill:
   - `APIFY_API_TOKEN` — from https://console.apify.com/account/integrations
   - `GOOGLE_SHEET_ID` — the `/d/<this-part>/edit` of your Sheet URL
   - `GOOGLE_SERVICE_ACCOUNT_PATH` — relative path to the service account JSON
3. Create a Google Cloud project, enable Sheets API, create a service account, download JSON, save as `./service-account.json`.
4. Share your Google Sheet (edit access) with the service account's email (inside the JSON).
5. Ensure `claude` CLI is installed and `claude login` has been run with the Max subscription account.

## Run

```bash
uv run python -m lead_hunter --niche "plumbers" --city "Burnaby BC"
uv run python -m lead_hunter --niche "hair salons" --city "North Vancouver BC" --max-results 50
```

Output: new rows appended to three tabs in the Sheet — `Leads`, `Rejected`, `Runs`.

## Tunable knobs

Edit `src/lead_hunter/config.py` → `Thresholds`:

- `REVIEWS_MIN` — minimum reviews to qualify (default 10)
- `RATING_MIN` — minimum rating for a hot lead (default 3.5)
- `SITE_SCORE_HOT_MIN` — site score above which a lead is hot (default 6)
- `FETCH_CONCURRENCY` — parallel website fetches (default 10)

Rubric itself lives in `src/lead_hunter/claude_judge.py` → `_SYSTEM_PROMPT`. Edit it to tune scoring signals.

## Costs

- Apify: ~$1 per 100 businesses (hard cap $5/run configured).
- Claude: $0 at margin (Claude Code / Max subscription via `claude -p`).
- Sheets + Google: free.

## Out of scope

No outreach. No scheduling. No reply handling. This agent produces the lead list — that's it.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(lead-hunter): operator-facing CLAUDE.md with setup and run instructions"
```

---

## Task 13: End-to-end smoke test (manual, with real accounts)

This task can't be automated — it verifies the whole thing works against live Apify and Sheets.

- [ ] **Step 1: Verify prerequisites are in place**

The operator must have completed the setup steps in `CLAUDE.md`:
- `.env` filled in
- `service-account.json` in the lead-hunter directory
- Google Sheet shared with the service account
- `claude` CLI authenticated (`claude --version` works)

- [ ] **Step 2: Run a small real batch**

```bash
cd /Users/ishansachdeva/Desktop/my-apps/agents/lead-hunter
uv run python -m lead_hunter --niche "plumbers" --city "Burnaby BC" --max-results 10
```

Expected:
- Takes 1-5 minutes
- Prints `→ lead-hunter: …` start line
- Prints `✓ run <id>: N qualified, M rejected, …` finish line
- Three tabs appear in the Sheet if they didn't already: `Leads`, `Rejected`, `Runs`
- New rows appear in the tabs matching the counts printed

- [ ] **Step 3: Spot-check 3 leads**

Open the Sheet. Pick 3 rows from `Leads` and visit the `website` URLs in a browser. The `site_evidence` and `lead_pitch` should match what you see. If they don't, tune the rubric in `claude_judge.py` and re-run.

- [ ] **Step 4: Re-run to verify dedup**

```bash
uv run python -m lead_hunter --niche "plumbers" --city "Burnaby BC" --max-results 10
```

Expected: `Runs` tab shows `new_after_dedup=0` (or close to 0). No duplicates in `Leads`.

- [ ] **Step 5: Commit any rubric tuning**

```bash
git add -p src/lead_hunter/claude_judge.py src/lead_hunter/config.py
git commit -m "tune(lead-hunter): adjust rubric/thresholds based on first real-batch spot-check"
```

---

## Self-Review

Checked against the spec:

- **§3 Inputs** (niche, city, max_results) — Task 11 CLI ✓
- **§4.1 Leads tab columns** — Task 2 `Lead.sheet_columns()` / `to_sheet_row()` ✓
- **§4.2 Rejected tab** — Task 2 `RejectedLead` ✓
- **§4.3 Runs tab** — Task 2 `Run` ✓
- **§5 Architecture** (Apify → dedup → parallel enrich → qualify → sheets) — Task 10 pipeline ✓
- **§6 Rubric** — Task 7 `_SYSTEM_PROMPT` ✓
- **§7 Qualifier logic** — Task 4 ✓
- **§8 Cost/limits** — Thresholds in Task 3, Apify cap passed through in Task 8 ✓
- **§9 Failure modes** — fetch retries/timeout in Task 6, unreachable-path in Task 7, batched writes in Task 9, dedup in Task 5 ✓
- **§10 Repo layout** — Task 1 ✓
- **§11 External deps** — `.env.example` Task 1, `CLAUDE.md` Task 12 ✓
- **§13 Success criteria** — manual smoke test Task 13 ✓

No placeholders. Type names consistent (`Tier` is `hot|warm`, `Verdict` is `qualify|reject`, `EmailConfidence` is `high|medium|low|none` throughout). `site_unreachable` threading through pipeline is addressed in Task 10 refinement step.
