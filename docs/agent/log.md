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
- Exact OpenRouter model ids for primary and second judge, chosen at stage 5 with prices.
- Leadership/people page URLs per probe unit: to be found at seed time (stage 2) or setup.
- No tests or import-linter yet (no code); they start at stage 1.

**Traps noted for later:** empty `allowed_tools` doesn't disable SDK built-ins; failed agent session
may report $0; Telem default routing fans out to all providers; Telem fetch is not evidence.
