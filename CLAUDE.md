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
