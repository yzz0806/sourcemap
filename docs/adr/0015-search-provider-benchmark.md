# 0015 — Search-provider benchmark: the same fixed queries through each Telem provider, scored with the product's own honesty rules

Status: proposed (stage 0, under review). The user chose this as the demo's centrepiece.

## Context
Telem routes queries to many search providers (Exa, Brave, Tavily, Perplexity…). sourcemap measures
which source is good for what; the same method can measure which search provider is good at
*finding* sources, per segment. Discovery already records which provider found each source
(ADR 0010). A fair comparison needs identical queries, and a notion of "a good find" that doesn't
depend on one provider's own ranking.

## Decision
- **Fixed query plan.** The discovery agent plans publisher categories and writes the queries
  **once** per data type and segment. The benchmark then sends that fixed list to every provider
  pinned individually, plus Telem's `auto_routing`, with the same `num_results`, in randomised order,
  in one sitting. No agent runs per provider (agent variation would confound the comparison).
- **Hits to candidates.** Each hit is normalised to a source candidate by registrable domain and
  path prefix; duplicates across providers collapse into one candidate that remembers every
  provider, rank and query that found it.
- **Two tasks.**
  1. **Known-answer task (automatic, the main source of trials).** For each probe unit, fixed
     query templates whose correct answer is a seeded identifier that passed stage 2's checks:
     theorg page (`"<company> org chart"`), LinkedIn company page (`"<company> LinkedIn"`), ROR
     record (`"<institution> ROR"`), people/leadership page (`"<company> leadership team"`,
     `"<institution> <department> people"`). Each provider's hits are matched to the expected URL
     after normalisation (scheme, `www`, trailing slash, query string). Metrics: hit rate in the top
     k (k = `num_results`) and mean reciprocal rank, per provider and segment. About 80 trials per
     provider per data type; no human review.
  2. **Open discovery task (blind review).** The fixed query plan below.
- **What counts as a good find** in the open task (the relevant set, pooled across providers):
  1. **known sources** from the seed (theorg, DART, OpenAlex, ORCID, company and university
     domains) — automatic, no review needed;
  2. candidates the user **keeps at gate B**. Gate B review is **blind**: candidates are shown
     pooled and deduplicated, in random order, without provider, rank or query.
- **Review without the UI.** `sourcemap review export` writes a CSV (candidate id, domain, example
  URL, up to 3 titles/snippets, segments; no provider/rank/query); `review import` records the
  decisions; `sourcemap review` offers the same rows in the terminal.
- **Review cap.** `sourcemap benchmark plan` shows the expected number of candidates to review and
  the time it takes. At most **~80 per data type** are reviewed: above that, a seeded random sample
  of 80 is reviewed, and open-task metrics are computed over reviewed candidates only (stated on
  the leaderboard). Known sources are labelled automatically and don't count toward the cap.
- **Execution before the worker exists.** The benchmark run and its jobs are stored in the database
  as usual and executed inline from the CLI (`--inline`, `resume --inline`) with the same stage
  code; the worker (stage 5a) runs the same jobs unchanged.
- **Metrics per provider, per segment and overall:**
  - precision = good finds / candidates it proposed;
  - pooled recall = good finds it found / all good finds by any provider;
  - known-source recall = known sources it surfaced / known sources for that segment;
  - exclusive finds (good finds no other provider returned);
  - cost per good find; median latency.
  - Later stages add downstream quality: mean measured coverage and accuracy of the kept sources it
    found (only for sources with adapters; otherwise "not probed").
- **Honesty rules carry over.** Proportions are Beta(1, 1) posteriors with a 90% interval; fewer than
  5 trials → "not enough data"; a provider that errored is "failed", not 0.
- **Cost control.** The plan's size (categories × queries × providers) and its estimated cost are
  shown before the run; over $5 asks first. Results are cached; a re-run of the same plan reuses them.
- Results are stored per run (`benchmark_result`) and shown as a leaderboard.

## Consequences
- The benchmark is reproducible from the stored query plan and hits.
- Pooled recall can only see what *some* provider found; sources no provider found are invisible.
  This is stated on the leaderboard.
- Blind review costs the user a few minutes at gate B, which already exists.

## Alternatives rejected
- **One agent session per provider** — cheaper to write, but agent behaviour differs run to run, so
  differences would not be the provider's.
- **Score by each provider's own top-k rank** — measures the provider against itself.
- **Model-judged relevance for every hit** — the judge would become the ground truth for the
  centrepiece; known sources plus blind gate B are stronger and cheap.
- **Open task only** — too few good finds per segment for intervals narrower than "not enough
  data"; the known-answer task supplies the trials.
- **Reviewing every candidate** — could be several hundred; a capped random sample keeps the
  estimate unbiased at a fixed cost to the user.
