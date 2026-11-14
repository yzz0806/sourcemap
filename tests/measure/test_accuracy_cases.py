"""Runs the accuracy case table (tests/cases/accuracy_cases.py) against measure.accuracy."""

from datetime import datetime

import pytest

from cases.accuracy_cases import ACCURACY_CASES, AccuracyCase
from sourcemap.domain.model import Source
from sourcemap.domain.vocab import Method, Subtype, Verdict
from sourcemap.measure.accuracy import beta_interval, estimate, prior_for
from sourcemap.measure.verdicts import exclude, method_weight

T0 = datetime(2026, 11, 14)


def _verifications(case: AccuracyCase):
    source = Source(1, "src", case.tier, Subtype.INFERRED if case.inferred else Subtype.CROWD_EDITED, "x")
    out = []
    for i, text in enumerate(case.verdicts):
        verdict, method = text.split(" by ")
        m = Method(method)
        from sourcemap.domain.model import Verification

        v = Verification(i, m, Verdict(verdict), T0, weight=method_weight(m, source))
        if i in case.excluded:
            v = exclude(v, "overlap not representative (R5)")
        out.append(v)
    return out


@pytest.mark.parametrize("case", ACCURACY_CASES, ids=lambda c: c.name)
def test_accuracy_case(case: AccuracyCase):
    est = estimate(_verifications(case), prior_for(case.tier))
    assert est.state is case.state
    assert est.n_decisive == case.n_decisive
    assert est.n_weighted == pytest.approx(case.n_weighted)
    assert est.stale_share == pytest.approx(case.stale_share)
    assert est.unverifiable_share == pytest.approx(case.unverifiable_share)
    if case.mean is None:
        assert est.mean is None
    else:
        assert est.mean == pytest.approx(case.mean)
    if case.interval is not None:
        assert est.interval.lo == pytest.approx(case.interval[0], abs=1e-3)
        assert est.interval.hi == pytest.approx(case.interval[1], abs=1e-3)
    if est.state.value == "unmeasured":
        assert est.interval is None  # the prior is never displayed (R8)


def test_hand_check_crowd_edited_three_correct():
    """PLAN stage 1 check 2: prior (2, 1), 3 correct → posterior mean (2+3)/(2+1+3)."""
    case = ACCURACY_CASES[0]
    est = estimate(_verifications(case), prior_for(case.tier))
    assert prior_for(case.tier) == (2.0, 1.0)
    assert est.posterior == (5.0, 1.0)
    assert est.posterior_mean == pytest.approx(5 / 6)


def test_more_checks_give_a_narrower_interval():
    """Same 80% proportion with 10 and with 200 checks: the interval clearly narrows (R6)."""
    a0, b0 = prior_for(3)
    small = beta_interval(a0 + 8, b0 + 2)
    large = beta_interval(a0 + 160, b0 + 40)
    assert (large.hi - large.lo) < 0.4 * (small.hi - small.lo)
