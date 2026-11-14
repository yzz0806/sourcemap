"""measure.freshness against tests/cases/freshness_cases.py (ADR 0012)."""

from datetime import datetime, timedelta

import pytest

from cases.freshness_cases import EXPIRY_DAYS, TITLE_RECHECK_CASES
from sourcemap.domain.model import Verification
from sourcemap.domain.specs import ACADEMIC_IDENTITY, ORG_CHART
from sourcemap.domain.vocab import Method, Verdict
from sourcemap.measure.freshness import due_for_recheck, expires_at, is_due

T0 = datetime(2026, 11, 1)
TITLE = ORG_CHART.claim_type("title")


@pytest.mark.parametrize("data_type,claim_type", list(EXPIRY_DAYS))
def test_expiry_days_match_adr_0012(data_type, claim_type):
    spec = {"org_chart": ORG_CHART, "academic_identity": ACADEMIC_IDENTITY}[data_type]
    ct = spec.claim_type(claim_type)
    assert expires_at(ct, T0) - T0 == timedelta(days=EXPIRY_DAYS[(data_type, claim_type)])


@pytest.mark.parametrize("name,days,due", TITLE_RECHECK_CASES, ids=[c[0] for c in TITLE_RECHECK_CASES])
def test_title_recheck_window(name, days, due):
    v = Verification(1, Method.LOOKUP, Verdict.CORRECT, T0, expires_at(TITLE, T0))
    assert is_due(v, T0 + timedelta(days=days)) is due


def test_due_oldest_first_and_capped():
    vs = [Verification(i, Method.LOOKUP, Verdict.CORRECT, T0 + timedelta(days=i), expires_at(TITLE, T0 + timedelta(days=i)))
          for i in range(5)]
    as_of = T0 + timedelta(days=40)
    out = due_for_recheck(list(reversed(vs)), as_of, budget_n=3)
    assert [v.claim_id for v in out] == [0, 1, 2]


def test_no_expiry_is_never_due():
    v = Verification(1, Method.LOOKUP, Verdict.CORRECT, T0)
    assert due_for_recheck([v], T0 + timedelta(days=999), 10) == []


def test_unchanged_claim_is_still_rechecked():
    """The earlier implementation's bug (ADR 0012): an unchanged claim must still come due."""
    v = Verification(1, Method.LOOKUP, Verdict.CORRECT, T0, expires_at(TITLE, T0))
    assert due_for_recheck([v], T0 + timedelta(days=25), 10) == [v]
