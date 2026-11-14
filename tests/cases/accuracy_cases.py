"""The accuracy case table — the specification of docs/domain.md §6 (R1–R10) and ADR 0002.

Each case is one cell's input in plain words and the expected result. A verdict is written as
"<verdict> by <method>" with an optional "(inferred)" for an inferred source. Tests:
tests/measure/test_accuracy_cases.py. Rules that are not about one cell's arithmetic (R2 search
never evidence, R3 plausible, R9 spot-checks, R10 trace) are enforced by the pipeline and the
schema and are listed at the bottom with where they are tested.
"""

from dataclasses import dataclass, field

from sourcemap.domain.vocab import AccuracyState, Tier


@dataclass(frozen=True)
class AccuracyCase:
    name: str
    rule: str
    tier: Tier
    verdicts: tuple[str, ...]
    state: AccuracyState
    n_decisive: int
    n_weighted: float
    mean: float | None = None          # expected displayed mean (None = not shown)
    interval: tuple[float, float] | None = None
    stale_share: float = 0.0
    unverifiable_share: float = 0.0
    inferred: bool = False
    excluded: tuple[int, ...] = ()     # indexes of verdicts excluded by the R5 gate
    note: str = ""
    extra: dict = field(default_factory=dict)


C, W, S, U = "correct by lookup", "wrong by lookup", "stale by lookup", "unverifiable by lookup"
AGREE = "correct by agreement"
REF_OK = "correct by reference"

ACCURACY_CASES = [
    AccuracyCase(
        "3 correct checks give an interval, not 100%",
        "R6", Tier.RESEARCHED, (C, C, C),
        AccuracyState.NOT_ENOUGH_DATA, 3, 3.0, mean=None, interval=(0.549, 0.990),
        note="crowd edited prior Beta(2,1) + 3 correct = Beta(5,1); posterior mean 5/6 = 0.833",
    ),
    AccuracyCase(
        "no checks at all: unmeasured, the prior is never shown",
        "R8", Tier.OFFICIAL, (),
        AccuracyState.UNMEASURED, 0, 0.0,
    ),
    AccuracyCase(
        "only unverifiable verdicts: unmeasured, not the prior",
        "R8", Tier.RESEARCHED, (U, U, U),
        AccuracyState.UNMEASURED, 0, 0.0, unverifiable_share=1.0,
    ),
    AccuracyCase(
        "2 correct + 1 stale + 1 unverifiable: n = 2, stale 25%, unverifiable 25%",
        "R8", Tier.RESEARCHED, (C, C, S, U),
        AccuracyState.NOT_ENOUGH_DATA, 2, 2.0, stale_share=0.25, unverifiable_share=0.25,
    ),
    AccuracyCase(
        "stale is excluded from accuracy: 5 correct + 5 stale is the same interval as 5 correct",
        "R8", Tier.RESEARCHED, (C,) * 5 + (S,) * 5,
        AccuracyState.MEASURED, 5, 5.0, mean=7 / 8, stale_share=0.5,
    ),
    AccuracyCase(
        "5 decisive checks: measured, mean shown",
        "R6", Tier.RESEARCHED, (C, C, C, C, W),
        AccuracyState.MEASURED, 5, 5.0, mean=6 / 8,
    ),
    AccuracyCase(
        "4 decisive checks: one short of the minimum, interval only",
        "ADR 0002", Tier.RESEARCHED, (C, C, C, W),
        AccuracyState.NOT_ENOUGH_DATA, 4, 4.0,
    ),
    AccuracyCase(
        "agreement counts half: 8 agreements weigh 4, still not enough data",
        "R7", Tier.RESEARCHED, (AGREE,) * 8,
        AccuracyState.NOT_ENOUGH_DATA, 8, 4.0,
    ),
    AccuracyCase(
        "agreement counts half: 10 agreements weigh 5, measured",
        "R7", Tier.RESEARCHED, (AGREE,) * 10,
        AccuracyState.MEASURED, 10, 5.0, mean=7 / 8,
    ),
    AccuracyCase(
        "inferred source: agreement alone gives nothing",
        "R7", Tier.AGGREGATE, (AGREE,) * 10,
        AccuracyState.UNMEASURED, 10, 0.0, inferred=True,
    ),
    AccuracyCase(
        "inferred source: lookups still count",
        "R7", Tier.AGGREGATE, (C,) * 5,
        AccuracyState.MEASURED, 5, 5.0, mean=6 / 7, inferred=True,
    ),
    AccuracyCase(
        "tier changes the prior: official source, 5 correct",
        "R6", Tier.OFFICIAL, (REF_OK,) * 5,
        AccuracyState.MEASURED, 5, 5.0, mean=9 / 10,
    ),
    AccuracyCase(
        "R5 gate failed: overlap verdicts are dropped from the estimate",
        "R5", Tier.RESEARCHED, (C, C, C, C, C, C, C, W, W),
        AccuracyState.NOT_ENOUGH_DATA, 2, 2.0, excluded=(0, 1, 2, 3, 4, 5, 6),
        note="the 7 correct overlap verdicts are excluded; only the 2 wrong lookups on the rest count",
    ),
]

# Rules enforced elsewhere (listed so every rule has a row):
ENFORCED_ELSEWHERE = {
    "R1 per claim type and segment": "a score is keyed by (source, segment, claim type) — data model",
    "R2 web search never evidence": "no foreign key from verification to search_hit — data model; "
    "Telem fetch returns PageText which the evidence store refuses (stage 3)",
    "R3 plausible is not correct": "verdicts come only from reference/lookup/agreement functions; "
    "no structural-plausibility method exists (measure.verdicts)",
    "R4 same lineage never verifies": "tests/measure/test_verdicts.py",
    "R7 strongest method wins": "tests/measure/test_verdicts.py",
    "R9 official sources spot-checked": "pipeline verify stage (stage 5a)",
    "R10 traceable": "score_verification table (stage 2) and trace command (stage 5a)",
}
