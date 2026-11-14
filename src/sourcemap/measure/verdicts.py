"""Verdicts: the lineage rule, method weights, and one current verdict per claim.

Implements docs/domain.md §6 R4 and R7, ADR 0003 and ADR 0005. Comparing values (same title?) is
done by the caller (measure.compare or the judge); these functions take the comparison's result.
"""

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime

from sourcemap.domain.model import Claim, Source, Verification
from sourcemap.domain.vocab import Method, Subtype, Verdict

AGREEMENT_WEIGHT = 0.5  # ADR 0002


def allowed_verifier(source: Source, verifier: Source, claim_type: str) -> bool:
    """R4: a source never verifies itself or a source of the same lineage for this claim type."""
    if source.id == verifier.id:
        return False
    return source.lineage_for(claim_type) != verifier.lineage_for(claim_type)


def method_weight(method: Method, source: Source) -> float:
    """R7: reference and lookup weigh 1; agreement 0.5, and 0 for inferred sources."""
    if method is not Method.AGREEMENT:
        return 1.0
    return 0.0 if source.subtype is Subtype.INFERRED else AGREEMENT_WEIGHT


def reference_verdict(
    claim: Claim,
    source: Source,
    reference_source: Source,
    same: bool | None,
    decided_at: datetime,
    expires_at: datetime | None = None,
    evidence: str | None = None,
) -> Verification | None:
    """Compare a claim with a reference source's claim about the same entity.

    `same` is the comparison result (None = undecided, ask the judge first). Returns None when the
    reference is not allowed (same lineage) or undecided.
    """
    if same is None or not allowed_verifier(source, reference_source, claim.claim_type):
        return None
    return Verification(
        claim_id=claim.id,
        method=Method.REFERENCE,
        verdict=Verdict.CORRECT if same else Verdict.WRONG,
        decided_at=decided_at,
        expires_at=expires_at,
        weight=method_weight(Method.REFERENCE, source),
        evidence=evidence,
        reason=f"reference {reference_source.slug}: {'same' if same else 'different'}",
    )


def lookup_verdict(
    claim: Claim,
    source: Source,
    verifier: Source,
    judge_verdict: Verdict,
    decided_at: datetime,
    expires_at: datetime | None = None,
    evidence: str | None = None,
    reason: str = "",
) -> Verification | None:
    """Turn a judge's answer about a lookup response into a verdict. None if the lineage rule forbids."""
    if not allowed_verifier(source, verifier, claim.claim_type):
        return None
    return Verification(
        claim_id=claim.id,
        method=Method.LOOKUP,
        verdict=judge_verdict,
        decided_at=decided_at,
        expires_at=expires_at,
        weight=method_weight(Method.LOOKUP, source),
        evidence=evidence,
        reason=reason or f"lookup {verifier.slug}",
    )


def agreement_verdict(
    claim: Claim,
    source: Source,
    others: Iterable[tuple[Claim, Source]],
    decided_at: datetime,
    expires_at: datetime | None = None,
) -> Verification | None:
    """`correct` by agreement when a source of a different lineage states the same value for the
    same entity. Copies (same lineage) are ignored, so they count at most once (R4). Disagreement is
    not evidence of `wrong` — either side may be the mistaken one — so it returns None.
    """
    for other, other_source in others:
        if other.subject_entity_id != claim.subject_entity_id or other.claim_type != claim.claim_type:
            continue
        if not allowed_verifier(source, other_source, claim.claim_type):
            continue
        if other.value_norm == claim.value_norm:
            return Verification(
                claim_id=claim.id,
                method=Method.AGREEMENT,
                verdict=Verdict.CORRECT,
                decided_at=decided_at,
                expires_at=expires_at,
                weight=method_weight(Method.AGREEMENT, source),
                evidence=f"claim:{other.id}",
                reason=f"agrees with {other_source.slug}",
            )
    return None


def is_valid(v: Verification, as_of: datetime) -> bool:
    """A verdict counts until it expires (ADR 0012)."""
    return v.expires_at is None or v.expires_at > as_of


def current_verdict(verifications: Iterable[Verification], as_of: datetime) -> Verification | None:
    """R7: of a claim's unexpired verdicts, the strongest method wins; ties go to the newest."""
    valid = [v for v in verifications if is_valid(v, as_of)]
    if not valid:
        return None
    return max(valid, key=lambda v: (v.method.strength, v.decided_at))


def exclude(v: Verification, reason: str) -> Verification:
    """Keep a verdict for the trace but leave it out of the score (e.g. R5 gate failed)."""
    return replace(v, excluded_reason=reason)
