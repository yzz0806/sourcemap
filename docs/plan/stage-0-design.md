# Stage 0 — Design on paper

**Status:** done (commits `08dd90b`, `b1c3a78`), awaiting approval.

## Goal
Turn the brief into a design the user agrees with, before any code.

## What gets built
- `docs/domain.md` — problem, vocabulary, both data types, the pipeline steps, the 10 accuracy
  rules with examples, ground truth without humans, matching, drift, money.
- `docs/containers.md` — API, worker, adapter child, SQLite, raw store, outside services.
- `docs/data-model.md` — every table, with the trace from score to evidence.
- `docs/components/` — one doc per part, planned functions, layering contracts.
- ADRs 0001–0016 (0015: search-provider benchmark, 0016: change monitor); README skeleton;
  `.gitignore`; this plan.

## How you check
1. Read `docs/domain.md` without the brief open: can a new teammate follow the steps and the 10 rules?
2. Container diagram: only the worker touches the internet, models or money; API and worker share only the database.
3. Trace questions — each answer names concrete tables and steps:
   - "theorg says Howie Liu is CEO of Airtable. Where is that stored, and how does it become an accuracy number?"
   - "Which verifier checks a theorg title, and why can't LinkedIn check a ZoomInfo title?"
   - "The worker crashes in the middle of verify. What happens on restart?"
   - "An adapter loops forever. What stops it?"
   - "A new data type is added. How do its records fit without a schema change?"
4. Every ADR lists rejected alternatives.
5. The data model has raw fetches, records, claims, verifications with evidence, scores over time,
   map snapshots, runs, jobs, gate decisions and the run event log.

## On approval
ADRs 0001–0016 change from *proposed* to *accepted*; after that they are only superseded.
