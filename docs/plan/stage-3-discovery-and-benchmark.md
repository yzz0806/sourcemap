# Stage 3 — Discovery and the search-provider benchmark (centrepiece)

Built right after storage: it needs search, the seed and gate B — not adapters, not the judge,
not the web UI.

## Goal
Measure which search provider behind Telem is good at finding sources, per segment, with enough
trials for honest intervals (ADR 0015). Two tasks:

1. **Known-answer task (automatic).** For each probe unit, fixed queries whose correct answer is a
   seeded identifier that passed stage 2's checks: the theorg page, the LinkedIn company page, the
   ROR record, the people/leadership page. Every provider's hits are checked against the seed
   automatically (normalised URL match). About 16 × 3 + 17 × 2 ≈ 80 trials per provider per run —
   enough for intervals, with no human review.
2. **Open discovery task (blind review).** The discovery agent's fixed query plan, sent to every
   provider; pooled candidates reviewed blind at gate B; scored by precision, pooled recall,
   known-source recall, exclusive finds.

## How it runs without the worker
The worker loop (leasing, heartbeats, scheduler) is stage 5a. Stage 3 creates the run and its jobs
in the database exactly as later, and executes them **inline** from the CLI with the same stage
code: `sourcemap run benchmark <data_type> --inline`. At gate B the command stops; after review,
`sourcemap resume <run> --inline` continues. In 5a the worker runs the same jobs unchanged.

## How the blind gate-B review works before the UI exists
- `sourcemap review export <run> > review.csv` — one row per pooled candidate in random order:
  candidate id, domain, an example URL, up to 3 titles/snippets, the segments it was found for.
  **No provider, rank or query column.** Open it in any spreadsheet and fill `keep` / `reject`.
- `sourcemap review import <run> review.csv` — validates and records the decisions; known sources
  are pre-marked and not in the sheet.
- Or `sourcemap review <run>` — the same rows one by one in the terminal (k / r / s(kip)).

## What gets built
- `services.websearch` (Telem behind `search()` / `fetch()`; pinned providers or auto routing;
  small `num_results`; 429 handling; budget; provider, rank and latency per call) and
  `services.budget`. Telem's request format, provider list, prices and **boolean `OR` support per
  provider** confirmed against its docs and one tiny probe query first (the monitor in 5b needs `OR`).
- `agents.discovery`: categories and the fixed query plan, written once (ADR 0007).
- Benchmark stages: plan → send (each provider pinned + auto, randomised, cached) → known-answer
  scoring → pool candidates → blind gate B → score → `benchmark_result`.
- `sourcemap benchmark plan <data_type>` shows, before anything is sent: queries per task,
  providers, number of calls, **estimated cost**, **expected number of candidates to review**, and
  estimated review time. Review is **capped at about 80 candidates per data type**: above the cap,
  a random sample of 80 is reviewed and open-task metrics are computed on the reviewed sample
  (stated on the leaderboard).
- `sourcemap leaderboard [--segment]`.

## Order of work
Telem docs + one probe query → ADR 0010/0015/0016 amended if anything differs → tests (prompt as
text, fake agent, fake search with recorded responses, metric case tables) → code → component
docs → show the plan and cost → run per data type (asks if > $5) → blind review →
`docs/experiments/0001-benchmark.md` → checks, log, commit, wait.

## How you check
1. `benchmark plan` lists tasks, queries, providers, calls, estimated cost and expected review
   count (≤ 80 per data type).
2. Known-answer: pick one trial; the expected URL comes from the seed and the hit list shows where
   (if anywhere) each provider returned it.
3. Review sheet: no provider, rank or query column. Open 3 candidates: real, hold the data.
4. Leaderboard per segment: known-answer hit rate and open-task metrics, with intervals and n;
   errors show "failed"; small samples "not enough data"; the sampling and pooled-recall limits stated.
5. One "exclusive find": no other provider's hits contain it.
6. Costs per provider and per agent session match the spend ledger; re-running the plan is free (cached).
7. A tiny budget (e.g. $0.50) stops cleanly with a clear message.
8. Which providers honour `OR` is recorded in ADR 0016.

## You need to provide
- `TELEM_API_KEY` in `.env`.
- Approval of the cost shown by `benchmark plan` if over $5.
- The blind review: up to ~80 candidates per data type, about 10–15 minutes each.

## Cost
Estimate **$3–5** for both data types (≈ 80 known-answer + ~30 open queries per data type, × ~5
providers + auto routing, small `num_results`). Telem's real prices are confirmed first; if the
plan is over budget, fewer providers or fewer open queries are run, never fewer known-answer trials.
Agent sessions run on the Claude Code login.
