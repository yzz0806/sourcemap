"""Verdict expiry and re-check selection (ADR 0012, docs/domain.md §9).

Case table: tests/cases/freshness_cases.py. Time is always passed in (`as_of`), never read.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta

from sourcemap.domain.model import ClaimTypeSpec, Verification

RECHECK_WINDOW = 0.2  # last 20% of a verdict's life


def expires_at(spec: ClaimTypeSpec, decided_at: datetime) -> datetime:
    """When a verdict of this claim type stops counting."""
    return decided_at + timedelta(days=spec.expiry_days)


def is_due(v: Verification, as_of: datetime, window: float = RECHECK_WINDOW) -> bool:
    """Due when within the last `window` of its life, or already expired. No expiry → never due."""
    if v.expires_at is None:
        return False
    life = v.expires_at - v.decided_at
    return as_of >= v.expires_at - life * window


def due_for_recheck(
    verifications: Iterable[Verification],
    as_of: datetime,
    budget_n: int,
    window: float = RECHECK_WINDOW,
) -> list[Verification]:
    """Verdicts due for re-check, oldest decided first, at most `budget_n`."""
    due = [v for v in verifications if is_due(v, as_of, window)]
    due.sort(key=lambda v: (v.decided_at, v.claim_id))
    return due[: max(budget_n, 0)]
