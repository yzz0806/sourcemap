"""Comparing claim values: same, different, or a question for the judge.

Implements docs/domain.md §6 (values are compared per claim type) and ADR 0004 / ADR 0009 (the
judge is asked only what rules can't decide). Case table: tests/cases/compare_cases.py.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from sourcemap.domain.model import ClaimTypeSpec
from sourcemap.domain.vocab import CompareMode, ValueKind


class Comparison(StrEnum):
    SAME = "same"
    DIFFERENT = "different"
    ASK_JUDGE = "ask_judge"


@dataclass(frozen=True, slots=True)
class JudgeQuestion:
    """A question the caller sends to the judge. `kind` is e.g. "same_title", "same_value",
    "same_person"; `context` holds extra facts as (key, value) pairs (titles, mention ids)."""

    kind: str
    a: str
    b: str
    context: tuple[tuple[str, str], ...] = ()


def _strip_punct_ends(s: str) -> str:
    start, end = 0, len(s)
    while start < end and unicodedata.category(s[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(s[end - 1]).startswith("P"):
        end -= 1
    return s[start:end]


def normalise_text(value: object) -> str:
    """NFKC, casefold, collapse whitespace, strip punctuation at both ends."""
    s = unicodedata.normalize("NFKC", str(value)).casefold()
    s = re.sub(r"\s+", " ", s).strip()
    return _strip_punct_ends(s).strip()


def normalise_url(value: object) -> str:
    """Drop scheme, `www.`, query, fragment and trailing slash; lowercase the host."""
    s = str(value).strip()
    s = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", s)
    s = s.split("#", 1)[0].split("?", 1)[0]
    host, _, path = s.partition("/")
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    path = path.rstrip("/")
    return f"{host}/{path}" if path else host


def normalise_value(spec: ClaimTypeSpec, value: object) -> str:
    """The comparable form of a claim value for its claim type's value kind."""
    kind = spec.value_kind
    if kind is ValueKind.BOOL:
        return "true" if bool(value) else "false"
    if kind is ValueKind.EMAIL:
        return str(value).strip().lower()
    if kind is ValueKind.URL:
        return normalise_url(value)
    if kind is ValueKind.ENTITY:
        return str(value).strip()
    return normalise_text(value)


def compare_values(spec: ClaimTypeSpec, a: object, b: object) -> Comparison:
    """EXACT and NORMALISED modes decide by normalised equality. JUDGE mode says SAME when the
    normalised values are equal and otherwise ASK_JUDGE — never DIFFERENT by rule."""
    same = normalise_value(spec, a) == normalise_value(spec, b)
    if same:
        return Comparison.SAME
    if spec.compare is CompareMode.JUDGE:
        return Comparison.ASK_JUDGE
    return Comparison.DIFFERENT


def judge_question(spec: ClaimTypeSpec, a: object, b: object, **context: str) -> JudgeQuestion:
    """The judge question for an ASK_JUDGE comparison."""
    kind = "same_title" if spec.slug == "title" else "same_value"
    ctx = (("claim_type", spec.slug),) + tuple(sorted((k, str(v)) for k, v in context.items()))
    return JudgeQuestion(kind, str(a), str(b), ctx)
