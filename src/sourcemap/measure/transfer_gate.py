"""The representativeness gate: does accuracy on the overlap transfer to the rest of a source?

Implements docs/domain.md §6 R5 and ADR 0002 (failed gate → overlap verdicts excluded from the
cell's estimate, kept for the trace). Case table: tests/cases/gate_cases.py.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

from sourcemap.domain.model import Verification
from sourcemap.measure.verdicts import exclude

EXCLUDED_REASON = "overlap not representative (R5)"


@dataclass(frozen=True, slots=True)
class ClaimInfo:
    """Plain facts about one claim, for comparing the overlap with the rest."""

    fields_filled: int
    fields_total: int
    depth: int
    age_days: float
    format_tag: str


@dataclass(frozen=True, slots=True)
class Features:
    fill_rate: float
    mean_depth: float
    median_age_days: float
    format_signature: str


@dataclass(frozen=True, slots=True)
class Tolerances:
    fill_rate: float = 0.15
    depth: float = 1.0
    age_days: float = 90.0


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]  # subset of "fill_rate", "depth", "freshness", "format"


def features(claims: Iterable[ClaimInfo]) -> Features:
    """Summarise one side. The format signature is the most common format tag (ties: sorted)."""
    claims = list(claims)
    if not claims:
        raise ValueError("features() needs at least one claim")
    total = sum(c.fields_total for c in claims)
    counts = Counter(c.format_tag for c in claims)
    top = max(counts.values())
    return Features(
        fill_rate=sum(c.fields_filled for c in claims) / total if total else 0.0,
        mean_depth=sum(c.depth for c in claims) / len(claims),
        median_age_days=float(median(c.age_days for c in claims)),
        format_signature=sorted(t for t, n in counts.items() if n == top)[0],
    )


def representative(overlap: Features, rest: Features, tol: Tolerances = Tolerances()) -> GateResult:
    """R5: the overlap represents the rest only if it looks like it on every feature."""
    reasons = []
    if abs(overlap.fill_rate - rest.fill_rate) > tol.fill_rate + 1e-9:
        reasons.append("fill_rate")
    if abs(overlap.mean_depth - rest.mean_depth) > tol.depth + 1e-9:
        reasons.append("depth")
    if abs(overlap.median_age_days - rest.median_age_days) > tol.age_days + 1e-9:
        reasons.append("freshness")
    if overlap.format_signature != rest.format_signature:
        reasons.append("format")
    return GateResult(not reasons, tuple(reasons))


def apply_gate(verifications_on_overlap: Iterable[Verification], gate: GateResult) -> list[Verification]:
    """When the gate failed, mark the overlap's verdicts excluded (kept for the trace)."""
    vs = list(verifications_on_overlap)
    return vs if gate.passed else [exclude(v, EXCLUDED_REASON) for v in vs]
