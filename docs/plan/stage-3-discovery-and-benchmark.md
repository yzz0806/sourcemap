# Stage 3 — Discovery and the search-provider benchmark (centrepiece)

Moved before "reading sources" so the centrepiece is built early: it needs search, the seed and
gate B, not adapters.

## Goal
An agent finds where the data is published; the same fixed queries are sent to every search
provider behind Telem; the user reviews pooled candidates blind; each provider is scored per
segment with the product's honesty rules (ADR 0015).

## What gets built
- `services.websearch`: Telem `/v1/search` and `/v1/fetch` behind `search()` / `fetch()`;
  providers pinned or `auto_routing`; small `num_results`; 429 handling; every call charged to the
  run budget; provider, rank and latency recorded per call (ADR 0010). Request/response format and
  prices confirmed against Telem's docs first.
- `services.budget` and the spend ledger.
- `agents.discovery`: plan publisher categories and write the query plan once; built-in SDK tools
  disabled explicitly; sessions capped (ADR 0007).
- Benchmark run: plan → send to each provider + auto routing (randomised, cached) → collapse hits
  into candidates → **blind gate B** → `benchmark_result` (precision, pooled recall, known-source
  recall, exclusive finds, cost per good find, latency, with intervals).
- `sourcemap benchmark plan <data_type>` shows the plan, providers and estimated cost before
  anything is sent; `sourcemap leaderboard` prints the result.
- Kept candidates become sources (lineage and tier filled by the agent, checked by the user);
  sources without an adapter show "not probed — no adapter".
- People-page finder: Telem search restricted to a probe unit's own domain, for missing
  leadership/department page URLs.

## Order of work
ADR 0010 and 0015 confirmed against real Telem docs → tests: prompt-as-text, fake agent, fake
search with recorded provider responses, metric case table (in stage 1's `measure.benchmark`) →
code → `services.md`, `agents.md`, `pipeline.md` updated → show the plan and cost → one benchmark
run per data type (asks first if > $5) → `docs/experiments/0001-benchmark.md` → checks, log,
commit, wait.

## How you check
1. Before sending: the plan lists categories, queries, providers and an estimated cost.
2. Blind review: candidates show no provider names. Open 3: real, hold the data, lineage honest.
3. The leaderboard per segment shows each provider's metrics with intervals and n; providers that
   errored show "failed"; small samples show "not enough data".
4. Pick one provider's "exclusive find": no other provider's hits contain that candidate.
5. Known-source recall: for Korean listed, which providers surfaced DART?
6. "What did each provider and each agent session cost?" — matches the spend ledger.
7. Re-running the same plan costs nothing (cached).
8. A run with a tiny budget (e.g. $0.50) stops cleanly with a clear message.
9. No search hit is referenced by any verification (the schema has no such link).
