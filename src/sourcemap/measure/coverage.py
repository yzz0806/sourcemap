"""Coverage of one source for one segment, with the three states and partial failure.

Implements docs/domain.md §6 "Coverage": measured / not probed / failed; failed (and unfetched)
units leave the denominator and are reported; untested is never 0%; an empty answer is a valid
measured result. Case table: tests/cases/coverage_cases.py.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sourcemap.domain.vocab import CoverageState

OK, FAILED, NOT_FETCHED = "ok", "failed", "not_fetched"


@dataclass(frozen=True, slots=True)
class UnitOutcome:
    """What one panel unit's fetch produced. `entities`: entity ids it returned (after matching);
    `claim_types`: claim types with at least one claim for this unit."""

    status: str  # "ok" | "failed" | "not_fetched"
    entities: frozenset[int] = frozenset()
    claim_types: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Coverage:
    """Coverage of one (source, segment[, claim type]). `ratio` is None unless MEASURED.

    `ok_units`: units fetched without failure (the denominator); `covered_units`: units with at
    least one valid record (or claim of the claim type)."""

    state: CoverageState
    ratio: float | None
    units_panel: int
    units_covered: int
    units_failed: int
    units_not_fetched: int
    covered_units: frozenset[int]
    ok_units: frozenset[int]
    entities: frozenset[int]
    reason: str | None = None  # for NOT_PROBED: "no_adapter" | "not_offered" | "never_fetched"

    @property
    def label(self) -> str:
        """Human text, e.g. "3/3 covered, 1 of 4 failed"."""
        if self.state is CoverageState.NOT_PROBED:
            return f"not probed ({self.reason})"
        if self.state is CoverageState.FAILED:
            return f"failed ({self.units_failed} of {self.units_panel} failed)"
        text = f"{self.units_covered}/{len(self.ok_units)} covered"
        if self.units_failed:
            text += f", {self.units_failed} of {self.units_panel} failed"
        if self.units_not_fetched:
            text += f", {self.units_not_fetched} of {self.units_panel} not fetched"
        return text


def coverage(
    panel: Iterable[int],
    outcomes: Mapping[int, UnitOutcome],
    *,
    has_adapter: bool,
    offered: bool,
    claim_type: str | None = None,
) -> Coverage:
    """Coverage of one source over a segment's panel. Units missing from `outcomes` are
    not fetched. With `claim_type`, a unit is covered only if it has a claim of that type."""
    panel = list(dict.fromkeys(panel))
    get = lambda u: outcomes.get(u, UnitOutcome(NOT_FETCHED))  # noqa: E731
    ok = frozenset(u for u in panel if get(u).status == OK)
    failed = frozenset(u for u in panel if get(u).status == FAILED)
    not_fetched = len(panel) - len(ok) - len(failed)

    def make(state, ratio=None, covered=frozenset(), entities=frozenset(), reason=None):
        return Coverage(state, ratio, len(panel), len(covered), len(failed), not_fetched,
                        frozenset(covered), ok, frozenset(entities), reason)

    if not has_adapter:
        return make(CoverageState.NOT_PROBED, reason="no_adapter")
    if not offered:
        return make(CoverageState.NOT_PROBED, reason="not_offered")
    if not ok and not failed:
        return make(CoverageState.NOT_PROBED, reason="never_fetched")
    if not ok:
        return make(CoverageState.FAILED)

    def is_covered(u: int) -> bool:
        o = get(u)
        return claim_type in o.claim_types if claim_type else bool(o.entities)

    covered = frozenset(u for u in ok if is_covered(u))
    entities = frozenset().union(*(get(u).entities for u in covered)) if covered else frozenset()
    return make(CoverageState.MEASURED, len(covered) / len(ok), covered, entities)
