# Store — `sourcemap.store`

The only code that talks to SQLite and the raw store. Used by the API (reads, gate decisions,
run requests) and the pipeline (everything else). Schema: `store/migrations/0001_init.sql`
(authoritative), described in `docs/data-model.md`. Seed content: `seeds/*.json`.

| Module | Public functions (one line each) |
|---|---|
| `db.py` | `connect(path) -> Connection` — WAL, foreign keys on, autocommit with explicit transactions, rows as `sqlite3.Row`; `migrate(conn) -> [versions]` — apply `migrations/NNNN_*.sql` not yet in `schema_migration`. |
| `rawstore.py` | `RawStore(root)`: `put(bytes) -> sha256` — write-once, content-addressed at `ab/cd/<sha256>`, read-only file; `get(sha256) -> bytes`; `path_of(sha256)`. |
| `seed.py` | `load_seed_files(seeds_dir, units_file=None) -> dict`; `seed(conn, specs, data)` — upsert data types, claim types, segment tree, units (one leaf segment each), sources, offers, adapters; idempotent. |
| `queue.py` | `enqueue_run(conn, data_type, kind, mode, as_of, budget_usd, stages, *, now, settings, scenario) -> run_id`; `lease_job(conn, *, now, lease_s=300) -> Job | None` — stages of a run in order, expired leases re-leased; `heartbeat`, `finish_job` (last job → run done), `fail_job` (run failed). |
| `events.py` | `log_event(conn, run_id, message, *, now, stage, level, data)`; `events_since(conn, run_id, after_id)`. |
| `spend.py` | `charge(conn, run_id, service, usd, *, now, units, ref)`; `remaining(conn, run_id) -> usd`. |

Planned for later stages: `evidence.py`, `entities.py`, `scores.py`, `trace.py`, `gates.py`
(see the stage files in `docs/plan/`).
