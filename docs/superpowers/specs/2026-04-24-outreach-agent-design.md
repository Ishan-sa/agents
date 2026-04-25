# Outreach Agent — Design Spec

**Date:** 2026-04-24
**Owner:** Ishan Sachdeva
**Status:** Draft, pending review

## 1. Purpose

Read qualified leads from the existing Google Sheet (produced by `lead-hunter`), draft a personalized cold email per lead grounded in the lead's actual website, and stage each email as a Gmail draft in the operator's inbox. The operator reviews each draft and clicks send manually. The sheet's `status` column tracks which leads have been drafted so no lead is drafted twice.

This is a "concierge" outreach model: low volume, high personalization, real inbox, full operator review. Not a mass-blast SDR.

**Non-goals:** sending, reply detection, follow-up cadences, mockup production, LinkedIn / contact-form outreach, analytics. Each is a separate agent or a separate phase.

## 2. Operator context

- Solo founder, agency offer: "website in under a week."
- Cannot do voice calls (stammer) — sales motion is text-only. Inbound calls (when prospects book) are fine.
- Will send from his own Gmail or Workspace inbox. Doesn't need separate sending infrastructure for v1.
- Will set up a Calendly / Cal.com link before first run. URL goes in `.env`.
- Source of truth for leads is the Google Sheet maintained by `lead-hunter`.

## 3. CTA / offer in the email

Two CTAs in every email:

- **Primary:** "Reply 'yes' for a free 1-page mockup of your homepage rebuilt." Operator produces the mockup manually after a positive reply (out of scope for this agent).
- **Secondary:** "Or book a 15-min chat: <calendar URL>"

## 4. Inputs

CLI invocation:

```bash
uv run python -m outreach_agent --batch-size 5
```

Optional filters (any combination):

- `--niche "plumbers"` — only leads from this niche
- `--city "Burnaby BC"` — only leads from this city
- `--tier hot|warm` — only this tier
- `--dry-run` — research and write the email but skip the Gmail draft creation; print to stdout

Defaults and limits:

- `--batch-size` defaults 5, hard cap 20
- No env-configurable defaults beyond hard cap; CLI flag overrides everything

## 5. Lead selection

A lead is eligible if:

- `status` column is empty (never drafted before)
- AND has a usable contact: `email_guess` is non-empty OR `contact_form_url` starts with `http`

Among eligible leads, sort:

1. `tier=hot` first
2. Then `site_score` descending
3. Take the first N (where N = `--batch-size`)

Filters from `--niche`, `--city`, `--tier` apply before sorting.

## 6. Outputs

### 6.1 New columns added to the Leads tab

Added once on first run if not present:

- `status` — `""` | `drafted` | `sent` | `replied` | `skipped`
- `date_drafted` — ISO timestamp set when a draft is created
- `subject_line` — the subject line the agent used
- `gmail_draft_id` — the Gmail API draft ID (used for future operations)
- `skip_reason` — populated when `status=skipped`

For v1, `sent` and `replied` are written-by-future-agents; this agent only writes `drafted` and `skipped`.

### 6.2 New worksheet: `Outreach_Runs`

One row per agent invocation. Created on first run if not present.

| Column | Description |
|---|---|
| `run_id` | ULID |
| `date` | ISO timestamp |
| `batch_size` | From input |
| `filter_niche` / `filter_city` / `filter_tier` | From input, blank if unfiltered |
| `eligible_count` | Number of leads matching the filter (before batch_size cap) |
| `drafted` | Count of drafts created this run |
| `skipped` | Count where Claude returned `action: skip` |
| `errors` | Count of leads that errored (fetch fail, malformed JSON, Gmail API fail) |
| `duration_seconds` | Wall clock |
| `dry_run` | TRUE/FALSE |
| `notes` | Free text — anomalies, error summaries |

### 6.3 Gmail drafts

For each non-skipped lead, a draft is created in the configured Gmail account via the Gmail API `users.drafts.create` endpoint. The draft has:

- `To`: `email_guess` (always) — even if `email_confidence=low`. The operator visually verifies before sending.
- `Subject`: as written by Claude
- `Body`: plain text, no HTML
- No CC, no BCC, no attachments, no tracking pixels

If `email_guess` is empty but `contact_form_url` is present, the agent still creates a draft addressed to `email_guess` (which is empty — Gmail allows this; operator will see "no recipient" and use the form URL listed in the sheet manually). **Refinement during implementation:** consider routing form-only leads to a separate `Form_Outreach` queue rather than creating an empty-recipient Gmail draft. Defer this decision until first batch.

## 7. Architecture

