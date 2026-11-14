"""measure.sampling: lookups go where uncertainty is largest (docs/domain.md §4 step 5)."""

from sourcemap.domain.model import Interval
from sourcemap.measure.sampling import pick_lookups

CELLS = {"narrow": Interval(0.8, 0.9), "wide": Interval(0.2, 0.9), "unmeasured": None}
CLAIMS = {"narrow": [1, 2, 3], "wide": [4, 5, 6], "unmeasured": [7, 8, 9]}


def test_widest_cells_first_round_robin():
    out = pick_lookups(CELLS, CLAIMS, set(), budget_n=3, seed=1)
    assert out[0] in CLAIMS["unmeasured"] and out[1] in CLAIMS["wide"] and out[2] in CLAIMS["narrow"]


def test_claims_with_valid_verdicts_are_skipped():
    out = pick_lookups(CELLS, CLAIMS, {7, 8, 9}, budget_n=9, seed=1)
    assert not {7, 8, 9} & set(out) and len(out) == 6


def test_budget_caps_and_seed_is_deterministic():
    a = pick_lookups(CELLS, CLAIMS, set(), budget_n=5, seed=3)
    b = pick_lookups(CELLS, CLAIMS, set(), budget_n=5, seed=3)
    assert a == b and len(a) == 5 and len(set(a)) == 5


def test_nothing_to_pick():
    assert pick_lookups(CELLS, {}, set(), budget_n=5) == []
