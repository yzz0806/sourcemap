# Stage 2 — Storage, starting content and identifier checks

**Status:** done, awaiting approval. Re-run: `.venv/bin/sourcemap seed --check-ids`, `.venv/bin/sourcemap ids --failed`.

## Goal
The database, the raw store, the polite fetch helper, a command that loads the hand-built starting
content into a fresh database, and **automatic checks that every seeded identifier is real**
(stage 3's known-answer benchmark uses these identifiers as its answers).

## What gets built
- `store`: SQLite schema as numbered migrations matching `docs/data-model.md`; WAL; foreign keys;
  content-addressed write-once raw store; job queue operations; run event log; spend ledger.
- `sandbox.kit` (moved here from stage 4): the polite fetch helper — robots.txt, per-host rate
  limit, back-off, raw bytes as served. Stage 4 adds the isolated child process around it.
- `sourcemap seed`: both data types, segment trees, panels (16 companies, 17 departments), known
  sources with tier, lineage and offers, adapter rows with allowed keys, and per unit: theorg slug,
  domain, LinkedIn company URL, DART corp code; OpenAlex institution id, ROR id, department page
  URL; leadership/people page URL where known.
- `sourcemap seed --check-ids`: one check per identifier, results in `identifier_check`:

| Identifier | Automatic check | Possible results |
|---|---|---|
| theorg slug | GET theorg.com/org/<slug>: 200 and the page title contains the company name | ok / mismatch / unreachable |
| LinkedIn company URL | format only (LinkedIn blocks automated fetches; a paid Apify check is not worth it here) | format_ok / bad_format |
| DART corp code | Open DART company API: the returned name matches | ok / mismatch / no_key |
| ROR id | api.ror.org: name matches the institution | ok / mismatch |
| OpenAlex institution id | api.openalex.org: same ROR id | ok / mismatch |
| people / leadership page URL | GET: 200 and the visible text contains the unit's name | ok / mismatch / unreachable / blocked_by_robots |

  Anything not `ok` (or `format_ok`) is listed for the user to fix or accept; stage 3's known-answer
  task uses **only identifiers that passed**.

## Order of work
Data-model doc check → migration, idempotency, raw-store and identifier-check tests (fake HTTP) →
code → `store.md`, `sandbox-and-adapters.md` updated → run the checks for real (free) → log,
commit, wait.

## How you check
1. Run seed on a fresh data directory, then again: the second run changes nothing.
2. Counts: 2 data types, 16 companies, 17 departments, the known sources; segments form a tree under "all".
3. `sourcemap seed --check-ids`: a table of every identifier and its result; every failure is
   listed with the reason. Spot-check one passing identifier in a browser.
4. Samsung Electronics and KAIST CS: right segment and all identifiers `ok` (DART `no_key` if the
   key isn't set yet).
5. Raw store: the same content stored twice gives one file. Queue: an expired lease is leased again.

## You need to provide
- `OPENDART_API_KEY` in `.env` (free) — otherwise DART codes show `no_key`.
- A decision on each failed identifier (fix the value, or drop it from the known-answer task).

## Cost
$0 (free APIs and public pages only).
