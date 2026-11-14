# Session log

## 2026-11-14 — Stage 0: design on paper

**Built:** docs only, no code. `docs/domain.md`, `docs/containers.md`, `docs/data-model.md`,
`docs/components/` (8 docs + layering), ADRs 0001–0012, README skeleton, `.gitignore`.

**The user's decisions** (made by the user, not the agent; they differ from the reference
`DEMO.md`, and the user confirmed them in the stage 0 review):
- **Both data types**, org chart and academic identity.
- **All 4 org-chart segments including Korean listed, so DART is in scope.**
- **No human-labelled gold set.** The user does not want hand-checking. Ground truth comes from
  reference sources, cross-lineage lookups and agreement (ADR 0003). Judge error is estimated with an
  easy-case suite and a second-family judge; the UI says it is not measured against humans.
- **Telem for search**, not Tavily (ADR 0010).

**Agent's design choices** (proposed, for review): stages follow `PLAN.md` (0–9) adapted to this
scope; agents limited to discovery; first-party pages extracted by a judge call (ADR 0006).

### Stage 0 review fixes (same day)
1. Decisions above marked as the user's.
2. A discovered source with no adapter: kept as `approved`, map cells "not probed — no adapter",
   listed under "needs an adapter" (domain §4 step 2). **Weekly discovery dropped**: on demand only.
3. Entity ids stable across runs, merges/splits logged, split invalidates cross-entity verdicts
   (ADR 0013, domain §8, `entity_event`).
4. Departure simulation: scenario files, run in a database copy, fabricated fetches flagged with
   their source fetch and patch, UI banner, never exported or mixed into real scores (ADR 0014,
   domain §4 "Simulated days").
5. Gate D in one place: end of setup runs only (domain step 8); pipeline diagram fixed.
- Telem label in `containers.md` fixed (discovery + finding people pages, never evidence).
- Stage-0 ADRs marked **proposed** until approval and amended in place; accepted on approval.

### Plan written down
`docs/plan/` added at the user's request: an index with the per-stage working order and the checks
for every stage, and one file per stage (0–9) with goal, what gets built, order of work and checks.
Keep each stage file's status line current.

### More Telem: benchmark and monitor (user's decision)
- The user wants Telem used as much as is legitimate. **User's decision:** build the
  **search-provider benchmark first, as the centrepiece** (ADR 0015, domain §10), and the **change
  monitor second** (ADR 0016, domain §11). In the demo the monitor is presented honestly as "how it
  works, plus one real example if we caught one", not as a measured result.
- Telem stays out of verification and probe evidence (R2); the schema has no link from a
  verification to a search hit.
- Stages 3 and 4 swapped so the benchmark is built right after storage: stage 3 = discovery +
  benchmark, stage 4 = reading sources.
- Considered and not taken now: gap finder, identifier finder at seed time (cheap extras for later).

### Plan review fixes
1. **Dependencies:** judge service moved to stage 4 (first-party extraction needs it; ADR 0009).
   Stage 3 runs the benchmark **inline** from the CLI with the same jobs and stage code (the worker
   arrives in 5a). Blind gate B before the UI: `review export/import` CSV or `review` in the terminal.
   Polite fetch helper (`sandbox.kit`) moved to stage 2 for the identifier checks.
2. **Known-answer task** added to the benchmark: seeded theorg / LinkedIn / ROR / people-page URLs
   searched through every provider and scored automatically (~80 trials per provider per data type)
   (ADR 0015, domain §10, `known_answer_trial`).
3. `benchmark plan` shows the expected review count; review capped at ~80 per data type, random
   sample above that (ADR 0015).
4. Stage 5 split into **5a** (pipeline, trace, resume) and **5b** (expiry, simulations, monitor,
   calibration).
- Stage 2 gets automatic identifier checks (`seed --check-ids`, `identifier_check`).
- Every stage file has "You need to provide" and "Cost"; the plan index sums them: ≈ $15–21,
  close to the $20 budget — stage 8 re-scores the cached benchmark; the open task is trimmed first
  if Telem prices are higher.
- Monitor `OR` support: to be confirmed per provider in stage 3 with a probe query and recorded in
  ADR 0016; fallback is one plain query per company.

### Notes for later stages (from the review)
- **Stage 3/5:** first-party extraction — every extracted value's quote must be found in the visible
  text of the raw HTML, else the value is dropped and counted; `record.extracted_by_judge_call_id`
  links record → judge call (column already in the data model).
- **Stage 1/7:** show **weighted n** (agreement = 0.5) next to raw n (`score.n_weighted` added).
- **Stage 1:** coverage with partial failure — units whose fetch failed are excluded from the
  denominator and shown as "k of N failed" (`score.units_failed` added); never counted as uncovered.
  Rule to be written into domain §6 Coverage and the case table at stage 1.

**Reference material** (read-only, not in this repo): `../../sourcemap/rebuild/{BRIEF,PLAN,DEMO,CLAUDE}.md`.

**Open items:**
- Open DART API key — user is getting it. Without it the Korean segment's DART cells are "not probed".
- Telem request/response details (provider names, `usage` field) to confirm against its docs at stage 4.
- Exact OpenRouter model ids: primary judge chosen at stage 4, second judge at stage 5b, with prices.
- Leadership/people page URLs per probe unit: to be found at seed time (stage 2) or setup.
- No tests or import-linter yet (no code); they start at stage 1.

