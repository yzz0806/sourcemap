"""Name normalising — measure.names (docs/domain.md §8)."""

import pytest

from sourcemap.measure.names import normalise_name, script_of

SAME = [
    ("Park, Hyung-Kwan", "Hyung-Kwan Park"),
    ("Park, Hyung-Kwan", "HYUNG KWAN PARK"),
    ("Dr. Jane Smith", "Jane Smith"),
    ("José Álvarez", "Jose Alvarez"),
    ("Jane Smith, PhD", "jane smith"),
    ("Seán O'Brien", "Sean OBrien"),
    ("Smith, Jane", "Jane Smith"),
]
DIFFERENT = [
    ("John Smith", "Jane Smith"),
    ("Jane Smith", "Jane Smyth"),
]


@pytest.mark.parametrize("a,b", SAME)
def test_same_after_normalising(a, b):
    assert normalise_name(a).key == normalise_name(b).key


@pytest.mark.parametrize("a,b", DIFFERENT)
def test_different_after_normalising(a, b):
    assert normalise_name(a).key != normalise_name(b).key


def test_initials_are_marked():
    n = normalise_name("J. Smith")
    assert n.initials == {"j"} and n.full == {"smith"}


def test_hangul_is_kept_whole():
    n = normalise_name("박형관")
    assert n.tokens == ("박형관",) and n.script == "hangul"


def test_scripts():
    assert script_of("Hyung-Kwan Park") == "latin"
    assert script_of("박형관") == "hangul"
    assert script_of("박 Park") == "mixed"
