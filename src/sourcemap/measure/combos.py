"""Best combination of up to k sources per segment, and gap detection.

Implements docs/domain.md §4 step 6 and §6 "Coverage": a combination counts the union of covered
units and of unique entities, so two sources returning the same 30 people count 30, not 60.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations

from sourcemap.domain.vocab import CoverageState
from sourcemap.measure.coverage import Coverage

COVERAGE_TARGET = 0.5  # docs/domain.md §3


@dataclass(frozen=True, slots=True)
class Combo:
    """A set of sources and what they cover together. `ratio` is None when no source in the
    segment has measured coverage."""

    sources: tuple[str, ...]
    units_covered: int
    entities: frozenset[int]
    ratio: float | None


def best_combo(
    segment_units: Iterable[int], coverage_by_source: Mapping[str, Coverage], k: int = 3
) -> Combo:
    """Exhaustive search over combinations of up to k sources with MEASURED coverage.

    Ranking: more units covered, then more unique entities, then fewer sources, then slug order.
    The ratio's denominator is the units at least one chosen source fetched without failure.
    """
    units = frozenset(segment_units)
    measured = sorted(s for s, c in coverage_by_source.items() if c.state is CoverageState.MEASURED)
    best_key, best = None, Combo((), 0, frozenset(), None)
    for size in range(1, min(k, len(measured)) + 1):
        for combo in combinations(measured, size):
            covs = [coverage_by_source[s] for s in combo]
            covered = frozenset().union(*(c.covered_units for c in covs)) & units
            ok = frozenset().union(*(c.ok_units for c in covs)) & units
            entities = frozenset().union(*(c.entities for c in covs))
            key = (-len(covered), -len(entities), size, combo)
            if best_key is None or key < best_key:
                best_key = key
                best = Combo(combo, len(covered), entities, len(covered) / len(ok) if ok else None)
    return best


def is_gap(combo: Combo, target: float = COVERAGE_TARGET) -> bool:
    """A segment is a gap when its best combination covers less than the target. A segment with
    no measured source at all is also a gap: nothing is known to cover it."""
    return combo.ratio is None or combo.ratio < target
