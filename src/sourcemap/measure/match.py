"""Matching mentions into entities within one probe unit, keeping entity ids stable across runs.

Implements docs/domain.md §8, ADR 0004 (rules first, judge for borderline pairs, cannot-link) and
ADR 0013 (attach to existing entities first; ids never reused; merges keep the older id).
Case table: tests/cases/match_cases.py.

Order of evidence for "same person", strongest first:
  1. a shared identifier (LinkedIn URL, ORCID iD, …), compared after URL normalising;
  2. the same source and the same `local_ref` (e.g. a theorg person slug);
  3. identical normalised names;
  4. a stored judge decision "same".
A stored decision "different" — or two different values of the same identifier kind — is a
cannot-link: the two mentions never end in one entity, even through a third mention.
Everything else that rules can't settle (initials, different scripts, extra name tokens) becomes
a judge question, and the pair stays apart until the answer is stored.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sourcemap.domain.model import Mention
from sourcemap.measure.compare import JudgeQuestion, normalise_url
from sourcemap.measure.names import NormName, normalise_name


@dataclass(frozen=True, slots=True)
class ExistingEntity:
    """An entity from earlier runs with the mentions it is already known by."""

    id: int
    mentions: tuple[Mention, ...]


@dataclass(frozen=True, slots=True)
class PairDecision:
    """A stored answer about two mentions (from the judge or an earlier rule)."""

    mention_a: int
    mention_b: int
    same: bool


@dataclass(frozen=True, slots=True)
class NewEntity:
    id: int
    mention_ids: tuple[int, ...]
    display_name: str


@dataclass(frozen=True, slots=True)
class MatchResult:
    """`assignments` covers every mention given (existing and new) → entity id.
    `merges` are (loser, survivor) pairs of existing entities; `splits_needed` lists existing
    entities that contain a cannot-link pair (entity id, mention a, mention b) for the caller to split."""

    assignments: dict
    new_entities: tuple[NewEntity, ...]
    merges: tuple[tuple[int, int], ...]
    judge_questions: tuple[JudgeQuestion, ...]
    splits_needed: tuple[tuple[int, int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class MatchQuality:
    pairs: int
    false_merges: int
    missed_merges: int


# --- helpers ------------------------------------------------------------------------------------

def _norm_identifier(value: str) -> str:
    v = value.strip()
    return normalise_url(v) if ("/" in v or "." in v) else v.lower()


def _identifiers(m: Mention) -> dict[str, str]:
    return {k: _norm_identifier(v) for k, v in m.identifiers if v}


def name_relation(a: NormName, b: NormName) -> str:
    """"same", "different" or "borderline" (needs the judge) for two normalised names."""
    if a.key == b.key:
        return "same"
    if a.script != b.script or "mixed" in (a.script, b.script):
        return "borderline"
    if a.script == "hangul":
        return "different"
    for small, big in ((a, b), (b, a)):
        if not small.full or not small.full <= big.full:
            continue
        extra = (big.full - small.full) | big.initials
        if all(any(t.startswith(i) for t in extra) for i in small.initials):
            return "borderline"
    return "different"


class _UnionFind:
    def __init__(self, items: Iterable[int], cannot: set[frozenset[int]]):
        self.parent = {i: i for i in items}
        self.members = {i: {i} for i in self.parent}
        self.cannot = cannot

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def blocked(self, ra: int, rb: int) -> bool:
        return any(frozenset((x, y)) in self.cannot for x in self.members[ra] for y in self.members[rb])

    def union(self, a: int, b: int, force: bool = False) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        if not force and self.blocked(ra, rb):
            return False
        if ra > rb:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.members[ra] |= self.members.pop(rb)
        return True


# --- matching -----------------------------------------------------------------------------------

def match_mentions(
    new_mentions: Iterable[Mention],
    existing: Iterable[ExistingEntity] = (),
    decisions: Iterable[PairDecision] = (),
    next_entity_id: int = 1,
) -> MatchResult:
    """Group the mentions of one probe unit into entities (see the module docstring)."""
    existing = sorted(existing, key=lambda e: e.id)
    new = sorted(new_mentions, key=lambda m: m.id)
    old_entity_of = {m.id: e.id for e in existing for m in e.mentions}
    mentions = {m.id: m for e in existing for m in e.mentions} | {m.id: m for m in new}
    new_ids = {m.id for m in new}
    ids = sorted(mentions)
    norm = {i: normalise_name(mentions[i].name) for i in ids}
    idents = {i: _identifiers(mentions[i]) for i in ids}

    stored: dict[frozenset[int], bool] = {}
    for d in decisions:
        stored[frozenset((d.mention_a, d.mention_b))] = d.same
    cannot = {pair for pair, same in stored.items() if not same}
    for x in ids:
        for y in ids:
            if x < y and any(k in idents[y] and idents[y][k] != v for k, v in idents[x].items()):
                cannot.add(frozenset((x, y)))

    uf = _UnionFind(ids, cannot)
    splits: list[tuple[int, int, int]] = []
    for e in existing:
        ms = sorted(m.id for m in e.mentions)
        for x in ms:
            for y in ms:
                if x < y and frozenset((x, y)) in cannot:
                    splits.append((e.id, x, y))
        for m in ms[1:]:
            uf.union(ms[0], m, force=True)

    pairs = [(x, y) for i, x in enumerate(ids) for y in ids[i + 1:] if x in new_ids or y in new_ids]

    def same_by(rule) -> None:
        for x, y in pairs:
            if rule(x, y):
                uf.union(x, y)

    same_by(lambda x, y: any(idents[y].get(k) == v for k, v in idents[x].items()))
    same_by(lambda x, y: mentions[x].local_ref is not None
            and mentions[x].source_id == mentions[y].source_id
            and mentions[x].local_ref == mentions[y].local_ref)
    same_by(lambda x, y: norm[x].key == norm[y].key and bool(norm[x].tokens))
    same_by(lambda x, y: stored.get(frozenset((x, y))) is True)

    questions: list[JudgeQuestion] = []
    asked: set[frozenset[int]] = set()
    for x, y in pairs:
        rx, ry = uf.find(x), uf.find(y)
        if rx == ry or frozenset((x, y)) in stored or uf.blocked(rx, ry):
            continue
        if name_relation(norm[x], norm[y]) != "borderline":
            continue
        groups = frozenset((rx, ry))
        if groups in asked:
            continue
        asked.add(groups)
        mx, my = mentions[x], mentions[y]
        ctx = (("mention_a", str(x)), ("mention_b", str(y)))
        ctx += tuple((f"a_{k}", v) for k, v in mx.attrs) + tuple((f"b_{k}", v) for k, v in my.attrs)
        questions.append(JudgeQuestion("same_person", mx.name, my.name, ctx))

    groups: dict[int, list[int]] = {}
    for i in ids:
        groups.setdefault(uf.find(i), []).append(i)

    assignments: dict[int, int] = {}
    new_entities: list[NewEntity] = []
    merges: list[tuple[int, int]] = []
    next_id = next_entity_id
    for members in sorted(groups.values(), key=min):
        olds = sorted({old_entity_of[m] for m in members if m in old_entity_of})
        if olds:
            eid = olds[0]
            merges.extend((loser, eid) for loser in olds[1:])
        else:
            eid = next_id
            next_id += 1
            display = max((mentions[m].name for m in members), key=len)
            new_entities.append(NewEntity(eid, tuple(members), display))
        for m in members:
            assignments[m] = eid

    return MatchResult(assignments, tuple(new_entities), tuple(merges), tuple(questions), tuple(splits))


# --- matching quality (docs/domain.md §7) -------------------------------------------------------

def strip_identifiers(mentions: Iterable[Mention]) -> list[Mention]:
    """The same mentions without identifiers, to test the matcher on pairs whose answer is known."""
    return [Mention(m.id, m.source_id, m.probe_unit_id, m.name, m.local_ref, (), m.attrs) for m in mentions]


def known_pairs_from_identifiers(mentions: Iterable[Mention]) -> list[tuple[int, int, bool]]:
    """Pairs whose answer the identifiers give: a shared identifier → same; two different values of
    the same identifier kind → different. Pairs with no common identifier kind are unknown."""
    ms = sorted(mentions, key=lambda m: m.id)
    idents = {m.id: _identifiers(m) for m in ms}
    out: list[tuple[int, int, bool]] = []
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            common = idents[a.id].keys() & idents[b.id].keys()
            if not common:
                continue
            same = any(idents[a.id][k] == idents[b.id][k] for k in common)
            out.append((a.id, b.id, same))
    return out


def match_quality(result: MatchResult, known_pairs: Iterable[tuple[int, int, bool]]) -> MatchQuality:
    """False merges (known different, matched together) and missed merges (known same, left apart —
    including pairs still waiting for the judge)."""
    n = fm = mm = 0
    for a, b, same in known_pairs:
        if a not in result.assignments or b not in result.assignments:
            continue
        n += 1
        together = result.assignments[a] == result.assignments[b]
        if together and not same:
            fm += 1
        elif same and not together:
            mm += 1
    return MatchQuality(n, fm, mm)
