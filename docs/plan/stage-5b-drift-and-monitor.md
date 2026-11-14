# Stage 5b — Drift, simulations, change monitor, calibration

## Goal
The map follows the internet: verdicts expire and are re-checked, breakages and departures are
shown (simulated, isolated), news reorders re-checks, and the judge and matcher are measured.

## What gets built
- Expiry and re-checks (ADR 0012); source health compared with the previous run; drift alerts when
  intervals stop overlapping; history per cell.
- `sourcemap sim <scenario> [--days N]`: database copy, scenario files (`departure`, `break`),
  fabricated fetches flagged with their source fetch and patch (ADR 0014).
- **Change monitor** (ADR 0016): one Telem news search per company per maintenance run (last 7
  days), using `OR` only with providers that honour it (recorded in stage 3), otherwise one plain
  query; hits matched to tracked people; their claims first in the re-check queue; verifications
  record the triggering hit. Presented as how it works plus any real case caught.
- **Calibration:** second-family judge on a sample each run, agreement shown; matching quality on
  identifier-known pairs (false and missed merges).

## Order of work
Docs → tests (expiry tables, health transitions, drift alert cases, scenario isolation: nothing
written to the real database) → code → `pipeline.md`, `measure.md` updated → real and simulated
runs → experiment note → checks, log, commit, wait.

## How you check
1. Simulate a broken source: "broken", the run still finishes, history marks it; the real
   database is unchanged (row counts before and after).
2. Simulate a departure: within one cycle the claim is `stale` and the cell moves; every
   fabricated fetch shows `simulated` with its patch.
3. A claim older than its expiry is re-checked; an expired verdict leaves the score.
4. Monitor: 16 news searches in the spend ledger; any matched hit shows person → triggered
   re-check → verdict from a lookup or reference. With no real case, the page says so.
5. Judge calibration (second-judge agreement, with model ids and prompt version) and matching
   quality are printed with the map.

## You need to provide
- Nothing new; optionally pick the person for the departure scenario (otherwise the agent picks
  one with a valid `correct` title verdict).

## Cost
About **$1**: monitor searches (16 per run), re-check lookups, second-judge sample. Simulations
replay stored fetches and cost almost nothing.
