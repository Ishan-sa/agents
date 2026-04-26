# agents

A monorepo of automated sales agents for a solo web-design agency. Each agent
is a standalone Python project (own `pyproject.toml`, own `CLAUDE.md`, own
`.env`, own tests) but they share one Google Sheet as the source of truth and
one OpenRouter key for LLM calls.

The pipeline: **lead-hunter → outreach-agent → reply-handler.** Find prospects,
draft cold emails, then close the loop on replies and follow-ups. Every agent
stages drafts in Gmail for manual review and send — nothing goes out without
me clicking Send.

## The three agents

### 1. `lead-hunter/` — find prospects

Scrapes Google Maps via Apify, fetches each business's website, scores it via
OpenRouter (gemini-2.5-flash), writes qualified leads to the `Leads` tab of
the shared Google Sheet (with `Rejected` and `Runs` tabs for visibility).

```bash
cd lead-hunter
uv run python -m lead_hunter --niche "plumbers" --city "Burnaby BC"
```

### 2. `outreach-agent/` — draft cold emails

Reads qualified leads from the sheet, re-fetches each website, drafts a
personalized cold email via OpenRouter, stages it as a Gmail draft. Sets
`status=drafted`. Voice is tunable via `outreach-agent/voice_examples.md`.

```bash
cd outreach-agent
uv run python -m outreach_agent --batch-size 5
```

### 3. `reply-handler/` — close the loop

Three jobs in one agent that close the loop after I send:

- **`sync-sent`** — detects which drafts I actually sent. Flips
  `status=drafted → sent`, records `gmail_thread_id`, `gmail_message_id`,
  `date_sent`.
- **`check-replies`** — for each `sent` thread, finds the latest inbound
  message, classifies it (interested / question / declined / auto_reply /
  none) via OpenRouter, drafts a contextual in-thread reply.
- **`follow-ups`** — cadence-based nudges. Follow-up #1 at 5 days, #2 at 12
  days, mark `cold` at 25 days. All configurable via `.env`.

```bash
cd reply-handler
uv run python -m reply_handler all          # do everything in order
uv run python -m reply_handler all --dry-run  # preview without writes
```

Safe to run on a daily cron once configured.

## How they connect

```
                   ┌───────────────────────────┐
                   │   Google Sheet (shared)   │
                   │  Leads / Rejected / Runs  │
                   │  Outreach_Runs            │
                   │  Reply_Handler_Runs       │
                   └─────────────▲─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────┴─────┐           ┌──────┴──────┐         ┌───────┴────────┐
   │ lead-    │  writes   │ outreach-   │  reads  │ reply-handler  │
   │ hunter   │ Leads ──▶ │ agent       │ ──────▶ │ (3 jobs)       │
   │          │           │ status=     │ updates │ status=        │
   │          │           │ drafted     │         │ sent / replied │
   │          │           │             │         │ / followup_ /  │
   │          │           │             │         │ cold           │
   └──────────┘           └─────────────┘         └────────────────┘
        │                        │                        │
        └────── Gmail (drafts) ◀─┴────── Gmail (drafts) ◀─┘
                          (I review + send manually)
```

The sheet is the only shared state. Each agent reads/writes specific columns.
Status flow (column `status` in the `Leads` tab):

```
(empty) ──[lead-hunter]──▶ (qualified, no status)
                              │
                              ├─[outreach-agent]──▶ drafted
                              │
                              ├─[outreach-agent skip]──▶ skipped
                              │
                              ▼
                          [I send the draft from Gmail]
                              │
                          [reply-handler sync-sent]
                              │
                              ▼
                            sent
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
[check-replies]       [follow-ups, day 5]   [follow-ups, day 12]
        │                     │                     │
        ▼                     ▼                     ▼
replied_interested    followup_1_drafted    followup_2_drafted
replied_question              │                     │
replied_declined              ▼                     ▼
replied_auto_reply    [follow-ups, day 25]  [follow-ups, day 25]
replied_none                  │                     │
                              ▼                     ▼
                            cold                   cold
```

## Repo conventions

- **Each agent is a sibling subdir** with its own `pyproject.toml`,
  `CLAUDE.md`, `tests/`, and `.env`. Single git repo at the root.
- **All LLM calls go through OpenRouter** via `httpx` — no `claude -p`
  subprocess (token-expensive and flaky).
- **Default model:** `google/gemini-2.5-flash`. Override per-agent via the
  `OPENROUTER_MODEL` env var.
- **Secrets never committed.** `.env`, `service-account.json`,
  `gmail-oauth-credentials.json`, `gmail-token.json` are all gitignored at the
  repo root.
- **Drafts only, never auto-send.** Every agent stages in Gmail; I click Send.
- **Idempotent jobs.** Re-running any job is safe — status checks prevent
  duplicates.

## First-time setup at a glance

Each agent has a per-directory `CLAUDE.md` with full setup steps. The shared
prerequisites:

1. Google Cloud project with Sheets API + Gmail API enabled.
2. Service account JSON shared with the Sheet (edit access). Copied into each
   agent dir as `service-account.json`.
