"""Runs the value comparison case table (tests/cases/compare_cases.py) against measure.compare."""

import pytest

from cases.compare_cases import COMPARE_CASES, CompareCase
from sourcemap.domain.specs import ACADEMIC_IDENTITY, ORG_CHART
from sourcemap.measure.compare import (
    Comparison,
    compare_values,
    judge_question,
    normalise_url,
    normalise_value,
)

SPECS = {s.slug: s for s in (ORG_CHART, ACADEMIC_IDENTITY)}


@pytest.mark.parametrize("case", COMPARE_CASES, ids=lambda c: c.name)
def test_compare_case(case: CompareCase):
    spec = SPECS[case.data_type].claim_type(case.claim_type)
    assert compare_values(spec, case.a, case.b) is Comparison(case.expected)
    assert compare_values(spec, case.b, case.a) is Comparison(case.expected)


def test_bool_normalises_to_words():
    spec = ORG_CHART.claim_type("employment")
    assert normalise_value(spec, True) == "true" and normalise_value(spec, False) == "false"


def test_url_keeps_path_case_but_lowercases_host():
    assert normalise_url("HTTPS://WWW.Example.COM/People/Jane/") == "example.com/People/Jane"


def test_judge_question_for_titles():
    q = judge_question(ORG_CHART.claim_type("title"), "VP Sales", "Vice President of Sales", unit="gong")
    assert q.kind == "same_title" and ("unit", "gong") in q.context
