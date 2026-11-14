# Stage 5 — The daily pipeline, change monitor and drift

## Goal
A maintenance run that works end to end on real data — probe → match → verify → score → map
snapshot — with a budget cap, crash resume, source health, verdict expiry, drift alerts, and
simulated scenarios for the drift demo.

## What gets built
- Worker loop with job leasing and heartbeats; stages idempotent per unit (ADR 0011).
- Stages: probe (reuse fresh fetches), match (stable entities, ADR 0013), verify (reference,
  lookup + judge, agreement; sampling; re-checks; tier-1 spot-checks), score (scores,
  `score_verification` links, map snapshot, health, alerts).
- `services.judge`: OpenRouter, batched and cached; primary and second-family models chosen with
  prices (ADR 0009); easy-case suite must pass before use.
- Judge calibration (second-judge agreement) and matching quality (identifier-known pairs) per run.
- `sourcemap run maintenance <data_type> --mode test`, `status`, `map` (terminal print), `trace`.
- `sourcemap sim <scenario>`: departure and broken-source scenarios in a database copy (ADR 0014).
- **Change monitor** (ADR 0016): one Telem news search per company per maintenance run (last 7 days),
  hits matched to tracked people by name, their claims moved to the front of the re-check queue;
  verifications record the triggering hit. Presented as how it works plus any real case caught,
  never as a measured hit rate.

## Order of work
Docs for any rule refined while wiring → whole-run tests with fake adapters, fake judge, fake
sandbox → code → `pipeline.md`, `services.md` updated → real test-mode runs (ask if > $5) →
experiment note → checks, log, commit, wait.

## How you check
1. Test-mode maintenance run for org chart; cost under the test budget.
2. Terminal map: each segment shows cells with coverage and an interval or a state.
3. Trace one number: "show me the verifications behind theorg / NA mid-size / title", then one
   verdict's claim, the verifier's raw response and the judge's reason. Do you agree?
4. No LinkedIn claim verified by LinkedIn; no claim verified by its own lineage.
5. Run again: much cheaper (fetches reused, checks not repeated), two map snapshots, same entity ids.
6. Simulate a broken source: "broken", the run still finishes, history marks it.
7. Simulate a departure: within one cycle the claim is `stale` and the cell moves; the simulation is
   flagged and the real map is unchanged.
8. Academic identity run: many "unverifiable" verdicts expected; low measured share, not high accuracy.
9. Kill the worker mid-run, restart: the run continues from its stage without repaying.
10. Judge calibration and matching quality are printed with the map.
11. Monitor: the run made one news search per company (16, see the spend ledger); any matched hit
    shows the person, the triggered re-check and its verdict, which came from a lookup or reference,
    not from the news. With no real departure caught, the monitor page says so plainly.