3. Apify token (lead-hunter only).
4. OpenRouter API key (`OPENROUTER_API_KEY` in every agent's `.env`).
5. Two Gmail OAuth clients — one for `outreach-agent` (`gmail.compose` scope),
   one for `reply-handler` (broader `gmail.modify` scope to read replies).

## Costs

- **Apify:** ~$1 per 100 businesses scraped (lead-hunter, capped at $5/run).
- **OpenRouter (gemini-2.5-flash):** pennies per draft / classification.
- **Gmail / Sheets:** free.
- **Per qualified lead through the full pipeline:** ~$0.05.

## Daily / weekly playbook — what to run, when

### When to run each agent

| Agent           | Frequency             | Trigger                                              |
|-----------------|-----------------------|------------------------------------------------------|
| `lead-hunter`   | As needed             | When the qualified-lead backlog is running low, or you want to try a new niche/city. |
| `outreach-agent`| ~Once per send batch  | Before you sit down to do outreach for the day. Drafts are queued in Gmail; you review + send. |
| `reply-handler` | Daily (ideally)       | Every morning — picks up replies, drafts responses, fires follow-ups on schedule. |

### Step-by-step: a full cycle, end-to-end

**1. Find new leads** (only when backlog is thin)

```bash
cd lead-hunter
uv run python -m lead_hunter --niche "plumbers" --city "Burnaby BC" --max-results 50
```

New rows land in the `Leads` tab with `status=""` (qualified, ready for outreach).

**2. Draft cold emails**

```bash
cd outreach-agent
uv run python -m outreach_agent --batch-size 5 --dry-run     # preview first
uv run python -m outreach_agent --batch-size 5               # for real
```

For each lead this drafts: subject + body, stages a Gmail draft, sets
`status=drafted`, and writes the `gmail_draft_id` to the sheet.

**3. Review + send drafts (manual, in Gmail)**

Open Gmail → Drafts. Edit anything that needs tweaking. Click Send. This is
the ONLY step that's non-automated — and intentionally so. It protects your
sender reputation.

**4. Run reply-handler daily**

```bash
cd reply-handler
uv run python -m reply_handler all --dry-run      # preview
uv run python -m reply_handler all                # for real
```

This does three things in one shot:

- **sync-sent** — finds drafts you actually sent. Flips `drafted → sent`,
  records `gmail_thread_id`, `gmail_message_id`, `date_sent`.
- **check-replies** — for each `sent` thread, looks for an inbound reply.
  Classifies it (`interested` / `question` / `declined` / `auto_reply` /
  `none`) and drafts a contextual in-thread response. Sets
  `status=replied_<class>`.
- **follow-ups** — for `sent` threads with no reply: drafts nudge #1 at 5d,
  nudge #2 at 12d, marks `cold` at 25d. Cadence configurable via
  `reply-handler/.env`.

You can also run any one job individually:

```bash
uv run python -m reply_handler sync-sent
uv run python -m reply_handler check-replies
uv run python -m reply_handler follow-ups
```

`--dry-run` works before or after the subcommand: `... all --dry-run` or
`... --dry-run all`.

**5. Review + send reply / follow-up drafts (manual, in Gmail)**

Same as step 3 — open Gmail, review the new in-thread drafts, click Send.

### What you should be running each day, minimum

```bash
# morning, takes ~30 seconds
cd ~/Desktop/my-apps/agents/reply-handler
uv run python -m reply_handler all
# then: open Gmail, review whatever's in Drafts, send what looks good
```

That alone keeps the pipeline alive — replies get answered, follow-ups go
out on schedule. Lead-hunter and outreach-agent only need to run when you're
actively topping up the funnel.

### Status flow at a glance

```
(empty) ──[lead-hunter qualifies it]──▶ ready for outreach
                                            │
                                  [outreach-agent]
                                            │
                                            ▼
                                         drafted ──[you send in Gmail]──▶
                                                                          │
                                                  [reply-handler sync-sent]
                                                                          │
                                                                          ▼
                                                                        sent
                          ┌───────────────────────────────────────────────┤
                          │                                               │
              [check-replies finds reply]                  [no reply for 5/12/25 days]
                          │                                               │
                          ▼                                               ▼
              replied_interested                              followup_1_drafted
              replied_question                                followup_2_drafted
              replied_declined                                cold
              replied_auto_reply
              replied_none
```

## What's next (ideas, not built yet)

- **Cron / launchd** that runs `reply-handler all` automatically each morning.
- **Send-rate guardrails** in outreach-agent (max-per-day, randomized spacing)
  to protect sender reputation.
- **Mockup-generation agent:** when reply-handler classifies a reply as
  `interested` and they want the free mockup, auto-generate a 1-page rebuild.
- **A/B testing harness** for cold-email opening hooks, scored by reply rate.
- **LinkedIn outreach:** same shape as outreach-agent but a different channel.
- **Lead-pool expansion:** just running lead-hunter on more niche/city combos.