```
Operator (terminal)
   │  uv run python -m outreach_agent --batch-size 5
   ▼
Pipeline
   │
   ├─► 1. Read Leads + existing Outreach_Runs from Google Sheet
   ├─► 2. Filter eligible leads, sort, take N
   │
   ├─► 3. For each lead (parallel, concurrency=3):
   │      ├─ Re-fetch website (15s timeout, 1 retry)
   │      ├─ Build draft prompt: business info + lead_pitch + fresh HTML
   │      │   + voice examples (from voice_examples.md) + CTA template
   │      ├─ Subprocess: claude -p --output-format json --max-turns 1
   │      │   → JSON {action: "draft"|"skip", subject, body, skip_reason}
   │      ├─ If draft: Gmail API drafts.create → capture draft_id
   │      └─ If skip: record skip_reason
   │
   ├─► 4. Batch-update Leads tab (status, date_drafted, subject_line,
   │      gmail_draft_id, skip_reason for each processed lead)
   └─► 5. Append one row to Outreach_Runs
```

Key choices:

- **Re-fetch fresh HTML at draft time.** Lead-hunter's snapshot may be days old. Drafts that reference stale specifics ("your COVID-19 banner") are embarrassing.
- **Concurrency 3, not 10.** Gmail API quotas are tighter than HTTP fetches; Claude calls are heavyweight.
- **Idempotency via the sheet.** `status` column is the source of truth. A crash mid-run leaves the sheet partially updated, which is safe — already-drafted leads have `status=drafted` and won't be re-processed next run.
- **Sheet writes are batched at end of run.** A mid-run crash means recently-created Gmail drafts have no sheet entry. These are logged to `data/orphaned_drafts.log` with draft_id + business_name for manual reconciliation. Rare.

## 8. The email itself (voice and structure)

Plain text only. ~80–130 words. No HTML, no images, no fancy signatures.

Loose structure (Claude writes freeform; not a rigid template):

```
Subject: short, specific, lowercase often, ~6-8 words
        e.g. "noticed something on artisanplumbing.ca"

Hey [first name from owner_name_guess if confident,
     else "team at <business name>" / "<business name> team"],

[1-2 sentences: ONE specific observation about the site, grounded in the
 lead_pitch evidence. Must reference something only an actual site-visitor would know.]

[1 sentence: what the operator does — "I rebuild sites for trades businesses
 in Vancouver, usually shipping in under a week."]

Want a free 1-page mockup of your homepage rebuilt? Just reply 'yes'.
Or here's my calendar if you'd rather chat: <calendly URL>

<sender first name>
```

The system prompt for the draft writer embeds:

- Operator voice rules (casual, direct, short, no corporate-speak, lowercase OK)
- Sender identity (name, agency name, calendar URL — from `.env`)
- 3-4 example emails of the desired tone
- The CTA template
- Skip rules (chains, non-English sites, out-of-area businesses, etc.)
- The output JSON schema

Voice examples live in `voice_examples.md` at the repo root and are loaded into the system prompt at runtime. Operator edits this file — not code — to retune the agent's voice.

## 9. Skip rules

The agent can decide not to draft a lead. It returns `action: "skip"` with a reason. Skip cases:

