# Demo — Samsung Electronics marketing org chart (replaces stages 3–9 for today)

Decided with the user on 2026-11-14 with ~2 hours left. Supersedes the stage 3–9 plan for the
demo; those stage files stay as the full-product plan.

**The question:** "Where can I get Samsung Electronics' marketing department org chart, and which
source should I trust?"

## Flow
1. **Plan sources** — one structured model call (OpenRouter) plans categories of publishers
   (Korean regulator filings, the company's own pages, crowd-edited org-chart sites, press/news…)
   with queries per category. *Deviation from ADR 0007:* a single call, not a Claude Agent SDK
   session, to save setup time.
2. **Search** — every query through every search provider behind Telem (ADR 0010, 0015).
3. **Pool + blind review** — candidates by domain; the user keeps/rejects without seeing providers.
4. **Provider leaderboard** — which provider found the known sources (DART, theorg, samsung.com).
5. **Read** — DART executive table (official, tier 1, the reference), filtered to marketing by its
   responsibilities field; theorg's Samsung marketing people; Samsung's own pages if they list any.
6. **Measure** — match names across scripts (judge), check employment/title claims against DART,
   score coverage and accuracy with the stage 1 rules (ADR 0002, 0003, 0004).
7. **Show** — one static page: sources found and by whom, the source map with intervals,
   drill-down to evidence, Samsung's marketing org chart with each value's source.

## Honest limits (shown on the page)
- One company: these are Samsung's numbers, not a segment's.
- DART lists executives (임원) only: non-executive marketers on theorg are `unverifiable`, not wrong.
- reports_to: DART has no manager field → unverifiable.
- DART is the reference and is not itself spot-checked (R9 cut).

## Cut for today
LinkedIn/Apify, other companies and segments, academic identity, daily runs, expiry, monitor,
simulations, drift, the Agent SDK, sandbox child process, worker, web app.

## Fallback
If theorg can't be read by ~1:05, measure Samsung's own pages against DART instead.

Cost estimate: $1–3.
