# 0014 — Simulated runs (departures, breakages) run in a separate database and are always flagged

Status: accepted (stage 0, approved by the user 2026-11-14)

## Context
The drift demo must show a person leaving a company and the claim turning `stale`, and a source
breaking, without waiting weeks. That needs fabricated snapshots. Fabricated data must never reach
the real map, real history or the assembled dataset, or the product's numbers stop being honest.

## Decision
- **Separate database.** `sourcemap sim <scenario>` copies the real database at that moment to
  `data/sim/<scenario>.sqlite` and runs there. The real database is never written by a simulation.
  The raw store is shared (it is write-once and content-addressed), but simulated bytes are only
  referenced from the simulation database.
- **Flags everywhere.** In the simulation database every run has `scenario` set; every fabricated
  raw fetch has `simulated = 1`, `derived_from_raw_fetch_id` (the real fetch it was edited from)
  and `sim_patch_json` (exactly what was changed). Real fetches replayed unchanged keep
  `simulated = 0`.
- **Scenario files** (`scenarios/*.yaml`, in the repo) declare the change, e.g.:
  `departure: {unit: gong, person: <entity id>, left_on: 2026-12-01}` →
  from that date, the LinkedIn lookup response for that person is the stored real response with the
  Gong position given an end date, and the company page fetch is the stored one with that person
  removed. `break: {source: theorg, from: 2026-12-03, mode: http_404}` → the adapter returns a 404.
- **Days advance by `as_of`.** Each simulated run is one day later. The scenario forces the departed
  person's claims into the re-check set on the day after `left_on`, so the verdict turns `stale`
  within one cycle and the cell's accuracy and history move.
- **UI.** The API can open a simulation database only on explicit choice (`?db=sim:<scenario>`); every
  page then shows a persistent "SIMULATION — <scenario>" banner, and CSV exports are refused.
  The default view is always the real database.

## Consequences
- No query mistake can mix simulated and real scores: they are in different files.
- Simulations are reproducible from the scenario file and the real database copy.

## Alternatives rejected
- **A `realm` column in one database** — one missing `WHERE` clause anywhere mixes fake into real.
- **Editing real raw fetches** — raw fetches are write-once evidence; never edited.
- **Waiting for a real departure** — not possible within the demo.
