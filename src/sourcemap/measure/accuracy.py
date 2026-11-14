"""Accuracy as a weighted Beta posterior with tier priors and three display states.

Implements docs/domain.md §6 R6–R8 and ADR 0002. The case table in tests/cases/accuracy_cases.py
is the specification.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from scipy.stats import beta as beta_dist

from sourcemap.domain.model import Interval, Verification
from sourcemap.domain.vocab import AccuracyState, Tier, Verdict

MIN_DECISIVE = 5  # ADR 0002: below this weighted count the cell says "not enough data".

_PRIORS = {
    Tier.OFFICIAL: (4.0, 1.0),
    Tier.FIRST_PARTY: (3.0, 1.0),
    Tier.RESEARCHED: (2.0, 1.0),
    Tier.AGGREGATE: (1.0, 1.0),
}


def prior_for(tier: Tier) -> tuple[float, float]:
    """The weak Beta prior (a, b) for a tier (docs/domain.md §5)."""
    return _PRIORS[Tier(tier)]


def beta_interval(a: float, b: float) -> Interval:
    """The 90% equal-tailed interval of Beta(a, b)."""
    return Interval(float(beta_dist.ppf(0.05, a, b)), float(beta_dist.ppf(0.95, a, b)))


@dataclass(frozen=True, slots=True)
class AccuracyEstimate:
    """One cell's accuracy. `mean` is None unless state is MEASURED; `interval` is None when
    UNMEASURED (the prior is never displayed, R8). `posterior_mean` is kept for the trace."""

    state: AccuracyState
    mean: float | None
    interval: Interval | None
    n_correct: int
    n_wrong: int
    n_stale: int
    n_unverifiable: int
    n_decisive: int
    n_weighted: float
    stale_share: float
    unverifiable_share: float
    prior: tuple[float, float]
    posterior: tuple[float, float]
    posterior_mean: float


def estimate(
    verifications: Iterable[Verification],
    prior: tuple[float, float],
    min_decisive: float = MIN_DECISIVE,
) -> AccuracyEstimate:
    """Estimate one cell from the **current** verdicts of its claims (one per claim, chosen by
    measure.verdicts.current_verdict). Verdicts with `excluded_reason` (e.g. R5 gate) are ignored.

    correct adds its weight to a, wrong to b; stale and unverifiable never enter a or b (R8).
    """
    counts = {v: 0 for v in Verdict}
    w_correct = w_wrong = 0.0
    for v in verifications:
        if v.excluded_reason:
            continue
        counts[v.verdict] += 1
        if v.verdict is Verdict.CORRECT:
            w_correct += v.weight
        elif v.verdict is Verdict.WRONG:
            w_wrong += v.weight

    a0, b0 = prior
    a, b = a0 + w_correct, b0 + w_wrong
    n_weighted = w_correct + w_wrong
    total = sum(counts.values())
    stale_share = counts[Verdict.STALE] / total if total else 0.0
    unverifiable_share = counts[Verdict.UNVERIFIABLE] / total if total else 0.0
    posterior_mean = a / (a + b)

    if n_weighted == 0:
        state, mean, interval = AccuracyState.UNMEASURED, None, None
    elif n_weighted < min_decisive:
        state, mean, interval = AccuracyState.NOT_ENOUGH_DATA, None, beta_interval(a, b)
    else:
        state, mean, interval = AccuracyState.MEASURED, posterior_mean, beta_interval(a, b)

    return AccuracyEstimate(
        state=state,
        mean=mean,
        interval=interval,
        n_correct=counts[Verdict.CORRECT],
        n_wrong=counts[Verdict.WRONG],
        n_stale=counts[Verdict.STALE],
        n_unverifiable=counts[Verdict.UNVERIFIABLE],
        n_decisive=counts[Verdict.CORRECT] + counts[Verdict.WRONG],
        n_weighted=n_weighted,
        stale_share=stale_share,
        unverifiable_share=unverifiable_share,
        prior=(a0, b0),
        posterior=(a, b),
        posterior_mean=posterior_mean,
    )
