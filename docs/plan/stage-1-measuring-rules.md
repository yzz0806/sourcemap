# Stage 1 — Measuring rules, offline

**Status:** next.

## Goal
The pure logic that turns records, claims and verdicts into scores — every rule of
`docs/domain.md` §6–§9 — tested with plain data. No internet, database, model or keys; costs nothing.

## What gets built (`src/sourcemap/domain`, `src/sourcemap/measure`)
| Part | Decides |
|---|---|
| Claims | how a record is split into claims (employment, title, reports_to; exists, role, affiliation, email, profile_link) |
| Names | normalising for comparison: accents, honorifics, "Last, First", case, hyphens, token order; script detection (Latin / Hangul) |
| Matching | mentions → entities: shared identifiers, rules, judge questions for borderline pairs, cannot-link, attaching to existing entities so ids stay stable (ADR 0013) |
| Compare | two values: same / different / ask the judge |
| Verdicts | strongest unexpired method wins; same-lineage verifier refused (R4, R7) |
| Accuracy | Beta posterior with tier priors, agreement weight 0.5 (0 for inferred), stale/unverifiable shares, states measured / not enough data / unmeasured, raw and weighted n (ADR 0002) |
| Transfer gate | overlap vs rest: fill rate, tree depth, freshness, formats (R5) |
| Coverage | measured / not probed / failed; partial failure "k of N failed" excluded from the denominator; unique entities |
| Combos and gaps | best set of up to 3 sources per segment by union of unique entities; gap below target |
| Sampling, freshness | which claims get lookups (widest intervals first, seeded); expiry; re-check selection |
| Health, drift | ok / degraded / broken / shape_changed / changed; drift alert on non-overlapping intervals |
| Assembly choice | winning value per field, alternatives, reason |
| Benchmark metrics | hits → candidates; per provider precision, pooled recall, known-source recall, exclusive finds, cost per good find, with intervals (ADR 0015) |
| Monitor matching | news hit → tracked entity by normalised name; matched claims first in the re-check queue (ADR 0016) |

Plus project setup: `pyproject.toml`, pytest (fast suite default, `slow` marker), import-linter
contracts from `docs/components/README.md`, `scipy` for Beta quantiles.

## Order of work
1. Write the partial-failure coverage rule into `docs/domain.md` §6.
2. Case tables first: `tests/cases/accuracy_cases.py` (every rule R1–R10 has a row, in plain words),
   names, matching, coverage, health.
3. Code until green.
4. Update `docs/components/measure.md` and `domain-types.md` to the real functions.
5. Checks, log, commit, wait.

## How you check
1. Open the accuracy case table: find "3 correct checks → interval, not 100%", "only unverifiable →
   unmeasured", "same-lineage agreement → ignored", "stale excluded from accuracy", "inferred:
   agreement alone gives nothing".
2. By hand: crowd edited, prior Beta(2, 1), 3 correct → mean (2+3)/(2+1+3) = 0.833.
3. The agent runs in front of you:
   - 2 correct + 1 stale + 1 unverifiable → n = 2, stale 25%, unverifiable 25%;
   - only unverifiable → unmeasured, not the prior;
   - same proportions with 10 and with 200 checks → clearly narrower interval;
   - gate fails → overlap verdicts dropped from the estimate.
4. Names: "Park, Hyung-Kwan" / "Hyung-Kwan Park" / "HYUNG KWAN PARK" match; "Dr. Jane Smith" /
   "Jane Smith" match; "John Smith" / "Jane Smith" don't; "J. Smith" / "Jane Smith" → judge;
   "박형관" / "Hyung-Kwan Park" → judge.
5. Benchmark case table: two providers with known hits → expected precision, pooled recall and
   exclusive finds; a provider that errored → "failed", not 0.
6. Import-linter proves `measure` imports no database, HTTP or model library.

## You need to provide
- OK to install Python 3.13 with Homebrew, only if packages fail on the machine's Python 3.15.
- 10 minutes to read the case table and do the one hand calculation.

## Cost
$0 (no network, no keys).
