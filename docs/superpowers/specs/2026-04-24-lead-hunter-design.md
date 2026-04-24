# Lead-Hunter Agent — Design Spec

**Date:** 2026-04-24
**Owner:** Ishan Sachdeva
**Status:** Draft, pending review

## 1. Purpose

A Claude Code agent that produces a daily (on-demand) list of qualified website-redesign leads for a solo web agency operator. Takes a niche + metro area as input, outputs a curated Google Sheet of local businesses whose current websites are bad or missing, ranked by how good a prospect they are.

**Non-goal:** this agent does not do outreach. Outreach is a separate agent, to be designed after this one is proven.

## 2. Operator context

- Solo founder, agency offer: "website in under a week."
- Based in Vancouver BC, Pacific timezone.
- Cannot do voice calls (stammer) — sales motion must be text-based (email, LinkedIn, forms).
- Claude Max subscription: Claude reasoning is effectively free at the margin when run via Claude Code.
- First target metro: Metro Vancouver (Vancouver, Burnaby, Surrey, Richmond, North Van, Coquitlam).
- First niches: local trades (plumbers, electricians, roofers, HVAC), then salons/gyms/clinics. Real estate agents explicitly excluded.

## 3. Inputs

Agent is invoked from the terminal with:

- `niche` — free-text, e.g. `"plumbers"`, `"hair salons"`, `"hvac"`
- `city` — free-text, e.g. `"Burnaby BC"`, `"North Vancouver BC"`
- `max_results` — optional, default 100, hard cap 250

## 4. Outputs

New rows appended to a single Google Sheet with three tabs:

### 4.1 `Leads` tab (the master list, deduped by website OR phone)

| Column | Description |
|---|---|
| `date_added` | ISO date of run |
| `source_run` | Run ID, links back to Runs tab |
| `business_name` | From Google Maps |
| `niche` | From input |
| `city` | From input |
| `address` | From Google Maps |
| `phone` | From Google Maps |
| `website` | From Google Maps; `""` if none |
| `maps_rating` | From Google Maps (e.g., 4.6) |
| `maps_reviews` | Review count |
| `site_score` | 0-10, higher = worse = better lead |
| `site_evidence` | One-line-per-flagged-signal from rubric |
| `owner_name_guess` | Best guess from site/LinkedIn; `""` if unknown |
| `email_guess` | Best guess; `""` if unknown |
| `email_confidence` | `high` \| `medium` \| `low` \| `none` |
| `contact_form_url` | Fallback if no email |
| `linkedin_url` | If a public page exists for business or owner |
| `lead_pitch` | 1-2 sentence summary: why this is a good lead |
| `tier` | `hot` \| `warm` |
| `site_unreachable` | Boolean; true if website fetch failed |
| `status` | Blank; reserved for future outreach agent |

### 4.2 `Rejected` tab

Businesses the agent looked at but disqualified. Same columns as Leads plus a `reject_reason` column. Purpose: prevent re-processing on future runs and let the operator audit agent judgment.

### 4.3 `Runs` tab

One row per agent invocation.

| Column | Description |
|---|---|
| `run_id` | ULID or ISO timestamp |
| `date` | ISO date/time |
| `niche` | From input |
| `city` | From input |
| `max_results` | From input |
| `apify_results` | How many businesses Apify returned |
| `new_after_dedup` | How many were not already in Leads/Rejected |
| `qualified` | Count added to Leads |
| `rejected` | Count added to Rejected |
| `apify_cost_usd` | Reported by Apify run summary |
| `duration_seconds` | Wall-clock run time |
| `notes` | Free text, any anomalies |

## 5. Architecture

```
Operator (terminal)
   │  "run lead-hunter for plumbers in Burnaby"
   ▼
Claude Code agent (local, uses Max subscription)
   │
   ├─► 1. Apify Google Maps Scraper
   │      query: "<niche> in <city>"
   │      output: raw JSON (~N businesses)
   │
   ├─► 2. Dedup pass
   │      read Leads + Rejected from Google Sheets
   │      drop any business where website OR phone matches existing row
   │
   ├─► 3. Per-business enrichment (parallel, concurrency=10)
   │      ├─ fetch homepage HTML (15s timeout, 1 retry)
   │      ├─ Claude scores site against rubric (§6) → 0-10 + per-signal evidence
   │      ├─ Claude extracts owner name, email, contact form, socials
   │      ├─ optional LinkedIn public-page lookup (no authenticated scraping)
   │      └─ Claude writes lead_pitch (1-2 sentences)
   │
   ├─► 4. Qualify / reject (§7)
   │
   └─► 5. Write to Google Sheets
          batch-append new Leads
          batch-append new Rejected
          append one Runs row with summary + cost
```

**Key design choices:**
- Apify for scraping (reliable at Google Maps); Claude for judgment (rubric scoring, extraction, lead pitch). Each tool where it's strongest.
- Dedup before enrichment — enrichment is the expensive step.
- Parallel enrichment capped at 10 concurrent to avoid rate limits and runaway cost.
- Rejected-as-tab (not deletion) keeps future runs cheap and makes judgment auditable.
- Writes are batched per run; a mid-run crash loses the run but never corrupts the sheet.

