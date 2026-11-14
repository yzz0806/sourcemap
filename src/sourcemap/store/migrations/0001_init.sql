-- 0001 — initial schema. Implements docs/data-model.md (ADR 0001, 0011, 0013, 0014, 0015, 0016).
-- Records of every data type share these tables; a new data type is rows, never a migration.

-- Definitions ------------------------------------------------------------------------------------

CREATE TABLE data_type (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  spec_version INTEGER NOT NULL,
  spec_json TEXT NOT NULL,
  published INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE claim_type (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  slug TEXT NOT NULL,
  value_kind TEXT NOT NULL,
  expiry_days INTEGER NOT NULL,
  compare TEXT NOT NULL,
  field TEXT,
  UNIQUE (data_type_id, slug)
);

CREATE TABLE segment (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  parent_id INTEGER REFERENCES segment(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  criteria TEXT NOT NULL DEFAULT '',
  UNIQUE (data_type_id, slug)
);

CREATE TABLE probe_unit (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  identifiers_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (data_type_id, slug)
);

CREATE TABLE panel_member (
  segment_id INTEGER NOT NULL REFERENCES segment(id),
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  PRIMARY KEY (segment_id, probe_unit_id)
);

CREATE TABLE identifier_check (
  id INTEGER PRIMARY KEY,
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  kind TEXT NOT NULL,
  value TEXT,
  result TEXT NOT NULL CHECK (result IN
    ('ok','format_ok','mismatch','unreachable','blocked_by_robots','bad_format','no_key','missing')),
  detail TEXT NOT NULL DEFAULT '',
  checked_at TEXT NOT NULL
);

CREATE TABLE source (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL DEFAULT '',
  tier INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 4),
  subtype TEXT NOT NULL,
  lineage TEXT NOT NULL,
  lineage_by_claim_json TEXT NOT NULL DEFAULT '{}',
  access TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'approved' CHECK (status IN ('proposed','approved','rejected','retired')),
  can_verify_json TEXT NOT NULL DEFAULT '[]',
  found_by_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (data_type_id, slug)
);

CREATE TABLE offer (
  source_id INTEGER NOT NULL REFERENCES source(id),
  segment_id INTEGER NOT NULL REFERENCES segment(id),
  state TEXT NOT NULL DEFAULT 'hypothesis' CHECK (state IN ('hypothesis','measured')),
  PRIMARY KEY (source_id, segment_id)
);

CREATE TABLE adapter (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES source(id),
  version INTEGER NOT NULL DEFAULT 1,
  module TEXT NOT NULL,
  keys_json TEXT NOT NULL DEFAULT '[]',
  supports_lookup INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','failed','retired')),
  UNIQUE (source_id, version)
);

-- Runs and jobs (ADR 0011) ---------------------------------------------------------------------------

CREATE TABLE run (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  kind TEXT NOT NULL CHECK (kind IN ('setup','maintenance','discovery','benchmark')),
  mode TEXT NOT NULL CHECK (mode IN ('test','real')),
  as_of TEXT NOT NULL,
  scenario TEXT,
  budget_usd REAL NOT NULL,
  spent_usd REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN
    ('queued','running','waiting_gate','done','failed','cancelled','out_of_budget')),
  settings_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE job (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  stage TEXT NOT NULL,
  seq INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
  lease_until TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE (run_id, seq)
);
CREATE INDEX job_status ON job(status, lease_until);

CREATE TABLE gate_decision (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  gate TEXT NOT NULL CHECK (gate IN ('B','D')),
  decision TEXT NOT NULL CHECK (decision IN ('approve','reject')),
  payload_json TEXT NOT NULL DEFAULT '{}',
  note TEXT NOT NULL DEFAULT '',
  decided_at TEXT NOT NULL
);

CREATE TABLE run_event (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  at TEXT NOT NULL,
  level TEXT NOT NULL,
  stage TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE spend (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  service TEXT NOT NULL,
  units REAL NOT NULL DEFAULT 1,
  usd REAL NOT NULL,
  ref TEXT NOT NULL DEFAULT '',
  at TEXT NOT NULL
);

CREATE TABLE agent_session (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  purpose TEXT NOT NULL,
  cost_usd REAL NOT NULL DEFAULT 0,
  turns INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  output_json TEXT
);

CREATE TABLE schedule (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  kind TEXT NOT NULL CHECK (kind IN ('maintenance')),
  cron TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1
);

-- Evidence chain ----------------------------------------------------------------------------------

CREATE TABLE judge_call (
  id INTEGER PRIMARY KEY,
  model TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  input_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  usd REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE (model, prompt_version, input_hash)
);

CREATE TABLE raw_fetch (
  id INTEGER PRIMARY KEY,
  run_id INTEGER REFERENCES run(id),
  source_id INTEGER REFERENCES source(id),
  probe_unit_id INTEGER REFERENCES probe_unit(id),
  kind TEXT NOT NULL CHECK (kind IN ('probe','lookup')),
  request_json TEXT NOT NULL DEFAULT '{}',
  url TEXT NOT NULL,
  status_code INTEGER,
  content_type TEXT NOT NULL DEFAULT '',
  sha256 TEXT,
  size INTEGER NOT NULL DEFAULT 0,
  fetched_at TEXT NOT NULL,
  error TEXT,
  simulated INTEGER NOT NULL DEFAULT 0,
  derived_from_raw_fetch_id INTEGER REFERENCES raw_fetch(id),
  sim_patch_json TEXT
);

CREATE TABLE record (
  id INTEGER PRIMARY KEY,
  raw_fetch_ids_json TEXT NOT NULL,
  source_id INTEGER NOT NULL REFERENCES source(id),
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  run_id INTEGER NOT NULL REFERENCES run(id),
  schema_version INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  valid INTEGER NOT NULL,
  errors_json TEXT NOT NULL DEFAULT '[]',
  extracted_by_judge_call_id INTEGER REFERENCES judge_call(id)
);

CREATE TABLE mention (
  id INTEGER PRIMARY KEY,
  record_id INTEGER NOT NULL REFERENCES record(id),
  local_ref TEXT,
  name TEXT NOT NULL,
  name_norm TEXT NOT NULL,
  identifiers_json TEXT NOT NULL DEFAULT '{}',
  attrs_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE entity (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  display_name TEXT NOT NULL,
  created_run_id INTEGER REFERENCES run(id),
  merged_into_id INTEGER REFERENCES entity(id)
);

CREATE TABLE match_decision (
  id INTEGER PRIMARY KEY,
  mention_a_id INTEGER NOT NULL REFERENCES mention(id),
  mention_b_id INTEGER NOT NULL REFERENCES mention(id),
  decision TEXT NOT NULL CHECK (decision IN ('same','different')),
  method TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  judge_call_id INTEGER REFERENCES judge_call(id)
);

CREATE TABLE mention_entity (
  mention_id INTEGER PRIMARY KEY REFERENCES mention(id),
  entity_id INTEGER NOT NULL REFERENCES entity(id),
  method TEXT NOT NULL CHECK (method IN ('identifier','local_ref','rule','judge')),
  match_decision_id INTEGER REFERENCES match_decision(id)
);

CREATE TABLE entity_event (
  id INTEGER PRIMARY KEY,
  run_id INTEGER REFERENCES run(id),
  kind TEXT NOT NULL CHECK (kind IN ('create','merge','split')),
  entity_id INTEGER NOT NULL REFERENCES entity(id),
  other_entity_id INTEGER REFERENCES entity(id),
  mention_ids_json TEXT NOT NULL DEFAULT '[]',
  reason TEXT NOT NULL DEFAULT '',
  match_decision_id INTEGER REFERENCES match_decision(id)
);

CREATE TABLE claim (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  claim_type_id INTEGER NOT NULL REFERENCES claim_type(id),
  subject_entity_id INTEGER NOT NULL REFERENCES entity(id),
  object_entity_id INTEGER REFERENCES entity(id),
  value_json TEXT NOT NULL,
  value_norm TEXT NOT NULL,
  fingerprint TEXT NOT NULL UNIQUE,
  first_record_id INTEGER NOT NULL REFERENCES record(id),
  first_seen_run_id INTEGER NOT NULL REFERENCES run(id),
  last_seen_run_id INTEGER NOT NULL REFERENCES run(id)
);

CREATE TABLE claim_record (
  claim_id INTEGER NOT NULL REFERENCES claim(id),
  record_id INTEGER NOT NULL REFERENCES record(id),
  PRIMARY KEY (claim_id, record_id)
);

CREATE TABLE monitor_hit (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  hit_id INTEGER NOT NULL REFERENCES search_hit(id),  -- a trigger for re-checks, never evidence
  matched_entity_id INTEGER REFERENCES entity(id),
  recheck_claim_ids_json TEXT NOT NULL DEFAULT '[]'
);

-- No column here references search_hit: search results are never evidence (R2).
CREATE TABLE verification (
  id INTEGER PRIMARY KEY,
  claim_id INTEGER NOT NULL REFERENCES claim(id),
  run_id INTEGER NOT NULL REFERENCES run(id),
  method TEXT NOT NULL CHECK (method IN ('reference','lookup','agreement')),
  verdict TEXT NOT NULL CHECK (verdict IN ('correct','wrong','stale','unverifiable')),
  weight REAL NOT NULL,
  evidence_raw_fetch_id INTEGER REFERENCES raw_fetch(id),
  reference_claim_id INTEGER REFERENCES claim(id),
  judge_call_id INTEGER REFERENCES judge_call(id),
  quote TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  decided_at TEXT NOT NULL,
  expires_at TEXT,
  trigger_monitor_hit_id INTEGER REFERENCES monitor_hit(id)
);

-- Scores and map -----------------------------------------------------------------------------------

CREATE TABLE source_health (
  run_id INTEGER NOT NULL REFERENCES run(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  state TEXT NOT NULL CHECK (state IN ('ok','degraded','broken','shape_changed','changed')),
  details_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (run_id, source_id)
);

CREATE TABLE score (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  source_id INTEGER NOT NULL REFERENCES source(id),
  segment_id INTEGER NOT NULL REFERENCES segment(id),
  claim_type_id INTEGER NOT NULL REFERENCES claim_type(id),
  coverage_state TEXT NOT NULL CHECK (coverage_state IN ('measured','not_probed','failed')),
  coverage_reason TEXT,
  units_covered INTEGER NOT NULL DEFAULT 0,
  units_panel INTEGER NOT NULL DEFAULT 0,
  units_failed INTEGER NOT NULL DEFAULT 0,
  units_not_fetched INTEGER NOT NULL DEFAULT 0,
  entities INTEGER NOT NULL DEFAULT 0,
  n_correct INTEGER NOT NULL DEFAULT 0,
  n_wrong INTEGER NOT NULL DEFAULT 0,
  n_stale INTEGER NOT NULL DEFAULT 0,
  n_unverifiable INTEGER NOT NULL DEFAULT 0,
  n_decisive INTEGER NOT NULL DEFAULT 0,
  n_weighted REAL NOT NULL DEFAULT 0,
  prior_a REAL NOT NULL, prior_b REAL NOT NULL,
  post_a REAL NOT NULL, post_b REAL NOT NULL,
  mean REAL, lo90 REAL, hi90 REAL,
  accuracy_state TEXT NOT NULL CHECK (accuracy_state IN ('measured','not_enough_data','unmeasured')),
  gate_json TEXT NOT NULL DEFAULT '{}',
  freshness_days REAL,
  UNIQUE (run_id, source_id, segment_id, claim_type_id)
);

CREATE TABLE score_verification (
  score_id INTEGER NOT NULL REFERENCES score(id),
  verification_id INTEGER NOT NULL REFERENCES verification(id),
  PRIMARY KEY (score_id, verification_id)
);

CREATE TABLE map_snapshot (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL UNIQUE REFERENCES run(id),
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  created_at TEXT NOT NULL,
  combos_json TEXT NOT NULL DEFAULT '{}',
  gaps_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE alert (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  kind TEXT NOT NULL CHECK (kind IN ('drift','broken','shape_changed')),
  source_id INTEGER REFERENCES source(id),
  segment_id INTEGER REFERENCES segment(id),
  claim_type_id INTEGER REFERENCES claim_type(id),
  details_json TEXT NOT NULL DEFAULT '{}'
);

-- Search: benchmark and monitor (ADR 0015, 0016) -------------------------------------------------------

CREATE TABLE search_query (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  segment_id INTEGER REFERENCES segment(id),
  probe_unit_id INTEGER REFERENCES probe_unit(id),
  category TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  purpose TEXT NOT NULL CHECK (purpose IN ('discovery','benchmark','known_answer','monitor','people_page'))
);

CREATE TABLE search_call (
  id INTEGER PRIMARY KEY,
  query_id INTEGER NOT NULL REFERENCES search_query(id),
  provider TEXT NOT NULL,
  routing TEXT NOT NULL CHECK (routing IN ('pinned','auto')),
  num_results INTEGER NOT NULL,
  status TEXT NOT NULL,
  usd REAL NOT NULL DEFAULT 0,
  latency_ms INTEGER,
  at TEXT NOT NULL
);

CREATE TABLE source_candidate (
  id INTEGER PRIMARY KEY,
  data_type_id INTEGER NOT NULL REFERENCES data_type(id),
  run_id INTEGER NOT NULL REFERENCES run(id),
  domain TEXT NOT NULL,
  url_prefix TEXT NOT NULL,
  known_source_id INTEGER REFERENCES source(id),
  in_review_sample INTEGER NOT NULL DEFAULT 0,
  review TEXT NOT NULL DEFAULT 'pending' CHECK (review IN ('keep','reject','pending','not_sampled')),
  reviewed_blind INTEGER NOT NULL DEFAULT 1,
  source_id INTEGER REFERENCES source(id),
  UNIQUE (run_id, url_prefix)
);

CREATE TABLE search_hit (
  id INTEGER PRIMARY KEY,
  call_id INTEGER NOT NULL REFERENCES search_call(id),
  rank INTEGER NOT NULL,
  url TEXT NOT NULL,
  domain TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  snippet TEXT NOT NULL DEFAULT '',
  candidate_id INTEGER REFERENCES source_candidate(id)
);

CREATE TABLE known_answer_trial (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  probe_unit_id INTEGER NOT NULL REFERENCES probe_unit(id),
  target TEXT NOT NULL CHECK (target IN ('theorg','linkedin','ror','people_page')),
  query_id INTEGER NOT NULL REFERENCES search_query(id),
  provider TEXT NOT NULL,
  expected_url TEXT NOT NULL,
  found_rank INTEGER,
  hit INTEGER NOT NULL
);

CREATE TABLE benchmark_result (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  provider TEXT NOT NULL,
  segment_id INTEGER REFERENCES segment(id),
  metric TEXT NOT NULL CHECK (metric IN ('known_hit_rate','known_mrr','precision','pooled_recall',
    'known_recall','exclusive','usd_per_good_find','latency_ms')),
  num REAL, den REAL, mean REAL, lo90 REAL, hi90 REAL,
  state TEXT NOT NULL
);

-- Assembly ---------------------------------------------------------------------------------------------

CREATE TABLE assembled_value (
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES run(id),
  entity_id INTEGER NOT NULL REFERENCES entity(id),
  claim_type_id INTEGER NOT NULL REFERENCES claim_type(id),
  chosen_claim_id INTEGER NOT NULL REFERENCES claim(id),
  alternatives_json TEXT NOT NULL DEFAULT '[]',
  reason_json TEXT NOT NULL DEFAULT '{}'
);
