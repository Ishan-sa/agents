# reply-handler

Closes the loop on the outreach-agent pipeline. Three jobs in one agent:

1. **sync-sent** — for each lead the outreach-agent staged as a Gmail draft, detect
   when you actually sent it. Flips sheet status `drafted → sent` and records
   `gmail_thread_id`, `gmail_message_id`, `date_sent`.
2. **check-replies** — for each `sent` thread, look for an inbound reply.
   Classify it (interested / question / declined / auto-reply) via OpenRouter,
   then draft a contextual in-thread response in your voice. You review + send
   manually.
3. **follow-ups** — for `sent` threads with no reply, draft a short nudge
   in-thread after 5 days, again at 12 days, and mark the lead `cold` after 25
   days (configurable via `.env`).

All three jobs read/write the same Google Sheet that lead-hunter and
outreach-agent use. They are idempotent: safe to run on a cron, or all together
via `reply-handler all`.

## Setup (one time)

1. `uv sync`
2. Copy `service-account.json` from `lead-hunter/` (same Google service account).
3. Copy `.env.example` to `.env` and fill values.
4. In Google Cloud Console (same project as outreach-agent):
   - Create a NEW OAuth Client ID (type **Desktop App**), name `reply-handler`.
   - Download JSON to `./gmail-oauth-credentials.json`.
   - In **OAuth consent screen → Scopes**, add `gmail.modify` (this scope covers
     reading messages and creating drafts, including in-thread drafts).
5. Run the OAuth bootstrap (separate from outreach-agent's token):
   ```bash
   uv run python -m reply_handler.bootstrap_gmail
   ```
   A browser opens. Grant the broader `gmail.modify` scope. Token is saved to
   `./gmail-token.json`.

## Run

```bash
# do everything in order: sync, then replies, then follow-ups
uv run python -m reply_handler all

# one job at a time
uv run python -m reply_handler sync-sent
uv run python -m reply_handler check-replies
uv run python -m reply_handler follow-ups

# preview without writing to Gmail or Sheets
uv run python -m reply_handler all --dry-run
```

After a real run:
- `Leads` sheet has updated `status` (`sent`, `replied_interested`,
  `replied_question`, `replied_declined`, `followup_1_drafted`,
  `followup_2_drafted`, `cold`) plus `date_sent`, `gmail_thread_id`,
  `gmail_message_id`, `last_reply_date`, `reply_class`, `reply_draft_id`,
  `followup_count`, `last_followup_date`, `last_followup_draft_id`.
- New reply / follow-up drafts appear in your Gmail Drafts folder, attached to
  the original thread. You review + send manually.
- `Reply_Handler_Runs` sheet has a row summarizing the run.

## Tuning

- Cadence: edit `FOLLOWUP_1_DAYS`, `FOLLOWUP_2_DAYS`, `COLD_DAYS` in `.env`.
- Voice: replies and follow-ups read `voice_examples.md` (same convention as
  outreach-agent). Add or trim examples to steer tone.
- Concurrency / timeouts: `src/reply_handler/config.py` → `Thresholds`.

## Costs

- OpenRouter (gemini-2.5-flash): a few cents per active thread.
- Gmail / Sheets: free.

## Out of scope

- No automatic sending — you click Send for everything.
- No mockup generation when someone says yes (separate agent later).
- No LinkedIn / SMS replies.
- No third follow-up — by 12 days you've nudged twice; further nudges hurt
  reputation.
