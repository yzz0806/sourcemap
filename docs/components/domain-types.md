# Domain types — `sourcemap.domain`

Plain, frozen dataclasses and enums using the vocabulary of `docs/domain.md`. No I/O, no logic
beyond validation. Everything else passes these around.

| Module | Contents (one line each) |
|---|---|
| `vocab.py` | `Tier`, `Subtype`, `Verdict` (`correct`/`wrong`/`stale`/`unverifiable`), `Method` (`reference`/`lookup`/`agreement`), `CoverageState`, `AccuracyState`, `HealthState`, `RunKind`, `RunMode`. |
| `spec.py` | `DataTypeSpec` (probe unit, record schema version, claim types, segment tree); `ClaimTypeSpec` (slug, value kind, expiry days, compare mode). |
| `units.py` | `ProbeUnit`, `Segment`, `Panel`. |
| `sources.py` | `Source` (tier, subtype, lineage, per-claim-type lineage, can-verify), `Offer`; `Source.lineage_for(claim_type) -> str`. |
| `records.py` | `RawFetchRef`, `Record`, `Mention`. |
| `claims.py` | `Claim` (subject entity, claim type, value, value_norm, source, unit), `Verification`. |
| `scores.py` | `Score`, `Interval`, `MapCell`, `Combo`. |
| `specs/org_chart.py`, `specs/academic_identity.py` | The two hand-written data type specs (record JSON schemas v1, claim extraction rules, segments, panels). |
