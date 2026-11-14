"""Core domain records: specs, units, sources, mentions, claims, verifications.

Implements the vocabulary of docs/domain.md §2 and the data model of docs/data-model.md. Mappings
are stored as tuples of pairs so the dataclasses stay frozen and hashable.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sourcemap.domain.vocab import CompareMode, Method, Subtype, Tier, ValueKind, Verdict


@dataclass(frozen=True, slots=True)
class ClaimTypeSpec:
    """A kind of claim (docs/domain.md §2). `field` is the person field the value comes from;
    None means an existence claim (employment / exists: "this person is at this probe unit")."""

    slug: str
    value_kind: ValueKind
    expiry_days: int
    compare: CompareMode
    field: str | None = None


@dataclass(frozen=True, slots=True)
class DataTypeSpec:
    """A data type (ADR 0001). Records are {"people": [person, ...]}; a person has `ref`, `name`,
    optional `identifiers` (dict) and the fields named by its claim types."""

    slug: str
    name: str
    spec_version: int
    claim_types: tuple[ClaimTypeSpec, ...]

    def claim_type(self, slug: str) -> ClaimTypeSpec:
        for ct in self.claim_types:
            if ct.slug == slug:
                return ct
        raise KeyError(slug)


@dataclass(frozen=True, slots=True)
class ProbeUnit:
    id: int
    slug: str
    name: str
    segment_id: int


@dataclass(frozen=True, slots=True)
class Source:
    """A source with its tier, subtype and lineage (ADR 0005)."""

    id: int
    slug: str
    tier: Tier
    subtype: Subtype
    lineage: str
    lineage_by_claim: tuple[tuple[str, str], ...] = ()

    def lineage_for(self, claim_type: str) -> str:
        return dict(self.lineage_by_claim).get(claim_type, self.lineage)


@dataclass(frozen=True, slots=True)
class Mention:
    """One person as they appear inside one record (docs/domain.md §2)."""

    id: int
    source_id: int
    probe_unit_id: int
    name: str
    local_ref: str | None = None
    identifiers: tuple[tuple[str, str], ...] = ()
    attrs: tuple[tuple[str, str], ...] = ()

    def identifier(self, kind: str) -> str | None:
        return dict(self.identifiers).get(kind)


@dataclass(frozen=True, slots=True)
class Claim:
    """One checkable statement (docs/domain.md §2). `value_norm` is the comparable form."""

    id: int
    source_id: int
    probe_unit_id: int
    claim_type: str
    subject_entity_id: int
    value: Any
    value_norm: str
    object_entity_id: int | None = None


@dataclass(frozen=True, slots=True)
class Verification:
    """A verdict on one claim, with its method (docs/domain.md §2, ADR 0003).

    `weight` is set by measure.verdicts (1.0 for reference/lookup, 0.5 for agreement, 0 for
    agreement on inferred sources). `excluded_reason` marks verdicts kept for the trace but left
    out of a score (e.g. the R5 gate)."""

    claim_id: int
    method: Method
    verdict: Verdict
    decided_at: datetime
    expires_at: datetime | None = None
    weight: float = 1.0
    evidence: str | None = None
    reason: str = ""
    excluded_reason: str | None = None


@dataclass(frozen=True, slots=True)
class Interval:
    """A 90% interval (ADR 0002)."""

    lo: float
    hi: float

    def overlaps(self, other: "Interval") -> bool:
        return self.lo <= other.hi and other.lo <= self.hi


def _people_payload() -> dict:
    return {"people": []}


@dataclass(frozen=True, slots=True)
class Record:
    """One source's converted answer for one probe unit (ADR 0001). `payload` = {"people": [...]}."""

    id: int
    source_id: int
    probe_unit_id: int
    valid: bool = True
    payload: dict = field(default_factory=_people_payload)
