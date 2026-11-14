# sourcemap

sourcemap tells you, with evidence, which public source to trust for which kind of entity and
which kind of fact, and keeps that answer current.

For a kind of data (org charts, academic identities), it finds the sources that publish it, reads
them, checks their statements against other sources, and draws a **map**: segments × sources, each
cell with coverage and an honest accuracy interval. Every number opens up to the checks behind
it, and every check to a saved copy of what the source returned.

> Status: **demo built** — Samsung Electronics marketing org chart: sources found through Telem, measured
> against DART (`docs/experiments/0001-…`), and a multi-segment source benchmark for Samsung, Nvidia and
> Airbus (`docs/experiments/0002-…`, page `data/multi/sourcemap_benchmark.html`). See `docs/plan/` and `docs/agent/log.md`.

## Read in this order

1. `docs/domain.md` — the problem, the vocabulary, the pipeline and the accuracy rules. The
   source of truth for behaviour.
2. `docs/containers.md` — the processes, stores and outside services.
3. `docs/data-model.md` — the database.
4. `docs/components/` — one doc per part of the system.
5. `docs/adr/` — the decisions and why.
6. `docs/plan/` — the stages: goal, what gets built, and how each is checked.
7. `docs/agent/log.md` — what happened in each session and what is open.

## Demo scope

- Two data types: **org chart** (16 companies in 4 segments) and **academic identity**
  (17 departments in 4 segments).
- Sources: theorg.com, Open DART, LinkedIn via Apify, OpenAlex, ORCID, company leadership pages,
  university directories.
- No human-labelled gold set: ground truth comes from reference sources and cross-lineage
  lookups (ADR 0003).
- **Centrepiece: the search-provider benchmark** — the same queries through every search provider
  behind Telem, scored per segment on how well each finds sources (ADR 0015). Second: a daily news
  **change monitor** that decides which claims to re-check first, never what is true (ADR 0016).

## Running it

_To be written in later stages._ Planned commands:

```
sourcemap seed                     # load starting content into a fresh database
sourcemap worker                   # the worker process (all internet, model and paid work)
sourcemap api                      # the API + web UI
sourcemap run maintenance org_chart --mode test
sourcemap map org_chart            # print the map in the terminal
```

Keys go in `.env` (never committed): `TELEM_API_KEY`, `OPENROUTER_API_KEY`, `APIFY_TOKEN`,
`OPENDART_API_KEY` (optional), `OPENALEX_EMAIL` (optional, polite pool). Agents use the local
Claude Code login.

## 5-minute demo

Open `data/demo/sourcemap_demo.html` (rebuild it with `.venv/bin/python scripts/demo_page.py`).

1. **The question** at the top, and the flow.
2. **Section 1:** the planner thinks in publisher *categories*: point at "Korean regulatory filings"
   and its Korean queries; this is how DART is found without anyone typing its URL.
3. **Section 2:** the same queries through every search provider behind Telem; the known-answer
   leaderboard with 90% intervals; who found DART, theorg and samsung.com.
4. **Section 3:** the source map: DART is the reference (1,119 executives, 93 in marketing); theorg's
   employment and title accuracy with intervals, and its marketing coverage of 2/93.
5. **Section 4:** open the checks behind a number: Seong H. Cho ↔ 조성혁, the DART quote, the verdict;
   and the one disagreement (Won-Jin Lee).
6. **Section 5:** Samsung's marketing org chart by unit, from the official filing.
7. **Honest limits.**

The data in `data/demo/` comes from live calls (Telem, OpenRouter, DART, theorg); it is not committed.

### Multi-segment benchmark

```
.venv/bin/python scripts/demo_multi.py refs|plan|search|read|verify   # each step cached in data/multi/
.venv/bin/python scripts/demo_multi_page.py                             # → data/multi/sourcemap_benchmark.html
```
