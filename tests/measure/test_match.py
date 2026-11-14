"""Runs the entity matching case table (tests/cases/match_cases.py) against measure.match."""

import pytest

from cases.match_cases import MATCH_CASES, MatchCase
from sourcemap.domain.model import Mention
from sourcemap.measure.match import (
    ExistingEntity,
    PairDecision,
    known_pairs_from_identifiers,
    match_mentions,
    match_quality,
    name_relation,
    strip_identifiers,
)
from sourcemap.measure.names import normalise_name


def mention(spec, unit=100):
    mid, source, name, local_ref, idents = spec
    return Mention(mid, source, unit, name, local_ref, tuple(sorted(idents.items())))


def run(case: MatchCase):
    return match_mentions(
        [mention(m) for m in case.new],
        [ExistingEntity(eid, tuple(mention(m) for m in ms)) for eid, ms in case.existing],
        [PairDecision(a, b, s) for a, b, s in case.decisions],
        case.next_entity_id,
    )


@pytest.mark.parametrize("case", MATCH_CASES, ids=lambda c: c.name)
def test_match_case(case: MatchCase):
    r = run(case)
    for group in case.together:
        assert len({r.assignments[m] for m in group}) == 1, group
    for a, b in case.apart:
        assert r.assignments[a] != r.assignments[b], (a, b)
    asked = {frozenset((q.a, q.b)) for q in r.judge_questions}
    for a, b in case.judge:
        assert frozenset((a, b)) in asked
    if case.no_judge:
        assert r.judge_questions == ()
    for m, eid in case.entity_of.items():
        assert r.assignments[m] == eid, (m, r.assignments)
    assert set(r.merges) == set(case.merges)


def test_running_twice_is_deterministic():
    case = MATCH_CASES[3]
    assert run(case) == run(case)


def test_new_ids_never_collide_with_existing():
    r = match_mentions(
        [mention((11, 2, "Howie Liu", None, {}))],
        [ExistingEntity(7, (mention((1, 1, "Jane Smith", None, {})),))],
        next_entity_id=8,
    )
    assert r.assignments[11] == 8 and r.new_entities[0].display_name == "Howie Liu"


def test_existing_entity_with_a_cannot_link_pair_is_reported_for_a_split():
    e = ExistingEntity(7, (mention((1, 1, "Jane Smith", None, {})), mention((2, 2, "Jane Smith", None, {}))))
    r = match_mentions([], [e], [PairDecision(1, 2, False)])
    assert r.splits_needed == ((7, 1, 2),)


@pytest.mark.parametrize("a,b,expected", [
    ("Jane Smith", "Dr. Jane Smith", "same"),
    ("John Smith", "Jane Smith", "different"),
    ("J. Smith", "Jane Smith", "borderline"),
    ("Smith", "Jane Smith", "borderline"),
    ("박형관", "Hyung-Kwan Park", "borderline"),
    ("박형관", "김민수", "different"),
    ("Jane Smith", "Jane Smyth", "different"),
])
def test_name_relation(a, b, expected):
    assert name_relation(normalise_name(a), normalise_name(b)) == expected


def test_match_quality_on_identifier_known_pairs():
    ms = [
        mention((1, 1, "Jane Smith", None, {"linkedin": "linkedin.com/in/jane"})),
        mention((2, 2, "J. Smith", None, {"linkedin": "https://www.linkedin.com/in/jane/"})),
        mention((3, 3, "Jane Smith", None, {"linkedin": "linkedin.com/in/other-jane"})),
    ]
    known = known_pairs_from_identifiers(ms)
    assert set(known) == {(1, 2, True), (1, 3, False), (2, 3, False)}
    blind = match_mentions(strip_identifiers(ms))
    q = match_quality(blind, known)
    # Without identifiers: 1 and 3 (same name) merge wrongly; 1 and 2 wait for the judge (missed).
    assert q.pairs == 3 and q.false_merges == 1 and q.missed_merges == 1
