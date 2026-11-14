"""Change monitor: match news hits to tracked people and move their claims up the re-check queue.

Implements ADR 0016 and docs/domain.md §11. A news hit never decides a verdict (R2); it only
reorders re-checks.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sourcemap.measure.names import NormName, normalise_name

PRIORITY_CLAIM_TYPES = ("employment", "title")


@dataclass(frozen=True, slots=True)
class NewsHit:
    id: int
    probe_unit_id: int
    title: str
    snippet: str = ""


@dataclass(frozen=True, slots=True)
class TrackedEntity:
    id: int
    probe_unit_id: int
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MonitorMatch:
    hit_id: int
    entity_id: int
    name: str


def _usable(n: NormName) -> bool:
    """A name can match news only with ≥ 2 full tokens (e.g. 'jane smith'), or one Hangul token of
    ≥ 2 syllables (Korean names are written without spaces). 'J. Smith' alone would match any Smith."""
    if n.script == "hangul":
        return len(n.full) >= 1 and all(len(t) >= 2 for t in n.full)
    return len(n.full) >= 2


def match_hits(hits: Iterable[NewsHit], entities: Iterable[TrackedEntity]) -> list[MonitorMatch]:
    """A hit matches an entity of the same probe unit when all full tokens of one of the entity's
    normalised names appear among the hit's tokens (title + snippet). One match per (hit, entity)."""
    by_unit: dict[int, list[TrackedEntity]] = {}
    for e in entities:
        by_unit.setdefault(e.probe_unit_id, []).append(e)
    out = []
    for h in hits:
        text_tokens = set(normalise_name(f"{h.title} {h.snippet}").tokens)
        for e in by_unit.get(h.probe_unit_id, []):
            for name in e.names:
                n = normalise_name(name)
                if _usable(n) and n.full <= text_tokens:
                    out.append(MonitorMatch(h.id, e.id, name))
                    break
    return out


def prioritise(
    recheck_queue: list[int],
    matches: Iterable[MonitorMatch],
    claims_by_entity: Mapping[int, Iterable[tuple[int, str]]],
    share_cap: int | None = None,
) -> list[int]:
    """Matched entities' employment and title claims first (deduped, at most `share_cap` of them),
    then the rest of the queue in its original order. Matched claims not yet in the queue are added."""
    front: list[int] = []
    for m in matches:
        for claim_id, claim_type in claims_by_entity.get(m.entity_id, ()):
            if claim_type in PRIORITY_CLAIM_TYPES and claim_id not in front:
                front.append(claim_id)
    if share_cap is not None:
        front = front[:share_cap]
    promoted = set(front)
    return front + [c for c in recheck_queue if c not in promoted]
