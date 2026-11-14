"""Accuracy drift alert (ADR 0012, docs/domain.md §9): fires when a cell's new 90% interval does
not overlap its previous one. No alert when either side has no interval."""

from sourcemap.domain.model import Interval


def drift_alert(prev: Interval | None, new: Interval | None) -> bool:
    return prev is not None and new is not None and not prev.overlaps(new)
