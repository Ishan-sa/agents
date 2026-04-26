# Roadmap

A living backlog of upgrades to make the pipeline more advanced. Items move
from this file into the codebase. As things ship, strike them through and
move them to the bottom under "Shipped" — that way the file stays a clear
"what's left to build."

Ordered by leverage, highest first. Tier names are a rough effort signal,
not a strict sequence — feel free to cherry-pick.

---

## Tier 1 — small, high-impact

### [ ] Daily cron / launchd for `reply-handler all`

Right now `reply-handler` only runs when I remember to run it. If I forget for
a week, follow-ups don't go out and conversion drops. Wire up a launchd plist
(or a simple `cron` entry) that runs `reply-handler all` every morning. ~30
minutes of work, infinite reliability gain.

### [ ] Send-rate guardrails in outreach-agent

Outreach-agent has no rate limit — drafting 15 emails in a 5-minute burst from
a fresh Gmail address is a fast path to getting flagged. Add:

- `--max-per-day N` flag that consults `Outreach_Runs` to cap daily sends.
- Randomized 2-15 minute jitter between draft creations so a bulk-send is
  naturally spaced out.

Strictly a flag on outreach-agent, not a new agent.

### [ ] Morning briefing notifier (Telegram / Slack)

Each morning, post a short summary: "5 new replies waiting (3 interested, 1
question, 1 declined). 4 follow-ups drafted today." So I open Gmail when
there's something to act on, instead of checking 10x a day.

Telegram MCP is already wired into this Claude Code setup, so the cheapest
path is probably a tiny Python script that reads `Reply_Handler_Runs` + the
latest sheet state and posts to my chat.

---

## Tier 2 — medium, real upgrades

### [ ] Mockup-generation agent

When reply-handler classifies a reply as `interested` and they want the free
mockup, this agent: reads the prospect's site, generates a 1-page rebuild via
AIDesigner / a frontend skill, hosts it on Vercel under a unique URL, drafts
a follow-up email with the link.

Single biggest revenue lever — turns "as many mockups as I have weekend
hours" into "as many as people want." Probably a sibling subdir
`mockup-agent/` under the same monorepo pattern.

### [ ] Reply-quality enrichment

Right now `check-replies` classifies based only on the reply text. Better:
when classifying, also fetch the prospect's LinkedIn / their business's
recent Google reviews / Twitter, and feed that to the LLM so the response is
hyper-contextual ("saw you just expanded to a second location — congrats…").

### [ ] A/B testing harness for cold-email opening hooks

Each cold email gets one of N opening hooks (random assignment). Track reply
rate per variant in `Outreach_Runs`. After ~50 sends per variant, surface the
winner. Voice examples that aren't winning get pruned. Difference between
"the agency runs" and "the agency improves."

---

## Tier 3 — bigger, transformational

### [ ] LinkedIn outreach agent

Same shape as outreach-agent but uses Sales Navigator / LinkedIn API.
Multi-channel = 2-3x reply rate from the same lead pool.

### [ ] CRM-light dashboard (Next.js, deployed on Vercel)

The Google Sheet is fine for now, but at 200+ live conversations a read-only
dashboard becomes valuable: live pipeline, drafts awaiting action, conversion
funnel, projected $. ~4 hours to build.

### [ ] Auto-onboarding agent

When a deal closes (`status=replied_interested` + confirmed): create the
project Notion page, send the intake form, schedule the kickoff (or async
equivalent), set up the Cal.com block. Closes the loop on the back end of the
pipeline.

---

## Shipped

(Empty — entries land here when they're done in the codebase, with a date
and the commit / PR reference.)