**Traps noted for later:** empty `allowed_tools` doesn't disable SDK built-ins; failed agent session
may report $0; Telem default routing fans out to all providers; Telem fetch is not evidence.

## 2026-11-14 — Stage 1: measuring rules, offline

**Built:** `pyproject.toml` (pytest, import-linter contracts "pure core" and "layers"), domain types
(`vocab`, `model`, `specs`), and 15 pure modules in `sourcemap.measure` (see
`docs/components/measure.md`). 195 fast tests, no network or keys. `scripts/stage1_checks.py`
prints the plan's checks.

**How the work was split:** I wrote the foundation (project setup, domain types, names, accuracy,
verdicts, and the accuracy case table) and committed it; then three parallel subagents each owned
separate files: (A) compare, claims, match; (B) coverage, combos, transfer gate, assemble;
(C) benchmark, monitor, freshness, sampling, health, drift. Each wrote its case tables before its
code. I integrated, ran the full suite and the linter, and updated the docs.

**Honest note on order:** for `accuracy.py` and `verdicts.py` I wrote the code a few minutes before
the case table rather than after; the table was written from the domain rules, not from the code,
and every row passed on the first run.

**Decisions taken while building (recorded in docs/domain.md):**
- Not-fetched units leave the coverage denominator like failed ones ("k of N not fetched").
- A fetched-but-empty answer is a measured "not covered".
- Two different values of the same identifier block a merge; only pairs with a new mention are
  matched; existing wrong merges are reported for a split.
- The monitor matches only names of ≥ 2 tokens (or Hangul ≥ 2 syllables).
- Health: a source whose every unit fails to parse is `broken` (broken outranks shape_changed).
- Benchmark metrics with a zero denominator are `not_enough_data` with no interval; MRR, exclusive
  finds, cost and latency are plain values.

**Open items:**
- `normalise_url` exists twice (`compare.py` keeps the port, `benchmark.py` drops it). Merge into one
  when the benchmark is wired in stage 3, with a test for the port case.
- Known-source recall per segment: the pipeline must pass the segment's own seed list as
  `known_keys` (stage 3).
- `scipy` import makes the first test take ~9 s cold; fine for now.

**Trap found:** `addopts` already has `-q`; adding another `-q` hides the "N passed" line.

## 2026-11-14 — Stage 2: storage, seed content, identifier checks

**Built:** SQLite schema (`store/migrations/0001_init.sql`, every table of docs/data-model.md),
`store` (db, rawstore, seed, queue, events, spend), `sandbox.kit` (polite fetch, stdlib only),
`pipeline.idcheck`, and the `sourcemap` CLI (`seed [--check-ids]`, `ids [--failed]`, `counts`).
Seed content in `seeds/sources.json` (segments, 7 sources, offers, adapters) and `seeds/units.json`
(16 companies, 17 departments with identifiers). 235 fast tests; import-linter 2 contracts kept.

**How the work was split:** a research subagent compiled `seeds/units.json` (identifiers found by
web search and the free ROR/OpenAlex APIs, with evidence links) while I wrote the schema, store,
kit, checks and CLI. The automated checks then verified the subagent's identifiers.

**Live check result (free, ~2 min):** 92 identifiers pass, 11 need the user's decision:
Samsung's theorg page is titled "Samsung" (slug `samsung`); 9 units have no people page in the
seed; MIT Physics' people page answers 403 to automated requests. All 17 ROR ids, 17 OpenAlex ids,
4 DART codes and 15 of 16 theorg slugs pass.

**Fixed while running the checks (each with a test):**
- robots.txt handling followed old practice (401/403 → disallow). `api.ror.org/robots.txt` answers
  403, which blocked all ROR checks. Now RFC 9309: 4xx → allowed, 5xx/unreachable → disallowed.
- DART codes were checked for every company; now only for Korean listed units.
- Institution short names added as unit `aliases` (Purdue University, Illinois/UIUC, MIT, KAIST,
  ETH, SNU, CMU) — pages use them instead of the full ROR name. No alias added for Samsung on
  purpose: whether theorg's "Samsung" page is Samsung Electronics is the user's call.
- The weak import-linter "env" contract (it only forbade `dotenv`) was replaced by
  `tests/test_env_rule.py`, which searches the source for environment reads outside `cli.py`.
- Identifier checks moved from `store` to `pipeline` (they need `sandbox.kit`; store must not
  import sandbox — layers contract).

**Research findings worth keeping:** theorg `/org/gong` is a Croatian company (gong.hr); Gong.io is
`gong-io`. `/org/lg-electronics` is 404; the seed's LG slug passed with the page titled "LG Electronics | The Org". Pennylane's LinkedIn slug is `pennylaneaccounting`. cs.illinois.edu redirects to
siebelschool.illinois.edu. "NSU" resolved to Norfolk State University (alternatives in the seed
notes). Purdue's ROR id is the West Lafayette campus (02dqehb95), not the system record.

**Open items:** the 11 decisions above; `normalise_url` duplication (stage 3).
