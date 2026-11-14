# API and web UI — `sourcemap.api`, `web/`

The API serves the built React UI and JSON endpoints. It reads the database and raw store, and
writes only gate decisions and run requests. It works with the worker stopped.

| Module | Public functions (one line each) |
|---|---|
| `api/app.py` | `create_app(settings) -> FastAPI` — mount routes and the built UI; opens the real database by default and a simulation copy only with `?db=sim:<scenario>`, adding a `simulation` flag to every response (ADR 0014). |
| `api/routes_catalog.py` | `GET /api/data-types` — data types with last run and map summary. |
| `api/routes_map.py` | `GET /api/map/{data_type}?claim_type&run` — cells for one claim type at a run (time slider); `GET /api/cells/{score_id}` — the checks behind a cell; `GET /api/cells/history` — one cell over runs. |
| `api/routes_trace.py` | `GET /api/verifications/{id}` — claim, verdict, method, reason, quote, links; `GET /api/raw/{raw_fetch_id}` — the raw bytes with their content type. |
| `api/routes_sources.py` | `GET /api/sources/{id}` — tier, lineage, offers, health history, scores. |
| `api/routes_runs.py` | `POST /api/runs` — enqueue; `GET /api/runs/{id}` and `/events?after=` — live console; `POST /api/runs/{id}/gates/{gate}` — approve/reject. |
| `api/routes_benchmark.py` | `GET /api/benchmark/{run}` — leaderboard per provider and segment; `GET /api/benchmark/{run}/candidates?blind=1` — pooled candidates for gate B without provider names; `GET /api/monitor` — news hits, triggered re-checks and their outcomes. |
| `api/routes_assembled.py` | `GET /api/assembled/{data_type}` — entities with chosen values, origin and reason; `GET …/export.csv`. |

## Pages (`web/`, React + Vite)

| Page | Shows |
|---|---|
| Catalog | Data types, last run, gaps. |
| Map | Heatmap segments × sources per claim type: coverage and accuracy interval with n; "not enough data" / "unmeasured" / "not probed" / "failed" as distinct states; judge calibration banner; time slider. |
| Cell | Checks behind a cell, labelled by method → verification → raw fetch (≤ 3 clicks from the map). |
| Source | Tier, lineage, offers, health over runs. |
| Run console | Live events, spend, gate approvals. |
| Assembled data | One row per entity; each value with origin and "why this source won"; CSV export. |
| History | Per cell coverage and accuracy over runs, breakages and drift alerts marked. |
| Provider leaderboard | Per provider and segment: precision, pooled recall, known-source recall, exclusive finds, cost per good find, latency, with intervals; the pooled-recall limit stated; click a provider → the candidates it found. |
| Blind review (gate B) | Pooled candidates without provider names; keep / reject. |
| Monitor | News hits → matched person → triggered re-check → verdict; raw counts, "too few to measure". |
| Any page, simulation open | Permanent "SIMULATION — <scenario>" banner; CSV export disabled. |
