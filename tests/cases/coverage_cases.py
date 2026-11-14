"""Coverage case table — docs/domain.md §6 "Coverage" (incl. partial failure).

Each case: per panel unit an outcome written in plain words, and the expected state, ratio and
counts. Outcomes: "ok: <n> people" (n entity ids returned), "ok: empty" (fetched fine, nobody),
"failed", "not fetched". Tests: tests/measure/test_coverage.py.
"""

from dataclasses import dataclass

from sourcemap.domain.vocab import CoverageState


@dataclass(frozen=True)
class CoverageCase:
    name: str
    outcomes: tuple[str, ...]
    state: CoverageState
    ratio: float | None
    units_covered: int
    units_failed: int
    has_adapter: bool = True
    offered: bool = True
    reason: str | None = None
    label: str | None = None


COVERAGE_CASES = [
    CoverageCase(
        "every unit returned people: 4/4 = 100%",
        ("ok: 30 people", "ok: 12 people", "ok: 5 people", "ok: 8 people"),
        CoverageState.MEASURED, 1.0, 4, 0, label="4/4 covered",
    ),
    CoverageCase(
        "partial failure: Notion timed out, 3/3 = 100% with '1 of 4 failed' — not 75%",
        ("ok: 30 people", "ok: 12 people", "ok: 5 people", "failed"),
        CoverageState.MEASURED, 1.0, 3, 1, label="3/3 covered, 1 of 4 failed",
    ),
    CoverageCase(
        "an empty answer is a valid measured result and counts as not covered",
        ("ok: 30 people", "ok: empty", "ok: empty", "ok: 4 people"),
        CoverageState.MEASURED, 0.5, 2, 0, label="2/4 covered",
    ),
    CoverageCase(
        "every fetched unit failed: failed, never 0%",
        ("failed", "failed", "failed", "failed"),
        CoverageState.FAILED, None, 0, 4,
    ),
    CoverageCase(
        "no adapter: not probed, never 0%",
        ("not fetched",) * 4,
        CoverageState.NOT_PROBED, None, 0, 0, has_adapter=False, reason="no_adapter",
    ),
    CoverageCase(
        "source does not offer this segment: not probed",
        ("not fetched",) * 4,
        CoverageState.NOT_PROBED, None, 0, 0, offered=False, reason="not_offered",
    ),
    CoverageCase(
        "adapter exists but nothing was ever fetched: not probed",
        ("not fetched",) * 4,
        CoverageState.NOT_PROBED, None, 0, 0, reason="never_fetched",
    ),
    CoverageCase(
        "test mode fetched only 3 of 4 units: the unfetched unit is left out, not counted as uncovered",
        ("ok: 3 people", "ok: 2 people", "ok: empty", "not fetched"),
        CoverageState.MEASURED, 2 / 3, 2, 0, label="2/3 covered, 1 of 4 not fetched",
    ),
    CoverageCase(
        "an empty segment is shown: everything fetched, nobody found → 0% measured",
        ("ok: empty", "ok: empty"),
        CoverageState.MEASURED, 0.0, 0, 0, label="0/2 covered",
    ),
]
