# Stage 5a — The daily pipeline: run, trace, resume

## Goal
A maintenance run that works end to end on real data — probe → match → verify → score → map
snapshot — run by the worker, with a budget cap, a traceable map and crash resume.

## What gets built
- Worker loop: job leasing, heartbeats, expired-lease recovery; stages idempotent per unit
  (ADR 0011). The inline mode from stage 3 runs the same jobs.
- Stages: probe (reuse fresh fetches; health per source), match (stable entities, ADR 0013), verify
  (reference, lookup + judge, agreement; sampling within budget; tier-1 spot-checks), score (scores,
  `score_verification` links, coverage incl. "k of N failed" and "no adapter", transfer gate, combos,
  gaps, map snapshot).
- `sourcemap run maintenance <data_type> --mode test`, `status`, `map` (terminal print with states
  and raw/weighted n), `trace <score|verification>`.

## Order of work
Docs for any rule refined while wiring → whole-run tests with fake adapters, fake judge, fake
sandbox (including a crash in the middle of verify) → code → `pipeline.md` updated → real
test-mode runs (asks if > $5) → experiment note → checks, log, commit, wait.

## How you check
1. Test-mode maintenance run for org chart; cost under the test budget.
2. Terminal map: each segment shows cells with coverage and an interval or a state.
3. Trace one number: "show me the verifications behind theorg / NA mid-size / title", then one
   verdict's claim, the verifier's raw response and the judge's reason. Do you agree?
4. No claim verified by its own lineage (no LinkedIn claim verified by LinkedIn).
5. Run again: much cheaper (fetches reused, checks not repeated), two map snapshots, same entity ids.
6. Academic identity run: many "unverifiable" verdicts expected; low measured share, not high accuracy.
7. Kill the worker mid-run, restart: the run continues from its stage without repaying.

## You need to provide
- Approval of each real test-mode run over $5 (none expected).
- Your judgement on the one traced verdict in check 3.

## Cost
About **$4–6**: the first org-chart run (Apify people lists and lookups, judge calls) within the
~$6 test budget; the second run much cheaper; academic identity cents (free APIs + judge).
