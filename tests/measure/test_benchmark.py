"""measure.benchmark against tests/cases/benchmark_cases.py (ADR 0015)."""

import pytest

from cases.benchmark_cases import (
    CANDIDATE_KEY_CASES,
    KNOWN_ANSWER_CASES,
    NORMALISE_URL_CASES,
    SCENARIO,
)
from sourcemap.measure.benchmark import (
    Candidate,
    Hit,
    KnownTrial,
    ProviderCall,
    candidate_key,
    normalise_url,
    provider_metrics,
    review_sample,
    score_known_answer,
    to_candidates,
)


@pytest.mark.parametrize("name,raw,expected", NORMALISE_URL_CASES, ids=[c[0] for c in NORMALISE_URL_CASES])
def test_normalise_url(name, raw, expected):
    assert normalise_url(raw) == expected


@pytest.mark.parametrize("name,expected,hits,result", KNOWN_ANSWER_CASES, ids=[c[0] for c in KNOWN_ANSWER_CASES])
def test_known_answer(name, expected, hits, result):
    assert score_known_answer(expected, hits) == result


@pytest.mark.parametrize("name,url,key", CANDIDATE_KEY_CASES, ids=[c[0] for c in CANDIDATE_KEY_CASES])
def test_candidate_key(name, url, key):
    assert candidate_key(url) == key


def test_hits_collapse_into_one_candidate_remembering_providers():
    hits = [
        Hit("exa", 1, 2, "https://theorg.com/org/gong", "na_mid"),
        Hit("brave", 1, 1, "https://www.theorg.com/org/airtable/", "na_mid"),
        Hit("brave", 2, 3, "https://gong.io/team"),
    ]
    cands = {c.key: c for c in to_candidates(hits)}
    theorg = cands["theorg.com/org"]
    assert theorg.providers == {"exa", "brave"}
    assert theorg.ranks == (("brave", 1), ("exa", 2))
    assert theorg.query_ids == {1}
    assert theorg.example_url == "https://www.theorg.com/org/airtable/"
    assert set(cands) == {"theorg.com/org", "gong.io/team"}


def _cands(n):
    return [Candidate(f"d{i}.com/", "u", frozenset({"p"}), (), frozenset(), frozenset()) for i in range(n)]


def test_review_sample_caps_and_is_seeded():
    s1 = review_sample(_cands(200), cap=80, seed=7)
    s2 = review_sample(_cands(200), cap=80, seed=7)
    assert len(s1) == 80 and [c.key for c in s1] == [c.key for c in s2]
    assert len({c.key for c in s1}) == 80


def test_review_sample_under_cap_returns_all():
    assert len(review_sample(_cands(30), cap=80, seed=1)) == 30


def _scenario_metrics():
    proposed = SCENARIO["proposed"]
    keys = sorted({k for ks in proposed.values() for k in ks})
    cands = [
        Candidate(k, "u", frozenset(p for p, ks in proposed.items() if k in ks), (), frozenset(), frozenset())
        for k in keys
    ]
    ms = provider_metrics(["a", "b"], [], cands, SCENARIO["known"], SCENARIO["kept"], SCENARIO["reviewed"], [])
    return {(m.provider, m.metric): m for m in ms}


@pytest.mark.parametrize("metric", ["precision", "pooled_recall", "known_recall"])
def test_scenario_proportions(metric):
    ms = _scenario_metrics()
    for p, (num, den) in SCENARIO[metric].items():
        assert (ms[(p, metric)].num, ms[(p, metric)].den) == (num, den)


def test_scenario_exclusive_finds():
    ms = _scenario_metrics()
    for p, n in SCENARIO["exclusive"].items():
        assert ms[(p, "exclusive")].mean == n


def test_small_samples_are_not_enough_data_with_interval_only():
    m = _scenario_metrics()[("b", "precision")]  # 2 of 3
    assert m.state == "not_enough_data" and m.mean is None and m.lo90 is not None


def test_known_answer_rate_measured_with_beta_1_1():
    trials = [KnownTrial("exa", True, 1)] * 8 + [KnownTrial("exa", False, None)] * 2
    ms = {m.metric: m for m in provider_metrics(["exa"], trials, [], set(), set(), set(), [])}
    rate = ms["known_hit_rate"]
    assert rate.state == "measured" and rate.mean == pytest.approx(9 / 12)
    assert rate.lo90 < rate.mean < rate.hi90
    assert ms["known_mrr"].mean == pytest.approx(0.8)


def test_provider_that_errored_on_every_call_is_failed_not_zero():
    calls = [ProviderCall("perplexity", ok=False)] * 3
    ms = provider_metrics(["perplexity"], [], [], set(), set(), set(), calls)
    assert all(m.state == "failed" and m.mean is None for m in ms)


def test_unreviewed_candidates_are_excluded():
    """k6 was not sampled for review: it is neither a hit nor a miss for provider a."""
    ms = _scenario_metrics()
    assert ms[("a", "precision")].den == 5  # not 6


def test_cost_per_good_find_and_latency():
    proposed = SCENARIO["proposed"]
    keys = sorted({k for ks in proposed.values() for k in ks})
    cands = [Candidate(k, "u", frozenset(p for p, ks in proposed.items() if k in ks), (), frozenset(), frozenset())
             for k in keys]
    calls = [ProviderCall("a", True, 0.03, 100), ProviderCall("a", True, 0.03, 300), ProviderCall("a", False, 0.0)]
    ms = {(m.provider, m.metric): m for m in provider_metrics(
        ["a", "b"], [], cands, SCENARIO["known"], SCENARIO["kept"], SCENARIO["reviewed"], calls)}
    assert ms[("a", "usd_per_good_find")].mean == pytest.approx(0.06 / 3)
    assert ms[("a", "latency_ms")].mean == 200
    assert ms[("a", "precision")].state != "failed"  # some calls succeeded
