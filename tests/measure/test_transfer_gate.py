"""Representativeness gate (R5) — runs tests/cases/gate_cases.py against measure.transfer_gate."""

from datetime import datetime

import pytest

from cases.gate_cases import GATE_CASES, GateCase
from sourcemap.domain.model import Verification
from sourcemap.domain.vocab import Method, Tier, Verdict
from sourcemap.measure.accuracy import estimate, prior_for
from sourcemap.measure.transfer_gate import (
    EXCLUDED_REASON,
    ClaimInfo,
    Features,
    apply_gate,
    features,
    representative,
)

T0 = datetime(2026, 11, 14)


def _f(side) -> Features:
    return Features(side.fill_rate, side.mean_depth, side.median_age_days, side.format_signature)


@pytest.mark.parametrize("case", GATE_CASES, ids=lambda c: c.name)
def test_gate_case(case: GateCase):
    result = representative(_f(case.overlap), _f(case.rest))
    assert result.passed is case.passed
    assert result.reasons == case.reasons


def test_features_from_claims():
    claims = [ClaimInfo(3, 3, 1, 10, "title_en"), ClaimInfo(1, 3, 3, 30, "title_en"),
              ClaimInfo(2, 3, 2, 20, "title_ko")]
    f = features(claims)
    assert f.fill_rate == pytest.approx(6 / 9)
    assert f.mean_depth == 2.0 and f.median_age_days == 20 and f.format_signature == "title_en"


def test_samsung_from_claims_fails():
    execs = [ClaimInfo(3, 3, 1, 30, "title_en")] * 27
    rest = [ClaimInfo(1, 3, 4, 30, "title_en")] * 300 + [ClaimInfo(2, 3, 4, 30, "title_en")] * 30
    assert not representative(features(execs), features(rest)).passed


def test_failed_gate_drops_overlap_verdicts_from_the_estimate():
    overlap = [Verification(i, Method.REFERENCE, Verdict.CORRECT, T0) for i in range(27)]
    gate = representative(_f(GATE_CASES[0].overlap), _f(GATE_CASES[0].rest))
    gated = apply_gate(overlap, gate)
    assert all(v.excluded_reason == EXCLUDED_REASON for v in gated)
    est = estimate(gated, prior_for(Tier.RESEARCHED))
    assert est.n_decisive == 0 and est.state.value == "unmeasured"


def test_passed_gate_keeps_verdicts():
    vs = [Verification(1, Method.REFERENCE, Verdict.CORRECT, T0)]
    gate = representative(_f(GATE_CASES[1].overlap), _f(GATE_CASES[1].rest))
    assert apply_gate(vs, gate) == vs
