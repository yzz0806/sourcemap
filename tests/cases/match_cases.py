"""Entity matching case table — the specification of measure.match (docs/domain.md §8, ADR 0004,
ADR 0013).

A mention is written as (mention id, source id, name, local_ref, identifiers). Existing entities
are (entity id, mentions known from earlier runs). Decisions are stored judge answers
(mention a, mention b, same?). Expectations:
- together: groups of mention ids that must end in one entity;
- apart: pairs of mention ids that must end in different entities;
- judge: pairs of names that must be asked to the judge (in either order);
- entity_of: mention id → exact entity id expected (stable ids, ADR 0013);
- merges: (loser, survivor) pairs of existing entities.
"""

from dataclasses import dataclass, field

M = tuple  # (id, source_id, name, local_ref, identifiers dict)


@dataclass(frozen=True)
class MatchCase:
    name: str
    new: tuple[M, ...]
    existing: tuple[tuple[int, tuple[M, ...]], ...] = ()
    decisions: tuple[tuple[int, int, bool], ...] = ()
    next_entity_id: int = 100
    together: tuple[tuple[int, ...], ...] = ()
    apart: tuple[tuple[int, int], ...] = ()
    judge: tuple[tuple[str, str], ...] = ()
    no_judge: bool = False
    entity_of: dict = field(default_factory=dict)
    merges: tuple[tuple[int, int], ...] = ()


LI_JANE = {"linkedin": "https://www.linkedin.com/in/jane-smith-123/"}

MATCH_CASES = [
    MatchCase(
        "Park, Hyung-Kwan and HYUNG KWAN PARK are the same person",
        new=((1, 1, "Park, Hyung-Kwan", None, {}), (2, 2, "HYUNG KWAN PARK", None, {})),
        together=((1, 2),), no_judge=True,
    ),
    MatchCase(
        "Dr. Jane Smith and Jane Smith are the same person",
        new=((1, 1, "Dr. Jane Smith", None, {}), (2, 2, "Jane Smith", None, {})),
        together=((1, 2),), no_judge=True,
    ),
    MatchCase(
        "John Smith and Jane Smith are different people, no judge needed",
        new=((1, 1, "John Smith", None, {}), (2, 2, "Jane Smith", None, {})),
        apart=((1, 2),), no_judge=True,
    ),
    MatchCase(
        "J. Smith and Jane Smith go to the judge and stay apart until it answers",
        new=((1, 1, "J. Smith", None, {}), (2, 2, "Jane Smith", None, {})),
        apart=((1, 2),), judge=(("J. Smith", "Jane Smith"),),
    ),
    MatchCase(
        "Jane A. Smith and Jane Smith go to the judge",
        new=((1, 1, "Jane A. Smith", None, {}), (2, 2, "Jane Smith", None, {})),
        judge=(("Jane A. Smith", "Jane Smith"),),
    ),
    MatchCase(
        "박형관 and Hyung-Kwan Park (different scripts) go to the judge",
        new=((1, 1, "박형관", None, {}), (2, 2, "Hyung-Kwan Park", None, {})),
        apart=((1, 2),), judge=(("박형관", "Hyung-Kwan Park"),),
    ),
    MatchCase(
        "a stored judge answer 'same' merges a borderline pair without asking again",
        new=((1, 1, "J. Smith", None, {}), (2, 2, "Jane Smith", None, {})),
        decisions=((1, 2, True),),
        together=((1, 2),), no_judge=True,
    ),
    MatchCase(
        "same LinkedIn URL with different spellings is the same person",
        new=((1, 1, "Jane Smith", None, LI_JANE),
             (2, 2, "Smith J.", None, {"linkedin": "http://linkedin.com/in/jane-smith-123"})),
        together=((1, 2),), no_judge=True,
    ),
    MatchCase(
        "a stored 'different' between A and C blocks chaining A-B-C",
        new=((1, 1, "Jane Smith", None, LI_JANE),
             (2, 2, "Jane Smith", None, {}),
             (3, 3, "Jane Smith", None, {"linkedin": "https://linkedin.com/in/other-jane"})),
        decisions=((1, 3, False),),
        apart=((1, 3),),
    ),
    MatchCase(
        "re-running the same mentions next run keeps the same entity ids",
        existing=((7, ((1, 1, "Jane Smith", "jane-smith", {}),)),
                  (8, ((2, 1, "Howie Liu", "howie-liu", {}),))),
        new=((11, 1, "Jane Smith", "jane-smith", {}), (12, 1, "Howie Liu", "howie-liu", {})),
        entity_of={11: 7, 12: 8, 1: 7, 2: 8}, no_judge=True,
    ),
    MatchCase(
        "same source and same local ref attaches even if the name changed",
        existing=((7, ((1, 1, "Jane Smith", "p-42", {}),)),),
        new=((11, 1, "Jane Smith-Lee", "p-42", {}),),
        entity_of={11: 7},
    ),
    MatchCase(
        "a new mention gets a fresh id from next_entity_id, never a reused one",
        existing=((7, ((1, 1, "Jane Smith", None, {}),)),),
        new=((11, 2, "Howie Liu", None, {}),),
        next_entity_id=50,
        entity_of={11: 50, 1: 7},
    ),
    MatchCase(
        "a new mention matching two existing entities merges them into the older id",
        existing=((7, ((1, 1, "Jane Smith", None, LI_JANE),)),
                  (9, ((2, 2, "Jane Smith", None, {"orcid": "0000-0002-1825-0097"}),))),
        new=((11, 3, "Jane Smith", None, {**LI_JANE, "orcid": "0000-0002-1825-0097"}),),
        entity_of={11: 7, 1: 7, 2: 7},
        merges=((9, 7),),
    ),
    MatchCase(
        "matching by identical name attaches to an existing entity",
        existing=((7, ((1, 1, "Jane Smith", None, {}),)),),
        new=((11, 2, "Dr. Jane Smith", None, {}),),
        entity_of={11: 7},
    ),
]