## 6. Site-quality rubric

Claude scores each website against these signals. Higher score = worse site = better lead.

| Signal | Check | Points |
|---|---|---|
| No website at all | Maps has no URL, or URL 404s | +4 (auto-qualified) |
| Social-only presence | URL is facebook.com/… or instagram.com/… | +3 |
| Mobile-broken | Missing viewport meta, no responsive CSS | +2 |
| Pre-2015 aesthetic | Table layouts, tiny fonts, dated styles | +2 |
| No HTTPS | `http://` only | +1 |
| No clear CTA | No visible "Book/Call/Quote" or phone above fold | +1 |
| Slow / heavy | Page > 5MB or > 50 render-blocking resources | +1 |
| Broken visuals | Missing images, no favicon, obvious defects | +1 |
| Placeholder content | "Lorem ipsum", "Your Business Name", default templates | +2 |
| Free-tier builder | Wix free, GoDaddy default, Weebly default, default WP theme | +2 |

Cap score at 10. Claude records one evidence line per flagged signal.

Rubric lives in the agent's `CLAUDE.md` so it can be tuned without code changes.

## 7. Qualifier logic

After scoring:

- `site_score ≥ 6` AND `reviews ≥ 10` AND `rating ≥ 3.5` → **hot lead** → Leads (`tier=hot`)
- `site_score 3-5` AND `reviews ≥ 10` AND `rating ≥ 3.5` → **warm lead** → Leads (`tier=warm`)
- `site_score ≤ 2` → **Rejected** (`reject_reason="site already good"`)
- `reviews < 5` → **Rejected** (`reject_reason="too few reviews, likely dead/fake"`)
- `rating < 3.0` → **Rejected** (`reject_reason="rating too low, bad association"`)
- Google Maps flags business as permanently closed → **Rejected** (`reject_reason="closed"`)

Thresholds are defined as constants in one place so they can be tuned from a single edit.

## 8. Cost & limits

Per run of ~100 businesses:
- Apify: ~$0.50–$1.50
- Claude: $0 at margin (Max subscription via Claude Code)
- Google Sheets: free
- **Total: ~$1 per batch.**

Hard limits:
- `max_results` defaults 100, cap 250
- Apify spend cap per run: $5 (configured on the Apify run)
- Parallel fetch concurrency: 10
- Website fetch timeout: 15s
- Network retries: 1

## 9. Failure modes

| Failure | Behavior |
|---|---|
| Apify returns 0 results | Log, no sheet writes, exit 0 |
| Apify partial failure | Process what returned, note partial count in Runs.notes |
| Website unreachable | Qualify from Maps signals only, flag `site_unreachable=true` |
| Claude extraction uncertain | Save with `email_confidence=none`, populate `contact_form_url` as fallback |
| Sheets API rate-limited | Batched writes (one append per tab per run) avoid this by design |
| Duplicate run (same niche+city same day) | Dedup catches it; Runs row shows 0 new leads |
| Mid-run crash | Writes are end-of-run only; re-run is safe |

## 10. Repo layout

```
agents/
├── .gitignore                # ignores .env, service-account.json, node_modules, data/
├── README.md
└── lead-hunter/
    ├── .env                  # not committed
    ├── .env.example          # committed template
    ├── service-account.json  # not committed
    ├── CLAUDE.md             # agent instructions + rubric
    ├── src/                  # implementation code
    ├── docs/                 # specs + plans
    └── data/                 # local run logs, cached HTML for debugging (gitignored)
```

Each future agent is a sibling directory with its own `.env`, `CLAUDE.md`, and `src/`.

## 11. External dependencies

One-time setup by operator:
1. Apify account (free signup, pay-as-you-go) → `APIFY_API_TOKEN`
2. Google Cloud project with Sheets API enabled → service account JSON (free tier)
3. A Google Sheet, shared with the service account's email → `GOOGLE_SHEET_ID`
4. Claude Code installed (already done)

No Claude API key required — agent runs under Claude Code / Max subscription.

## 12. Out of scope

- Outreach of any kind (drafts, sending, personalization, replies)
- Scheduling / cron — manual invocation only
- UI or dashboard beyond the Google Sheet itself
- Multi-user support
- Authenticated LinkedIn scraping (only public-page existence checks)
- CRM integration
- n8n (may be used for later agents, not this one)

## 13. Success criteria

The agent is considered working when, for a single run of `plumbers in Burnaby BC` with `max_results=100`:

1. Apify returns a list of businesses (any count > 0).
2. Dedup correctly skips any row already present in Leads or Rejected.
3. Every remaining business receives a site_score with evidence and a lead_pitch.
4. Qualifier correctly routes each business to Leads or Rejected.
5. Google Sheet is updated with new rows on all three tabs as applicable.
6. Runs tab shows accurate counts and cost.
7. Operator can read the top 10 hot leads in Sheets and agree with the agent's judgment on at least 8 of them (spot-check by visiting the actual websites).

Criterion 7 is the only one that matters — the rest are plumbing. Lead quality is the product.
