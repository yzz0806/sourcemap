# Store — `sourcemap.store`

The only code that talks to SQLite and the raw store. Used by the API (reads, gate decisions,
run requests) and the pipeline (everything else). Schema in `docs/data-model.md`.

| Module | Public functions (one line each) |
|---|---|
| `db.py` | `connect(path) -> Connection` — WAL mode, foreign keys on; `migrate(conn)` — apply `migrations/NNNN_*.sql` in order. |
| `rawstore.py` | `put(bytes) -> sha256` — write-once, content-addressed; `get(sha256) -> bytes`; `path_of(sha256)`. |
| `seed.py` | `seed(conn, specs, sources)` — load data types, segments, panels, sources, offers, adapters; idempotent. |
| `queue.py` | `enqueue_run(conn, kind, data_type, mode, as_of, budget) -> run_id`; `lease_job(conn, now) -> Job | None`; `finish_job`, `fail_job`, `heartbeat(job)`. |
| `events.py` | `log_event(conn, run_id, stage, level, message, data)`; `events_since(conn, run_id, after_id)`. |
| `spend.py` | `charge(conn, run_id, service, units, usd, ref)`; `remaining(conn, run_id) -> usd`. |
| `evidence.py` | `save_raw_fetch`, `save_record`, `save_mentions`, `upsert_claim` (by fingerprint), `add_verification`, `save_judge_call`, `cached_judge(model, prompt_version, input_hash)`. |
| `entities.py` | `save_match_result(conn, unit, result)`; `entities_for(conn, unit)`. |
| `scores.py` | `save_scores`, `save_map_snapshot`, `save_alerts`, `save_health`, `latest_map(data_type)`, `cell_history(source, segment, claim_type)`. |
| `trace.py` | `trace_cell(score_id) -> verifications`; `trace_verification(id) -> claim, raw fetches, judge call` (R10). |
| `gates.py` | `record_gate_decision(run_id, gate, decision, payload)`; `pending_gate(run_id)`. |
