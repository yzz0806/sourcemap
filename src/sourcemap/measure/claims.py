"""Splitting a record into claims, and claim fingerprints.

Implements docs/domain.md §2 ("claims, not records, are checked and scored"), ADR 0001 (records
are {"people": [...]} validated against the data type's schema) and ADR 0013 (fingerprints contain
the stable subject entity id).
"""

import hashlib
from dataclasses import dataclass

from sourcemap.domain.model import DataTypeSpec, Record
from sourcemap.measure.compare import normalise_value


@dataclass(frozen=True, slots=True)
class ClaimDraft:
    """A claim before matching: who it is about is still the record-local `person_ref`.
    For reports_to, `value` is the manager's `ref` in the same record (resolved to an entity later)."""

    person_ref: str
    claim_type: str
    value: object
    value_norm: str


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def extract_claims(spec: DataTypeSpec, record: Record) -> list[ClaimDraft]:
    """One draft per person per claim type whose value is present. Existence claim types (field
    None) always yield value True. Invalid records yield nothing. A reports_to whose manager ref
    is not a person of the same record is skipped (it can't be resolved to an entity)."""
    if not record.valid:
        return []
    people = record.payload.get("people") or []
    refs = {str(p.get("ref")) for p in people if p.get("ref") is not None}
    drafts: list[ClaimDraft] = []
    for person in people:
        ref = person.get("ref")
        if ref is None or _empty(person.get("name")):
            continue
        ref = str(ref)
        for ct in spec.claim_types:
            if ct.field is None:
                value: object = True
            else:
                value = person.get(ct.field)
                if _empty(value):
                    continue
                if ct.slug == "reports_to":
                    value = str(value)
                    if value not in refs or value == ref:
                        continue
            drafts.append(ClaimDraft(ref, ct.slug, value, normalise_value(ct, value)))
    return drafts


def fingerprint(
    source_id: int, probe_unit_id: int, subject_entity_id: int, claim_type: str, value_norm: str
) -> str:
    """Stable identity of a claim across runs (ADR 0013): sha1 of its five parts."""
    raw = "\x1f".join([str(source_id), str(probe_unit_id), str(subject_entity_id), claim_type, value_norm])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
