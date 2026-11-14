# Stage 2 — Storage and starting content

## Goal
The database, the raw store, and a command that loads the hand-built starting content into a fresh
database.

## What gets built (`src/sourcemap/store`)
- SQLite schema as numbered migrations, matching `docs/data-model.md`; WAL mode, foreign keys on.
- Content-addressed, write-once raw store.
- Job queue table operations (enqueue, lease, heartbeat, finish, fail) and the run event log.
- `sourcemap seed`: both data types (specs, claim types, record schemas v1), segment trees, panels
  (16 companies, 17 departments), known sources with tier, lineage (per claim type where it
  differs) and offers, adapter rows with their allowed keys.
- Real identifiers per probe unit: theorg slug, domain, LinkedIn company URL, DART corp code;
  OpenAlex institution id, ROR id, department page URL; leadership/people page URLs where known.

## Order of work
Data-model doc check → migration tests and seed idempotency tests → code → `store.md` updated →
checks, log, commit, wait.

## How you check
1. Run seed on a fresh data directory, then again: the second run changes nothing.
2. Counts: 2 data types, 16 companies, 17 departments, the known sources; segments form a tree under "all".
3. Samsung Electronics and KAIST CS: right segment, real identifiers (theorg slug, DART code,
   LinkedIn URL; OpenAlex id, ROR). Spot-check one in a browser.
4. Raw store: the same content stored twice gives one file.
5. Queue: a leased job whose lease expires is leased again.
