"""Choosing one value per entity and claim type from competing sources, with the reason.

Implements docs/domain.md §4 step 8: the value comes from the source most accurate for that claim
type in that segment; every alternative is kept with its origin; the reason says honestly what
decided it (measured accuracy, interval only, or tier prior only).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sourcemap.domain.model import Claim, Source
from sourcemap.domain.vocab import AccuracyState
from sourcemap.measure.accuracy import AccuracyEstimate

BASIS = {
    AccuracyState.MEASURED: "measured accuracy",
    AccuracyState.NOT_ENOUGH_DATA: "interval only (not enough data)",
    AccuracyState.UNMEASURED: "tier prior only (unmeasured)",
}


@dataclass(frozen=True, slots=True)
class Candidate:
    claim: Claim
    source: Source
    estimate: AccuracyEstimate  # for (source, segment, claim type)


@dataclass(frozen=True, slots=True)
class Alternative:
    value: Any
    value_norm: str
    sources: tuple[str, ...]
    state: AccuracyState  # best state among its sources
    mean: float | None


@dataclass(frozen=True, slots=True)
class Choice:
    claim_type: str
    winner: Claim
    winner_source: Source
    winner_sources: tuple[str, ...]  # every source stating the winning value
    alternatives: tuple[Alternative, ...]  # other values, best first
    reason: dict


def _midpoint(e: AccuracyEstimate) -> float:
    return (e.interval.lo + e.interval.hi) / 2 if e.interval else 0.0


def _rank(c: Candidate) -> tuple:
    e = c.estimate
    if e.state is AccuracyState.MEASURED:
        group, score = 0, -e.mean
    elif e.state is AccuracyState.NOT_ENOUGH_DATA:
        group, score = 1, -_midpoint(e)
    else:
        group, score = 2, 0.0
    return (group, score, int(c.source.tier), c.source.slug)


def _acc(e: AccuracyEstimate) -> dict:
    if e.state is AccuracyState.MEASURED:
        return {"acc": round(e.mean, 3)}
    if e.state is AccuracyState.NOT_ENOUGH_DATA:
        return {"interval": (round(e.interval.lo, 3), round(e.interval.hi, 3))}
    return {"acc": None}


def choose_value(claim_type: str, candidates: Iterable[Candidate]) -> Choice:
    """Pick the winning value. Ranking: MEASURED by mean, then NOT_ENOUGH_DATA by interval
    midpoint, then UNMEASURED by tier; ties → stronger tier, then source slug."""
    ranked = sorted(candidates, key=_rank)
    if not ranked:
        raise ValueError("choose_value() needs at least one candidate")
    win = ranked[0]

    groups: dict[str, list[Candidate]] = {}
    for c in ranked:  # ranked order, so each group's first member is its best source
        groups.setdefault(c.claim.value_norm, []).append(c)

    alternatives = tuple(
        Alternative(cs[0].claim.value, norm, tuple(c.source.slug for c in cs),
                    cs[0].estimate.state, cs[0].estimate.mean)
        for norm, cs in groups.items() if norm != win.claim.value_norm
    )

    reason: dict = {"winner": win.source.slug, "basis": BASIS[win.estimate.state]}
    reason.update({f"winner_{k}": v for k, v in _acc(win.estimate).items()})
    runner = next((c for c in ranked if c.claim.value_norm != win.claim.value_norm), None)
    if runner is not None:
        reason["runner_up"] = runner.source.slug
        reason.update({f"runner_up_{k}": v for k, v in _acc(runner.estimate).items()})

    return Choice(
        claim_type=claim_type,
        winner=win.claim,
        winner_source=win.source,
        winner_sources=tuple(c.source.slug for c in groups[win.claim.value_norm]),
        alternatives=alternatives,
        reason=reason,
    )