- Site is in a non-English language (operator can't follow up in that language)
- Business is a chain / franchise (e.g., "Mr. Rooter Plumbing of Burnaby BC", "1-800-Got-Junk") — these go through corporate procurement, not local owner outreach
- Site indicates business is not actually local to operator's area (out-of-province, virtual-only operating elsewhere)
- Site is so broken / unreachable that the agent has no specific evidence to ground the email in
- The Claude judge's `lead_pitch` was thin and a re-read of the site doesn't surface anything specific

Each skip writes `skip_reason` to the sheet so operator can audit and unblock the lead manually if disagreement.

## 10. Gmail integration

Drafts in the operator's personal Gmail or Workspace inbox require **OAuth user credentials** (not service account).

**One-time setup:**

1. In Google Cloud Console (same project as lead-hunter): enable Gmail API.
2. Create OAuth Client ID, type: **Desktop App**, name: `outreach-agent`.
3. Download the OAuth client JSON, save to `outreach-agent/gmail-oauth-credentials.json` (gitignored).
4. Run `uv run python -m outreach_agent.bootstrap_gmail`:
   - Opens browser
   - Operator logs into the Google account that should receive drafts
   - Authorizes the app for scope `https://www.googleapis.com/auth/gmail.compose`
   - Refresh token saved to `outreach-agent/gmail-token.json` (gitignored)
5. Done. All future runs use the saved token. Token refresh is automatic via `google-auth`.

**Scope discipline:** `gmail.compose` only. The agent can create / update / delete drafts. It cannot send mail and cannot read inbox or threads. Reply handling later requires `gmail.readonly` and is out of scope here.

## 11. Cost & limits

Per draft:

- Apify: $0 (no scraping; uses lead-hunter's existing data)
- Website re-fetch: free
- Claude reasoning: $0 at margin (Max subscription via `claude -p` subprocess)
- Gmail API: free, well below quota (`drafts.create` is 5 quota units; default daily limit is 1,000,000,000 units)
- Sheets writes: free

**Total per draft: ~$0.** Per batch of 5: ~$0.

Hard limits:

- `--batch-size` cap: 20
- Concurrency: 3
- Re-fetch timeout: 15s
- Re-fetch retries: 1
- Subprocess timeout per Claude call: 120s

## 12. Failure modes

| Failure | Behavior |
|---|---|
| Re-fetch fails | Skip lead this run; status stays `""`; logged to Outreach_Runs notes; retry next run |
| Claude returns malformed JSON | Skip lead this run; logged; status stays `""`; retry next run |
| Claude returns `action: skip` | `status=skipped`, `skip_reason` populated |
| Gmail API rate-limited | Retry with backoff; if persistent, abort batch (don't write partial sheet update) |
| Gmail token expired and refresh fails | Hard fail: print "re-run `python -m outreach_agent.bootstrap_gmail`" |
| Sheet write fails after Gmail draft created | Log draft_id + business_name to `data/orphaned_drafts.log` for manual cleanup |
| `--dry-run` mode | All same logic, except no Gmail call and no sheet write — prints draft to stdout |

## 13. Repo layout

```
agents/outreach-agent/
├── .gitignore
├── .env.example
├── pyproject.toml
├── CLAUDE.md
├── voice_examples.md           ← operator edits this to tune agent voice
├── gmail-oauth-credentials.json (gitignored, operator-provided)
├── gmail-token.json            (gitignored, created by bootstrap script)
├── src/outreach_agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── sheets.py               ← reads Leads, writes Leads + Outreach_Runs
│   ├── fetch.py                ← website re-fetcher (httpx async)
│   ├── draft_writer.py         ← claude -p subprocess wrapper
│   ├── gmail_client.py         ← Gmail API wrapper, drafts.create
│   ├── bootstrap_gmail.py      ← one-time OAuth flow
│   └── pipeline.py             ← orchestrator
├── tests/
└── data/
    ├── .gitkeep
    └── orphaned_drafts.log     (gitignored)
```

Sibling to `lead-hunter/`. Own `.git`. Own `pyproject.toml`. No shared library between agents — small duplication is cheaper than premature abstraction.

## 14. Environment variables

```
GOOGLE_SHEET_ID=<same as lead-hunter>
GOOGLE_SERVICE_ACCOUNT_PATH=./service-account.json   # for Sheets reads/writes
GMAIL_OAUTH_CREDENTIALS_PATH=./gmail-oauth-credentials.json
GMAIL_TOKEN_PATH=./gmail-token.json
SENDER_NAME=Ishan
SENDER_AGENCY_NAME=<your agency name>
SENDER_CALENDAR_URL=<your Calendly / Cal.com URL>
```

Operator copies the same `service-account.json` from `lead-hunter/` (Sheets API auth is shared via the service account; Gmail uses separate OAuth user credentials).

## 15. Out of scope (defers to future agents)

- Sending — operator clicks Send in Gmail manually
- Auto-detecting that an email was sent (status `drafted` → `sent`)
- Reply detection and threading
- Follow-up sequences ("nudge if no reply in 5 days")
- Mockup production for positive replies
- LinkedIn outreach
- Contact-form-fill outreach (we may revisit; for v1, form-only leads still get an email draft addressed to the empty `email_guess`, which Gmail will show as "no recipient" — operator handles those manually)
- Open / click tracking (would degrade deliverability)
- Multiple sender inboxes / rotation
- Analytics beyond what's in the sheet

## 16. Success criteria

After one real run with `--batch-size 5` on the existing Leads sheet:

1. 5 Gmail drafts appear in the operator's inbox.
2. Each draft has a non-generic subject and a body that references something specific from the lead's website.
3. The Leads tab shows `status=drafted` for the 5 processed leads, with `date_drafted`, `subject_line`, `gmail_draft_id` populated.
4. Outreach_Runs tab shows one new row with accurate counts.
5. Operator reads all 5 drafts and would be willing to send at least 3 of them with no edits, and the other 2 with minor edits.

Criterion 5 is the only one that matters. The rest is plumbing. Email quality is the product.
