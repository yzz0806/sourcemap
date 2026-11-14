# Session log

## 2026-11-14 — Stage 0: design on paper

**Built:** docs only, no code. `docs/domain.md`, `docs/containers.md`, `docs/data-model.md`,
`docs/components/` (8 docs + layering), ADRs 0001–0012, README skeleton, `.gitignore`.

**Scope decided with the user** (differs from the reference `DEMO.md`):
- Both data types (org chart + academic identity) and all 4 org-chart segments incl. Korean listed
  → DART is in scope.
- **No human-labelled gold set.** Ground truth from reference sources, cross-lineage lookups and
  agreement (ADR 0003). Judge error is estimated with an easy-case suite and a second-family judge;
  the UI says it is not measured against humans.
- Telem for search (not Tavily) (ADR 0010).
- Stages follow `PLAN.md` (0–9) adapted to this scope; agents limited to discovery; first-party pages
  extracted by a judge call (ADR 0006).

**Reference material** (read-only, not in this repo): `../../sourcemap/rebuild/{BRIEF,PLAN,DEMO,CLAUDE}.md`.

**Open items:**
- Open DART API key — user is getting it. Without it the Korean segment's DART cells are "not probed".
- Telem request/response details (provider names, `usage` field) to confirm against its docs at stage 4.
- Exact OpenRouter model ids for primary and second judge, chosen at stage 5 with prices.
- Leadership/people page URLs per probe unit: to be found at seed time (stage 2) or setup.
- No tests or import-linter yet (no code); they start at stage 1.

**Traps noted for later:** empty `allowed_tools` doesn't disable SDK built-ins; failed agent session
may report $0; Telem default routing fans out to all providers; Telem fetch is not evidence.
