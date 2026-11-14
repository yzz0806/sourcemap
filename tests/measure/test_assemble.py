"""Choosing one value per field with the reason — measure.assemble (docs/domain.md §4 step 8)."""

from datetime import datetime

import pytest

from sourcemap.domain.model import Claim, Source, Verification
from sourcemap.domain.vocab import Method, Subtype, Tier, Verdict
from sourcemap.measure.accuracy import estimate, prior_for
from sourcemap.measure.assemble import Candidate, choose_value

T0 = datetime(2026, 11, 14)
GONG = Source(1, "company:gong.io", Tier.FIRST_PARTY, Subtype.FIRST_PARTY, "company:gong.io")
THEORG = Source(2, "theorg", Tier.RESEARCHED, Subtype.CROWD_EDITED, "theorg")
LINKEDIN = Source(3, "linkedin_apify", Tier.AGGREGATE, Subtype.PROFILE_AGGREGATE, "linkedin")
DART = Source(4, "dart", Tier.OFFICIAL, Subtype.OFFICIAL_FILING, "dart")


def est(source, correct, wrong):
    vs = [Verification(i, Method.LOOKUP, Verdict.CORRECT, T0) for i in range(correct)]
    vs += [Verification(i, Method.LOOKUP, Verdict.WRONG, T0) for i in range(wrong)]
    return estimate(vs, prior_for(source.tier))


def cand(cid, source, value, correct, wrong):
    claim = Claim(cid, source.id, 1, "title", 10, value, value.lower())
    return Candidate(claim, source, est(source, correct, wrong))


def test_measured_accuracy_decides_and_reason_says_so():
    choice = choose_value("title", [
        cand(1, THEORG, "VP Sales", 15, 6),
        cand(2, GONG, "Vice President of Sales", 22, 1),
    ])
    assert choice.winner.value == "Vice President of Sales"
    assert choice.reason["winner"] == "company:gong.io"
    assert choice.reason["runner_up"] == "theorg"
    assert choice.reason["basis"] == "measured accuracy"
    assert choice.reason["winner_acc"] > choice.reason["runner_up_acc"]
    assert [a.value for a in choice.alternatives] == ["VP Sales"]


def test_measured_beats_not_enough_data_even_with_a_higher_midpoint():
    choice = choose_value("title", [cand(1, THEORG, "A", 6, 2), cand(2, DART, "B", 3, 0)])
    assert choice.winner_source is THEORG


def test_interval_only_basis_is_stated():
    choice = choose_value("title", [cand(1, THEORG, "A", 2, 0), cand(2, LINKEDIN, "B", 1, 1)])
    assert choice.reason["basis"] == "interval only (not enough data)"
    assert "winner_interval" in choice.reason


def test_unmeasured_falls_back_to_tier_and_says_so():
    choice = choose_value("title", [cand(1, LINKEDIN, "A", 0, 0), cand(2, GONG, "B", 0, 0)])
    assert choice.winner_source is GONG
    assert choice.reason["basis"] == "tier prior only (unmeasured)"
    assert choice.reason["winner_acc"] is None


def test_same_value_from_several_sources_collapses():
    choice = choose_value("title", [
        cand(1, GONG, "CEO", 10, 0), cand(2, THEORG, "ceo", 8, 2), cand(3, LINKEDIN, "Founder", 5, 0),
    ])
    assert choice.winner_sources == ("company:gong.io", "theorg")
    assert len(choice.alternatives) == 1 and choice.alternatives[0].sources == ("linkedin_apify",)


def test_no_alternative_means_no_runner_up():
    choice = choose_value("title", [cand(1, GONG, "CEO", 10, 0)])
    assert "runner_up" not in choice.reason and choice.alternatives == ()


def test_no_candidates_is_an_error():
    with pytest.raises(ValueError):
        choose_value("title", [])
