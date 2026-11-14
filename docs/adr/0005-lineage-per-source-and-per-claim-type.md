# 0005 — Lineage is recorded per source, with per-claim-type overrides

Status: accepted (stage 0)

## Context
R4: same lineage never verifies itself. Usually lineage is a property of a source (ZoomInfo and
Apollo are `linkedin`). But some sources share lineage for one claim type and not another:
OpenAlex uses ORCID iDs to tell authors apart (shared for `profile_link`), while its affiliations
come from papers and ORCID's from the person (independent for `affiliation`).

## Decision
- `source.lineage` is the default lineage; `source.lineage_by_claim_json` overrides it per claim type.
- `measure.verdicts.allowed_verifier(source, verifier, claim_type)` compares
  `lineage_for(claim_type)` of both and refuses equal lineages. Every verify path goes through it.
- First-party lineages are per domain (`company:gong.io`, `university:purdue.edu`), so two
  companies' pages are different lineages, but a company page never verifies itself.
- Agreement between same-lineage sources is ignored, and agreement among several copies counts once.
- Discovery must state lineage on every source card; a person checks it at gate B.

## Consequences
- The OpenAlex/ORCID pair can verify each other's affiliations but not profile links.
- A wrongly stated lineage inflates accuracy; it is visible on the source page and at gate B.

## Alternatives rejected
- **Lineage per source only** — would forbid OpenAlex ↔ ORCID affiliation checks entirely, or allow
  the circular profile-link check.
- **Infer lineage automatically from overlap** — high overlap can mean either copying or both
  being right; it can't tell the two apart.
