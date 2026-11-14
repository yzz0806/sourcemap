# Domain types — `sourcemap.domain`

Plain, frozen dataclasses and enums using the vocabulary of `docs/domain.md`. No I/O, no logic
beyond small helpers. Everything else passes these around. Mappings are tuples of pairs so the
dataclasses stay frozen.

| Module | Contents (one line each) |
|---|---|
| `vocab.py` | `Tier` (1 official … 4 aggregate), `Subtype`, `Verdict` (+ `.decisive`), `Method` (+ `.strength`: reference 3 > lookup 2 > agreement 1), `CoverageState`, `AccuracyState`, `HealthState`, `ValueKind`, `CompareMode`, `RunKind`, `RunMode`. |
| `model.py` | `ClaimTypeSpec(slug, value_kind, expiry_days, compare, field)` — `field=None` is an existence claim; `DataTypeSpec(slug, name, spec_version, claim_types)` + `.claim_type(slug)`; `ProbeUnit`; `Source(id, slug, tier, subtype, lineage, lineage_by_claim)` + `.lineage_for(claim_type)` (ADR 0005); `Mention` + `.identifier(kind)`; `Claim`; `Verification(claim_id, method, verdict, decided_at, expires_at, weight, evidence, reason, excluded_reason)`; `Interval(lo, hi)` + `.overlaps()`; `Record(id, source_id, probe_unit_id, valid, payload)`. |
| `specs.py` | `ORG_CHART` (employment, title, reports_to), `ACADEMIC_IDENTITY` (exists, role, affiliation, email, profile_link), `ALL_SPECS`. Expiry days from ADR 0012. Segments, panels and sources are seed content (stage 2). |

A record's payload is `{"people": [{"ref", "name", "identifiers", <claim fields>…}]}`; the claim
type's `field` names the person field its value comes from (`title`, `manager_ref`, `role`, …).
