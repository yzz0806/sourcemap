# Data model

SQLite. This doc is the design; once code exists, the migration files under
`src/sourcemap/store/migrations/` are authoritative and this doc is kept in step with them.

Records of every data type share the same tables: the shape of a record lives in a versioned JSON
schema stored as data, not as columns (ADR 0001).

```mermaid
erDiagram
  data_type ||--o{ claim_type : defines
  data_type ||--o{ segment : has
  segment ||--o{ segment : parent
  segment ||--o{ panel_member : includes
  probe_unit ||--o{ panel_member : in
  data_type ||--o{ source : for
  source ||--o{ offer : claims
  segment ||--o{ offer : covered_by
  source ||--o{ adapter : read_by
  run ||--o{ job : stages
  run ||--o{ run_event : logs
  run ||--o{ gate_decision : waits_for
  run ||--o{ spend : charges
  raw_fetch }o--|| source : from
  raw_fetch }o--|| probe_unit : about
  record }o--|| raw_fetch : converted_from
  record ||--o{ mention : contains
  mention }o--|| entity : resolved_to
  match_decision }o--|| mention : pair
  record ||--o{ claim : yields
  claim }o--|| entity : subject
  claim ||--o{ verification : checked_by
  verification }o--o| raw_fetch : evidence
  verification }o--o| claim : reference_claim
  verification }o--o| judge_call : decided_by
  score }o--|| run : in
  run ||--o| map_snapshot : draws
  entity ||--o{ assembled_value : has
  assembled_value }o--|| claim : chosen
```

## Definitions (setup content)

| Table | Key columns | Notes |
|---|---|---|
| `data_type` | id, slug, name, spec_version, spec_json | `spec_json`: probe unit definition, record JSON schema, claim extraction rules. |
| `claim_type` | id, data_type_id, slug, value_kind (`bool`/`text`/`entity`/`url`/`email`), expiry_days, compare (`exact`/`normalised`/`judge`) | `reports_to` has value_kind `entity`. |
| `segment` | id, data_type_id, parent_id, slug, name, criteria | A tree; each data type has a root `all`. |
| `probe_unit` | id, data_type_id, slug, name, identifiers_json | e.g. `{"theorg":"airtable","domain":"airtable.com","linkedin":"…","dart_corp_code":"…"}`; `{"openalex_institution":"I…","ror":"…","dept_url":"…"}`. |
| `panel_member` | segment_id, probe_unit_id | |
| `source` | id, data_type_id, slug, name, url, tier, subtype, lineage, lineage_by_claim_json, access, status (`proposed`/`approved`/`rejected`/`retired`), can_verify_json, found_by_json | `found_by_json`: which search provider and query found it (discovery provenance). |
| `offer` | source_id, segment_id, state (`hypothesis`/`measured`) | |
| `adapter` | id, source_id, version, module, keys_json, supports_lookup, status | Hand-written in the demo; `keys_json` lists the only env keys the child receives. |

## Runs and jobs

| Table | Key columns | Notes |
|---|---|---|
| `run` | id, data_type_id, kind (`setup`/`maintenance`/`discovery`), mode (`test`/`real`), as_of, budget_usd, spent_usd, status (`queued`/`running`/`waiting_gate`/`done`/`failed`/`cancelled`/`out_of_budget`), settings_json, created_at | `as_of` is the run's clock (real or simulated). |
| `job` | id, run_id, stage, seq, status (`queued`/`running`/`done`/`failed`), lease_until, attempts, error, started_at, finished_at | The queue. A stage is idempotent; restart re-runs it and skips work already stored. |
| `gate_decision` | id, run_id, gate (`B`/`D`), decision (`approve`/`reject`), payload_json, note, decided_at | Written by the API. |
| `run_event` | id, run_id, at, level, stage, message, data_json | The live log. |
| `spend` | id, run_id, service, units, usd, ref, at | Every paid call; `run.spent_usd` is their sum. |
| `agent_session` | id, run_id, purpose, cost_usd, turns, status, output_json | Capped by count per run. |
| `schedule` | id, data_type_id, kind, cron, enabled | Created on publish. |

## Evidence chain

| Table | Key columns | Notes |
|---|---|---|
| `raw_fetch` | id, run_id, source_id, probe_unit_id, kind (`probe`/`lookup`), request_json, url, status_code, content_type, sha256, size, fetched_at, error | Bytes in the raw store at `sha256`. Never updated. |
| `record` | id, raw_fetch_ids_json, source_id, probe_unit_id, run_id, schema_version, payload_json, valid, errors_json | One source's converted answer for one probe unit in one run. |
| `mention` | id, record_id, local_ref, name, name_norm, identifiers_json, attrs_json | One person inside one record. |
| `entity` | id, data_type_id, probe_unit_id, display_name, created_run_id | |
| `mention_entity` | mention_id, entity_id, method (`identifier`/`rule`/`judge`), match_decision_id | |
| `match_decision` | id, mention_a_id, mention_b_id, decision (`same`/`different`), method, reason, judge_call_id | `different` is a cannot-link constraint. |
| `claim` | id, data_type_id, source_id, probe_unit_id, claim_type_id, subject_entity_id, object_entity_id, value_json, value_norm, fingerprint, first_record_id, first_seen_run_id, last_seen_run_id | `fingerprint` = (source, unit, subject entity, claim type, value_norm). An unchanged claim keeps its row across runs; a changed value is a new claim. |
| `claim_record` | claim_id, record_id | Which records stated the claim (all runs). |
| `verification` | id, claim_id, run_id, method (`reference`/`lookup`/`agreement`), verdict (`correct`/`wrong`/`stale`/`unverifiable`), weight, evidence_raw_fetch_id, reference_claim_id, judge_call_id, quote, reason, decided_at, expires_at | Never updated; a re-check adds a new row. The current verdict of a claim is the strongest unexpired one (R7). |
| `judge_call` | id, model, prompt_version, input_hash, input_json, output_json, usd, created_at | Also the judge cache. |

## Scores and map

| Table | Key columns | Notes |
|---|---|---|
| `source_health` | run_id, source_id, state (`ok`/`degraded`/`broken`/`shape_changed`/`changed`), details_json | |
| `score` | id, run_id, source_id, segment_id, claim_type_id, coverage_state (`measured`/`not_probed`/`failed`), units_covered, units_panel, entities, n_correct, n_wrong, n_stale, n_unverifiable, n_decisive, prior_a, prior_b, post_a, post_b, mean, lo90, hi90, accuracy_state (`measured`/`not_enough_data`/`unmeasured`), gate_json, freshness_days | One row per cell per run: the history. |
| `map_snapshot` | id, run_id, data_type_id, created_at, combos_json, gaps_json | Best combination of up to 3 sources per segment and gap flags. |
| `alert` | id, run_id, kind (`drift`/`broken`/`shape_changed`), source_id, segment_id, claim_type_id, details_json | |
| `score_verification` | score_id, verification_id | The exact verdicts a score used — makes R10 a join, not a re-computation. |

## Assembly

| Table | Key columns | Notes |
|---|---|---|
| `assembled_value` | id, run_id, entity_id, claim_type_id, chosen_claim_id, alternatives_json, reason_json | `reason_json`: e.g. `{"winner":"company:gong.io","acc":0.92,"loser":"theorg","acc":0.71,"segment":"na_mid"}`. |

## The trace (R10)

`score` → `score_verification` → `verification` → `claim` (→ `claim_record` → `record` →
`raw_fetch` of the claim) and `verification.evidence_raw_fetch_id` / `reference_claim_id` (the
evidence). All links are foreign keys.
