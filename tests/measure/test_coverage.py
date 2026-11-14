"""Runs the coverage case table (tests/cases/coverage_cases.py) against measure.coverage."""

import pytest

from cases.coverage_cases import COVERAGE_CASES, CoverageCase
from sourcemap.domain.vocab import CoverageState
from sourcemap.measure.coverage import UnitOutcome, coverage


def _outcome(text: str, unit: int) -> UnitOutcome | None:
    if text == "failed":
        return UnitOutcome("failed")
    if text == "not fetched":
        return None
    if text == "ok: empty":
        return UnitOutcome("ok")
    n = int(text.split()[1])
    return UnitOutcome("ok", frozenset(unit * 1000 + i for i in range(n)), frozenset({"employment", "title"}))


def _run(case: CoverageCase, claim_type=None):
    panel = list(range(len(case.outcomes)))
    outcomes = {u: o for u in panel if (o := _outcome(case.outcomes[u], u)) is not None}
    return coverage(panel, outcomes, has_adapter=case.has_adapter, offered=case.offered,
                    claim_type=claim_type)


@pytest.mark.parametrize("case", COVERAGE_CASES, ids=lambda c: c.name)
def test_coverage_case(case: CoverageCase):
    cov = _run(case)
    assert cov.state is case.state
    assert cov.units_covered == case.units_covered
    assert cov.units_failed == case.units_failed
    if case.ratio is None:
        assert cov.ratio is None  # untested is never 0%
    else:
        assert cov.ratio == pytest.approx(case.ratio)
    if case.reason:
        assert cov.reason == case.reason
    if case.label:
        assert cov.label == case.label


def test_per_claim_type_needs_a_claim_of_that_type():
    panel = [1, 2]
    outcomes = {
        1: UnitOutcome("ok", frozenset({10}), frozenset({"employment", "title"})),
        2: UnitOutcome("ok", frozenset({20}), frozenset({"employment"})),
    }
    title = coverage(panel, outcomes, has_adapter=True, offered=True, claim_type="title")
    reports = coverage(panel, outcomes, has_adapter=True, offered=True, claim_type="reports_to")
    assert title.ratio == 0.5
    assert reports.state is CoverageState.MEASURED and reports.ratio == 0.0


def test_entities_are_unique_ids_of_covered_units():
    outcomes = {1: UnitOutcome("ok", frozenset({1, 2, 3})), 2: UnitOutcome("ok", frozenset({3, 4}))}
    cov = coverage([1, 2], outcomes, has_adapter=True, offered=True)
    assert cov.entities == {1, 2, 3, 4}
