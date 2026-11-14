# 0012 — Drift: source health per run, verdicts expire and are re-checked, drift alerts on non-overlapping intervals

Status: proposed (stage 0, under review)

## Context
The map must follow the internet. Sources break or change shape without notice, and people leave
companies even when a source never updates. The earlier implementation never re-checked an
unchanged claim, so a stale claim stayed `correct` forever.

## Decision
- **Health** per source per run, from this run vs the previous one: `broken` (no valid record for
  any unit), `shape_changed` (≥ 50% of fetched units fail validation), `degraded` (some units fail),
  `changed` (≥ 30% of claim fingerprints differ for units seen both times), else `ok`. A broken
  source never stops the run.
- **Expiry** by claim type: title and reports_to 30 days, employment and affiliation 60, role 90,
  exists 180. Expired verdicts leave the current score (they remain in history).
- **Re-check:** each maintenance run re-checks verdicts within the last 20% of their life, oldest
  first, up to a share of the lookup budget (default 30%). A re-check adds a new verification row.
- A lookup showing the subject's position at the probe unit has ended yields `stale`, not `wrong`.
- **Drift alert** when a cell's new 90% interval does not overlap the previous run's.
- **Simulated days:** a run's `as_of` date drives expiry and freshness. Departures and breakages
  for the demo are simulated only in a database copy, with fabricated fetches flagged (ADR 0014).
- Unchanged claims keep their row (same fingerprint, which relies on stable entity ids, ADR 0013)
  and their valid verdicts carry over — no repaid checks — until expiry.

## Consequences
- Accuracy can drop without the source changing, as people leave; this is intended.
- Re-checks cost money every run; capped by the re-check share.

## Alternatives rejected
- **Re-check only changed claims** — the known bug: departures are never seen.
- **Re-check everything every run** — far over budget.
- **Alert on any change of mean** — noisy at small n; non-overlap of intervals is a real shift.
