# 0016 — Change monitor: daily news searches reorder re-checks; they never decide verdicts

Status: accepted (stage 0, approved by the user 2026-11-14)

## Context
People leave companies between verdict re-checks (ADR 0012). Random or oldest-first re-checks find
departures slowly. Leadership changes are often in the news. News snippets are search results, so
by R2 they can never be evidence.

## Decision
- **Daily, org chart only.** Each maintenance run makes one Telem search per company, restricted to
  the last 7 days, e.g. `"<company>" (appoints OR joins OR leaves OR steps down OR hires)`, with pinned
  providers and small `num_results`. 16 searches per run.
- **`OR` support is confirmed, not assumed.** Stage 3 sends one tiny probe query with `OR` to each
  provider and records here which honour it. The monitor uses the `OR` query only with those
  providers; otherwise it sends one plain query (`"<company>" executive appointment departure`), never
  several queries per company. Result of the stage 3 check: _to be filled in_.
- **Matching hits to people.** A hit matches a tracked entity of that company when a normalised name
  of the entity appears in the hit's title or snippet (rules only, no judge).
- **Effect: re-check priority only.** The matched entity's employment and title claims move to the
  front of the re-check queue, within the existing re-check share of the lookup budget. The verdict
  still comes from reference or lookup evidence. The verification records
  `trigger_monitor_hit_id`, and the drill-down shows "re-check triggered by a news hit (provider X)".
- **Unknown names** in hits (possible new hires) are listed for information; they create nothing.
- **Presentation: examples, not a rate.** The demo shows how it works and any real case it caught
  (hit → re-check → `stale`). It does not claim a hit rate; counts are shown as raw numbers with
  "too few to measure" until there are enough triggered and random re-checks to compare.

## Consequences
- Departures can be caught days earlier, at the cost of ~16 searches per day.
- A wrong news hit costs one extra lookup, never a wrong verdict.

## Alternatives rejected
- **Use the news hit as a `stale` verdict** — breaks R2.
- **Judge-based name matching on every hit** — more cost for a step that only reorders a queue.
- **Monitor academic departments too** — departmental news rarely names students; not worth it in the demo.
