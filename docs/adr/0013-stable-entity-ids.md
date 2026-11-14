# 0013 — Entity ids stay stable across runs

Status: accepted (stage 0, approved by the user 2026-11-14)

## Context
A claim's fingerprint is (source, probe unit, **subject entity**, claim type, value_norm). Unchanged
claims keep their row across runs, and their valid verdicts carry over (ADR 0012). If matching
created fresh entity ids every run, every fingerprint would change every run: every claim would
look new, every verdict would be lost, and every check would be paid again. Matching decisions can
also change later (a new mention links two entities; the judge splits a wrong merge).

## Decision
- **Entities persist.** The match stage of a run starts from the existing entities of the probe
  unit and their known mentions. A new mention attaches to an existing entity when, in this order:
  (1) it shares an identifier with it; (2) the same source's previous mention with the same
  `local_ref` (e.g. theorg person slug) belongs to it; (3) its normalised name equals one of the
  entity's known mentions; (4) the judge says same for a borderline pair. Only a mention with no
  match creates a new entity.
- **Ids are never reused or renumbered.** `entity.id` is assigned once.
- **Merge:** when two existing entities turn out to be one, the older id survives; the other gets
  `merged_into_id` and is never used again. Its claims are re-pointed to the survivor and their
  fingerprints recomputed; verdicts stay attached to the claim rows. If two claims collide on the
  new fingerprint, the older row survives and the newer is linked to it.
- **Split:** when the judge later calls two mentions of one entity different, the mentions on the
  minority side move to a new entity. Their claims are re-pointed; **reference and agreement
  verdicts that paired claims across the wrong merge are invalidated** (a new verification row with
  reason `entity_split`), lookups are kept (they looked up the named person).
- Every merge and split is logged in `entity_event` with the run and the reason.

## Consequences
- An unchanged source re-probed tomorrow produces the same fingerprints, so no checks are repaid.
- Corrections of matching are visible and auditable, never silent renumbering.

## Alternatives rejected
- **Fresh entities each run** — breaks fingerprints and verdict carry-over (the problem above).
- **Fingerprint by name string instead of entity** — brings back the exact-name bug (ADR 0004).
- **Never split once merged** — a wrong merge would corrupt reference checks forever.
