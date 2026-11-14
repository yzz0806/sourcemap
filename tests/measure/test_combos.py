"""Best combination of sources and gaps — measure.combos (docs/domain.md §6 "Coverage")."""

from sourcemap.measure.combos import best_combo, is_gap
from sourcemap.measure.coverage import UnitOutcome, coverage

PANEL = [1, 2, 3, 4]


def cov(units_people: dict, *, has_adapter=True, offered=True, failed=()):
    outcomes = {u: UnitOutcome("ok", frozenset(p)) for u, p in units_people.items()}
    outcomes.update({u: UnitOutcome("failed") for u in failed})
    return coverage(PANEL, outcomes, has_adapter=has_adapter, offered=offered)


def test_two_sources_with_the_same_30_people_count_30_not_60():
    people = set(range(30))
    combo = best_combo(PANEL, {"a": cov({1: people}), "b": cov({1: people})})
    assert len(combo.entities) == 30
    assert combo.sources == ("a",)  # adding b covers nothing new → fewer sources wins


def test_union_of_units_beats_any_single_source():
    srcs = {"theorg": cov({1: {1}, 2: {2}}), "dart": cov({3: {3}}), "page": cov({4: {4}})}
    combo = best_combo(PANEL, srcs)
    assert combo.sources == ("dart", "page", "theorg")
    assert combo.units_covered == 4 and combo.ratio == 1.0


def test_k_limits_the_combination_size():
    srcs = {s: cov({u: {u}}) for s, u in zip("abcd", PANEL)}
    combo = best_combo(PANEL, srcs, k=2)
    assert len(combo.sources) == 2 and combo.units_covered == 2


def test_more_entities_break_a_tie_on_units():
    srcs = {"a": cov({1: {1}}), "b": cov({1: {1, 2, 3}})}
    assert best_combo(PANEL, srcs, k=1).sources == ("b",)


def test_not_probed_and_failed_sources_are_never_chosen():
    srcs = {"no_adapter": cov({}, has_adapter=False), "broken": cov({}, failed=PANEL)}
    combo = best_combo(PANEL, srcs)
    assert combo.sources == () and combo.ratio is None
    assert is_gap(combo)


def test_gap_below_target():
    combo = best_combo(PANEL, {"a": cov({1: {1}, 2: set(), 3: set(), 4: set()})})
    assert combo.ratio == 0.25 and is_gap(combo)
    combo2 = best_combo(PANEL, {"a": cov({1: {1}, 2: {2}, 3: set(), 4: set()})})
    assert combo2.ratio == 0.5 and not is_gap(combo2)
