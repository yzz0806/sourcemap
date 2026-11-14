# Stage 4 — Discovery

## Goal
An agent finds where the data is published; the user keeps the sources worth reading (gate B).

## What gets built
- `services.websearch`: Telem `/v1/search` and `/v1/fetch` behind `search()` / `fetch()`, providers
  pinned or `auto_routing: "accuracy"`, small `num_results`, 429 handling, every call charged to the
  run budget, provider recorded per hit (ADR 0010). Request/response details confirmed against
  Telem's docs first.
- `services.budget` and the spend ledger.
- `agents.discovery`: plan publisher categories, search each in parallel, return source cards with
  honest lineage and `found_by` (ADR 0007). Built-in SDK tools disabled explicitly; sessions capped.
- People-page finder: Telem search restricted to a probe unit's own domain, for leadership and
  department pages missing from the seed.
- Setup run up to gate B; `sourcemap approve <run> B` from the command line.
- Approved sources without an adapter: "not probed — no adapter", listed under "needs an adapter".

## Order of work
ADR 0010 confirmed against real Telem docs → prompt-as-text tests and fake-agent tests → code →
`services.md`, `agents.md` updated → one small test-mode discovery run (asks first if > $5) →
experiment note → checks, log, commit, wait.

## How you check
1. Open 3 proposed URLs: real, hold the data, lineage honest (anything built from LinkedIn says `linkedin`).
2. Each card shows which search provider found it.
3. Keep about 3 new sources at gate B; reject one run once and see it stop cleanly.
4. "What did each agent session and each search cost?" — totals match the spend ledger.
5. A run with a tiny budget (e.g. $0.50) stops cleanly with a clear message.
6. No search result is stored as evidence (grep the raw store references).
