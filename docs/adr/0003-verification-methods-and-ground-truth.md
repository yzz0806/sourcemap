# 0003 — How claims are verified: reference, lookup + judge, agreement; never web search; no human gold set

Status: accepted (stage 0)

## Context
Accuracy needs something to compare against. Options were a human-labelled gold set, reference
sources, lookups in independent sources, agreement between sources, and web search. The user
decided against hand-labelling: ground truth must come from sources, automatically. Web search
results look like evidence but are third-party summaries that change and cannot be stored as what
a named source said.

## Decision
- Three methods, strongest first, each stored on the verification row:
  1. **reference** — the same entity's claim from a tier-1 or tier-2 source of a different lineage
     (DART for Korean executives; company leadership pages; university directories).
  2. **lookup** — the subject is looked up in a verifier source of a different lineage (LinkedIn via
     Apify; OpenAlex/ORCID for academics); the response is saved as a raw fetch; the judge decides
     `correct`/`wrong`/`stale`/`unverifiable` and quotes the part of the evidence it used.
  3. **agreement** — a source of a different lineage states the same value for the same entity.
- **Web search is never evidence**, and neither is Telem fetch output (a markdown rendering).
  Evidence is always a raw fetch from a named source.
- Lookups are sampled where intervals are widest, within the run budget; a claim with a valid
  verdict is not looked up again until it is due for re-check.
- Tier-1 sources are spot-checked by lookup each run (R9).
- **No human gold set.** Instead, the automated parts are measured another way and shown:
  - Judge: a fixed easy-case suite (identical titles, known translations such as 대표이사 = CEO,
    clearly different names) must pass 100% before a run uses a judge model or prompt version; a
    second model from a different family re-judges a sample each run, and the agreement rate is
    shown. The UI states "judge error: not measured against humans".
  - Matching: scored on pairs whose answer is known from shared identifiers (ADR 0004).
- Where no verifier exists for a claim type in a segment (e.g. `reports_to` almost everywhere),
  verdicts are `unverifiable` and the cell shows "unmeasured — no verifier".

## Consequences
- Every verdict has a stored artefact a person can open.
- Accuracy is relative to the best available reference, and the map says which method decided
  each verdict, so a reader can discount weaker ones.
- The judge's true error rate against humans is unknown; this is stated, not hidden. A gold set can
  be added later as a fourth, strongest method without changing the tables (method `gold`).

## Alternatives rejected
- **Human gold set of ~50 people** — the strongest anchor, but the user chose not to spend the
  labelling time. Can be added later.
- **Web search to confirm claims** — not reproducible, not a named source, often itself copied from
  the source under test.
- **Majority vote of all sources** — copies would outvote the truth; lineage would be ignored.
