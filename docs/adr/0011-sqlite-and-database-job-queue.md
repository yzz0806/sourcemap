# 0011 — SQLite for all state; the job queue lives in the database; stages are idempotent

Status: proposed (stage 0, under review)

## Context
Two processes (API, worker) must share state and talk only through the database. A worker crash in
the middle of a stage must resume, not restart the run or pay twice. The data is small (tens of
thousands of claims).

## Decision
- One SQLite file in WAL mode; foreign keys on; schema changes by numbered migration files.
- Raw fetch bytes live in a content-addressed file store, not in SQLite.
- The queue is the `job` table. The worker leases a job with `UPDATE … WHERE status='queued' …
  RETURNING`, sets `lease_until`, and heartbeats. A job whose lease expired is re-leased on restart.
- Each job is one stage of one run. A stage reads its inputs from the database, writes results per
  unit of work (per probe unit, per claim batch) in its own transaction, and skips units whose
  results already exist for this run. So re-running a stage after a crash continues where it stopped
  and never repeats a paid call already recorded.
- Stages check for cancellation and remaining budget between units.
- Gates: a run waiting at a gate has status `waiting_gate`; the API records the decision; the worker
  sees it on its next tick and enqueues the next stage.

## Consequences
- No broker or extra service to run. The API keeps working with the worker down.
- One writer at a time is enough at this size; the worker runs stages one by one, with parallel
  network calls inside a stage.

## Alternatives rejected
- **Postgres** — more setup for no gain at this size; the brief says SQLite is enough.
- **Redis/Celery queue** — a second store and a second source of truth for run state.
- **In-memory run state in the worker** — lost on crash; the brief requires resumable stages.
