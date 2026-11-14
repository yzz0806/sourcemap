# 0002 — Accuracy standard: weighted Beta posterior, three display states

Status: accepted (stage 0)

## Context
The product's value is its accuracy numbers (BRIEF §1, §4). Small samples must not look certain:
"3 of 3 correct" is not 100%. Agreement between sources is weaker evidence than a reference or a
lookup. Stale and unverifiable verdicts are not errors. A prior must never be shown as if measured.

## Decision
- Per (source, segment, claim type), accuracy is a Beta posterior. Prior by tier: tier 1 Beta(4, 1),
  tier 2 Beta(3, 1), tier 3 Beta(2, 1), tier 4 Beta(1, 1). Prior strength is 2–5 pseudo-checks, so
  real checks dominate quickly.
- Each claim contributes its **current verdict** only (strongest unexpired method wins: reference >
  lookup > agreement).
- Weights: reference and lookup verdicts weigh 1. Agreement weighs **0.5**, and **0** when the
  source's subtype is `inferred`. `correct` adds the weight to α, `wrong` to β.
- `stale` and `unverifiable` never enter α or β; they are shown as shares of all verdicts.
- Display: mean and a 90% equal-tailed interval (Beta quantiles 0.05 and 0.95), and `n` (number of
  decisive verdicts).
- States: `unmeasured` when n = 0 (no number shown, never the prior); `not_enough_data` when
  0 < weighted decisive checks < **5** (interval shown, no mean); `measured` otherwise.
- If the representativeness gate (R5) fails for a cell, verdicts on the overlap with the reference
  are excluded from that cell's estimate; they stay visible in the drill-down, marked "excluded:
  overlap not representative".
- Worked example for the stage 1 hand check: tier 3, prior Beta(2, 1), 3 correct → Beta(5, 1),
  mean 5/6 = 0.833, 90% interval [0.05^(1/5), 0.95^(1/5)] = [0.549, 0.990].

## Consequences
- Cells with few checks are visibly uncertain; the map never shows a confident number from 3 checks.
- Tier priors encode prior trust but cannot produce a displayed number on their own.
- The minimum of 5 is a setting recorded here; changing it needs a new ADR.

## Alternatives rejected
- **Raw percentage (correct / checked)** — 3/3 shows 100%, the exact failure the brief forbids.
- **Wilson interval** — fine for proportions, but has no natural place for tier priors or fractional
  agreement weights.
- **Uniform prior for every tier** — throws away the tier information the brief asks us to use.
- **Counting agreement fully** — sources copy each other; it would inflate accuracy for popular facts.
