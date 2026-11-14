"""Name normalising for comparison (docs/domain.md §8, ADR 0004).

"Park, Hyung-Kwan", "Hyung-Kwan Park" and "HYUNG KWAN PARK" normalise to the same tokens;
"Dr. Jane Smith" and "Jane Smith" too. Hangul is kept as written (never decomposed into jamo).
"""

import re
import unicodedata
from dataclasses import dataclass

HONORIFICS = frozenset(
    {"dr", "prof", "professor", "mr", "mrs", "ms", "mx", "miss", "sir", "dame", "lord", "lady", "rev"}
)
SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "phd", "md", "mba", "esq", "jd", "cpa", "msc", "bsc"})

_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_LATIN = re.compile(r"[a-z]")


@dataclass(frozen=True, slots=True)
class NormName:
    """A normalised name. `tokens` are sorted; `initials` are one-letter tokens (from "J." etc.);
    `full` are the other tokens; `script` is "latin", "hangul", "mixed" or "other"."""

    tokens: tuple[str, ...]
    initials: frozenset[str]
    full: frozenset[str]
    script: str

    @property
    def key(self) -> str:
        return " ".join(self.tokens)


def _fold_char(ch: str) -> str:
    if _HANGUL.match(ch):
        return ch
    decomposed = unicodedata.normalize("NFD", ch)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def script_of(s: str) -> str:
    """The writing system of a name: "latin", "hangul", "mixed" or "other"."""
    s = s.casefold()
    has_hangul = bool(_HANGUL.search(s))
    folded = "".join(_fold_char(c) for c in s)
    has_latin = bool(_LATIN.search(folded))
    if has_hangul and has_latin:
        return "mixed"
    if has_hangul:
        return "hangul"
    if has_latin:
        return "latin"
    return "other"


def normalise_name(s: str) -> NormName:
    """Fold case and accents, drop honorifics and suffixes, split on spaces/hyphens/commas, sort."""
    s = unicodedata.normalize("NFKC", s).casefold()
    s = "".join(_fold_char(c) for c in s)
    s = s.replace("'", "").replace("’", "")  # O'Brien -> obrien
    raw = re.split(r"[\s,\-‐-―./()]+", s)
    tokens = [t for t in raw if t and t not in HONORIFICS and t not in SUFFIXES]
    initials = frozenset(t for t in tokens if len(t) == 1 and not _HANGUL.match(t))
    full = frozenset(t for t in tokens if t not in initials)
    return NormName(tuple(sorted(tokens)), initials, full, script_of(s))
