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
