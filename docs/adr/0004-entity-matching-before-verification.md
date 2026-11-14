# 0004 — Match mentions into entities before verifying, by rules first and the judge for borderline pairs

Status: accepted (stage 0)

## Context
The same person appears as "J. Smith" on theorg and "Jane Smith" on gong.io, or as "박형관" in DART
and "Hyung-Kwan Park" on LinkedIn. The earlier implementation matched by exact normalised name
during checking, so the same person under two spellings was never compared, coverage counted
duplicates, and reference checks silently failed.

## Decision
- Matching runs as its own stage **after probe and before verify**. Claims point at an entity, and
  verification pairs claims by entity, never by name string.
- Matching happens only within one probe unit.
- Order of decisions:
  1. Shared identifier (LinkedIn URL, ORCID iD, OpenAlex author id) → same.
  2. Identical normalised names (fold, strip accents/honorifics/suffixes, reorder "Last, First",
     sort tokens) → same.
  3. Clearly different (both given names fully spelled and different; or different surnames in the
     same script) → different.
  4. Everything else — initials, different scripts, nicknames — goes to the judge with both mentions'
     titles as context.
- A `different` decision is a cannot-link constraint: union–find never joins two groups that contain
  a cannot-link pair, even through a third mention.
- Decisions are stored (`match_decision`) and reused in later runs.
- Quality is measured on identifier-known pairs: the matcher is run again without the identifier,
  and false merges and missed merges are reported on the map page.

## Consequences
- Coverage of source combinations counts unique entities.
- Judge cost scales with borderline pairs only.
- Cross-script names (Korean) depend on the judge; this is visible in the matching quality numbers.

## Alternatives rejected
- **Exact normalised name only** — the known bug: misses "J. Smith" / "Jane Smith".
- **Fuzzy string similarity threshold** — merges "Jon Smith" and "John Smith" (two people) as easily
  as it merges true variants; no principled threshold.
- **Judge every pair** — quadratic cost per company for no gain on the easy majority.
- **Match only at assembly time** — too late: coverage and accuracy would already be wrong.
