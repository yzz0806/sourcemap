"""Source health per run, compared with the previous run (ADR 0012, docs/domain.md §9).

Case table: tests/cases/health_cases.py. Priority: broken > shape_changed > degraded > changed > ok.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from sourcemap.domain.vocab import HealthState

SHAPE_CHANGED_SHARE = 0.5
CHANGED_SHARE = 0.3


@dataclass(frozen=True)
class RunStats:
    """One source's probe outcome in one run.

    units_attempted: panel units fetched or tried; units_failed: fetch errors (timeout, HTTP);
    shape_failures: fetched but the record failed validation; units_valid: units with ≥1 valid
    record; fingerprints: claim fingerprints per unit (for the "changed" comparison)."""

    units_attempted: int
    units_failed: int
    shape_failures: int
    units_valid: int
    fingerprints: Mapping[str, frozenset[str]] = field(default_factory=dict)

    @property
    def units_fetched(self) -> int:
        return self.units_attempted - self.units_failed


def changed_share(prev: RunStats, this: RunStats) -> float:
    """Share of fingerprints that differ, over units seen in both runs (0 when none in common)."""
    common = set(prev.fingerprints) & set(this.fingerprints)
    union = diff = 0
    for u in common:
        a, b = prev.fingerprints[u], this.fingerprints[u]
        union += len(a | b)
        diff += len(a ^ b)
    return diff / union if union else 0.0


def source_health(prev: RunStats | None, this: RunStats) -> HealthState:
    if this.units_valid == 0:
        return HealthState.BROKEN
    if this.units_fetched > 0 and this.shape_failures / this.units_fetched >= SHAPE_CHANGED_SHARE:
        return HealthState.SHAPE_CHANGED
    if this.units_failed > 0:
        return HealthState.DEGRADED
    if prev is not None and changed_share(prev, this) >= CHANGED_SHARE:
        return HealthState.CHANGED
    return HealthState.OK
