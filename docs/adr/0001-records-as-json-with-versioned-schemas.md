# 0001 — Records of any data type are stored as JSON with versioned schemas

Status: accepted (stage 0, approved by the user 2026-11-14)

## Context
sourcemap must hold org charts, academic identities, and data types users create later. The brief
fixes that adding a data type never changes the database schema, and that an agent never changes
it. Org-chart records (people, titles, managers) and academic records (people, roles, emails,
profile links) have different shapes.

## Decision
- A data type's spec (`data_type.spec_json`) holds a **versioned JSON schema** for one record and
  the rules that pull claims out of it.
- `record.payload_json` stores one source's converted answer, validated against the schema
  version named in `record.schema_version`. Invalid records are stored with `valid = 0` and their
  errors, so health can see them.
- Everything that is scored is normalised into fixed tables: `mention`, `claim` (value in
  `value_json` + `value_norm`), `verification`. These have the same columns for every data type.
- Claim types are rows (`claim_type`), not columns.

## Consequences
- A new data type is new rows, never a migration.
- Queries over claims are uniform; queries inside record payloads use SQLite JSON functions and are
  only for display.
- Schema changes for a data type are a new spec version; old records keep the version they were
  written with.

## Alternatives rejected
- **One table per data type** — every new data type would need a migration, which the brief forbids.
- **Entity–attribute–value for everything, no record payload** — loses the source's answer as a
  whole, which the drill-down needs, and makes validation harder.
- **A document database** — a second store to run for no gain at this size; SQLite JSON is enough.
