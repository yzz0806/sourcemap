"""Representativeness gate case table — docs/domain.md §6 R5.

Overlap = the part of a source that a reference also covers; rest = everything else. Each side
is described by fill rate, mean depth in the org tree, median age in days and the dominant value
format. Tests: tests/measure/test_transfer_gate.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Side:
    fill_rate: float
    mean_depth: float
    median_age_days: float
    format_signature: str


@dataclass(frozen=True)
class GateCase:
    name: str
    overlap: Side
    rest: Side
    passed: bool
    reasons: tuple[str, ...] = ()


GATE_CASES = [
    GateCase(
        "Samsung: 27 executives (depth 1, all fields filled) say nothing about 3,000 deeper people",
        Side(1.0, 1.0, 30, "title_en"), Side(0.4, 4.0, 30, "title_en"),
        False, ("fill_rate", "depth"),
    ),
    GateCase(
        "overlap looks like the rest: accuracy transfers",
        Side(0.90, 2.0, 40, "title_en"), Side(0.85, 2.6, 60, "title_en"),
        True,
    ),
    GateCase(
        "fill rate just inside tolerance (0.15) passes",
        Side(0.90, 2.0, 40, "title_en"), Side(0.75, 2.0, 40, "title_en"),
        True,
    ),
    GateCase(
        "much older data in the rest fails on freshness",
        Side(0.9, 2.0, 20, "title_en"), Side(0.9, 2.0, 400, "title_en"),
        False, ("freshness",),
    ),
    GateCase(
        "different value formats (Korean titles vs English) fail",
        Side(0.9, 2.0, 20, "title_ko"), Side(0.9, 2.0, 20, "title_en"),
        False, ("format",),
    ),
]
